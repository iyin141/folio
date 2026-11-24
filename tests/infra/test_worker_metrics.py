from fastapi.testclient import TestClient

from folio.api.app import app
from folio.worker import _load_task_modules
from folio.worker import app as celery_app


def test_routes_and_tolerant_autodiscovery():
    r = celery_app.conf.task_routes
    assert r["folio.ingest.tasks.*"]["queue"] == "ingest"
    assert r["folio.retrieval.tasks.*"]["queue"] == "embed"
    assert r["folio.eval.tasks.*"]["queue"] == "eval"
    _load_task_modules()  # absent modules must not raise


def test_health_and_metrics():
    c = TestClient(app)
    assert c.get("/health").json() == {"status": "ok"}
    m = c.get("/metrics")
    assert m.status_code == 200 and "python_info" in m.text
