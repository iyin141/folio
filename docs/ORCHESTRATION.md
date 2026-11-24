# Folio orchestration contract (read before any edit)

Several agents build Folio in parallel, one branch each. The orchestrator
reviews every phase and does every merge. This file keeps the branches from
colliding. If a rule here blocks you, stop and report it; do not work around it.

Plans: `docs/plans/03_FOLIO_BOOKS_RAG_BACKEND.md` (backend),
`docs/plans/04_FOLIO_BOOKS_RAG_UI.md` (UI), `docs/plans/00_RESOURCES_AND_SKILLS.md`
(libraries). Where this file and a plan disagree, **this file wins**.

## User decisions that override the plans

- **Reader LLM = Claude headless** (`claude -p` on the logged-in subscription). No
  `ANTHROPIC_API_KEY` anywhere. The Claude API reader and Ollama are optional
  ablations behind the same `Reader` interface; Ollama is a compose profile only.
- **Reader eval cap:** 200 NarrativeQA + 200 QuALITY questions per method, **4k
  budget only**, reader `claude-haiku-5-5`. Retrieval metrics (routing@k, recall
  proxy@k) need no LLM and run on the full sets, all budgets.
- **Book synopses** for routing: a small local model (e.g. Qwen2.5-3B-Instruct)
  on a Kaggle/Colab GPU in the same notebook as the embedding run. Never Claude.
  A no-LLM variant (title + author + subjects + opening text) is an ablation.
- **Tracing = Langfuse v2** (Postgres only; own DB `langfuse` in the compose
  Postgres). Tracing must be optional: no Langfuse env = no-op, tests never need it.
- **Postgres runs in compose** (`pgvector/pgvector:0.8.0-pg17` image is fine, plain
  postgres also fine), with a backup sidecar. Not Neon.
- **Where work runs:** this PC = code + tests + a 20-50 book smoke corpus. The
  Oracle VM (arm64, 4 cores, 24 GB, shared with other apps) = full corpus, dataset
  downloads, real evals. Every image builds for `linux/arm64`.
- The reader package lives at `folio/reader/claude_headless/` (plan says
  `packages/reader/claude_headless/`; same thing, flat layout).
- `$ per 1k questions` = the CLI's `total_cost_usd`, labelled "equivalent cost".

## Branches and worktrees

| Agent | Branch | Worktree | Scope |
|---|---|---|---|
| orchestrator | `folio/integration` | `folio/` (main checkout) | scaffold, shared files, merges |
| B0 infra | `folio/infra` | `folio/wt/infra` | compose, Dockerfiles, DB schema + migrations, Celery app, CI, Makefile, VM runbook |
| B2 eval | `folio/eval` | `folio/wt/eval` | dataset loaders, metrics, bootstrap CIs, eval runner, leaderboard |
| B1 ingest | `folio/ingest` | `folio/wt/ingest` | Gutenberg ingest, chapters, chunking, Qdrant indexes, `/search`, `/books` |
| B3a reader | `folio/reader` | `folio/wt/reader` | Claude headless reader, LangGraph ask graph, `/ask` SSE, MCP server |
| B3b retrieval | `folio/retrieval` | `folio/wt/retrieval` | routing, rerank, DOS, RAPTOR, budgets, `/galaxy` |
| U1 UI | `folio/ui` | `folio/wt/ui` | `web/` (plan 04) |

Waves: B0+B2, then B1+B3a, then B3b+U1. All branches start from
`folio/integration`. Work only inside your own worktree. Never `git checkout`
another branch, never merge, never push, never touch another worktree.

## File ownership

| Paths | Owner |
|---|---|
| `docker-compose*.yml`, `docker/`, `Dockerfile*`, `.dockerignore`, `deploy/`, `Makefile`, `.github/`, `.env.example`, `folio/db/**`, `migrations/`, `folio/worker.py`, `folio/api/routers/health.py`, `docs/VM_RUNBOOK.md`, `tests/infra/**` | B0 |
| `folio/eval/**`, `folio/api/routers/eval.py`, `tests/eval/**`, `scripts/eval/**` | B2 |
| `folio/ingest/**`, `folio/api/routers/books.py`, `folio/api/routers/search.py`, `tests/ingest/**`, `scripts/ingest/**` | B1 |
| `folio/reader/**`, `folio/api/routers/ask.py`, `folio/mcp_server/**`, `tests/reader/**` | B3a |
| `folio/retrieval/**`, `folio/api/routers/galaxy.py`, `tests/retrieval/**`, `notebooks/**` | B3b |
| `web/**` | U1 |
| `pyproject.toml`, `folio/contracts.py`, `folio/api/app.py`, `README.md`, `.gitignore`, `.gitattributes`, this file, `docs/plans/**` | orchestrator only |
| `docs/progress/<your-agent>.md`, `folio/<your-area>/NEEDS.md` | that agent |

Everything not listed is read-only. Need a change outside your paths (a new
dependency, a contract field, a shared helper)? Write it under "Needs from
orchestrator" in your progress file and carry on with what you can (a local
subclass or adapter in your own folder is fine meanwhile).

**New dependencies:** list them pinned in `folio/<your-area>/NEEDS.md` (B0: in
your progress file). Install them into your own venv. The orchestrator moves
them into `pyproject.toml` at merge. Heavy ML deps (torch, sentence-transformers,
umap) go in an optional group and are imported lazily inside functions, never at
module import time of anything the API process loads.

## Already wired (do not re-wire)

- `folio/contracts.py`: `Book`, `Chapter`, `Chunk`, `Hit`, `BookHit`, `Evidence`,
  `Answer`, `MethodConfig`, `RetrievalResult`, `Retriever`/`Reader` protocols,
  the `/ask` SSE event models and `AskRequest`. Code against these.
  - `Retriever.retrieve(question, method, book_id=None) -> RetrievalResult`
  - `Reader.answer(question, evidence, options=None) -> Answer`
  - Evidence ids are `E1..En`, assigned **by a counter in prompt order**. (F1 had
    a bug where every hit got `E1`; test with fakes returning several hits.)
- **`Book.id` = the Gutenberg id** (every library book comes from Gutenberg). So
  gold Gutenberg ids from NarrativeQA/QuALITY map to `Book.id` by identity; no
  lookup table.
- `folio/api/app.py` includes every router: `health` (no prefix), `books`
  (prefix `/books`), `search`, `ask`, `eval` (prefix `/eval`), `galaxy`. Fill your
  own router module only.
- Tests: `tests/<area>/`, `--import-mode=importlib` (same test file names in two
  folders are fine). Run from the worktree root: `.venv/Scripts/python -m pytest`.

## Runtime isolation

- Own venv per worktree: `uv venv .venv` then
  `uv pip install --python .venv -e . pytest==8.3.5` plus your NEEDS. The network
  here corrupts downloads: set `UV_HTTP_RETRIES=10` and retry the command; it
  usually succeeds on the 2nd-4th try.
- Ports and compose project names (only if you need a server):
  B0 8100 / `folio-infra`, B2 8101 / `folio-eval`, B1 8102 + Qdrant 6340 /
  `folio-ingest`, B3a 8103 / `folio-reader`, B3b 8104 + Qdrant 6341 /
  `folio-retrieval`, U1 3010. Taken on this PC, never use: 80, 3000, 3002, 5433,
  8000-8030, 12000-12500.
- Git Bash: prefix `docker compose exec` with `MSYS_NO_PATHCONV=1`.
- Never `source` a `.env`; load with python-dotenv inside a process.
- Data downloads on this PC: at most the small fixtures you need (a few
  Gutenberg books, a few dataset rows). Commit small fixtures under
  `tests/<area>/fixtures/`. Anything bigger is `DEFERRED-VM`.

## Hard rules

- No live network calls in tests (Gutenberg, Hugging Face, `claude`, Qdrant
  cloud). Use fixtures, fakes, an in-memory Qdrant (`QdrantClient(":memory:")`)
  or a skip marker for integration tests that need a running service.
- Retrieval methods are configs (`MethodConfig`), not code forks.
- Methods are compared at equal token budgets only.
- No secrets in the repo. This repo is **public**.
- Never name a folder after a dependency (`mcp/`, `qdrant/` ...): it shadows the
  package. Use `mcp_server/` etc.
- Keep ad-hoc scripts out of `test_*.py` names.
- Torch/model code never loads in the web process at import.

## LLM calls: Claude headless

No API key. The `claude` CLI runs headless on the subscription, as a subprocess.
Reference (read, reimplement generic parts, copy nothing domain-specific):
`C:/Users/iyino/Videos/F1-project/wt/integration/backend/api/assistant/llm.py`
(most complete: streaming, effort, safe mode, error classes, `FakeRunner`) and
`C:/Users/iyino/Videos/stock-index-project/services/rag-pipeline/rag_pipeline/claude_headless.py`
+ `langchain_adapter.py`.

- argv: `claude -p --output-format json --json-schema '<inline>' --model <full id>
  --append-system-prompt '<text>' --tools "" --no-session-persistence
  --disable-slash-commands --safe-mode [--effort low]`; prompt on stdin; cwd an
  empty temp dir. Streaming: `--output-format stream-json --verbose
  --include-partial-messages`. `structured_output` holds the parsed JSON.
- Never `--bare`. On Windows resolve the real `claude.exe` behind the npm shim.
- Errors: rate limit (backoff), auth expired (never retry), bad JSON (retry
  once), timeout (retry once).
- Verify flags against `claude --help` (CLI 2.1.305 here) before relying on them.
- In Docker: image installs the CLI via npm (pinned), host `~/.claude` mounted,
  `CLAUDE_CONFIG_DIR` set. Only the container that calls Claude needs it.
- **Live calls cost the user's subscription: at most 5 per phase.** Tests use a
  fake runner.

## Deferred: needs the Oracle VM

Full corpus download, embedding 500-5,000 books, synopsis generation, dataset
downloads beyond fixtures, real eval runs, arm64 runtime checks. Build the code
paths and tests, write the exact commands into your progress file under
`DEFERRED-VM` (B0 collects them into `docs/VM_RUNBOOK.md`), and move on.

## Phase protocol

1. Do exactly one phase (the orchestrator names it), then stop.
2. Commit on your branch in small commits. **No Claude co-author or attribution
   lines in commit messages.**
3. Update `docs/progress/<agent>.md`: phase, status, commits, files touched,
   test result (counts), DEFERRED-VM items, open questions, "Needs from orchestrator".
4. Your final message is the report: the same content, short.
5. Before the next phase, the orchestrator tells you to `git rebase folio/integration`.

Test baseline on `folio/integration` at scaffold: 2 passed. Your phase must not
add failures.
