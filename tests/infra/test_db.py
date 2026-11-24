from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from folio.db import Base, Book, Chapter, EvalResult, EvalRun, IngestJob, make_engine, session_factory


def _upgrade(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 't.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    return url


def test_migration_matches_models(tmp_path, monkeypatch):
    url = _upgrade(tmp_path, monkeypatch)
    insp = inspect(make_engine(url))
    assert set(insp.get_table_names()) - {"alembic_version"} == set(Base.metadata.tables)
    for name, table in Base.metadata.tables.items():
        assert {c["name"] for c in insp.get_columns(name)} == {c.name for c in table.columns}


def test_round_trip(tmp_path, monkeypatch):
    _upgrade(tmp_path, monkeypatch)
    S = session_factory()
    with S.begin() as s:
        s.add(Book(id=1, gutenberg_id=84, title="Frankenstein", subjects=["Horror"]))
        s.add(Chapter(book_id=1, idx=0, title="Letter 1", start_char=0, end_char=99))
        s.add(IngestJob(n_requested=5))
        s.add(EvalRun(id=1, method_config={"name": "m"}, dataset="quality", n_questions=1, metrics={"acc": 1.0}))
        s.add(EvalResult(run_id=1, question_id="q1", gold=["a", "b"], prediction="a",
                         routed_book_ids=[1], evidence_ids=["E1"]))
    with S() as s:
        assert s.get(Book, 1).subjects == ["Horror"]
        assert s.get(IngestJob, 1).status == "queued"
        r = s.query(EvalResult).one()
        assert r.gold == ["a", "b"] and r.evidence_ids == ["E1"] and r.failure_label is None
        assert s.get(EvalRun, 1).created_at is not None
