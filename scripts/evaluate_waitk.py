"""Run every read/write policy on every clip and write metrics + the trade-off plot.

Usage:  python scripts/evaluate_waitk.py [--tgt-word-s 0.40]
Output: results/metrics.csv           one row per (clip, policy)
        results/metrics_aggregate.csv one row per policy (latency = mean over clips,
                                      entity accuracy = pooled over all entities)
        results/entity_timing.csv     one row per (clip, policy, entity)
        results/simulated_outputs.jsonl  the simulated English text per run
        results/latency_vs_entity_accuracy.png
If any clip uses placeholder timings, every file is written under results/placeholder/
instead, so placeholder numbers can never overwrite or be confused with measured ones.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import load_all  # noqa: E402
from src.plotting import plot_tradeoff  # noqa: E402
from src.waitk_simulator import DEFAULT_POLICIES, TGT_WORD_S, simulate  # noqa: E402


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
    real = sources == ["mms_fa_auto"]
    out = ROOT / "results" if real else ROOT / "results" / "placeholder"
    if not real:
        print(f"WARNING: timings are {timing}; writing to {out} (not reportable as measured)")

    per_run, ent_rows, agg, sims = [], [], [], []
    for p in DEFAULT_POLICIES:
        runs = [simulate(c, p, tgt_word_s=args.tgt_word_s) for c in clips]
        for r in runs:
            per_run.append({"clip_id": r.clip_id, "policy": r.policy, "kind": r.kind, "k": r.k,
                            "timing_source": r.timing_source, "tgt_word_s": args.tgt_word_s,
                            **{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.metrics.items()}})
            for e in r.entity_rows:
                ent_rows.append({"clip_id": r.clip_id, "policy": r.policy, **e})
            sims.append({"clip_id": r.clip_id, "policy": r.policy, "text": r.sim_text, "g": r.g})
        ne = sum(r.metrics["n_entities"] for r in runs)
        agg.append({
            "policy": p.name, "kind": p.kind, "k": p.k, "timing_source": timing, "n_clips": len(runs),
            "n_entities": ne,
            **{m: round(statistics.mean(r.metrics[m] for r in runs), 3)
               for m in ("AL_words", "AP", "AL_decision_s", "AL_onset_s", "first_output_s", "end_offset_s")},
            "evidence_safe_rate": round(sum(r.metrics["evidence_safe"] for r in runs) / ne, 4),
            "sim_entity_acc": round(sum(r.metrics["sim_pass"] for r in runs) / ne, 4),
            "fixed_text_acc": round(sum(r.metrics["fixed_text_pass"] for r in runs) / ne, 4),
        })
    write_csv(out / "metrics.csv", per_run)
    write_csv(out / "metrics_aggregate.csv", agg)
    write_csv(out / "entity_timing.csv", ent_rows)
    with open(out / "simulated_outputs.jsonl", "w", encoding="utf-8") as f:
        for s in sims:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    plot_tradeoff(agg, out / "latency_vs_entity_accuracy.png", timing)
    print(f"{'policy':22s} {'ALw':>6s} {'ALdec_s':>8s} {'ALon_s':>7s} {'first_s':>7s} {'endoff_s':>8s} {'safe':>6s} {'simAcc':>6s} {'fixAcc':>6s}")
    for a in agg:
        print(f"{a['policy']:22s} {a['AL_words']:6.2f} {a['AL_decision_s']:8.2f} {a['AL_onset_s']:7.2f} "
              f"{a['first_output_s']:7.2f} {a['end_offset_s']:8.2f} {a['evidence_safe_rate']:6.1%} "
              f"{a['sim_entity_acc']:6.1%} {a['fixed_text_acc']:6.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
