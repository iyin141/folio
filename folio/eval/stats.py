"""Bootstrap confidence intervals and a paired bootstrap. Fixed seed, configurable resamples."""
from __future__ import annotations

import random

from .metrics import percentile


def _means(values: list[float], resamples: int, seed: int) -> list[float]:
    rng, n = random.Random(seed), len(values)
    return [sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)]


def bootstrap_ci(values: list[float], resamples: int = 1000, seed: int = 0, alpha: float = 0.05) -> dict:
    """Percentile bootstrap CI of the mean. `values` are per-question scores (booleans count as 0/1)."""
    if not values:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    v = [float(x) for x in values]
    m = _means(v, resamples, seed)
    return {"mean": sum(v) / len(v), "lo": percentile(m, 100 * alpha / 2),
            "hi": percentile(m, 100 * (1 - alpha / 2)), "n": len(v)}


def paired_bootstrap(a: list[float], b: list[float], resamples: int = 1000, seed: int = 0,
                     alpha: float = 0.05) -> dict:
    """Compare methods A and B scored on the SAME questions (same order). Resamples question indices
    jointly. Returns mean(a-b), its CI, and a two-sided p = 2*min(P(d<=0), P(d>=0))."""
    if len(a) != len(b):
        raise ValueError("paired bootstrap needs equal-length, aligned score lists")
    if not a:
        return {"diff": None, "lo": None, "hi": None, "p": None, "n": 0}
    d = [float(x) - float(y) for x, y in zip(a, b)]
    m = _means(d, resamples, seed)
    le = sum(x <= 0 for x in m) / resamples
    ge = sum(x >= 0 for x in m) / resamples
    return {"diff": sum(d) / len(d), "lo": percentile(m, 100 * alpha / 2),
            "hi": percentile(m, 100 * (1 - alpha / 2)), "p": min(1.0, 2 * min(le, ge)), "n": len(d)}
