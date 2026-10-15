import csv
import math

import pytest

from src.adaptive_policy import waitk_schedule
from src.dataset import load_all
from src.latency_metrics import al_words
from src.sweep import (ALPHAS, SWEEP_K, dominates, knee_distances, load_aggregate_csv,
                       pareto_flags, run_sweep, select_operating_point, utilities, waitk_policies)
from src.waitk_simulator import DEFAULT_POLICIES, TGT_WORD_S


@pytest.fixture(scope="module")
def sweep():
    clips = load_all()
    return clips, run_sweep(clips, waitk_policies(), TGT_WORD_S, "test")


def test_every_requested_k_is_evaluated(sweep):
    clips, (per_run, _, agg, _, _) = sweep
    assert SWEEP_K == tuple(range(1, 11))
    assert [a["k"] for a in agg] == list(SWEEP_K)
    for k in SWEEP_K:
        assert sorted(r["clip_id"] for r in per_run if r["k"] == k) == sorted(c.clip_id for c in clips)
    assert {p.k for p in DEFAULT_POLICIES if p.kind == "waitk"} == set(SWEEP_K)


def test_sweep_is_deterministic(sweep):
    clips, (_, _, agg, _, _) = sweep
    _, _, agg2, _, _ = run_sweep(clips, waitk_policies(), TGT_WORD_S, "test")
    assert agg == agg2


def test_larger_k_never_reduces_initial_context(sweep):
    clips, (per_run, _, agg, _, runs) = sweep
    for c in clips:
        gs = [runs[f"wait-{k}"][[x.clip_id for x in runs[f"wait-{k}"]].index(c.clip_id)].g for k in SWEEP_K]
        for k, g in zip(SWEEP_K, gs):
            assert g[0] == min(k, len(c.src_words))
        for a, b in zip(gs, gs[1:]):                       # pointwise monotone in k
            assert all(y >= x for x, y in zip(a, b))
    inits = [a["min_initial_src_words"] for a in agg]
    assert inits == sorted(inits)


def test_metrics_consistent_with_metric_functions(sweep):
    clips, (per_run, _, agg, _, runs) = sweep
    for k in SWEEP_K:
        for c, r in zip(clips, runs[f"wait-{k}"]):
            g = waitk_schedule(len(c.src_words), len(c.tgt_tokens), k)
            g[-1] = len(c.src_words)
            assert r.g == g
            assert r.metrics["AL_words"] == pytest.approx(al_words(g, len(c.src_words)))
            assert r.metrics["sim_pass"] <= r.metrics["n_entities"]
    for a in agg:
        assert all(math.isfinite(v) for v in a.values() if isinstance(v, float))
        assert 0 <= a["evidence_safe_rate"] <= 1
        assert len({x["fixed_text_acc"] for x in agg}) == 1      # fixed text: identical by construction
    al = [a["AL_words"] for a in agg]
    assert al == sorted(al)


def _row(k, acc, lat, n=37):
    return {"k": k, "policy": f"wait-{k}", "acc": acc, "lat": lat, "n_entities": n}


def test_pareto_dominance_definition():
    a, b, c = _row(1, 0.5, 1.0), _row(2, 0.5, 2.0), _row(3, 0.6, 2.0)
    assert dominates(a, b, "acc", "lat") and not dominates(a, a, "acc", "lat")
    assert pareto_flags([a, b, c], "acc", "lat") == [True, False, True]


def test_knee_on_synthetic_concave_curve():
    rows = [_row(1, 0.1, 1), _row(2, 0.8, 2), _row(3, 0.9, 3), _row(4, 0.95, 4), _row(5, 0.95, 5)]
    sel = select_operating_point(rows, acc="acc", lat="lat")
    assert sel["selected"]["k"] == 2 and sel["method"] == "knee"
    assert sel["dominated_k"] == [5]


def test_selected_point_follows_documented_rule(sweep):
    _, (_, _, agg, _, _) = sweep
    sel = select_operating_point(agg)
    front = pareto_flags(sorted(agg, key=lambda r: r["k"]), "evidence_safe_rate", "AL_words")
    rows = sorted(agg, key=lambda r: r["k"])
    assert sel["pareto_k"] == [r["k"] for r, f in zip(rows, front) if f]
    k = sel["selected"]["k"]
    assert k in sel["pareto_k"]
    dist = knee_distances(rows, front, "evidence_safe_rate", "AL_words")
    best = max(d for d in dist if d is not None)
    assert dist[[r["k"] for r in rows].index(k)] == pytest.approx(best)
    for s in sel["utility_sensitivity"]:
        u = utilities(rows, "evidence_safe_rate", "AL_words", s["alpha"])
        assert u[[r["k"] for r in rows].index(s["selected_k"])] == pytest.approx(max(u))
    assert [s["alpha"] for s in sel["utility_sensitivity"]] == list(ALPHAS)


def test_results_csv_covers_k1_to_10_if_present():
    from src.dataset import ROOT
    p = ROOT / "results" / "metrics_aggregate.csv"
    if not p.exists():
        pytest.skip("run scripts/evaluate_waitk.py first")
    ks = {r["k"] for r in load_aggregate_csv(p) if r["kind"] == "waitk"}
    assert ks == set(SWEEP_K)
    with open(ROOT / "results" / "metrics.csv", encoding="utf-8") as f:
        assert {int(r["k"]) for r in csv.DictReader(f) if r["kind"] == "waitk"} == set(SWEEP_K)
