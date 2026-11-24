"""Celery app. Queues: ingest, embed, eval, routed by task module. Task modules belong to other agents;
missing ones are skipped so the worker boots at any point of the build."""
from __future__ import annotations

import importlib
import os

from celery import Celery

BROKER = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
TASK_MODULES = ("folio.ingest.tasks", "folio.retrieval.tasks", "folio.eval.tasks")

app = Celery("folio", broker=BROKER, backend=os.environ.get("CELERY_RESULT_BACKEND", BROKER))
app.conf.task_routes = {
    "folio.ingest.tasks.*": {"queue": "ingest"},
    "folio.retrieval.tasks.*": {"queue": "embed"},
    "folio.eval.tasks.*": {"queue": "eval"},
}
app.conf.task_default_queue = "ingest"
app.conf.worker_prefetch_multiplier = 1
app.conf.task_acks_late = True


def _load_task_modules(_sender=None, **_kw) -> list[str]:
    loaded = []
    for name in TASK_MODULES:
        try:
            importlib.import_module(name)
            loaded.append(name)
        except ModuleNotFoundError as e:
            if e.name is None or not name.startswith(e.name):
                raise  # the module exists but one of its own imports is broken: surface it
    return loaded


app.on_after_configure.connect(_load_task_modules, weak=False)
