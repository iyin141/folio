# Build Prompt 4 of 6: Folio UI

## Role and goal

You are building the web app for **Folio**, the library-scale book Q&A system. It has to do two jobs:

1. Be a pleasant reading and asking experience.
2. **Make retrieval visible.** A reviewer should *see* the book routing, passage scores, reranking and citations, then open the benchmark leaderboard.

Load these skills first: `frontend-design`, `astryx`, `webapp-testing`, `theme-factory`.

## Stack

| Concern | Choice |
|---|---|
| Framework | Next.js (App Router, TypeScript, React 19), `output: "standalone"` |
| Components | **Astryx**: start each page with `astryx build "<purpose>"`, then `astryx template`. Pin versions (it's in beta). |
| AI state | **thinking-orbs**: `searching` (routing books), `connecting` (retrieving passages), `solving` (reranking), `composing` (writing the answer) |
| Charts | ECharts (leaderboard bars, recall@k curves, latency distributions) |
| Big scatter | **deck.gl** `ScatterplotLayer` for the book galaxy (5,000+ points, WebGL) |
| Tables | TanStack Table (leaderboard, per-question explorer) |
| Streaming | `EventSource` / fetch-stream over the `/ask` SSE events |

## Design direction

- **Literary and calm.** Cream and near-black text, with **burnt orange** reserved for the primary action and active citations (the two-plus-one rule).
- **Type:** a serif for reading passages (book feel) and a clean sans for UI chrome. Generous line-height in the reader.
- Retrieval visuals look like a library card catalogue, not a generic dashboard. Use the `frontend-design` skill to commit to that direction.

## Pages

### 1. Ask (`/`)

- A large question box with an optional "limit to book" picker.
- A **live retrieval trace** shown as the answer streams:
  1. **Routing:** candidate books as cards with cover initials, title, author and routing score bar. The chosen books are highlighted.
  2. **Passages:** the top passages with BM25, dense and fused scores, and rerank deltas (↑ / ↓).
  3. **Answer:** streamed text with numbered citation markers.
- Clicking a citation opens the Reader at that passage.
- A method switcher (advanced): pick the retrieval config and budget to compare answers side by side for the same question.

### 2. Reader (`/books/[id]`)

- Chapter navigation, and passage highlight on deep link (`?start=&end=`).
- A margin note showing which questions in the eval set cite this passage (if any).

### 3. Library galaxy (`/galaxy`)

- A deck.gl scatter of every book: UMAP of the book vectors, coloured by subject.
- Hover shows the title and author. Click opens the book.
- Search highlights matches and animates the camera to them.
- Benchmark books (NarrativeQA and QuALITY) can be toggled on to show how they hide among the distractors.

### 4. Leaderboard (`/eval`)

- The headline cards: routing@5, answer F1 at the 4k budget, and the oracle gap.
- A sortable table of all methods × budgets with confidence intervals.
- Charts:
  - recall-proxy@k curves per method;
  - cost versus quality scatter (dollars per 1k questions vs F1);
  - latency box plots per stage.
- **Per-question explorer:** filter to failures by type (wrong book, wrong passage, reader error) and open the full trace for any question.

### 5. About (`/about`)

The Archify architecture diagram (embedded HTML export), the method write-up, "what didn't work", and links to the code and dataset licences.

## Docker

Multi-stage `node:22-alpine`, arm64, standalone output, served behind nginx at `/` with the API at `/api/`.

## Testing (webapp-testing)

1. Ask a known NarrativeQA question and confirm the routing cards appear, the passages appear, the answer streams, and a citation click opens the reader at the highlighted passage.
2. The galaxy renders 5,000 points at 60 fps while panning, measured with a Playwright performance trace.
3. Leaderboard sorting and the failure filter work.

## Definition of done

- All five pages ship and are responsive. The galaxy falls back to a static image on mobile.
- Accessibility AA. Orbs respect reduced motion.
- A README GIF shows the retrieval trace for one question.
