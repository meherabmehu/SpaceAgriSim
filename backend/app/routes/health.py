from fastapi import APIRouter

from app.config.settings import settings
from app.observability import snapshot

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    """Simple liveness probe used by the frontend to show backend status."""
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.get("/metrics")
def metrics() -> dict:
    """Minimal deployment diagnostics without PII or secret-bearing labels."""
    return {"metrics": snapshot(), "scope": "per-process; resets on deployment"}
