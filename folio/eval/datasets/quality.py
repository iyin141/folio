"""QuALITY dev loader. Source: nyu-mll/quality v1.0.1 `QuALITY.v1.0.1.htmlstripped.dev` (2,086 Qs, 230 articles).

One JSON object per article: {article_id, source ("Gutenberg"|"Slate"|"misc-*"), title, author, url, article,
questions: [{question, question_unique_id, options[4], gold_label (1-4), writer_label, validation, difficult}]}.
Gutenberg id: articles with source "Gutenberg" carry it as `article_id` and in the aleph.gutenberg.org URL.
Slate / misc-* articles are not Gutenberg books, so they stay unmapped (gold_gutenberg_id None) and
are excluded from routing metrics; they remain usable for oracle-document accuracy.
"""
from __future__ import annotations

import json

from .models import Question, gutenberg_id_from_url, resolve

CACHE_NAME = "quality_dev.jsonl"
URL = "https://raw.githubusercontent.com/nyu-mll/quality/main/data/v1.0.1/QuALITY.v1.0.1.htmlstripped.dev"


def article_gutenberg_id(art: dict) -> int | None:
    if art.get("source") != "Gutenberg":
        return None
    gid = gutenberg_id_from_url(art.get("url"))
    if gid is None and str(art.get("article_id", "")).isdigit():
        gid = int(art["article_id"])
    return gid


def parse_article(art: dict) -> list[Question]:
    gid = article_gutenberg_id(art)
    return [Question(
        id=f"quality-{q['question_unique_id']}", dataset="quality", question=q["question"],
        options=list(q["options"]), gold_choice=q["gold_label"] - 1, gold_gutenberg_id=gid,
        doc_kind="gutenberg" if gid else "other", doc_id=str(art["article_id"])) for q in art["questions"]]


def load_quality(path) -> list[Question]:
    with open(resolve(path, CACHE_NAME), encoding="utf-8") as f:
        return [q for line in f if line.strip() for q in parse_article(json.loads(line))]


def unmapped_report(questions: list[Question]) -> dict:
    """Honest accounting of what could not be mapped to a Gutenberg id."""
    n = len(questions)
    un = sum(q.gold_gutenberg_id is None for q in questions)
    return {"questions": n, "unmapped": un, "mapped": n - un}


def download_quality(cache_dir) -> None:  # DEFERRED-VM: never called by tests
    import urllib.request
    from pathlib import Path
    out = Path(cache_dir); out.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(URL, out / CACHE_NAME)
