"""OpenTelemetry setup for Howler API."""

from flask import Flask
from howler.common.logging import get_logger
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = get_logger(__file__)

_flask_instrumentor: FlaskInstrumentor | None = None


def setup_telemetry() -> None:
    """Initialize the OpenTelemetry TracerProvider and library instrumentors.

    This should only be called when telemetry is enabled via config
    (core.telemetry.enabled). The OTLP exporter is configured via
    environment variables:
        - OTEL_EXPORTER_OTLP_ENDPOINT
        - OTEL_EXPORTER_OTLP_HEADERS
        - OTEL_EXPORTER_OTLP_PROTOCOL

    See https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/
    """
    global _flask_instrumentor  # noqa: PLW0603

    try:
        resource = Resource.create({"service.name": "howler"})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

        _flask_instrumentor = FlaskInstrumentor()

        logger.info("OpenTelemetry configured successfully.")
    except Exception:
        logger.exception("Failed to configure OpenTelemetry.")


def instrument_flask_app(app: Flask) -> None:
    """Instrument a Flask app with OpenTelemetry tracing."""
    if _flask_instrumentor is not None:
        _flask_instrumentor.instrument_app(app)
