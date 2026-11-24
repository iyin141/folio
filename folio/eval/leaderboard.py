"""Plan 03 headline table: methods x columns with 95% CIs, from stored runs.

    python -m folio.eval.leaderboard [--results-dir D] [--budget 4k] [--md out.md] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import METHODS
from .store import JsonFileStore, RunSummary, RunStore

# (column title, dataset the number comes from, metric key, kind)
COLUMNS = [
    ("Book routing @1", "narrativeqa", "route@1", "ci"),
    ("Book routing @5", "narrativeqa", "route@5", "ci"),
    ("Passage recall proxy @10", "narrativeqa", "recall_proxy@10", "ci"),
    ("NarrativeQA F1", "narrativeqa", "f1", "ci"),
    ("NarrativeQA ROUGE-L", "narrativeqa", "rouge_l", "ci"),
    ("NarrativeQA METEOR (exact)", "narrativeqa", "meteor", "ci"),
    ("QuALITY acc.", "quality", "accuracy", "ci"),
    ("p50 latency (ms)", "narrativeqa", "latency_ms", "p50"),
    ("$ per 1k questions (equiv.)", "narrativeqa", "per_1k", "cost_usd_equiv"),
]


def _cell(run: RunSummary | None, metric: str, kind: str):
    if run is None:
        return None
    m = run.metrics.get(metric)
    if not m:
        return None
    if kind == "ci":
        return None if m.get("mean") is None else {"mean": m["mean"], "lo": m["lo"], "hi": m["hi"], "n": m["n"]}
    v = m.get(kind)
    return None if v is None else {"mean": v}


def build_leaderboard(runs: list[RunSummary], budget: str = "4k") -> dict:
    """Newest run per (method, dataset) at `budget`. Latency / cost fall back to the QuALITY run."""
    latest: dict[tuple[str, str], RunSummary] = {}
    for r in sorted(runs, key=lambda r: (r.created_at, r.id)):
        if r.budget == budget:
            latest[(r.method, r.dataset)] = r
    order = {n: i for i, n in enumerate(METHODS)}
    methods = sorted({m for m, _ in latest}, key=lambda m: (order.get(m, len(order)), m))
    rows = []
    for m in methods:
        cells = {}
        for title, ds, key, kind in COLUMNS:
            cell = _cell(latest.get((m, ds)), key, kind)
            if cell is None and kind != "ci":
                cell = _cell(latest.get((m, "quality")), key, kind)
            cells[title] = cell
        rows.append({"method": m, "cells": cells,
                     "runs": {ds: latest[(m, ds)].id for ds in ("narrativeqa", "quality") if (m, ds) in latest}})
    return {"budget": budget, "columns": [c[0] for c in COLUMNS], "rows": rows}


def _fmt(title: str, cell) -> str:
    if cell is None:
        return "n/a"
    if "latency" in title:
        return f"{cell['mean']:.0f}"
    if title.startswith("$"):
        return f"${cell['mean']:.2f}"
    return f"{cell['mean']:.3f} ({cell['lo']:.3f}-{cell['hi']:.3f})"


def render_markdown(lb: dict) -> str:
    cols = lb["columns"]
    out = [f"Budget {lb['budget']}. Cells: mean (95% bootstrap CI). Recall is a proxy (a reference answer "
           "appears in retrieved text), not gold-passage recall. Cost is the CLI's equivalent cost, not billed.", "",
           "| Method | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for r in lb["rows"]:
        out.append(f"| {r['method']} | " + " | ".join(_fmt(c, r["cells"][c]) for c in cols) + " |")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None, store: RunStore | None = None) -> int:
    ap = argparse.ArgumentParser(prog="folio.eval.leaderboard")
    ap.add_argument("--results-dir")
    ap.add_argument("--budget", default="4k")
    ap.add_argument("--md", help="write Markdown here (default: print)")
    ap.add_argument("--json", help="write JSON for the UI here")
    a = ap.parse_args(argv)
    store = store or (JsonFileStore(a.results_dir) if a.results_dir else JsonFileStore())
    lb = build_leaderboard(store.list_runs(), a.budget)
    md = render_markdown(lb)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
    else:
        print(md)
    if a.json:
        Path(a.json).write_text(json.dumps(lb, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
