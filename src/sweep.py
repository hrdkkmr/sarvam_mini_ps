"""Wait-k sweep, aggregation and operating-point selection (Pareto frontier + knee).

Everything here is deterministic and operates on the outputs of `waitk_simulator.simulate`.

Selection rule (documented in RESULTS.md and the report; do not change silently)
-------------------------------------------------------------------------------
Candidates: the wait-k policies of the sweep (k = 1..10). Baselines (sentence-by-sentence,
whole-clip) and EAW variants are shown for reference but are not candidates for "the selected k".

1. Pareto frontier. Policy A dominates B if acc(A) >= acc(B) and lat(A) <= lat(B), with at least
   one strict inequality. Non-dominated candidates form the frontier.
2. Knee point (primary). Both axes are min-max normalised over the candidates. Draw the straight
   line from the frontier point with the lowest latency to the frontier point with the highest
   accuracy. The knee is the frontier point with the largest signed distance ABOVE that line
   (largest accuracy gain beyond a linear exchange of latency for accuracy). Ties -> smaller k.
   If no point lies above the line (flat or convex curve) there is no knee and the rule falls
   back to the alpha = 0.5 utility below; this is flagged in the output.
3. Near-equivalent alternatives: frontier points whose knee distance is at least
   NEAR_FRACTION of the knee's distance, plus the knee's frontier neighbours. The knee is
   flagged `knee_is_weak` when its distance is smaller than the normalised effect of a single
   entity flipping (1 / n_entities / accuracy range): then the curve is effectively linear and
   the "best" k is a preference, not a property of the data.
4. Sensitivity (secondary, exploratory): utility(k) = alpha * acc_norm(k) + (1 - alpha) *
   (1 - lat_norm(k)) for alpha = 0.1..0.9, min-max normalisation over candidates, ties -> smaller k.
   alpha is a preference weight, not a scientific constant.
"""
from __future__ import annotations

import math
import statistics
from collections.abc import Iterable

from .dataset import Clip
from .waitk_simulator import WAITK_SWEEP, Policy, RunResult, simulate

SWEEP_K = WAITK_SWEEP
ALPHAS = tuple(round(0.1 * i, 1) for i in range(1, 10))
NEAR_FRACTION = 0.75
MEAN_METRICS = ("AL_words", "AP", "AL_decision_s", "AL_onset_s", "first_output_s", "end_offset_s")


def waitk_policies(ks: Iterable[int] = SWEEP_K) -> list[Policy]:
    return [Policy(f"wait-{k}", "waitk", k) for k in ks]


def aggregate(policy: Policy, runs: list[RunResult], timing: str) -> dict:
    """Latency = unweighted mean over clips; entity rates = pooled over all annotated entities."""
    ne = sum(r.metrics["n_entities"] for r in runs)
    return {
        "policy": policy.name, "kind": policy.kind, "k": policy.k, "timing_source": timing,
        "n_clips": len(runs), "n_entities": ne,
        **{m: round(statistics.mean(r.metrics[m] for r in runs), 3) for m in MEAN_METRICS},
        "evidence_safe_rate": round(sum(r.metrics["evidence_safe"] for r in runs) / ne, 4),
        "sim_entity_acc": round(sum(r.metrics["sim_pass"] for r in runs) / ne, 4),
        "fixed_text_acc": round(sum(r.metrics["fixed_text_pass"] for r in runs) / ne, 4),
        "min_initial_src_words": min(r.g[0] for r in runs),
    }


def run_sweep(clips: list[Clip], policies: list[Policy], tgt_word_s: float, timing: str):
    """Evaluate every clip under every policy. Returns (per_run, entity_rows, agg, sims, runs)."""
    per_run, ent_rows, agg, sims, all_runs = [], [], [], [], {}
    for p in policies:
        runs = [simulate(c, p, tgt_word_s=tgt_word_s) for c in clips]
        all_runs[p.name] = runs
        for r in runs:
            per_run.append({"clip_id": r.clip_id, "policy": r.policy, "kind": r.kind, "k": r.k,
                            "timing_source": r.timing_source, "tgt_word_s": tgt_word_s,
                            "initial_src_words": r.g[0],
                            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.metrics.items()}})
            for e in r.entity_rows:
                ent_rows.append({"clip_id": r.clip_id, "policy": r.policy, **e})
            sims.append({"clip_id": r.clip_id, "policy": r.policy, "text": r.sim_text, "g": r.g})
        agg.append(aggregate(p, runs, timing))
    return per_run, ent_rows, agg, sims, all_runs


# ---------------------------------------------------------------- operating-point selection

def dominates(a: dict, b: dict, acc: str, lat: str) -> bool:
    return (a[acc] >= b[acc] and a[lat] <= b[lat]) and (a[acc] > b[acc] or a[lat] < b[lat])


def pareto_flags(rows: list[dict], acc: str, lat: str) -> list[bool]:
    """True where the row is non-dominated within `rows`."""
    return [not any(dominates(o, r, acc, lat) for o in rows if o is not r) for r in rows]


def _norm(v: float, lo: float, hi: float) -> float:
    return 0.0 if hi == lo else (v - lo) / (hi - lo)


def normalised(rows: list[dict], acc: str, lat: str) -> list[tuple[float, float]]:
    a = [float(r[acc]) for r in rows]
    t = [float(r[lat]) for r in rows]
    return [(_norm(x, min(t), max(t)), _norm(y, min(a), max(a))) for x, y in zip(t, a)]


def knee_distances(rows: list[dict], front: list[bool], acc: str, lat: str) -> list[float | None]:
    """Signed distance above the chord joining the frontier's extremes (normalised space)."""
    pts = normalised(rows, acc, lat)
    fp = [(p, i) for i, (p, f) in enumerate(zip(pts, front)) if f]
    (x0, y0), _ = min(fp, key=lambda q: (q[0][0], -q[0][1]))     # lowest latency
    (x1, y1), _ = max(fp, key=lambda q: (q[0][1], -q[0][0]))     # highest accuracy
    length = math.hypot(x1 - x0, y1 - y0)
    out = []
    for (x, y), f in zip(pts, front):
        if not f or length == 0:
            out.append(None if not f else 0.0)
        else:
            out.append(((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) / length)
    return out


def utilities(rows: list[dict], acc: str, lat: str, alpha: float) -> list[float]:
    return [alpha * y + (1 - alpha) * (1 - x) for x, y in normalised(rows, acc, lat)]


def _argmax_small_k(rows: list[dict], scores: list[float]) -> int:
    best = max(scores)
    return min((i for i, s in enumerate(scores) if math.isclose(s, best, abs_tol=1e-12)),
               key=lambda i: rows[i]["k"])


def select_operating_point(candidates: list[dict], acc: str = "evidence_safe_rate",
                           lat: str = "AL_words", alphas: Iterable[float] = ALPHAS) -> dict:
    """Apply the documented rule. `candidates` are wait-k aggregate rows (must have 'k')."""
    rows = sorted(candidates, key=lambda r: r["k"])
    front = pareto_flags(rows, acc, lat)
    dist = knee_distances(rows, front, acc, lat)
    above = [(d, i) for i, d in enumerate(dist) if d is not None and d > 1e-12]
    if above:
        dmax = max(d for d, _ in above)
        knee_i = min((i for d, i in above if math.isclose(d, dmax, abs_tol=1e-12)), key=lambda i: rows[i]["k"])
        method = "knee"
    else:
        knee_i = _argmax_small_k(rows, utilities(rows, acc, lat, 0.5))
        dmax, method = 0.0, "fallback_utility_alpha_0.5"
    front_idx = [i for i, f in enumerate(front) if f]
    pos = front_idx.index(knee_i) if knee_i in front_idx else None
    neighbours = set()
    if pos is not None:
        neighbours |= {front_idx[j] for j in (pos - 1, pos + 1) if 0 <= j < len(front_idx)}
    near = {i for i, d in enumerate(dist) if d is not None and dmax > 0 and d >= NEAR_FRACTION * dmax}
    alt_idx = sorted((neighbours | near) - {knee_i}, key=lambda i: rows[i]["k"])
    sens = []
    for a in alphas:
        u = utilities(rows, acc, lat, a)
        j = _argmax_small_k(rows, u)
        sens.append({"alpha": a, "selected_k": rows[j]["k"], "utility": round(u[j], 4),
                     "accuracy_metric": acc, "latency_metric": lat})
    aggressive = rows[0]

    def summary(i: int) -> dict:
        r = rows[i]
        return {"k": r["k"], "policy": r["policy"], acc: r[acc], lat: r[lat],
                "knee_distance": None if dist[i] is None else round(dist[i], 4)}

    sel = rows[knee_i]
    # resolution: one entity flipping changes acc by 1/n_entities; in normalised units:
    acc_range = max(r[acc] for r in rows) - min(r[acc] for r in rows)
    one_entity = (1 / rows[0]["n_entities"]) / acc_range if acc_range else float("inf")
    return {
        "accuracy_metric": acc, "latency_metric": lat, "method": method,
        "knee_distance": round(dmax, 4),
        "one_entity_in_normalised_units": round(one_entity, 4),
        "knee_is_weak": dmax < one_entity,
        "candidates_k": [r["k"] for r in rows],
        "pareto_k": [rows[i]["k"] for i in front_idx],
        "dominated_k": [r["k"] for r, f in zip(rows, front) if not f],
        "knee_distance_by_k": {r["k"]: (None if d is None else round(d, 4)) for r, d in zip(rows, dist)},
        "selected": summary(knee_i),
        "alternatives": [summary(i) for i in alt_idx],
        "vs_most_aggressive": {
            "k": aggressive["k"],
            "latency_change": round(sel[lat] - aggressive[lat], 4),
            "accuracy_change_points": round(100 * (sel[acc] - aggressive[acc]), 2),
        },
        "utility_sensitivity": sens,
        "utility_selection_changes_with_alpha": len({s["selected_k"] for s in sens}) > 1,
    }


def baseline_dominance(agg: list[dict], acc: str, lat: str) -> list[dict]:
    """Which wait-k points are dominated by a non-wait-k policy (reference baselines / EAW)."""
    out = []
    for b in (r for r in agg if r["kind"] not in ("waitk", "full")):
        hit = [r["k"] for r in agg if r["kind"] == "waitk" and dominates(b, r, acc, lat)]
        out.append({"policy": b["policy"], acc: b[acc], lat: b[lat], "dominates_waitk": hit})
    return out


# ---------------------------------------------------------------- CSV round trip (plots read CSVs)

_INT_COLS = {"k", "n_clips", "n_entities", "min_initial_src_words"}
_STR_COLS = {"policy", "kind", "timing_source", "seconds_status"}


def load_aggregate_csv(path) -> list[dict]:
    import csv
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out = {}
            for c, v in r.items():
                if c in _STR_COLS:
                    out[c] = v
                elif c in _INT_COLS:
                    out[c] = int(v) if v != "" else None
                else:
                    out[c] = float(v)
            rows.append(out)
    return rows
