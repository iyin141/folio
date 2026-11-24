# Folio. `dc` runs inside the compose project; python targets run on the host venv or inside the api/worker container.
PY ?= $(if $(wildcard .venv/Scripts/python.exe),.venv/Scripts/python,$(if $(wildcard .venv/bin/python),.venv/bin/python,python))
DC ?= docker compose
N ?= 500
METHOD ?= hybrid_rerank_twostage
BUDGET ?= 4k

.PHONY: test lint up down migrate ingest eval leaderboard snapshot-restore

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

up:
	$(DC) up -d --build

down:
	$(DC) down

migrate:
	$(DC) run --rm api alembic upgrade head

# Commands below call modules owned by other agents (ingest, eval); they run in the worker container.
ingest:
	$(DC) run --rm worker python -m folio.ingest.cli --n $(N)

eval:
	$(DC) run --rm worker python -m folio.eval.cli --method $(METHOD) --budget $(BUDGET)

leaderboard:
	$(DC) run --rm worker python -m folio.eval.leaderboard

# Upload ./snapshots/<collection>.snapshot files into Qdrant.
snapshot-restore:
	$(DC) --profile restore run --rm qdrant-restore
