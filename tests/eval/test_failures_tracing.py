import pytest

from folio.eval.failures import label_failure
from folio.eval.tracing import trace_event


@pytest.mark.parametrize("routed,recall,ok,want", [
    (False, False, False, "wrong book"), (False, True, True, None),     # a correct answer is never a failure
    (True, False, False, "right book, wrong passage"), (True, True, False, "reader error"),
    (None, False, None, "right book, wrong passage"), (True, True, None, None),
])
def test_label_failure(routed, recall, ok, want):
    assert label_failure(routed_ok=routed, recall_ok=recall, answer_ok=ok) == want


def test_tracing_noop_without_env(monkeypatch):
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    assert trace_event("x", metadata={}) is None
