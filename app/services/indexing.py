"""
Document indexing and ingestion services.
"""
import logging
import os
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, StorageContext, Document
from llama_index.vector_stores.qdrant import QdrantVectorStore

from app.config import DATA_DIR, COLLECTION
from app.dependencies import client
from app.grounding import extract_grounding_payload, is_grounding_available
from app.observability import get_tracer, instrumentation_wrapper

logger = logging.getLogger(__name__)

# --- OCR loader (pymupdf + GLM-OCR via Ollama) ---
IMAGE_TEXT_THRESHOLD = 100  # chars — pages below this get OCR treatment
GLM_OCR_MODEL = "glm-ocr"
GLM_OCR_BASE_URL = "http://localhost:11434"


def _ocr_page_image(pil_image) -> str:
    """Run GLM-OCR on a PIL image via Ollama's generate endpoint, return extracted text."""
    import base64
    import io
    import urllib.request
    import json

    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    payload = json.dumps({
        "model": GLM_OCR_MODEL,
        "prompt": "Text Recognition:",
        "images": [img_b64],
        "stream": False
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{GLM_OCR_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "").strip()
    except Exception as e:
        logger.warning(f"GLM-OCR failed on page: {e}")
        return ""


def load_pdf_ocr(file_path: str) -> list:
    """
    Load a PDF using pymupdf for text extraction.
    Pages with little/no text (image-only) are rendered and passed through
    GLM-OCR via Ollama (Metal/GPU accelerated on Apple Silicon).
    """
    import fitz  # pymupdf
    fname = os.path.basename(file_path)
    doc = fitz.open(file_path)
    pages_text = []
    ocr_pages = 0

    for page_num, page in enumerate(doc):
        text = page.get_text().strip()
        if len(text) < IMAGE_TEXT_THRESHOLD:
            # Page is image-heavy — render and OCR
            pix = page.get_pixmap(dpi=150)
            import PIL.Image, io
            img = PIL.Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = _ocr_page_image(img)
            if ocr_text.strip():
                pages_text.append(ocr_text)
                ocr_pages += 1
            elif text:
                pages_text.append(text)
        else:
            pages_text.append(text)

    page_count = len(doc)
    doc.close()
    full_text = "\n\n".join(pages_text)
    logger.info(f"  {fname}: {page_count} pages, {ocr_pages} OCR'd, {len(full_text):,} chars")

    if not full_text.strip():
        logger.warning(f"  No text extracted from {fname}")
        return []

    return [Document(
        text=full_text,
        metadata={
            "file_name": fname,
            "file_path": file_path,
            "file_type": "application/pdf",
            "file_size": os.path.getsize(file_path),
            "ocr_pages": ocr_pages,
        }
    )]


def add_grounding_metadata(nodes, use_grounding=True):
    """
    Add ontology grounding metadata to nodes for OG-RAG-lite.

    Phase 1A: Ingest-time tagging
    - Calls BAS-Ontology /api/ground for each node
    - Adds compact grounding payload to node.metadata
    - Gracefully degrades if grounding unavailable

    Args:
        nodes: List of document nodes/chunks
        use_grounding: Enable grounding (default True)

    Returns:
        nodes with grounding metadata added
    """
    if not use_grounding:
        logger.info("Grounding disabled, skipping metadata tagging")
        return nodes

    # Check if grounding service is available
    if not is_grounding_available():
        logger.warning("BAS-Ontology grounding service not available, skipping grounding")
        return nodes

    logger.info(f"Adding grounding metadata to {len(nodes)} nodes...")
    grounded_count = 0

    for i, node in enumerate(nodes):
        # Extract text and metadata
        text = node.get_content()
        title = node.metadata.get("file_name", "")

        # Call grounding service
        grounding_payload = extract_grounding_payload(text, title)

        # Add compact grounding fields to node metadata
        node.metadata.update(grounding_payload)

        # Count nodes with actual grounding (non-empty)
        if grounding_payload.get("equip") or grounding_payload.get("ptags"):
            grounded_count += 1

        # Log progress every 10 nodes
        if (i + 1) % 10 == 0:
            logger.info(f"  Grounded {i + 1}/{len(nodes)} nodes ({grounded_count} with concepts)")

    logger.info(f"✅ Grounding complete: {grounded_count}/{len(nodes)} nodes have grounding metadata")
    return nodes


@instrumentation_wrapper("ingest_documents")
def build_index(force_rebuild=False):
    """
    Build or update the vector index.

    Args:
        force_rebuild: If True, deletes existing collection and rebuilds from scratch.
                      If False, only indexes new documents (incremental update).
    """
    tracer = get_tracer()
    logger.info(f"Starting ingestion from {DATA_DIR} (force_rebuild={force_rebuild})")

    # Load documents - use explicit file list for better control
    logger.info("Finding PDF files in directory tree...")
    import glob
    pdf_files = glob.glob(f"{DATA_DIR}/**/*.pdf", recursive=True)
    txt_files = glob.glob(f"{DATA_DIR}/**/*.txt", recursive=True)
    md_files = glob.glob(f"{DATA_DIR}/**/*.md", recursive=True)
    all_files = pdf_files + txt_files + md_files
    logger.info(f"Found {len(all_files)} files ({len(pdf_files)} PDFs, {len(txt_files)} TXT, {len(md_files)} MD)")

    if len(all_files) == 0:
        raise ValueError(f"No PDF, TXT, or MD files found in {DATA_DIR}")

    # Load documents one at a time with progress tracking to identify problematic PDFs
    logger.info(f"Loading {len(all_files)} documents with progress tracking...")
    docs = []
    failed_files = []

    for i, file_path in enumerate(all_files):
        try:
            filename = file_path.split('/')[-1]
            logger.info(f"  [{i+1}/{len(all_files)}] Loading: {filename}")

            # Use OCR for PDFs, SimpleDirectoryReader for txt/md
            if file_path.endswith(".pdf"):
                file_docs = load_pdf_ocr(file_path)
            else:
                reader = SimpleDirectoryReader(input_files=[file_path])
                file_docs = reader.load_data()
            docs.extend(file_docs)

            if (i + 1) % 50 == 0:
                logger.info(f"  Progress: {i+1}/{len(all_files)} files loaded ({len(docs)} documents)")
        except Exception as e:
            logger.warning(f"  ⚠️  Failed to load {file_path}: {str(e)}")
            failed_files.append((file_path, str(e)))
            continue

    logger.info(f"✅ Loaded {len(docs)} documents from {len(all_files) - len(failed_files)} files")
    if failed_files:
        logger.warning(f"⚠️  Failed to load {len(failed_files)} files:")
        for path, error in failed_files[:5]:  # Show first 5 failures
            logger.warning(f"     {path}: {error}")

    if len(docs) == 0:
        raise ValueError(f"No documents were successfully loaded from {DATA_DIR}")

    # Check if collection exists
    collection_exists = False
    try:
        client.get_collection(COLLECTION)
        collection_exists = True
        logger.info(f"Collection {COLLECTION} already exists")
    except Exception:
        logger.info(f"Collection {COLLECTION} does not exist")

    if force_rebuild and collection_exists:
        # Delete and recreate collection
        client.delete_collection(COLLECTION)
        logger.info(f"Deleted existing collection {COLLECTION} for rebuild")
        collection_exists = False

    if not collection_exists:
        # Create new collection
        embed_dim = len(Settings.embed_model.get_text_embedding("test"))
        logger.info(f"Creating collection {COLLECTION} with dimension {embed_dim}")
        client.create_collection(
            collection_name=COLLECTION,
            vectors_config={"size": embed_dim, "distance": "Cosine"}
        )

    # Create vector store
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    if collection_exists and not force_rebuild:
        # Incremental update: check which files are already indexed
        logger.info("Performing incremental update...")

        # Get existing filenames from Qdrant (paginate to handle large collections)
        indexed_files = set()
        offset = None

        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION,
                limit=100,  # Process in batches of 100
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            points, next_offset = scroll_result

            for point in points:
                if point.payload and "file_name" in point.payload:
                    indexed_files.add(point.payload["file_name"])

            # Break if no more results
            if next_offset is None:
                break

            offset = next_offset

        logger.info(f"Found {len(indexed_files)} files already indexed: {indexed_files}")

        # Filter to only new documents
        new_docs = [doc for doc in docs if doc.metadata.get("file_name") not in indexed_files]

        if len(new_docs) == 0:
            logger.info("✅ All documents already indexed. No new files to add.")
            # Return existing index
            index = VectorStoreIndex.from_vector_store(vector_store)
            collection_info = client.get_collection(COLLECTION)
            logger.info(f"Collection has {collection_info.points_count} vectors")
            return index

        logger.info(f"Found {len(new_docs)} new documents to index: {[d.metadata.get('file_name') for d in new_docs]}")
        docs = new_docs

    logger.info(f"Indexing {len(docs)} documents...")

    # Phase 1A: Parse into nodes explicitly so we can add grounding metadata
    node_parser = Settings.node_parser
    nodes = node_parser.get_nodes_from_documents(docs, show_progress=True)
    logger.info(f"Parsed {len(docs)} documents into {len(nodes)} chunks")

    # Phase 1A: Add grounding metadata to all nodes
    nodes = add_grounding_metadata(nodes, use_grounding=True)

    # Create/update index with grounded nodes
    if collection_exists and not force_rebuild:
        # Load existing index and add new nodes
        index = VectorStoreIndex.from_vector_store(vector_store)
        for node in nodes:
            index.insert_nodes([node])
        logger.info(f"Added {len(nodes)} new grounded nodes to existing index")
    else:
        # Build fresh index from grounded nodes
        index = VectorStoreIndex(
            nodes,
            storage_context=storage_context,
            show_progress=True
        )
        logger.info(f"Created new index with {len(nodes)} grounded nodes")

    # Verify vectors were stored
    collection_info = client.get_collection(COLLECTION)
    vector_count = collection_info.points_count
    logger.info(f"✅ Collection now has {vector_count} vectors")

    if vector_count == 0:
        logger.error("⚠️ WARNING: No vectors were stored! Check embeddings configuration.")

    return index
