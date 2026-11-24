"""Eval runner. Retrieval metrics run on every sampled question; the reader only on a capped subset
at the 4k budget (ORCHESTRATION.md: 200 questions per dataset, 4k only)."""
from __future__ import annotations

import random
import time
from collections.abc import Callable
from datetime import datetime, timezone

from folio.contracts import Evidence, Hit, MethodConfig, Reader, Retriever

from . import metrics as M
from .datasets.models import Question
from .failures import label_failure
from .stats import bootstrap_ci
from .store import QResult, RunRecord

READER_CAP = 200          # hard ceiling per dataset per method
READER_BUDGET = "4k"
RECALL_K = 10
FAIL_F1 = 0.5             # a NarrativeQA answer counts as correct for failure labelling at F1 >= this


def build_evidence(hits: list[Hit]) -> list[Evidence]:
    """E1..En by a counter, in prompt order (never the same id twice)."""
    return [Evidence(id=f"E{i}", chunk=h.chunk) for i, h in enumerate(hits, 1)]


def sample(questions: list[Question], limit: int | None, seed: int) -> list[Question]:
    qs = sorted(questions, key=lambda q: q.id)          # stable base order regardless of loader order
    if limit is None or limit >= len(qs):
        return qs
    return random.Random(seed).sample(qs, limit)


def references(q: Question) -> list[str]:
    if q.references:
        return q.references
    return [q.options[q.gold_choice]] if q.options is not None and q.gold_choice is not None else []


def _ci(values: list[float], resamples: int, seed: int) -> dict:
    return bootstrap_ci(values, resamples, seed)


def aggregate(results: list[QResult], resamples: int, seed: int) -> dict:
    def col(name, rows=results):
        return [float(getattr(r, name)) for r in rows if getattr(r, name) is not None]
    elig = [r for r in results if r.routing_eligible]
    ran = [r for r in results if r.answer is not None]
    out = {
        "route@1": _ci(col("route_at1", elig), resamples, seed),
        "route@5": _ci(col("route_at5", elig), resamples, seed),
        f"recall_proxy@{RECALL_K}": _ci(col("recall"), resamples, seed),
        "f1": _ci(col("f1"), resamples, seed), "rouge_l": _ci(col("rouge_l"), resamples, seed),
        "meteor": _ci(col("meteor"), resamples, seed), "accuracy": _ci(col("correct"), resamples, seed),
    }
    lat = M.latency_stats([r.latency_ms for r in results])
    out["latency_ms"] = {"p50": lat["p50"], "p95": lat["p95"], "n": len(results)}
    out["per_1k"] = {"tokens_in": M.per_1k(sum(r.tokens_in for r in ran), len(ran)),
                     "tokens_out": M.per_1k(sum(r.tokens_out for r in ran), len(ran)),
                     "cost_usd_equiv": M.per_1k(sum(r.cost_usd_equiv for r in ran), len(ran)) if ran else None,
                     "n": len(ran)}
    return out


def run_eval(*, retriever: Retriever, reader: Reader | None, method: MethodConfig, dataset: str,
             questions: list[Question], budget: str = "4k", limit: int | None = None, seed: int = 0,
             reader_cap: int = READER_CAP, resamples: int = 1000, reader_name: str | None = None,
             book_id_for: Callable[[int], int | None] | None = None, run_id: str | None = None) -> RunRecord:
    """book_id_for maps a Gutenberg id to the library's internal Book.id; only used for oracle_book methods."""
    qs = sample(questions, limit, seed)
    cfg = method.model_copy(update={"budget": budget})
    n_reader = min(reader_cap, READER_CAP, len(qs)) if reader is not None and budget == READER_BUDGET else 0
    results = []
    for i, q in enumerate(qs):
        book_id = book_id_for(q.gold_gutenberg_id) if cfg.oracle_book and book_id_for and q.gold_gutenberg_id else None
        t0 = time.perf_counter()
        rr = retriever.retrieve(q.question, cfg, book_id)
        ms = sum(rr.timings_ms.values()) if rr.timings_ms else (time.perf_counter() - t0) * 1000
        gids = [b.book.gutenberg_id for b in rr.routed_books]
        refs = references(q)
        res = QResult(
            qid=q.id, question=q.question, gold_gutenberg_id=q.gold_gutenberg_id, routing_eligible=q.routing_eligible,
            routed_gids=gids, recall=M.recall_proxy(refs, [h.chunk.text for h in rr.hits], RECALL_K) if refs else None)
        if q.routing_eligible:
            res.route_at1 = M.routing_hit(q.gold_gutenberg_id, gids, 1)
            res.route_at5 = M.routing_hit(q.gold_gutenberg_id, gids, 5)
        if i < n_reader:
            t1 = time.perf_counter()
            ans = reader.answer(q.question, build_evidence(rr.hits), q.options)
            ms += (time.perf_counter() - t1) * 1000
            res.answer, res.choice, res.evidence_ids = ans.answer, ans.choice, ans.evidence_ids
            res.tokens_in, res.tokens_out, res.cost_usd_equiv = ans.tokens_in, ans.tokens_out, ans.cost_usd_equiv
            if q.dataset == "quality":
                res.correct = ans.choice == q.gold_choice
            else:
                res.f1 = M.token_f1(ans.answer, refs)
                res.rouge_l, res.meteor = M.rouge_l(ans.answer, refs), M.meteor(ans.answer, refs)
                res.correct = res.f1 >= FAIL_F1
        res.latency_ms = ms
        # movie / unmapped rows have no library gold, so they get recall-based labels only
        res.label = label_failure(routed_ok=res.route_at5 if q.routing_eligible else None,
                                  recall_ok=bool(res.recall), answer_ok=res.correct)
        results.append(res)
    created = datetime.now(timezone.utc)
    return RunRecord(
        id=run_id or f"{created:%Y%m%dT%H%M%S}-{method.name}-{dataset}-{budget}", method=method.name,
        dataset=dataset, budget=budget, created_at=created.isoformat(timespec="seconds"), seed=seed, limit=limit,
        reader=reader_name if n_reader else None, n_questions=len(qs), n_reader=n_reader, config=cfg.model_dump(),
        metrics=aggregate(results, resamples, seed), results=results)
