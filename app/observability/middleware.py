import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from opentelemetry import trace
from opentelemetry.propagate import extract

logger = logging.getLogger(__name__)


class OTelMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for OpenTelemetry tracing.
    Creates a root span for each request and extracts trace context from headers.

    This enables distributed tracing when trace context is passed via
    W3C Trace Context headers (traceparent, tracestate).

    Usage:
        from app.observability.middleware import OTelMiddleware

        app = FastAPI()
        app.add_middleware(OTelMiddleware, service_name="daemoniq-rag")
    """

    def __init__(self, app, service_name: str = "daemoniq-rag"):
        super().__init__(app)
        self.tracer = trace.get_tracer(service_name)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract trace context from incoming headers (for distributed tracing)
        context = extract(dict(request.headers))

        span_name = f"{request.method} {request.url.path}"

        with self.tracer.start_as_current_span(
            span_name,
            context=context,
            kind=trace.SpanKind.SERVER
        ) as span:
            # Add request attributes
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.scheme", request.url.scheme)
            span.set_attribute("http.host", request.url.hostname or "")
            span.set_attribute("http.target", request.url.path)

            # Add client info if available
            if request.client:
                span.set_attribute("http.client_ip", request.client.host)

            start_time = time.time()

            try:
                response = await call_next(request)

                # Add response attributes
                span.set_attribute("http.status_code", response.status_code)
                duration_ms = (time.time() - start_time) * 1000
                span.set_attribute("http.duration_ms", duration_ms)

                if response.status_code >= 400:
                    span.set_status(trace.Status(trace.StatusCode.ERROR))
                else:
                    span.set_status(trace.Status(trace.StatusCode.OK))

                return response

            except Exception as e:
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                raise
