import time
import logging
from typing import Any, Dict, List, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Span

from llama_index.core.callbacks.base import BaseCallbackHandler
from llama_index.core.callbacks import CBEventType

logger = logging.getLogger(__name__)


class OTelLlamaIndexHandler(BaseCallbackHandler):
    """
    OpenTelemetry callback handler for LlamaIndex.
    Inspired by NVIDIA's opentelemetry_callback.py implementation.

    Tracks events: LLM calls, embeddings, chunking, retrieval, synthesis.

    Usage:
        from app.observability.callbacks import OTelLlamaIndexHandler
        from llama_index.core.callbacks import CallbackManager
        from llama_index.core import Settings as LlamaSettings

        otel_handler = OTelLlamaIndexHandler()
        callback_manager = CallbackManager([otel_handler])
        LlamaSettings.callback_manager = callback_manager
    """

    def __init__(self) -> None:
        super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])
        self._tracer = trace.get_tracer("llama-index")
        self._span_stack: Dict[str, Span] = {}
        self._start_times: Dict[str, float] = {}

    def _get_span_name(self, event_type: CBEventType) -> str:
        """Map LlamaIndex event types to readable span names."""
        mapping = {
            CBEventType.LLM: "llm_call",
            CBEventType.EMBEDDING: "embedding_generation",
            CBEventType.CHUNKING: "document_chunking",
            CBEventType.RETRIEVE: "vector_retrieval",
            CBEventType.SYNTHESIZE: "response_synthesis",
            CBEventType.QUERY: "query_processing",
            CBEventType.NODE_PARSING: "node_parsing",
            CBEventType.TREE: "tree_construction",
            CBEventType.SUB_QUESTION: "sub_question",
            CBEventType.TEMPLATING: "prompt_templating",
            CBEventType.RERANKING: "reranking",
        }
        return mapping.get(event_type, f"llamaindex_{event_type.name.lower()}")

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Start a span when a LlamaIndex event begins."""
        span_name = self._get_span_name(event_type)
        span = self._tracer.start_span(span_name)

        # Store span and start time for later
        self._span_stack[event_id] = span
        self._start_times[event_id] = time.time()

        # Add event-specific attributes
        span.set_attribute("event.type", event_type.name)
        span.set_attribute("event.id", event_id)

        if payload:
            self._add_payload_attributes(span, event_type, payload)

        logger.debug(f"Started span: {span_name} (event_id={event_id})")
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """End a span when a LlamaIndex event completes."""
        span = self._span_stack.pop(event_id, None)
        start_time = self._start_times.pop(event_id, None)

        if span is None:
            logger.warning(f"No span found for event_id={event_id}")
            return

        # Calculate duration
        if start_time:
            duration_ms = (time.time() - start_time) * 1000
            span.set_attribute("duration_ms", duration_ms)

        # Add end-event specific attributes
        if payload:
            self._add_end_payload_attributes(span, event_type, payload)

        span.set_status(Status(StatusCode.OK))
        span.end()

        logger.debug(f"Ended span for event_id={event_id}")

    def _add_payload_attributes(
        self, span: Span, event_type: CBEventType, payload: Dict[str, Any]
    ) -> None:
        """Add relevant attributes from event payload to span."""

        if event_type == CBEventType.LLM:
            # Capture model info, prompt length (NOT actual prompt content for privacy)
            if "messages" in payload:
                span.set_attribute("llm.message_count", len(payload["messages"]))
            if "model" in payload:
                span.set_attribute("llm.model", str(payload["model"]))
            if "temperature" in payload:
                span.set_attribute("llm.temperature", payload["temperature"])

        elif event_type == CBEventType.EMBEDDING:
            # Capture embedding dimensions, chunk count
            if "chunks" in payload:
                span.set_attribute("embedding.chunk_count", len(payload["chunks"]))

        elif event_type == CBEventType.RETRIEVE:
            # Capture query info (length only, not content)
            if "query_str" in payload:
                span.set_attribute("retrieval.query_length", len(payload["query_str"]))

        elif event_type == CBEventType.CHUNKING:
            if "chunks" in payload:
                span.set_attribute("chunking.output_count", len(payload["chunks"]))

    def _add_end_payload_attributes(
        self, span: Span, event_type: CBEventType, payload: Dict[str, Any]
    ) -> None:
        """Add end-event attributes like token counts and results."""

        if event_type == CBEventType.LLM:
            # Token usage is critical for cost tracking
            if "response" in payload:
                response = payload["response"]
                if hasattr(response, "raw"):
                    raw = response.raw
                    if hasattr(raw, "usage"):
                        span.set_attribute("llm.prompt_tokens", raw.usage.get("prompt_tokens", 0))
                        span.set_attribute("llm.completion_tokens", raw.usage.get("completion_tokens", 0))
                        span.set_attribute("llm.total_tokens", raw.usage.get("total_tokens", 0))

        elif event_type == CBEventType.RETRIEVE:
            if "nodes" in payload:
                span.set_attribute("retrieval.result_count", len(payload["nodes"]))

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        """Called when a trace starts."""
        pass

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """Called when a trace ends."""
        pass
