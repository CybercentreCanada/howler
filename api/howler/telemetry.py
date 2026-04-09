"""Telemetry setup for Howler API."""

from howler.common.logging import get_logger

logger = get_logger(__file__)


def setup_telemetry() -> None:
    """Initialize telemetry and library instrumentors.

    The backend is selected via ``config.core.telemetry.backend``.

    For ``opentelemetry``, a TracerProvider with the OTLP exporter is created
    manually. Environment variables control the exporter:
        - OTEL_EXPORTER_OTLP_ENDPOINT
        - OTEL_EXPORTER_OTLP_HEADERS
        - OTEL_EXPORTER_OTLP_PROTOCOL

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
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create()
            provider = TracerProvider(resource=resource)
            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            trace.set_tracer_provider(provider)
        elif backend == "azure_monitor":
            import os

            from azure.monitor.opentelemetry import configure_azure_monitor

            if not os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
                logger.error(
                    "Azure Monitor telemetry backend selected but APPLICATIONINSIGHTS_CONNECTION_STRING is not set."
                )
                return

            configure_azure_monitor()
        else:
            logger.error("Unsupported telemetry backend '%s'.", backend)
            return

        logger.info("Telemetry configured successfully (backend=%s).", backend)
    except Exception:
        logger.exception("Failed to configure telemetry (backend=%s).", backend)
