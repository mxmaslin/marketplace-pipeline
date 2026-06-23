from __future__ import annotations

PUBLIC_PATH_PREFIXES = (
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def is_public_path(path: str) -> bool:
    return any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_PATH_PREFIXES)
