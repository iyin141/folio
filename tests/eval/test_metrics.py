"""Every expected value below is computed by hand (working in the comment)."""
import pytest

from folio.eval import metrics as M
from folio.eval.stats import bootstrap_ci, paired_bootstrap


def test_normalize():
    assert M.normalize("The Cat, sat! on a MAT.") == "cat sat on mat"


def test_token_f1_max_over_refs():
    # pred -> [cat, sat]; ref1 [cat, sat, down]: common 2, P=2/2, R=2/3, F1=2*1*(2/3)/(1+2/3)=0.8; ref2 [dog]: 0
    assert M.token_f1("The cat sat", ["cat sat down", "a dog"]) == pytest.approx(0.8)
    assert M.token_f1("cat", ["dog"]) == 0.0
    assert M.token_f1("", [""]) == 1.0          # both empty after normalisation: SQuAD convention


def test_token_f1_duplicates_count_once_per_ref_occurrence():
    # pred [a b b] -> [b b] after article removal: pred [b b], ref [b c]: common 1, P=1/2, R=1/2, F1=0.5
    assert M.token_f1("a b b", ["b c"]) == pytest.approx(0.5)


def test_rouge_l_equal_precision_recall():
    # "cat sat mat" vs "cat on mat": LCS=2 (cat, mat); P=R=2/3; F=P=2/3 (second ref scores 0)
    assert M.rouge_l("cat sat mat", ["cat on mat", "dog"]) == pytest.approx(2 / 3)


def test_rouge_l_beta():
    # "cat sat" vs "cat sat on mat": LCS=2, P=1, R=0.5, beta=1.2 -> 2.44*1*0.5/(0.5+1.44*1)=1.22/1.94
    assert M.rouge_l("cat sat", ["cat sat on mat"]) == pytest.approx(1.22 / 1.94)
    assert M.rouge_l("cat", ["dog"]) == 0.0


def test_meteor_exact():
    # hyp "cat sat mat" vs ref "cat sat on mat": m=3, P=1, R=3/4, Fmean=10PR/(R+9P)=7.5/9.75=10/13
    # chunks: (cat,sat) is one chunk, mat another -> 2; penalty=0.5*(2/3)^3=4/27; score=10/13*23/27=230/351
    assert M.meteor("cat sat mat", ["cat sat on mat"]) == pytest.approx(230 / 351)
    # perfect two-word match: Fmean=1, chunks=1, penalty=0.5*(1/2)^3=1/16 -> 0.9375
    assert M.meteor("cat sat", ["cat sat", "x"]) == pytest.approx(0.9375)
    assert M.meteor("cat", ["dog"]) == 0.0


def test_quality_accuracy():
    assert M.quality_accuracy([0, 1, 2, None], [0, 1, 1, 3]) == 0.5     # 2 of 4
    assert M.quality_accuracy([], []) == 0.0


def test_routing_hit():
    assert M.routing_hit(5, [3, 5, 7], 1) is False
    assert M.routing_hit(5, [3, 5, 7], 5) is True
    assert M.routing_hit(None, [3, 5], 5) is False


def test_recall_proxy():
    texts = ["nothing here", "He saw the Eiffel Tower, Paris."]
    assert M.recall_proxy(["The Eiffel Tower"], texts) is True
    assert M.recall_proxy(["The Eiffel Tower"], texts, k=1) is False      # only first passage counted
    assert M.recall_proxy(["war"], ["a warrior came"]) is False           # token boundary, not substring
    assert M.recall_proxy(["", "the"], ["anything"]) is False             # empty normalised refs never match


def test_latency_percentiles():
    # sorted [1,2,3,4]: p50 -> pos 1.5 -> 2.5; p95 -> pos 2.85 -> 3 + 0.85*(4-3) = 3.85
    assert M.latency_stats([4, 1, 3, 2]) == pytest.approx({"p50": 2.5, "p95": 3.85})
    assert M.latency_stats([7]) == {"p50": 7, "p95": 7}
    assert M.latency_stats([]) == {"p50": 0.0, "p95": 0.0}


def test_per_1k():
    assert M.per_1k(0.5, 250) == pytest.approx(2.0)      # 0.5 / 250 * 1000
    assert M.per_1k(1, 0) == 0.0


def test_bootstrap_ci_constant_and_seeded():
    c = bootstrap_ci([1, 1, 1, 1], resamples=50, seed=3)
    assert (c["mean"], c["lo"], c["hi"], c["n"]) == (1.0, 1.0, 1.0, 4)
    v = [0, 1, 1, 0, 1, 1, 1, 0]
    a, b = bootstrap_ci(v, 200, seed=1), bootstrap_ci(v, 200, seed=1)
    assert a == b and a["mean"] == 5 / 8 and a["lo"] <= 5 / 8 <= a["hi"]
    assert bootstrap_ci([], 10)["mean"] is None


def test_paired_bootstrap():
    r = paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0], resamples=100, seed=0)
    assert (r["diff"], r["lo"], r["hi"], r["p"]) == (1.0, 1.0, 1.0, 0.0)
    r = paired_bootstrap([1, 0, 1], [1, 0, 1], resamples=100, seed=0)
    assert r["diff"] == 0 and r["p"] == 1.0
    with pytest.raises(ValueError):
        paired_bootstrap([1], [1, 2])
