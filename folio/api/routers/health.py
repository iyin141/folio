"""Owner: B0. /health stays dependency-free; B0 adds /metrics (Prometheus)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}
