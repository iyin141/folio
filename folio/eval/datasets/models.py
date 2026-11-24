"""Normalised question model shared by every dataset loader."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

DocKind = Literal["gutenberg", "movie", "other"]


class Question(BaseModel):
    id: str
    dataset: Literal["narrativeqa", "quality"]
    question: str
    references: list[str] = Field(default_factory=list)   # NarrativeQA: two free-text answers
    options: list[str] | None = None                      # QuALITY: four options
    gold_choice: int | None = None                        # QuALITY: 0-based index of the gold option
    gold_gutenberg_id: int | None = None                  # None = not mappable to a library book
    doc_kind: DocKind = "gutenberg"
    doc_id: str | None = None                             # dataset's own document / article id

    @property
    def routing_eligible(self) -> bool:
        """Counts toward library routing metrics (movie scripts and unmapped articles do not)."""
        return self.gold_gutenberg_id is not None and self.doc_kind != "movie"


_GUT = (re.compile(r"gutenberg\.org/(?:ebooks|files|cache/epub)/(\d+)"), re.compile(r"/(\d+)/+\1-h"))


def gutenberg_id_from_url(url: str | None) -> int | None:
    for rx in _GUT:
        m = rx.search(url or "")
        if m:
            return int(m.group(1))
    return None


def resolve(path, default_name: str):
    """A loader accepts a file, or a cache dir holding the default file name."""
    from pathlib import Path
    p = Path(path)
    return p / default_name if p.is_dir() else p
