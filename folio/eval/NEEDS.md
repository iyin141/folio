# B2 eval: dependencies

Everything in the test path is pure python (stdlib + pydantic + fastapi, already in pyproject). No numpy,
nltk, rouge-score or WordNet data: ROUGE-L, METEOR (exact-match variant) and the bootstrap are implemented
in `folio/eval/metrics.py` and `stats.py`.

Optional, imported lazily, never needed by tests or the API process:

| Package | Pin | Used by |
|---|---|---|
| `datasets` | `==3.2.0` | `download_narrativeqa()` only (DEFERRED-VM; fetches deepmind/narrativeqa test) |
| `langfuse` | `==2.60.3` (v2 line; verify the pin resolves on the VM) | `folio/eval/tracing.py`, only when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set |

Suggest an optional dependency group, e.g. `[project.optional-dependencies] eval = ["datasets==3.2.0", "langfuse==2.60.3"]`.
