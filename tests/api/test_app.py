from fastapi.testclient import TestClient

from folio.api.app import create_app
from folio.contracts import MethodConfig, Reader, Retriever


def test_health():
    assert TestClient(create_app()).get("/health").json() == {"status": "ok"}


def test_contract_defaults():
    m = MethodConfig(name="hybrid")
    assert (m.fusion, m.budget, m.rerank, m.two_stage) == ("rrf", "4k", False, False)
    assert Retriever and Reader
