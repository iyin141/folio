"""Run records and the narrow persistence interface (save_run, list_runs, get_run).

B0 builds the Postgres tables eval_runs / eval_results; the orchestrator wires a DB store with the
same three methods later. JsonFileStore keeps one JSON file per run under results/.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

DEFAULT_DIR = Path(__file__).parent / "results"


class QResult(BaseModel):
    qid: str
    question: str
    gold_gutenberg_id: int | None = None
    routing_eligible: bool = False
    routed_gids: list[int | None] = Field(default_factory=list)
    route_at1: bool | None = None
    route_at5: bool | None = None
    recall: bool | None = None
    answer: str | None = None
    choice: int | None = None
    f1: float | None = None
    rouge_l: float | None = None
    meteor: float | None = None
    correct: bool | None = None
    latency_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd_equiv: float = 0.0
    evidence_ids: list[str] = Field(default_factory=list)
    label: str | None = None


class RunSummary(BaseModel):
    id: str
    method: str
    dataset: str
    budget: str
    created_at: str
    seed: int
    limit: int | None = None
    reader: str | None = None
    n_questions: int = 0
    n_reader: int = 0
    config: dict = Field(default_factory=dict)
    metrics: dict = Field(default_factory=dict)   # name -> {mean, lo, hi, n} (or p50/p95, per-1k blocks)


class RunRecord(RunSummary):
    results: list[QResult] = Field(default_factory=list)

    def summary(self) -> RunSummary:
        return RunSummary(**self.model_dump(exclude={"results"}))


class RunStore(Protocol):
    def save_run(self, run: RunRecord) -> str: ...
    def list_runs(self) -> list[RunSummary]: ...          # newest first
    def get_run(self, run_id: str) -> RunRecord | None: ...


class JsonFileStore:
    def __init__(self, root: str | Path = DEFAULT_DIR):
        self.root = Path(root)

    def save_run(self, run: RunRecord) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{run.id}.json").write_text(run.model_dump_json(indent=1), encoding="utf-8")
        return run.id

    def list_runs(self) -> list[RunSummary]:
        if not self.root.is_dir():
            return []
        runs = [RunRecord.model_validate_json(p.read_text(encoding="utf-8")).summary()
                for p in self.root.glob("*.json")]
        return sorted(runs, key=lambda r: (r.created_at, r.id), reverse=True)

    def get_run(self, run_id: str) -> RunRecord | None:
        p = self.root / f"{Path(run_id).name}.json"   # .name: no path traversal from the API
        return RunRecord.model_validate_json(p.read_text(encoding="utf-8")) if p.is_file() else None
