"""Optional Langfuse v2 adapter. No LANGFUSE_* env (or no package) = silent no-op."""
from __future__ import annotations

import os


def _client():
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        from langfuse import Langfuse  # v2 API; lazy so tests/API never need it
        return Langfuse()
    except Exception:
        return None


def trace_event(name: str, **fields) -> None:
    c = _client()
    if c is None:
        return
    try:
        c.trace(name=name, **fields)
        c.flush()
    except Exception:
        pass   # tracing must never break an eval
