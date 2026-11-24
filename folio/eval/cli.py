"""python -m folio.eval.cli --method fake-oracle --dataset narrativeqa --budget 4k --limit 50 --reader

--budget all runs 2k, 4k and 8k (retrieval metrics at each; the reader only ever runs at 4k).
Data comes from --data-dir (default data/eval): files narrativeqa_test.jsonl / quality_dev.jsonl.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .datasets import LOADERS
from .registry import get_method, get_reader, get_retriever
from .runner import READER_CAP, run_eval
from .store import JsonFileStore
from .tracing import trace_event


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="folio.eval.cli")
    ap.add_argument("--method", required=True)
    ap.add_argument("--dataset", required=True, choices=sorted(LOADERS))
    ap.add_argument("--budget", default="4k", choices=["2k", "4k", "8k", "all"])
    ap.add_argument("--limit", type=int, default=None, help="sample N questions (deterministic); default all")
    ap.add_argument("--reader", action=argparse.BooleanOptionalAction, default=False)
    ap.add_argument("--reader-name", default="fake")
    ap.add_argument("--reader-cap", type=int, default=READER_CAP, help=f"max reader questions (hard cap {READER_CAP})")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resamples", type=int, default=1000)
    ap.add_argument("--data-dir", default="data/eval")
    ap.add_argument("--results-dir", default=None)
    ap.add_argument("--run-id", default=None)
    a = ap.parse_args(argv)

    questions = LOADERS[a.dataset](Path(a.data_dir))
    method = get_method(a.method)
    retriever = get_retriever(a.method, questions)
    reader = get_reader(a.reader_name) if a.reader else None
    store = JsonFileStore(a.results_dir) if a.results_dir else JsonFileStore()
    for budget in (["2k", "4k", "8k"] if a.budget == "all" else [a.budget]):
        run = run_eval(retriever=retriever, reader=reader, method=method, dataset=a.dataset, questions=questions,
                       budget=budget, limit=a.limit, seed=a.seed, reader_cap=a.reader_cap, resamples=a.resamples,
                       reader_name=a.reader_name if a.reader else None,
                       run_id=a.run_id if a.run_id and a.budget != "all" else None)
        store.save_run(run)
        trace_event("eval_run", metadata={"run_id": run.id, "method": run.method, "dataset": run.dataset})
        print(f"{run.id}: n={run.n_questions} reader_n={run.n_reader} "
              f"route@1={run.metrics['route@1']['mean']} recall={run.metrics['recall_proxy@10']['mean']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
