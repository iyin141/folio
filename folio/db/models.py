"""Postgres schema (plan 03 Data model). JSON columns are JSONB on Postgres, plain JSON elsewhere (SQLite tests)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Book(Base):
    __tablename__ = "books"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gutenberg_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column(Integer)
    subjects: Mapped[list] = mapped_column(Json, default=list)
    n_tokens: Mapped[int] = mapped_column(Integer, default=0)
    n_chunks: Mapped[int] = mapped_column(Integer, default=0)
    ingest_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|ingested|failed
    sha256: Mapped[str | None] = mapped_column(String(64))


class Chapter(Base):
    __tablename__ = "chapters"
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), primary_key=True)
    idx: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    start_char: Mapped[int] = mapped_column(Integer)
    end_char: Mapped[int] = mapped_column(Integer)


class IngestJob(Base):
    __tablename__ = "ingest_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), default="ingest")  # ingest|embed|snapshot
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed
    n_requested: Mapped[int] = mapped_column(Integer, default=0)
    n_done: Mapped[int] = mapped_column(Integer, default=0)
    params: Mapped[dict] = mapped_column(Json, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    method_config: Mapped[dict] = mapped_column(Json)
    dataset: Mapped[str] = mapped_column(String(64))
    n_questions: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[dict] = mapped_column(Json, default=dict)
    git_sha: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class EvalResult(Base):
    __tablename__ = "eval_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"))
    question_id: Mapped[str] = mapped_column(String(128))
    gold: Mapped[object] = mapped_column(Json)
    prediction: Mapped[object | None] = mapped_column(Json)
    metrics: Mapped[dict] = mapped_column(Json, default=dict)
    routed_book_ids: Mapped[list] = mapped_column(Json, default=list)
    evidence_ids: Mapped[list] = mapped_column(Json, default=list)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    failure_label: Mapped[str | None] = mapped_column(String(32))  # wrong_book|wrong_passage|reader_error
    __table_args__ = (Index("ix_eval_results_run_question", "run_id", "question_id"),)
