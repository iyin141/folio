"""Shared types and interfaces. Every agent codes against these; only the orchestrator edits this file.

Need a field or a new type? Write it under "Needs from orchestrator" in your progress file.
"""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Budget = Literal["2k", "4k", "8k"]
BUDGET_TOKENS: dict[str, int] = {"2k": 2000, "4k": 4000, "8k": 8000}


class Book(BaseModel):
    id: int
    gutenberg_id: int | None = None
    title: str
    author: str | None = None
    year: int | None = None
    subjects: list[str] = Field(default_factory=list)
    n_tokens: int = 0
    n_chunks: int = 0


class Chapter(BaseModel):
    book_id: int
    idx: int
    title: str | None = None
    start_char: int
    end_char: int


class Chunk(BaseModel):
    """One passage. Qdrant `chunks` payload carries exactly these fields."""
    book_id: int
    chapter_idx: int
    chunk_idx: int
    start_char: int
    end_char: int
    text: str


class Hit(BaseModel):
    """A retrieved chunk with every score the pipeline produced (None = stage not run)."""
    chunk: Chunk
    score: float
    bm25: float | None = None
    dense: float | None = None
    fused: float | None = None
    rerank: float | None = None


class BookHit(BaseModel):
    book: Book
    score: float


class Evidence(BaseModel):
    """A numbered evidence unit handed to the reader. ids are E1..En, assigned by a counter, in prompt order."""
    id: str
    chunk: Chunk


class Answer(BaseModel):
    answer: str
    type: Literal["answer", "not_found"] = "answer"
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    choice: int | None = None          # QuALITY: index of the chosen option
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd_equiv: float = 0.0        # CLI-reported total_cost_usd; the subscription is not billed per call


class MethodConfig(BaseModel):
    """A retrieval method is a config, not a code fork. `name` is the leaderboard row id."""
    name: str
    sparse: bool = True
    dense: bool = True
    fusion: Literal["rrf", "none"] = "rrf"
    rerank: bool = False
    two_stage: bool = False
    route_top_b: int = 3
    dos_order: bool = False
    raptor: bool = False
    oracle_book: bool = False
    budget: Budget = "4k"
    top_k: int = 10


class RetrievalResult(BaseModel):
    routed_books: list[BookHit] = Field(default_factory=list)
    hits: list[Hit] = Field(default_factory=list)   # final order, already trimmed to the token budget
    timings_ms: dict[str, float] = Field(default_factory=dict)


@runtime_checkable
class Retriever(Protocol):
    def retrieve(self, question: str, method: MethodConfig, book_id: int | None = None) -> RetrievalResult: ...


@runtime_checkable
class Reader(Protocol):
    def answer(self, question: str, evidence: list[Evidence], options: list[str] | None = None) -> Answer: ...


# --- /ask Server-Sent Events. `event:` name = the `event` field; `data:` = the model as JSON. ---

class RoutingEvent(BaseModel):
    event: Literal["routing"] = "routing"
    books: list[BookHit]
    chosen: list[int]


class RetrievalEvent(BaseModel):
    event: Literal["retrieval"] = "retrieval"
    hits: list[Hit]


class RerankEvent(BaseModel):
    event: Literal["rerank"] = "rerank"
    hits: list[Hit]


class TokenEvent(BaseModel):
    event: Literal["token"] = "token"
    text: str


class CitationsEvent(BaseModel):
    event: Literal["citations"] = "citations"
    answer: Answer
    evidence: list[Evidence]


class ErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    message: str


AskEvent = RoutingEvent | RetrievalEvent | RerankEvent | TokenEvent | CitationsEvent | ErrorEvent


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    book_id: int | None = None
    method: str | None = None
    budget: Budget | None = None
