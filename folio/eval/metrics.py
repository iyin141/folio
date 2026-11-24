"""Metrics. Pure python, no dependencies, no network.

Normalisation is the SQuAD / NarrativeQA one: lowercase, drop punctuation, drop articles (a, an, the),
collapse whitespace. All text metrics take max over the reference answers.
"""
from __future__ import annotations

import re
import string
from collections import Counter

_PUNCT = set(string.punctuation)


def normalize(text: str) -> str:
    text = "".join(c for c in text.lower() if c not in _PUNCT)
    return " ".join(re.sub(r"\b(a|an|the)\b", " ", text).split())


def _toks(text: str) -> list[str]:
    return normalize(text).split()


def _f1(pred: list[str], ref: list[str]) -> float:
    common = sum((Counter(pred) & Counter(ref)).values())
    if not pred or not ref:
        return float(pred == ref)
    if common == 0:
        return 0.0
    p, r = common / len(pred), common / len(ref)
    return 2 * p * r / (p + r)


def token_f1(pred: str, refs: list[str]) -> float:
    return max((_f1(_toks(pred), _toks(r)) for r in refs), default=0.0)


def _lcs(a: list[str], b: list[str]) -> int:
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


ROUGE_BETA = 1.2   # as in the NarrativeQA / coco-caption ROUGE-L


def rouge_l(pred: str, refs: list[str]) -> float:
    """ROUGE-L F (LCS based, beta=1.2), per reference, max over references."""
    best, p_t = 0.0, _toks(pred)
    for ref in refs:
        r_t = _toks(ref)
        lcs = _lcs(p_t, r_t)
        if lcs == 0:
            continue
        p, r = lcs / len(p_t), lcs / len(r_t)
        best = max(best, (1 + ROUGE_BETA**2) * p * r / (r + ROUGE_BETA**2 * p))
    return best


def _meteor_one(hyp: list[str], ref: list[str]) -> float:
    """METEOR with EXACT matching only (no stemming / WordNet synonyms), so it needs no data files.
    Fmean = 10PR/(R+9P); penalty = 0.5*(chunks/matches)^3. Scores run a little below the official
    Java/NLTK METEOR, which also credits stems and synonyms; report it as 'METEOR (exact)'."""
    used, align = set(), []
    for i, w in enumerate(hyp):
        cands = [j for j, v in enumerate(ref) if v == w and j not in used]
        if not cands:
            continue
        prev = align[-1][1] if align and align[-1][0] == i - 1 else None
        j = prev + 1 if prev is not None and prev + 1 in cands else cands[0]
        used.add(j); align.append((i, j))
    m = len(align)
    if m == 0:
        return 0.0
    p, r = m / len(hyp), m / len(ref)
    chunks = 1 + sum(not (b[0] == a[0] + 1 and b[1] == a[1] + 1) for a, b in zip(align, align[1:]))
    return (10 * p * r / (r + 9 * p)) * (1 - 0.5 * (chunks / m) ** 3)


def meteor(pred: str, refs: list[str]) -> float:
    return max((_meteor_one(_toks(pred), _toks(r)) for r in refs), default=0.0)


def quality_accuracy(choices: list[int | None], golds: list[int]) -> float:
    return sum(c == g for c, g in zip(choices, golds)) / len(golds) if golds else 0.0


def routing_hit(gold_gid: int | None, routed_gids: list[int | None], k: int) -> bool:
    return gold_gid is not None and gold_gid in routed_gids[:k]


def recall_proxy(refs: list[str], passages: list[str], k: int | None = None) -> bool:
    """PROXY, not gold-passage recall: True if any normalised reference answer occurs (on token
    boundaries) in the normalised text of the first k retrieved passages. NarrativeQA has no gold
    passages, so this over-counts short common answers and under-counts paraphrased ones."""
    text = " " + " ".join(normalize(p) for p in passages[:k]) + " "
    return any(n and f" {n} " in text for n in map(normalize, refs))


def percentile(values: list[float], q: float) -> float:
    """Linear interpolation between closest ranks (numpy default). q in [0, 100]."""
    if not values:
        return 0.0
    s = sorted(values)
    pos = (len(s) - 1) * q / 100
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def latency_stats(ms: list[float]) -> dict[str, float]:
    return {"p50": percentile(ms, 50), "p95": percentile(ms, 95)}


def per_1k(total: float, n_questions: int) -> float:
    return total / n_questions * 1000 if n_questions else 0.0
