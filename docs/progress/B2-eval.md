# B2 eval: progress

**Phase 1: done** (loaders, metrics, bootstrap, runner, CLI, store, failure labels, leaderboard, `/eval` router, tracing adapter).
Tests: `.venv/Scripts/python -m pytest` -> **35 passed** (2 baseline + 33 new), no network, no new test dependencies.

## Files
`folio/eval/`: `datasets/{models,narrativeqa,quality}.py`, `metrics.py`, `stats.py`, `failures.py`, `runner.py`, `cli.py`,
`store.py`, `registry.py`, `fakes.py`, `leaderboard.py`, `tracing.py`, `NEEDS.md`, `results/` (git-ignored except `sample-*.json`);
`folio/api/routers/eval.py`; `tests/eval/` (+ fixtures, snapshot).

## Decisions worth knowing
- Everything is pure python: no numpy / nltk / rouge-score / WordNet. **METEOR is exact-match only** (no stems or
  synonyms), labelled "METEOR (exact)"; it reads slightly below official METEOR. ROUGE-L is LCS F with beta 1.2 (NarrativeQA's script).
- Fixtures are real-format rows pulled from the HF datasets-server (NarrativeQA: 6 rows, 2 Gutenberg books + 1 movie, story
  text cut to 200 chars) and the official QuALITY dev file (12 questions, 3 Gutenberg articles + 1 Slate, article text cut to 1,200 chars).
- QuALITY to Gutenberg: `source == "Gutenberg"` -> id from the `aleph.gutenberg.org/.../<id>-h` URL (falls back to `article_id`).
  Slate and misc-* articles stay unmapped (`gold_gutenberg_id=None`), excluded from routing, reported by `unmapped_report`.
  Measured on the full official dev file: 1,552 of 2,086 questions map (86 distinct Gutenberg ids); 534 (Slate, misc) stay unmapped. Text matching was not needed.
- NarrativeQA movie rows: `doc_kind="movie"`, no gold id, excluded from routing@k, kept for recall/answer metrics.
- One run = one (method, dataset, budget). Reader runs only at 4k and on at most min(`--reader-cap`, 200) questions (hard cap in
  `runner.READER_CAP`); retrieval metrics run on the whole (sampled) set at every budget (`--budget all`).
- Recall proxy@10 = any normalised reference answer appears (token-boundary) in the first 10 hits. For QuALITY the gold option text is the reference.
- Registry registers only fakes (`fake-oracle`, `fake-noise`, reader `fake`) plus `MethodConfig`s for the 8 plan rows. Real
  retrievers: `register_retriever("default", factory)` where `factory(questions) -> Retriever`.
- Store: `RunStore` protocol (`save_run`, `list_runs`, `get_run`), `JsonFileStore`. Router uses `get_store` dependency (env `FOLIO_EVAL_DIR`); override it for a DB store.
- `LANGFUSE_*` unset -> `trace_event` no-ops; langfuse is never imported then.

## DEFERRED-VM
```
python -c "from folio.eval.datasets.narrativeqa import download_narrativeqa as d; d('data/eval')"   # needs datasets==3.2.0; writes data/eval/narrativeqa_test.jsonl
python -c "from folio.eval.datasets.quality import download_quality as d; d('data/eval')"          # writes data/eval/quality_dev.jsonl
python -m folio.eval.cli --method <name> --dataset narrativeqa --budget all --limit 200 --reader --reader-name <claude-headless>   # real run
python -m folio.eval.cli --method <name> --dataset quality --budget 4k --limit 200 --reader
python -m folio.eval.leaderboard --md results.md --json leaderboard.json
```
Retrieval-only (no `--reader`) runs on the full sets: omit `--limit`.

## Open questions
- NarrativeQA `--limit 1000` in plan 03 vs the 200 cap in ORCHESTRATION: I followed ORCHESTRATION.
- Leaderboard takes latency/cost from the NarrativeQA run (QuALITY as fallback); say if you want them pooled.

## Needs from orchestrator
- Add the optional deps in `folio/eval/NEEDS.md` to `pyproject.toml` (`datasets==3.2.0`, `langfuse==2.60.3`, optional group).
- Oracle-book method needs a Gutenberg id -> internal `Book.id` map; the runner takes a `book_id_for` callable. Confirm where it comes from (B1 `/books`?).
- Wire `register_retriever("default", ...)` / `register_reader("claude-headless", ...)` at integration, and a DB-backed `RunStore` via `get_store` override.
- `.gitignore` is yours: results are kept out via `folio/eval/results/.gitignore` meanwhile.
