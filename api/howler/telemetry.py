"""Telemetry setup for Howler API."""

import os

from flask import Flask

from howler.common.logging import get_logger

logger = get_logger(__file__)


def setup_telemetry(app: Flask) -> None:
    """Initialize telemetry and library instrumentors.

    The backend is selected via ``config.core.telemetry.backend``.

    For ``opentelemetry``, a TracerProvider with the OTLP exporter is created
    manually. Environment variables control the exporter:
        - OTEL_EXPORTER_OTLP_ENDPOINT
        - OTEL_EXPORTER_OTLP_HEADERS

    See https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/

    For ``azure_monitor``, ``configure_azure_monitor`` from
    ``azure-monitor-opentelemetry`` handles the full setup (provider,
    exporters, and instrumentation). Requires the
    ``APPLICATIONINSIGHTS_CONNECTION_STRING`` environment variable.
    """
    from howler.odm.models.config import config

    backend = config.core.telemetry.backend

    try:
        if backend == "opentelemetry":
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.instrumentation.flask import FlaskInstrumentor
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
                logger.error("OpenTelemetry telemetry backend selected but OTEL_EXPORTER_OTLP_ENDPOINT is not set.")
                return

            resource = Resource.create()
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            trace.set_tracer_provider(provider)
            FlaskInstrumentor().instrument_app(app)
        elif backend == "azure_monitor":
            from azure.monitor.opentelemetry import configure_azure_monitor
            from opentelemetry.instrumentation.flask import FlaskInstrumentor

            if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
                logger.error(
                    "Azure Monitor telemetry backend selected but APPLICATIONINSIGHTS_CONNECTION_STRING is not set."
                )
                return

            configure_azure_monitor()
            FlaskInstrumentor().instrument_app(app)
        else:
            logger.error("Unsupported telemetry backend '%s'.", backend)
            return

        logger.info("Telemetry configured successfully (backend=%s).", backend)
    except Exception:
        logger.exception("Failed to configure telemetry (backend=%s).", backend)
