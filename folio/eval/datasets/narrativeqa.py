"""NarrativeQA loader. Source: Hugging Face `deepmind/narrativeqa`, test split (10,557 Qs, 355 stories).

Row format (one JSON object per line in the local cache):
  document: {id, kind: "gutenberg"|"movie", url, file_size, word_count, start, end, summary: {...}, text}
  question: {text, tokens};  answers: [{text, tokens}, {text, tokens}]
The cache keeps every field except the full story text (not needed for QA eval).
"""
from __future__ import annotations

import hashlib
import json

from .models import Question, gutenberg_id_from_url, resolve

CACHE_NAME = "narrativeqa_test.jsonl"
HF_NAME = "deepmind/narrativeqa"


def parse_row(row: dict) -> Question:
    doc = row["document"]
    kind = doc.get("kind")
    gid = gutenberg_id_from_url(doc.get("url")) if kind == "gutenberg" else None
    qtext = row["question"]["text"]
    h = hashlib.sha1(f"{doc['id']}|{qtext}".encode()).hexdigest()[:10]
    return Question(
        id=f"nqa-{doc['id'][:8]}-{h}", dataset="narrativeqa", question=qtext,
        references=[a["text"] for a in row["answers"]], gold_gutenberg_id=gid,
        doc_kind=kind if kind in ("gutenberg", "movie") else "other", doc_id=doc["id"])


def load_narrativeqa(path) -> list[Question]:
    with open(resolve(path, CACHE_NAME), encoding="utf-8") as f:
        return [parse_row(json.loads(line)) for line in f if line.strip()]


def download_narrativeqa(cache_dir) -> None:  # DEFERRED-VM: never called by tests
    from pathlib import Path

    from datasets import load_dataset  # lazy: needs the `datasets` package, see NEEDS.md
    out = Path(cache_dir); out.mkdir(parents=True, exist_ok=True)
    with open(out / CACHE_NAME, "w", encoding="utf-8") as f:
        for row in load_dataset(HF_NAME, split="test"):
            row["document"]["text"] = ""   # stories are ingested via Gutenberg, not from here
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
