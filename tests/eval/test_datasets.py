from pathlib import Path

from folio.eval.datasets import gutenberg_id_from_url, load_narrativeqa, load_quality
from folio.eval.datasets.quality import unmapped_report

FX = Path(__file__).parent / "fixtures"


def test_gutenberg_id_from_url():
    assert gutenberg_id_from_url("http://www.gutenberg.org/ebooks/234.txt.utf-8") == 234
    assert gutenberg_id_from_url("http://aleph.gutenberg.org/5/2/8/4/52845//52845-h//52845-h.htm") == 52845
    assert gutenberg_id_from_url("http://www.imsdb.com/scripts/x.html") is None


def test_narrativeqa_fixture():
    qs = load_narrativeqa(FX / "narrativeqa_test_sample.jsonl")
    assert len(qs) == 6 and all(len(q.references) == 2 for q in qs)
    assert {q.gold_gutenberg_id for q in qs if q.doc_kind == "gutenberg"} == {47, 234}
    movies = [q for q in qs if q.doc_kind == "movie"]
    assert len(movies) == 2 and all(q.gold_gutenberg_id is None and not q.routing_eligible for q in movies)
    assert sum(q.routing_eligible for q in qs) == 4
    assert len({q.id for q in qs}) == 6
    assert qs[0].question and qs[0].dataset == "narrativeqa"


def test_quality_fixture():
    qs = load_quality(FX / "quality_dev_sample.jsonl")
    assert len(qs) == 12 and all(len(q.options) == 4 for q in qs)
    assert qs[0].gold_choice == 1          # first question: gold_label 2 (1-based) -> index 1
    assert {q.gold_gutenberg_id for q in qs} == {52845, 30029, 62139, None}
    assert unmapped_report(qs) == {"questions": 12, "unmapped": 3, "mapped": 9}   # the Slate article
    assert all(not q.routing_eligible for q in qs if q.gold_gutenberg_id is None)
