# Build Prompt 3 of 6: Folio, Library-Scale Book Retrieval (Backend)

## Role and goal

You are an ML and backend engineer building **Folio**, a question-answering system over **thousands of full-length books**, with **measured retrieval accuracy**.

The research gap Folio targets: published long-document RAG benchmarks (NarrativeQA, QuALITY) retrieve *inside one given document*, and none measure retrieval across a whole library. Folio mixes the benchmark books into a library of about 5,000 Project Gutenberg books. The system must first find the right book, then the right passages, then answer. It publishes a leaderboard of retrieval methods.

Load these skills first (see `00_RESOURCES_AND_SKILLS.md`): `claude-api`, `mcp-builder`, `archify`.

## Required first step: reuse the existing RAG pipeline (Claude headless)

Before writing any retrieval-to-answer or reader code, **read the RAG pipeline folder in `C:\Users\iyino\Videos\stock-index-project`** (on the Linux server, wherever that project is checked out). It already integrates RAG with **Claude running in headless mode**. This project copies and adapts that integration rather than building a new one.

1. Read the whole RAG pipeline folder:
   - how Claude headless is invoked (command, flags, output format);
   - how retrieved context is passed in;
   - how answers and citations are parsed;
   - how errors, timeouts and retries are handled;
   - which configuration and environment variables it uses.
2. Copy it into this repo as `packages/reader/claude_headless/` and keep its structure. Change only what this project needs:
   - the input becomes the numbered evidence units from the retrieval pipeline;
   - the output becomes the structured answer JSON defined below (`answer`, `type`, `evidence_ids`, `confidence`).
3. Make it the **default reader**. Keep the reader behind a small interface (`Reader.answer(question, evidence) -> Answer`), so the Claude API reader and a local Ollama reader remain ablations.
4. **Do not copy anything domain-specific** from that project: no stock, market or ticker names, prompts, data or docs. This repo is public. Copy only the generic pipeline code.
5. Record in the README which parts came from the existing pipeline and what changed.

## Headline deliverable

A results table, reproducible from one command (`make eval`), comparing:

| Method | Book routing @1/@5 | Passage recall proxy @10 | NarrativeQA F1 / ROUGE-L | QuALITY acc. | p50 latency | $ per 1k questions |
|---|---|---|---|---|---|---|
| BM25 (passages only) | | | | | | |
| Dense (bge-small) | | | | | | |
| Hybrid (BM25 + dense, RRF) | | | | | | |
| Hybrid + cross-encoder rerank | | | | | | |
| Two-stage: book routing, then hybrid + rerank | | | | | | |
| Two-stage + DOS ordering (passages re-sorted into reading order) | | | | | | |
| RAPTOR (tree summaries, collapsed tree) on routed books | | | | | | |
| Oracle book (upper bound: correct book given) | | | | | | |

Report honestly, even if simple methods win. The literature suggests they often do (Laitenberger et al. 2025: DOS RAG at least matched RAPTOR and ReadAgent).

## Stack

| Layer | Choice |
|---|---|
| API | **FastAPI** + Pydantic v2, async, uvicorn |
| Pipelines and agent | **LangChain** (loaders, splitters, retrievers) + **LangGraph** (the ask agent with routing, retrieval and answering steps) |
| Vector + sparse search | **Qdrant**: dense vectors with scalar or binary quantization, plus a sparse BM25 vector per chunk, in one collection, using Qdrant's hybrid query with RRF fusion |
| Metadata | Postgres (books, chapters, ingestion jobs, eval runs) |
| Queue | Celery (Redis broker) for ingestion, embedding and evals |
| Embeddings | `bge-small-en-v1.5` (384-d) for scale. Ablation: `bge-m3` on a 500-book subset. |
| Reranker | `bge-reranker-v2-m3` (cross-encoder) |
| Reader LLM | **Default: the Claude headless RAG integration copied from the existing pipeline (see the required first step).** Ablations: Claude API (`claude-api` skill, prompt caching on), or a local model via Ollama for cheap eval sweeps. |
| Tracing | **Langfuse** (self-hosted). Every run is traced, and each eval run is a Langfuse dataset run. |
| Packaging | Docker Compose, arm64 images |

## Corpus

- **Target:** about 5,000 English Gutenberg books, plus every Gutenberg book referenced by NarrativeQA and QuALITY (the distractor design depends on this). Exclude NarrativeQA movie scripts from the library index, but evaluate on them separately with the oracle document.
- **Source:** use Gutenberg's official offline catalog and mirrors, or a published Hugging Face dump. **Do not crawl gutenberg.org pages.** Strip the Gutenberg header and footer boilerplate.
- **Size estimate:**
  - 5,000 books × about 100k tokens ≈ 500M tokens;
  - at 400-token chunks with 50 overlap, about 1.4M chunks;
  - 384-d float32 vectors ≈ 2.1 GB, and about 0.55 GB with int8 scalar quantization.
  - This fits the VM (24 GB). Embed on a free Kaggle or Colab GPU, export a Qdrant snapshot, and restore it on the VM.

## Data model

- `books`: id, gutenberg_id, title, author, year, subjects, n_tokens, n_chunks, ingest_status, sha256.
- `chapters`: book_id, idx, title, start_char, end_char.
- Qdrant `chunks` collection payload: book_id, chapter_idx, chunk_idx, start_char, end_char, text. Dense vector `dense`, sparse vector `bm25`.
- Qdrant `books` collection (for routing): one vector per book, built from a short LLM-written synopsis of about 200 tokens, generated once on the GPU box or with a small model. Payload includes title, author and subjects. A sparse vector over title, author and synopsis.
- `eval_runs`: id, method_config JSON, dataset, n_questions, metrics JSON, git_sha, created_at.

## Retrieval methods (each is a config, not a code fork)

1. **Passage-only:** BM25, dense, hybrid with RRF, then an optional rerank to the top k.
2. **Two-stage:**
   - **Stage 1, book routing:** hybrid search over the `books` collection, plus a vote from the top passage hits (score aggregation per book), keeping the top-B books (B = 1, 3 or 5).
   - **Stage 2:** hybrid passage search filtered to those books, then rerank.
3. **DOS ordering:** after retrieval, sort the selected passages by `(book, start_char)` before prompting.
4. **RAPTOR:** for routed books only, build GMM-clustered summary trees offline (cache them in Postgres or Qdrant) and use collapsed-tree retrieval.
5. **Token budgets:** 2k, 4k and 8k context tokens for every method, matched across methods. Results are only comparable at equal budgets.

## Evaluation

**Datasets**
- **NarrativeQA test:** 10,557 questions over 355 stories. Use the full set for retrieval metrics. For reader metrics, sample 1,000 to control cost.
- **QuALITY dev:** 2,086 multiple-choice questions. Use accuracy.

**Metrics**
- **Book routing accuracy@1/@5:** is the gold book among the routed books?
- **Passage recall proxy@k:** NarrativeQA has no gold passages. Use (a) whether any reference answer appears in the retrieved text after normalisation, and (b) an LLM-judged evidence check on a 300-question subset. State clearly that it is a proxy.
- **Answer quality:** F1, ROUGE-L and METEOR versus the two reference answers (NarrativeQA), and accuracy (QuALITY).
- **Cost and latency:** p50 and p95 per stage, tokens in and out, dollars per 1k questions.

**Rigour**
- Fixed seeds.
- 95% confidence intervals by bootstrap.
- Reader held constant across retrieval methods.
- A failure-case gallery: 20 analysed misses, labelled "wrong book", "right book, wrong passage" or "reader error".

## API (FastAPI)

- `POST /ask` with body `{question, book_id?, method?, budget?}`. Streams Server-Sent Events: `routing` (candidate books with scores), `retrieval` (passages with scores), `rerank`, then `token`s, then `citations`.
- `GET /books`, `GET /books/{id}` (chapters, stats), `GET /books/{id}/passage?start=&end=`
- `GET /search?q=` (hybrid search without generation)
- `GET /eval/runs`, `GET /eval/runs/{id}` (metrics plus per-question results)
- `GET /galaxy` (precomputed 2D UMAP coordinates of book vectors, for the UI)
- `GET /health`, `GET /metrics` (Prometheus)
- MCP server (via `mcp-builder`): tools `search_library`, `route_books`, `get_passage`.

## Docker Compose

```
api        FastAPI (uvicorn, 2 workers)
worker     celery: ingest, embed (CPU fallback), evals
qdrant     qdrant/qdrant (arm64), volume, snapshot restore on boot
postgres   postgres:16
redis      redis:7-alpine
langfuse   langfuse + its postgres (or reuse the postgres container with a separate DB)
ollama     optional, profile "local-llm"
web        Folio UI (Prompt 4)
nginx
```

Use `make ingest N=500` to test small, then `make ingest N=5000`. `make eval METHOD=hybrid_rerank_twostage BUDGET=4k` runs one configuration. `make leaderboard` regenerates the README table.

## Phases

1. **Ingestion and index:** 500 books, BM25 + dense + hybrid working, and `/search` live.
2. **Eval harness:** NarrativeQA and QuALITY loaders, the metrics above, Langfuse datasets, and the first leaderboard rows.
3. **Two-stage routing + reranker + DOS:** scale to 5,000 books using the GPU embedding run and snapshot restore.
4. **RAPTOR ablation**, cost and latency tracking, and the failure-case gallery.
5. **Polish:**
   - README with an Archify architecture diagram;
   - the leaderboard;
   - a "what didn't work" section;
   - a blog-style write-up of the corpus-scale finding.

## Definition of done

- `docker compose up` plus a snapshot restore gives a working system on the VM.
- `make eval` reproduces the leaderboard within its confidence intervals.
- The README leads with the headline number: book routing@5 and answer F1 at the 4k budget, versus the oracle-book upper bound.
