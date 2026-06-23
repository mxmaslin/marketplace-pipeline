"""Backward-compatible settings re-export."""

from marketplace_pipeline.infrastructure.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
