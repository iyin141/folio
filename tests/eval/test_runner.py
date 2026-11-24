import shutil
from pathlib import Path

from folio.contracts import Answer, Evidence
from folio.eval import cli
from folio.eval.datasets import load_narrativeqa, load_quality
from folio.eval.datasets.models import Question
from folio.eval.fakes import FakeNoiseRetriever, FakeOracleRetriever, FakeReader
from folio.eval.registry import get_method
from folio.eval.runner import build_evidence, run_eval, sample
from folio.eval.store import JsonFileStore

FX = Path(__file__).parent / "fixtures"
NQA = load_narrativeqa(FX / "narrativeqa_test_sample.jsonl")
QUA = load_quality(FX / "quality_dev_sample.jsonl")


class SpyReader(FakeReader):
    def __init__(self):
        self.calls = []

    def answer(self, question, evidence: list[Evidence], options=None) -> Answer:
        self.calls.append([e.id for e in evidence])
        return super().answer(question, evidence, options)


def _run(retr, qs, ds, reader=None, **kw):
    return run_eval(retriever=retr(qs), reader=reader, method=get_method("fake"), dataset=ds, questions=qs,
                    resamples=50, **kw)


def test_evidence_ids_are_a_counter():
    rr = FakeOracleRetriever(NQA).retrieve(NQA[0].question, get_method("x"))
    assert [e.id for e in build_evidence(rr.hits)] == ["E1", "E2", "E3", "E4", "E5"]


def test_oracle_narrativeqa_with_reader():
    spy = SpyReader()
    run = _run(FakeOracleRetriever, NQA, "narrativeqa", spy, reader_name="fake")
    assert run.n_questions == 6 and run.n_reader == 6 and run.reader == "fake"
    assert all(c == ["E1", "E2", "E3", "E4", "E5"] for c in spy.calls)
    m = run.metrics
    assert m["route@1"]["mean"] == 1.0 and m["route@1"]["n"] == 4        # movie rows excluded from routing
    assert m["recall_proxy@10"]["mean"] == 1.0 and m["recall_proxy@10"]["n"] == 6
    assert m["f1"]["mean"] == 1.0 and m["rouge_l"]["mean"] == 1.0
    assert m["per_1k"]["cost_usd_equiv"] == 1.0 and m["per_1k"]["tokens_in"] == 100_000   # 0.001 * 1000
    assert all(r.label is None for r in run.results)


def test_noise_labels_and_movie_rows():
    run = _run(FakeNoiseRetriever, NQA, "narrativeqa", SpyReader())
    for r in run.results:
        # library rows: wrong book; movie rows have no routing gold, so recall decides
        assert r.label == ("wrong book" if r.routing_eligible else "right book, wrong passage")
    assert run.metrics["route@1"]["mean"] == 0.0


def test_quality_accuracy_with_fake_reader():
    run = _run(FakeOracleRetriever, QUA, "quality", SpyReader())
    assert run.metrics["accuracy"]["mean"] == 1.0 and run.metrics["accuracy"]["n"] == 12
    assert run.metrics["route@1"]["n"] == 9                            # 3 Slate questions unmapped


def test_reader_caps_and_budget():
    assert _run(FakeOracleRetriever, NQA, "narrativeqa", SpyReader(), reader_cap=2).n_reader == 2
    r2k = _run(FakeOracleRetriever, NQA, "narrativeqa", SpyReader(), budget="2k")
    assert r2k.n_reader == 0 and r2k.reader is None and r2k.metrics["route@1"]["mean"] == 1.0   # retrieval still runs
    big = [Question(id=f"q{i:04d}", dataset="narrativeqa", question=f"question {i}", references=["x"],
                    gold_gutenberg_id=1) for i in range(300)]
    spy = SpyReader()
    run = _run(FakeOracleRetriever, big, "narrativeqa", spy, reader_cap=1000)
    assert run.n_questions == 300 and run.n_reader == 200 and len(spy.calls) == 200   # hard cap


def test_sampling_is_deterministic():
    a = [q.id for q in sample(NQA, 3, seed=7)]
    assert a == [q.id for q in sample(list(reversed(NQA)), 3, seed=7)] and len(set(a)) == 3
    assert [q.id for q in sample(NQA, None, 7)] == sorted(q.id for q in NQA)


def test_cli_and_store(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(FX / "narrativeqa_test_sample.jsonl", data / "narrativeqa_test.jsonl")
    res = tmp_path / "res"
    assert cli.main(["--method", "fake-oracle", "--dataset", "narrativeqa", "--budget", "all", "--reader",
                     "--limit", "4", "--resamples", "20", "--data-dir", str(data), "--results-dir", str(res)]) == 0
    runs = JsonFileStore(res).list_runs()
    assert sorted(r.budget for r in runs) == ["2k", "4k", "8k"]
    by = {r.budget: r for r in runs}
    assert by["4k"].n_reader == 4 and by["2k"].n_reader == 0 and by["8k"].n_reader == 0
    full = JsonFileStore(res).get_run(by["4k"].id)
    assert len(full.results) == 4 and JsonFileStore(res).get_run("nope") is None
