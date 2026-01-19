import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator
from functools import wraps

logger = logging.getLogger(__name__)

_tracing_initialized = False


def setup_tracing(service_name: str = "daemoniq-rag") -> None:
    """Initialize OpenTelemetry tracing with OTLP exporter."""
    global _tracing_initialized

    if _tracing_initialized:
        logger.debug("Tracing already initialized, skipping")
        return

    enable_tracing = os.getenv("ENABLE_TRACING", "false").lower() == "true"
    if not enable_tracing:
        logger.info("Tracing disabled (set ENABLE_TRACING=true to enable)")
        return

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # Configure exporter based on environment
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

    if os.getenv("OTEL_EXPORTER", "otlp") == "console":
        processor = BatchSpanProcessor(ConsoleSpanExporter())
        logger.info("Tracing enabled with console exporter")
    else:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        processor = BatchSpanProcessor(exporter)
        logger.info(f"Tracing enabled, exporting to {otlp_endpoint}")

    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Set up context propagation (W3C Trace Context + Baggage)
    set_global_textmap(CompositePropagator([
        TraceContextTextMapPropagator(),
        W3CBaggagePropagator()
    ]))

    _tracing_initialized = True


def get_tracer(name: str = "daemoniq-rag"):
    """Get a tracer instance."""
    return trace.get_tracer(name)


def instrumentation_wrapper(span_name: str):
    """
    Decorator for instrumenting functions with OpenTelemetry spans.
    Similar to NVIDIA's instrumentation_wrapper pattern.

    Usage:
        @instrumentation_wrapper("my_operation")
        def my_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
