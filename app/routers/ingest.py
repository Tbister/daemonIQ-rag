"""
Document ingestion endpoints.
"""
import os
import glob
import logging
from fastapi import APIRouter, HTTPException

from app.config import DATA_DIR, COLLECTION
from app.models import IngestReq, IngestResp
from app.dependencies import client, set_index_cache
from app.services.indexing import build_index

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResp)
def ingest(req: IngestReq = IngestReq()):
    """Ingest documents into the vector store."""
    try:
        logger.info(f"Starting ingestion from {DATA_DIR} (force_rebuild={req.force_rebuild})")

        # Check if directory exists
        if not os.path.exists(DATA_DIR):
            raise HTTPException(status_code=400, detail=f"Data directory not found: {DATA_DIR}")

        # Find files
        files = [p for p in glob.glob(f"{DATA_DIR}/*") if any(p.endswith(ext) for ext in [".pdf", ".txt", ".md"])]
        logger.info(f"Found {len(files)} files in data directory")

        if len(files) == 0:
            raise HTTPException(status_code=400, detail=f"No PDF, TXT, or MD files found in {DATA_DIR}")

        # Build index (incremental by default, unless force_rebuild=True)
        logger.info(f"Building index (force_rebuild={req.force_rebuild})...")
        index = build_index(force_rebuild=req.force_rebuild)
        set_index_cache(index)

        # Get final count
        collection_info = client.get_collection(COLLECTION)
        total_vectors = collection_info.points_count

        mode = "full_rebuild" if req.force_rebuild else "incremental"
        logger.info(f"Successfully completed {mode} ingestion. Total vectors: {total_vectors}")

        return IngestResp(
            files_indexed=len(files),
            total_vectors=total_vectors,
            mode=mode
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
