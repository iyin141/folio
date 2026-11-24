Budget 4k. Cells: mean (95% bootstrap CI). Recall is a proxy (a reference answer appears in retrieved text), not gold-passage recall. Cost is the CLI's equivalent cost, not billed.

| Method | Book routing @1 | Book routing @5 | Passage recall proxy @10 | NarrativeQA F1 | NarrativeQA ROUGE-L | NarrativeQA METEOR (exact) | QuALITY acc. | p50 latency (ms) | $ per 1k questions (equiv.) |
|---|---|---|---|---|---|---|---|---|---|
| bm25 | 0.250 (0.150-0.350) | 0.500 (0.400-0.600) | 0.100 (0.050-0.150) | n/a | n/a | n/a | n/a | 30 | n/a |
| hybrid | 0.500 (0.400-0.600) | 0.750 (0.650-0.850) | 0.300 (0.200-0.400) | 0.250 (0.200-0.300) | 0.300 (0.250-0.350) | 0.200 (0.150-0.250) | 0.400 (0.300-0.500) | 120 | $1.23 |
