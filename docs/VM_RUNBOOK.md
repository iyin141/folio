# Folio VM runbook (Oracle VM, arm64, 4 cores, 24 GB, shared with other apps)

Ordered steps, run top to bottom. Each ends with a **Pass:** line; do not continue until it holds.
Conventions: `dc` = `docker compose` (`alias dc='docker compose'`), run from the repo root. `make` targets are in the `Makefile`.
Never paste `.env` values into chats or logs. No `ANTHROPIC_API_KEY` anywhere: the reader is `claude -p` on the logged-in subscription.

Sections marked **PLACEHOLDER** are filled by the agent that owns that part (B1 ingest, B3b embedding, B2 eval).

---

## 0. Before you touch anything

The VM runs other apps. Find what already listens on 80, 3100, 6333:

```bash
sudo ss -ltnp | grep -E ':(80|3100|6333)\b' || echo none
```

Pass: either `none`, or you picked free values for `NGINX_PORT`, `LANGFUSE_PORT`, `QDRANT_PORT` in step 2.

## 1. Clone

```bash
cd ~ && git clone https://github.com/<owner>/folio.git && cd folio
git checkout <release-branch>
```

Pass: `git status --short` prints nothing and `ls docker-compose.yml Makefile .env.example` lists all three.

## 2. Environment

```bash
cp .env.example .env && chmod 600 .env
openssl rand -hex 24      # POSTGRES_PASSWORD (url-safe); put the same value inside DATABASE_URL
openssl rand -hex 32      # LANGFUSE_NEXTAUTH_SECRET, run again for LANGFUSE_SALT
stat -c %u ~/.claude      # must print 1000 (the container user); CLAUDE_HOST_DIR=/home/ubuntu/.claude
```

Edit `.env`: `POSTGRES_PASSWORD`, `DATABASE_URL`, `LANGFUSE_NEXTAUTH_SECRET`, `LANGFUSE_SALT`, `CLAUDE_HOST_DIR`, ports from step 0,
`COMPOSE_PROJECT_NAME=folio`. Leave `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` empty until step 7.

Pass: `dc config -q` prints nothing (exit 0); `claude --version` works on the host and `~/.claude` shows a logged-in session (`claude -p "say ok"`).

## 3. Build and start

```bash
dc up -d --build          # first build on arm64 takes several minutes; add EXTRA_PIP in .env if pyproject lags (see progress file)
```

Optional profiles: `--profile web` (UI), `--profile local-llm` (ollama).

Pass: `dc ps` shows every service `healthy` (api, worker, qdrant, postgres, pgbackup, redis, langfuse, nginx) within ~3 min.

## 4. Migrate the database

```bash
make migrate              # = dc run --rm api alembic upgrade head
dc exec postgres psql -U folio -d folio -c '\dt'
```

Pass: `\dt` lists `books, chapters, eval_results, eval_runs, ingest_jobs, alembic_version`; and
`dc exec postgres psql -U folio -l | grep -c langfuse` prints `1`.

## 5. Health

```bash
curl -s http://localhost:${NGINX_PORT:-80}/api/health           # {"status":"ok"}
curl -s http://localhost:${NGINX_PORT:-80}/api/metrics | head -3 # Prometheus text
dc exec worker claude --version                                  # pinned CLI inside the worker
dc exec worker celery -A folio.worker inspect ping               # pong
```

Pass: health prints `{"status":"ok"}`, metrics starts with `# HELP`, `claude --version` prints `2.1.305`, celery answers `pong`.

## 6. Backups

The `pgbackup` sidecar writes `folio-YYYY-MM-DD.dump` and `langfuse-YYYY-MM-DD.dump` to the `pg_backups` volume at 03:00 UTC, 7 days kept.

```bash
dc exec pgbackup sh -c 'pg_dump -Fc folio > /backups/folio-manual.dump && ls -l /backups'     # on-demand check
# restore into an empty folio DB:
dc exec -T pgbackup sh -c 'pg_restore -d folio --clean --if-exists /backups/folio-manual.dump'
```

Pass: the dump file is non-empty and `pg_restore --list /backups/folio-manual.dump | head -3` prints a table of contents.

## 7. Langfuse (optional tracing)

Open `http://localhost:${LANGFUSE_PORT:-3100}` (tunnel with `ssh -L 3100:127.0.0.1:3100 vm`), create the first user and a project,
copy the project keys into `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` in `.env`, then `dc up -d api worker`.

Pass: the Langfuse UI loads and `curl -s http://127.0.0.1:${LANGFUSE_PORT:-3100}/api/public/health` returns `{"status":"OK"...}`.

---

## 8. Ingest: PLACEHOLDER (B1 fills)

Corpus download, `make ingest N=500`, then `make ingest N=5000`; exact commands and Pass lines go here.

## 9. Embedding snapshot restore: PLACEHOLDER (B3b fills the producing side; restore mechanics below are ready)

Embeddings are produced on a Kaggle/Colab GPU and exported as Qdrant snapshots named after their collection.

```bash
mkdir -p snapshots && scp chunks.snapshot books.snapshot vm:~/folio/snapshots/
make snapshot-restore     # = dc --profile restore run --rm qdrant-restore (uploads every ./snapshots/*.snapshot)
curl -s http://127.0.0.1:${QDRANT_PORT:-6333}/collections | head -c 300
```

Pass: the restore prints `restored 2 collection(s)` and the collections `chunks` and `books` appear with non-zero `points_count`
(collection names and counts to be fixed by B1/B3b).

## 10. Eval: PLACEHOLDER (B2 fills)

`make eval METHOD=... BUDGET=4k`, `make leaderboard`; reader caps (200 NarrativeQA + 200 QuALITY, 4k, `claude-haiku-5-5`) and Pass lines go here.

---

## Teardown / rollback

```bash
dc down                   # keeps volumes; add -v only to wipe data (qdrant, postgres, redis)
```

Never run `dc down -v` on a VM where `pg_backups` has the only copy you need: it lives in a named volume of the same project.
