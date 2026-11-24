"""Fakes for tests and the CLI smoke path. They stand in for the real Retriever/Reader (other agents)."""
from __future__ import annotations

import re
import zlib

from folio.contracts import Answer, Book, BookHit, Chunk, Evidence, Hit, MethodConfig, RetrievalResult

from .datasets.models import Question


def _chunk(book_id: int, i: int, text: str) -> Chunk:
    return Chunk(book_id=book_id, chapter_idx=0, chunk_idx=i, start_char=i * 100,
                 end_char=i * 100 + len(text), text=text)


def _answer_text(q: Question) -> str:
    if q.options is not None and q.gold_choice is not None:
        return q.options[q.gold_choice]
    return q.references[0] if q.references else ""


class FakeOracleRetriever:
    """Cheats on purpose: routes the gold book first and plants the gold answer in hit 3 of 5
    (so evidence ids need a real counter). For pipeline tests only."""

    def __init__(self, questions: list[Question]):
        self.by_q = {q.question: q for q in questions}

    def retrieve(self, question: str, method: MethodConfig, book_id: int | None = None) -> RetrievalResult:
        q = self.by_q[question]
        gid = q.gold_gutenberg_id or 0
        books = [BookHit(book=Book(id=gid, gutenberg_id=gid or None, title=f"Book {gid}"), score=1.0)]
        texts = ["filler passage one", "filler passage two", f"the story says {_answer_text(q)} here",
                 "filler passage four", "filler passage five"]
        hits = [Hit(chunk=_chunk(gid, i, t), score=1 - i / 10) for i, t in enumerate(texts)]
        ms = 1.0 + zlib.crc32(question.encode()) % 7
        return RetrievalResult(routed_books=books, hits=hits, timings_ms={"retrieve": ms})


class FakeNoiseRetriever:
    """Always wrong: routes a different book and returns passages with no answer in them."""

    def __init__(self, questions: list[Question]):
        pass

    def retrieve(self, question: str, method: MethodConfig, book_id: int | None = None) -> RetrievalResult:
        books = [BookHit(book=Book(id=9, gutenberg_id=999_999, title="Wrong"), score=1.0)]
        hits = [Hit(chunk=_chunk(9, i, f"unrelated text {i}"), score=0.5) for i in range(3)]
        return RetrievalResult(routed_books=books, hits=hits, timings_ms={"retrieve": 2.0})


class FakeReader:
    """Answers with the planted sentence's tail; picks the option with most word overlap."""

    def answer(self, question: str, evidence: list[Evidence], options: list[str] | None = None) -> Answer:
        text = " ".join(e.chunk.text for e in evidence)
        m = re.search(r"the story says (.*?) here", text)
        ans = m.group(1) if m else "not found"
        choice = None
        if options:
            words = set(text.lower().split())
            choice = max(range(len(options)), key=lambda i: len(words & set(options[i].lower().split())))
            ans = options[choice]
        return Answer(answer=ans, type="answer" if m else "not_found", evidence_ids=[e.id for e in evidence[:1]],
                      choice=choice, tokens_in=100, tokens_out=10, cost_usd_equiv=0.001)
