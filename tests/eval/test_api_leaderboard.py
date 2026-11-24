from pathlib import Path

from fastapi.testclient import TestClient

from folio.api.app import create_app
from folio.api.routers.eval import get_store
from folio.eval.leaderboard import build_leaderboard, render_markdown
from folio.eval.store import JsonFileStore, QResult, RunRecord

SNAP = Path(__file__).parent / "snapshots" / "leaderboard.md"


def ci(mean, lo, hi, n=100):
    return {"mean": mean, "lo": lo, "hi": hi, "n": n}


def mk(method, ds, created, metrics, rid=None, results=()):
    return RunRecord(id=rid or f"{method}-{ds}", method=method, dataset=ds, budget="4k", created_at=created, seed=0,
                     n_questions=100, metrics=metrics, results=list(results))


RUNS = [
    mk("hybrid", "narrativeqa", "2026-01-02T00:00:00", {
        "route@1": ci(0.5, 0.4, 0.6), "route@5": ci(0.75, 0.65, 0.85), "recall_proxy@10": ci(0.3, 0.2, 0.4),
        "f1": ci(0.25, 0.2, 0.3), "rouge_l": ci(0.3, 0.25, 0.35), "meteor": ci(0.2, 0.15, 0.25),
        "latency_ms": {"p50": 120.4, "p95": 300.0, "n": 100}, "per_1k": {"cost_usd_equiv": 1.234, "n": 100}}),
    mk("hybrid", "quality", "2026-01-02T00:00:00", {"accuracy": ci(0.4, 0.3, 0.5)}),
    mk("bm25", "narrativeqa", "2026-01-01T00:00:00", {          # retrieval only: no answer columns
        "route@1": ci(0.25, 0.15, 0.35), "route@5": ci(0.5, 0.4, 0.6), "recall_proxy@10": ci(0.1, 0.05, 0.15),
        "latency_ms": {"p50": 30.0, "p95": 80.0, "n": 100}, "per_1k": {"cost_usd_equiv": None, "n": 0}}),
]


def test_leaderboard_snapshot():
    md = render_markdown(build_leaderboard([r.summary() for r in RUNS]))
    if not SNAP.exists():                      # first run writes it; review the file by eye, then commit
        SNAP.parent.mkdir(exist_ok=True)
        SNAP.write_text(md, encoding="utf-8")
    assert md == SNAP.read_text(encoding="utf-8")


def test_leaderboard_row_order_and_missing_cells():
    lb = build_leaderboard([r.summary() for r in RUNS])
    assert [r["method"] for r in lb["rows"]] == ["bm25", "hybrid"]       # plan order, not alphabetical
    assert lb["rows"][0]["cells"]["QuALITY acc."] is None
    assert lb["rows"][1]["cells"]["QuALITY acc."]["mean"] == 0.4
    assert build_leaderboard([r.summary() for r in RUNS], budget="8k")["rows"] == []


def test_eval_api(tmp_path):
    results = [QResult(qid=f"q{i}", question="?", label="wrong book" if i % 2 else None) for i in range(5)]
    store = JsonFileStore(tmp_path)
    store.save_run(mk("hybrid", "narrativeqa", "2026-01-02T00:00:00", {"f1": ci(0.2, 0.1, 0.3)}, "r1", results))
    store.save_run(mk("bm25", "quality", "2026-01-03T00:00:00", {}, "r2"))
    app = create_app()
    app.dependency_overrides[get_store] = lambda: store
    c = TestClient(app)
    runs = c.get("/eval/runs").json()
    assert [r["id"] for r in runs] == ["r2", "r1"] and "results" not in runs[0]    # newest first, no per-question rows
    page = c.get("/eval/runs/r1", params={"offset": 1, "limit": 2}).json()
    assert page["total"] == 5 and [r["qid"] for r in page["results"]] == ["q1", "q2"]
    assert page["metrics"]["f1"]["mean"] == 0.2
    assert c.get("/eval/runs/r1", params={"label": "wrong book"}).json()["total"] == 2
    assert c.get("/eval/runs/missing").status_code == 404
    assert c.get("/eval/runs/r1", params={"limit": 0}).status_code == 422
