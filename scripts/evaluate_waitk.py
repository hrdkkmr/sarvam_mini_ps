"""Wait-k sweep (k = 1..10) + EAW + baselines on every clip; metrics, operating point and plots.

Usage:  python scripts/evaluate_waitk.py [--tgt-word-s 0.40]
Output (all under results/):
  metrics.csv                    one row per (clip, policy)
  metrics_aggregate.csv          one row per policy (latency = mean over clips,
                                 entity rates = pooled over all annotated entities)
  entity_timing.csv              one row per (clip, policy, entity)
  simulated_outputs.jsonl        the simulated (stress-test) English text per run
  k_sensitivity.csv              selected k under utility weights alpha = 0.1..0.9
  selected_operating_point.json  Pareto frontier, knee, alternatives, rationale (src/sweep.py)
  latency_vs_entity_accuracy.png, k_sweep.png, pareto_frontier.png  -- plotted from the CSV/JSON
                                 files AFTER they are written, never from in-memory values.
Every row carries `timing_source` and `seconds_status`. With placeholder timings every
seconds-based column is an ESTIMATE; word-based AL and entity rates do not depend on timings.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import load_all  # noqa: E402
from src.plotting import plot_k_sweep, plot_pareto, plot_tradeoff  # noqa: E402
from src.sweep import (ALPHAS, NEAR_FRACTION, baseline_dominance, load_aggregate_csv,  # noqa: E402
                       run_sweep, select_operating_point)
from src.waitk_simulator import DEFAULT_POLICIES, TGT_WORD_S  # noqa: E402

OUT = ROOT / "results"
ACC = "evidence_safe_rate"


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tgt-word-s", type=float, default=TGT_WORD_S)
    args = ap.parse_args()
    clips = load_all()
    sources = sorted({c.timing_source for c in clips})
    timing = sources[0] if len(sources) == 1 else "mixed:" + "+".join(sources)
    measured = sources == ["mms_fa_auto"]
    sec_status = ("measured source timings (MMS-FA); English duration fixed estimate" if measured else
                  f"ESTIMATED: placeholder source timings + fixed {args.tgt_word_s:.2f} s/English word; not measured")
    if not measured:
        print(f"WARNING: timings are {timing}; every seconds column is an estimate, not a measurement")

    per_run, ent_rows, agg, sims, _ = run_sweep(clips, DEFAULT_POLICIES, args.tgt_word_s, timing)
    for r in per_run + agg:
        r["seconds_status"] = sec_status
    write_csv(OUT / "metrics.csv", per_run)
    write_csv(OUT / "metrics_aggregate.csv", agg)
    write_csv(OUT / "entity_timing.csv", ent_rows)
    with open(OUT / "simulated_outputs.jsonl", "w", encoding="utf-8") as f:
        for s in sims:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    # ---- everything below uses the CSV as written to disk
    agg = load_aggregate_csv(OUT / "metrics_aggregate.csv")
    bad = [(r["policy"], c) for r in agg for c, v in r.items() if isinstance(v, float) and not math.isfinite(v)]
    if bad:
        print("ERROR: non-finite metric values:", bad)
        return 1
    wk = [r for r in agg if r["kind"] == "waitk"]
    primary = select_operating_point(wk, acc=ACC, lat="AL_words")
    seconds = select_operating_point(wk, acc=ACC, lat="AL_onset_s")
    selection = {
        "selection_rule": ("Candidates wait-k k=1..10. Pareto frontier on (max evidence-safe rate, min AL in "
                           "source words); knee = frontier point with the largest distance above the chord "
                           "joining the frontier extremes after min-max normalisation; ties -> smaller k; "
                           f"alternatives = knee neighbours + points within {NEAR_FRACTION:.0%} of the knee "
                           "distance. Utility alpha sweep is a secondary sensitivity analysis."),
        "data": {"n_clips": len(clips), "n_entities": wk[0]["n_entities"], "timing_source": timing,
                 "seconds_status": sec_status, "tgt_word_s": args.tgt_word_s,
                 "nature": "text-based timing simulation over fixed reference translations; no model run"},
        "accuracy_note": ("evidence_safe_rate == sim_entity_acc for every policy in this data (each annotated "
                          "premature guess fails the checker); fixed_text_acc is identical for every policy "
                          "by construction."),
        "sim_equals_evidence_safe": all(r["sim_entity_acc"] == r[ACC] for r in agg),
        "fixed_text_acc_values": sorted({r["fixed_text_acc"] for r in agg}),
        "primary_words": primary,
        "secondary_seconds_estimated": seconds,
        "reference_policies_dominating_waitk_words": baseline_dominance(agg, ACC, "AL_words"),
        "reference_policies_dominating_waitk_seconds_estimated": baseline_dominance(agg, ACC, "AL_onset_s"),
    }
    (OUT / "selected_operating_point.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")
    sens = [dict(s, latency_status="timing-independent" if s["latency_metric"] == "AL_words" else "ESTIMATED")
            for s in primary["utility_sensitivity"] + seconds["utility_sensitivity"]]
    write_csv(OUT / "k_sensitivity.csv", sens)

    sel_disk = json.loads((OUT / "selected_operating_point.json").read_text(encoding="utf-8"))["primary_words"]
    plot_tradeoff(agg, OUT / "latency_vs_entity_accuracy.png", timing)
    plot_k_sweep(agg, OUT / "k_sweep.png", timing)
    plot_pareto(agg, sel_disk, OUT / "pareto_frontier.png", timing)

    print(f"\n{'policy':22s} {'ALw':>6s} {'ALon_s*':>7s} {'endoff_s*':>9s} {'safe':>6s} {'simAcc':>6s} {'fixAcc':>6s}")
    for a in agg:
        print(f"{a['policy']:22s} {a['AL_words']:6.2f} {a['AL_onset_s']:7.2f} {a['end_offset_s']:9.2f} "
              f"{a[ACC]:6.1%} {a['sim_entity_acc']:6.1%} {a['fixed_text_acc']:6.1%}")
    if not measured:
        print("* seconds columns are ESTIMATES (placeholder timings)")
    p = primary
    print(f"\nPareto (words): k = {p['pareto_k']}; dominated: {p['dominated_k']}")
    print(f"Selected: wait-{p['selected']['k']} (method={p['method']}, knee distance {p['knee_distance']}, "
          f"one entity = {p['one_entity_in_normalised_units']}, weak={p['knee_is_weak']}); "
          f"alternatives: {[a['k'] for a in p['alternatives']]}")
    print("Utility alpha -> k (words):", {s['alpha']: s['selected_k'] for s in p['utility_sensitivity']})
    print("Seconds-based (estimated) knee: wait-%d" % seconds["selected"]["k"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
