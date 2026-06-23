"""Re-export for backward compatibility — prefer infrastructure.observability.metrics."""

from marketplace_pipeline.infrastructure.observability.metrics import MetricsRegistry

__all__ = ["MetricsRegistry"]
