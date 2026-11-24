"""Failure labelling for the failure-case gallery."""
from __future__ import annotations

WRONG_BOOK = "wrong book"
WRONG_PASSAGE = "right book, wrong passage"
READER_ERROR = "reader error"


def label_failure(*, routed_ok: bool | None, recall_ok: bool, answer_ok: bool | None) -> str | None:
    """routed_ok: gold book among routed books (None = no library gold, e.g. movie script).
    recall_ok: recall proxy at the run's k. answer_ok: answer judged correct (None = reader not run).
    Returns None for a success (or for an unlabellable row)."""
    if answer_ok:
        return None
    if routed_ok is False:
        return WRONG_BOOK
    if not recall_ok:
        return WRONG_PASSAGE
    return READER_ERROR if answer_ok is False else None
