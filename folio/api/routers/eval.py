"""Owner: B2. See docs/ORCHESTRATION.md. Reads eval runs from the RunStore (JSON files now, DB later)."""
import os

from fastapi import APIRouter, Depends, HTTPException, Query

from folio.eval.store import DEFAULT_DIR, JsonFileStore, RunRecord, RunStore, RunSummary

router = APIRouter()


def get_store() -> RunStore:
    """Override with app.dependency_overrides[get_store] to wire another store (e.g. Postgres)."""
    return JsonFileStore(os.getenv("FOLIO_EVAL_DIR", str(DEFAULT_DIR)))


@router.get("/runs", response_model=list[RunSummary])
def list_runs(store: RunStore = Depends(get_store)):
    return store.list_runs()


@router.get("/runs/{run_id}")
def get_run(run_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=500),
            label: str | None = None, store: RunStore = Depends(get_store)):
    run: RunRecord | None = store.get_run(run_id)
    if run is None:
        raise HTTPException(404, f"no eval run {run_id!r}")
    rows = [r for r in run.results if label is None or r.label == label]
    return {**run.summary().model_dump(), "total": len(rows), "offset": offset, "limit": limit,
            "results": [r.model_dump() for r in rows[offset:offset + limit]]}
