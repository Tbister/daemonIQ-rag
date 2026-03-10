"""
Query endpoints for RAG chat and retrieval.
"""
import time
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from llama_index.core.prompts import PromptTemplate
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.core.schema import QueryBundle

from app.config import RETRIEVAL_MODE, OLLAMA_MODEL, ENABLE_TRACING
from app.models import QueryReq
from app.dependencies import get_or_build_index
from app.services.retrieval import grounded_retrieve
from app.observability import get_tracer, instrumentation_wrapper, create_rag_metrics

logger = logging.getLogger(__name__)
router = APIRouter(tags=["query"])

# Instantiate metric instruments if tracing is enabled
_rag_metrics = create_rag_metrics() if ENABLE_TRACING else {}

# BAS-SPECIFIC prompt optimized for technical manuals
QA_PROMPT = PromptTemplate(
    "You are a Building Automation System (BAS) technical assistant specializing in Honeywell, Niagara, and CIPer systems.\n\n"
    "INSTRUCTIONS:\n"
    "- Answer ONLY using information from the context below\n"
    "- Answer the question directly and naturally — do not impose a fixed structure\n"
    "- Use bullet points only when listing multiple items or specs; use prose for 'what is' questions\n"
    "- Include specific technical details (model numbers, I/O specs, DIP switches, wiring) when they are relevant to the question and present in the context\n"
    "- Do NOT make up information or use external knowledge\n"
    "- Only mention missing information if the user explicitly asked for something that is not in the context\n\n"
    "Context from BAS documentation:\n{context_str}\n\n"
    "Question: {query_str}\n\n"
    "Answer:\n"
)

# Simplified prompt for streaming
STREAMING_QA_PROMPT = PromptTemplate(
    "You are a Building Automation System (BAS) technical assistant specializing in Honeywell, Niagara, and CIPer systems.\n\n"
    "INSTRUCTIONS:\n"
    "- Answer ONLY using information from the context below\n"
    "- Answer the question directly and naturally\n"
    "- Use bullet points only when listing multiple items or specs\n"
    "- Include specific technical details when relevant and present in the context\n"
    "- Do NOT make up information or use external knowledge\n\n"
    "Context from BAS documentation:\n{context_str}\n\n"
    "Question: {query_str}\n\n"
    "Answer:\n"
)


@router.post("/retrieve")
@instrumentation_wrapper("retrieve_documents")
def retrieve_only(req: QueryReq):
    """Retrieve relevant chunks without LLM generation - useful for testing."""
    tracer = get_tracer()
    try:
        query_text = req.get_query()
        logger.info(f"Retrieving chunks for: {query_text} (field: {'q' if req.q else 'query'})")
        index = get_or_build_index()

        # Phase 1B: Use grounded retrieval with tracing
        with tracer.start_as_current_span("vector_search") as span:
            span.set_attribute("query_length", len(query_text))
            span.set_attribute("top_k", req.k)
            nodes = grounded_retrieve(index, query_text, top_k=req.k)
            span.set_attribute("result_count", len(nodes))

        results = []
        for node in nodes:
            # Handle both vanilla (node has .text) and grounded (node has .node.text) retrieval
            text = node.text if hasattr(node, 'text') else node.node.text
            metadata = node.metadata if hasattr(node, 'metadata') else node.node.metadata
            results.append({
                "score": node.score,
                "text": text,
                "metadata": metadata
            })

        logger.info(f"Retrieved {len(results)} chunks (mode: {RETRIEVAL_MODE})")
        return {"count": len(results), "results": results, "mode": RETRIEVAL_MODE}
    except Exception as e:
        logger.error(f"Error during retrieval: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.post("/chat")
@instrumentation_wrapper("rag_query")
def chat(req: QueryReq):
    """RAG chat endpoint - retrieves context and generates response."""
    tracer = get_tracer()
    start_time = time.time()
    try:
        query_text = req.get_query()
        logger.info(f"Querying: {query_text} (field: {'q' if req.q else 'query'})")
        index = get_or_build_index()

        # Enforce minimum retrieval of 4 chunks
        top_k = max(req.k, 4)

        # Phase 1B: Use grounded retrieval with tracing
        with tracer.start_as_current_span("retrieval") as retrieval_span:
            retrieval_span.set_attribute("query_length", len(query_text))
            retrieval_span.set_attribute("top_k", top_k)
            retrieval_span.set_attribute("mode", RETRIEVAL_MODE)
            logger.info(f"Retrieving {top_k} chunks for RAG (mode: {RETRIEVAL_MODE})...")
            retrieval_start = time.time()
            source_nodes = grounded_retrieve(index, query_text, top_k=top_k)
            retrieval_ms = (time.time() - retrieval_start) * 1000
            retrieval_span.set_attribute("result_count", len(source_nodes))
            retrieval_span.set_attribute("duration_ms", retrieval_ms)

        # Create query engine and synthesize response from retrieved nodes with tracing
        with tracer.start_as_current_span("llm_synthesis") as llm_span:
            llm_span.set_attribute("llm.model", OLLAMA_MODEL)
            llm_start = time.time()

            synthesizer = get_response_synthesizer(
                response_mode="compact",
                text_qa_template=QA_PROMPT
            )

            query_bundle = QueryBundle(query_str=query_text)
            resp = synthesizer.synthesize(query_bundle, nodes=source_nodes)

            llm_ms = (time.time() - llm_start) * 1000
            llm_span.set_attribute("duration_ms", llm_ms)
            llm_span.set_attribute("response_length", len(str(resp)))

        # Build deduplicated sources array with page numbers for UI
        sources = list(dict.fromkeys(
            f"{s.node.metadata.get('file_name', '')} (p.{s.node.metadata.get('page_label', '?')})"
            for s in source_nodes
        ))

        # Log retrieval details for debugging
        logger.info(f"=== RETRIEVAL DEBUG ===")
        logger.info(f"Retrieved {len(source_nodes)} chunks")
        unique_files = set(sources)
        logger.info(f"Unique source files: {len(unique_files)} - {unique_files}")

        for i, node in enumerate(source_nodes):
            score = node.score if hasattr(node, 'score') else None
            page = node.node.metadata.get("page_label", "?")
            filename = node.node.metadata.get("file_name", "?")
            text_preview = node.text[:300].replace('\n', ' ')

            # Format score properly
            score_str = f"{score:.4f}" if isinstance(score, float) else "N/A"
            logger.info(f"Chunk {i+1}: score={score_str}, file={filename}, page={page}")
            logger.info(f"  Preview: {text_preview}...")

        # Log total query time
        total_time_ms = (time.time() - start_time) * 1000
        logger.info(f"Query completed in {total_time_ms:.2f}ms. Sources: {sources}")

        # Record metrics
        if _rag_metrics:
            _rag_metrics["query_counter"].add(1, {"mode": RETRIEVAL_MODE})
            _rag_metrics["query_latency"].record(total_time_ms, {"mode": RETRIEVAL_MODE})
            _rag_metrics["retrieval_latency"].record(retrieval_ms, {"mode": RETRIEVAL_MODE})
            _rag_metrics["llm_latency"].record(llm_ms, {"model": OLLAMA_MODEL})
            _rag_metrics["chunks_retrieved"].record(len(source_nodes), {"mode": RETRIEVAL_MODE})

        return {"answer": str(resp), "sources": sources}
    except TimeoutError:
        logger.error("LLM query timed out after 300 seconds")
        raise HTTPException(status_code=504, detail="LLM query timed out. Try: 1) Reduce k value, 2) Ask simpler question, 3) Check Ollama logs")
    except Exception as e:
        logger.error(f"Error during query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/chat-stream")
def chat_stream(req: QueryReq):
    """Streaming endpoint - shows partial results as they're generated."""
    try:
        query_text = req.get_query()
        logger.info(f"Streaming query: {query_text} (field: {'q' if req.q else 'query'})")
        index = get_or_build_index()

        # Enforce minimum retrieval of 4 chunks
        top_k = max(req.k, 4)

        # Phase 1B: Use grounded retrieval
        logger.info(f"Retrieving {top_k} chunks for streaming RAG (mode: {RETRIEVAL_MODE})...")
        source_nodes = grounded_retrieve(index, query_text, top_k=top_k)

        # Create streaming response synthesizer
        synthesizer = get_response_synthesizer(
            response_mode="compact",
            text_qa_template=STREAMING_QA_PROMPT,
            streaming=True
        )

        query_bundle = QueryBundle(query_str=query_text)

        def generate():
            streaming_response = synthesizer.synthesize(query_bundle, nodes=source_nodes)
            for text in streaming_response.response_gen:
                yield text

        return StreamingResponse(generate(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error during streaming: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")
