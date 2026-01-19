import os
import logging
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME

logger = logging.getLogger(__name__)

_metrics_initialized = False


def setup_metrics(service_name: str = "daemoniq-rag") -> None:
    """Initialize OpenTelemetry metrics."""
    global _metrics_initialized

    if _metrics_initialized:
        logger.debug("Metrics already initialized, skipping")
        return

    enable_tracing = os.getenv("ENABLE_TRACING", "false").lower() == "true"
    if not enable_tracing:
        return

    resource = Resource.create({SERVICE_NAME: service_name})

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    if os.getenv("OTEL_EXPORTER", "otlp") == "console":
        reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
        logger.info("Metrics enabled with console exporter")
    else:
        exporter = OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True)
        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
        logger.info(f"Metrics enabled, exporting to {otlp_endpoint}")

    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)

    _metrics_initialized = True


def get_meter(name: str = "daemoniq-rag"):
    """Get a meter instance."""
    return metrics.get_meter(name)


def create_rag_metrics(meter=None):
    """
    Create metrics specific to RAG operations.

    Returns a dictionary of metric instruments for tracking:
    - Query counts and latency
    - Retrieval performance
    - LLM generation metrics
    - Token usage
    - Document ingestion
    """
    if meter is None:
        meter = get_meter()

    return {
        "query_counter": meter.create_counter(
            "rag.queries.total",
            description="Total number of RAG queries",
            unit="1"
        ),
        "query_latency": meter.create_histogram(
            "rag.query.latency",
            description="RAG query latency in milliseconds",
            unit="ms"
        ),
        "retrieval_latency": meter.create_histogram(
            "rag.retrieval.latency",
            description="Vector retrieval latency in milliseconds",
            unit="ms"
        ),
        "llm_latency": meter.create_histogram(
            "rag.llm.latency",
            description="LLM generation latency in milliseconds",
            unit="ms"
        ),
        "embedding_latency": meter.create_histogram(
            "rag.embedding.latency",
            description="Embedding generation latency in milliseconds",
            unit="ms"
        ),
        "tokens_used": meter.create_counter(
            "rag.tokens.total",
            description="Total tokens used",
            unit="1"
        ),
        "chunks_retrieved": meter.create_histogram(
            "rag.chunks.retrieved",
            description="Number of chunks retrieved per query",
            unit="1"
        ),
        "documents_ingested": meter.create_counter(
            "rag.documents.ingested",
            description="Total documents ingested",
            unit="1"
        ),
    }
