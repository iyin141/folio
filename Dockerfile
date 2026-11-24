# syntax=docker/dockerfile:1
# Folio app image. Targets: api, worker. Builds for linux/amd64 and linux/arm64, no apt.
# Offline/flaky network: put pre-downloaded wheels in ./wheelhouse/ (git-ignored, optional);
# pip uses it first via --find-links.

FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /src
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# the glob copes with wheelhouse/ being absent (.dockerignore always matches, so COPY never fails)
COPY .dockerignore wheelhouse* /wheelhouse/
# deps first (cache layer), then the package itself
COPY pyproject.toml README.md ./
COPY folio/__init__.py folio/__init__.py
# EXTRA_PIP: pinned packages not yet in pyproject.toml (empty once the orchestrator merges NEEDS)
ARG EXTRA_PIP=""
RUN pip install --retries 10 --find-links /wheelhouse . $EXTRA_PIP
COPY folio folio
RUN pip install --retries 10 --find-links /wheelhouse --no-deps .

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH=/opt/venv/bin:$PATH HOME=/home/folio
RUN useradd --uid 1000 --create-home --home-dir /home/folio folio
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY alembic.ini ./
COPY migrations migrations
USER 1000:1000

FROM runtime AS api
EXPOSE 8000
CMD ["uvicorn", "folio.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# The worker is the only container that calls Claude (headless `claude -p`).
# Node is copied from the official image (apt-free); the CLI version is pinned (host CLI here: 2.1.305).
FROM runtime AS worker
USER root
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:22-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm config set fetch-retries 10 \
 && npm install -g @anthropic-ai/claude-code@2.1.305 \
 && claude --version
USER 1000:1000
ENV CLAUDE_CONFIG_DIR=/home/folio/.claude
CMD ["celery", "-A", "folio.worker", "worker", "-Q", "ingest,embed,eval", "--concurrency", "2", "--loglevel", "INFO"]
