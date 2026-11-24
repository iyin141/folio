# B0 infra: progress

**Phase:** 1 (schema, worker, metrics, Docker, Makefile, CI, runbook skeleton)
**Status:** done, pending orchestrator review. Branch `folio/infra`.

## Files touched
- DB: `folio/db/{__init__,models,session}.py`, `alembic.ini`, `migrations/{env.py,script.py.mako,versions/0001_initial.py}`
- `folio/worker.py` (Celery: queues ingest/embed/eval, routes by module, tolerant autodiscovery; broker `REDIS_URL`)
- `folio/api/routers/health.py` (`/health` unchanged, `/metrics` Prometheus)
- `Dockerfile` (targets `api`, `worker`), `.dockerignore`, `docker-compose.yml`, `docker/{nginx,postgres,web}/`, `.env.example`
- `Makefile`, `.github/workflows/ci.yml`, `docs/VM_RUNBOOK.md`
- `tests/infra/{test_db.py,test_worker_metrics.py}`

## Tests
`pytest`: 6 passed (2 scaffold + 4 new: migration matches models on SQLite, model round-trip, route table + tolerant autodiscovery, `/health` + `/metrics`). `ruff check .` clean.

## Verification
- `docker compose config -q` valid with `.env.example` values, also with `--profile web --profile local-llm --profile restore`.
- api image build: see "Docker build" below.

## Design notes
- Schema: `books` (plan fields + ingest_status, sha256), `chapters` (PK book_id+idx), `ingest_jobs`, `eval_runs`, `eval_results` (run_id, question_id, gold, prediction, metrics, routed_book_ids, evidence_ids, latency_ms, tokens_in/out, failure_label). JSON is JSONB on Postgres. Session factory: `folio.db.session_factory()` reads `DATABASE_URL`.
- Dockerfile installs `pip install .` from pyproject. Until the orchestrator merges the NEEDS below, pass them with `EXTRA_PIP` (build arg, wired in compose from `.env`). Empty once merged.
- Worker image: node copied from `node:22-slim` (apt-free), `@anthropic-ai/claude-code@2.1.305` pinned (the host CLI version), runs as uid 1000, `~/.claude` mounted at `/home/folio/.claude`, `CLAUDE_CONFIG_DIR` set. API image has no CLI.
- Qdrant snapshot restore: `make snapshot-restore` uploads every `./snapshots/<collection>.snapshot` (profile `restore`). Not on boot automatically (an upload replaces a collection; explicit is safer).
- nginx resolves `api`/`web` at request time, so it boots without the `web` profile; `/` returns a 503 text until U1's web service is up.
- Host ports: nginx `NGINX_PORT`, qdrant and langfuse bound to 127.0.0.1.

## DEFERRED-VM
- arm64 image build and runtime (CI builds arm64 under qemu; not run here).
- Worker image build (needs npm registry fetch of the CLI; not built locally) and `claude --version` in container.
- Full `dc up` incl. langfuse v2 (`langfuse/langfuse:2.95.11`, tag unverified against the registry), qdrant `v1.13.6`, ollama `0.5.7`, `curlimages/curl:8.11.1` pulls and health, pgbackup nightly run, snapshot restore. Commands are in `docs/VM_RUNBOOK.md`.

## Open questions
- Image tags above were chosen from memory; confirm they exist on first VM pull.
- Runbook step 1 has `<owner>`/`<release-branch>` placeholders (repo is public; orchestrator to fill).

## Needs from orchestrator
Add to `pyproject.toml` `dependencies`:
```
sqlalchemy==2.0.40
alembic==1.15.2
psycopg[binary]==3.2.6
celery==5.5.2
redis==5.2.1
prometheus-client==0.21.1
```
(`ruff==0.11.8` and `pytest==8.3.5` are already in the dev group.) CI installs these explicitly until then.
Also: `.gitignore` should include `snapshots/`, `backups/`, `wheelhouse/` (already), `.env` (already); add `snapshots/` and `backups/`.
