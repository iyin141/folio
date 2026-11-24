"""Name -> MethodConfig / Retriever factory / Reader factory. Only fakes are registered here;
the integration wiring calls register_* with real implementations."""
from __future__ import annotations

from collections.abc import Callable

from folio.contracts import MethodConfig, Reader, Retriever

from .datasets.models import Question
from .fakes import FakeNoiseRetriever, FakeOracleRetriever, FakeReader

METHODS: dict[str, MethodConfig] = {m.name: m for m in [
    MethodConfig(name="bm25", dense=False, fusion="none"),
    MethodConfig(name="dense", sparse=False, fusion="none"),
    MethodConfig(name="hybrid"),
    MethodConfig(name="hybrid-rerank", rerank=True),
    MethodConfig(name="two-stage", rerank=True, two_stage=True),
    MethodConfig(name="two-stage-dos", rerank=True, two_stage=True, dos_order=True),
    MethodConfig(name="raptor", rerank=True, two_stage=True, raptor=True),
    MethodConfig(name="oracle-book", rerank=True, oracle_book=True),
]}
RETRIEVERS: dict[str, Callable[[list[Question]], Retriever]] = {
    "fake-oracle": FakeOracleRetriever, "fake-noise": FakeNoiseRetriever}
READERS: dict[str, Callable[[], Reader]] = {"fake": FakeReader}


def register_retriever(name: str, factory: Callable[[list[Question]], Retriever]) -> None:
    """A factory registered under "default" serves every method name that has no own entry."""
    RETRIEVERS[name] = factory


def register_reader(name: str, factory: Callable[[], Reader]) -> None:
    READERS[name] = factory


def get_method(name: str) -> MethodConfig:
    return METHODS.get(name) or MethodConfig(name=name)


def get_retriever(name: str, questions: list[Question]) -> Retriever:
    factory = RETRIEVERS.get(name) or RETRIEVERS.get("default")
    if factory is None:
        raise KeyError(f"no retriever registered for {name!r}; known: {sorted(RETRIEVERS)}")
    return factory(questions)


def get_reader(name: str) -> Reader:
    if name not in READERS:
        raise KeyError(f"no reader registered for {name!r}; known: {sorted(READERS)}")
    return READERS[name]()
