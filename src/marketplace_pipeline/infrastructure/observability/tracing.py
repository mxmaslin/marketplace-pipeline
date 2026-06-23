from __future__ import annotations

import logging

from fastapi import FastAPI

logger = logging.getLogger(__name__)


def setup_opentelemetry(app: FastAPI, *, service_name: str, otlp_endpoint: str) -> None:
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError as exc:
        raise RuntimeError(
            "Install marketplace-pipeline[scale] for OpenTelemetry support"
        ) from exc

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    logger.info("OpenTelemetry enabled: service=%s endpoint=%s", service_name, otlp_endpoint)


def setup_sentry(*, dsn: str, environment: str = "production") -> None:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
    except ImportError as exc:
        raise RuntimeError("Install marketplace-pipeline[scale] for Sentry support") from exc

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        integrations=[FastApiIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,
    )
    logger.info("Sentry enabled")
