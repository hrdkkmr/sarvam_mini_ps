"""Measure the entity checker itself against hand-labelled translation variants.

Usage:  python scripts/evaluate_checker.py
Output: results/checker_eval.csv (one row per variant x entity),
        results/checker_summary.json (accuracy, error precision/recall, per category),
        results/reference_check.csv (checker on the literal and fluent references).
This does not depend on audio or timings.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import load_all  # noqa: E402
from src.entity_checker import check_all  # noqa: E402
from src.evaluation import evaluate_checker  # noqa: E402


def main() -> int:
    clips = load_all()
    rows, summ = evaluate_checker(clips)
    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    with open(out / "checker_eval.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in rows[0] if k != "text"])
        w.writeheader()
        w.writerows({k: v for k, v in r.items() if k != "text"} for r in rows)
    (out / "checker_summary.json").write_text(json.dumps(summ, indent=2), encoding="utf-8")

    ref = []
    for c in clips:
        for mode, text in (("fluent", c.tgt_fluent), ("literal", c.tgt_literal)):
            for r in check_all(c.entities, text, mode):
                ref.append({"clip_id": c.clip_id, "mode": mode, "entity_id": r.entity_id,
                            "category": r.category, "pass": r.passed, "reason": r.reason})
    with open(out / "reference_check.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ref[0]))
        w.writeheader()
        w.writerows(ref)

    o = summ["overall"]
    print(f"variants={summ['n_variants']} decisions={o['n']} accuracy={o['accuracy']:.3f} "
          f"error_precision={o['error_precision']:.3f} error_recall={o['error_recall']:.3f} "
          f"(tp={o['tp']} fp={o['fp']} fn={o['fn']} tn={o['tn']})")
    for cat, m in summ["by_category"].items():
        print(f"  {cat:10s} n={m['n']:3d} acc={m['accuracy']:.3f} tp={m['tp']} fp={m['fp']} fn={m['fn']}")
    for mode in ("fluent", "literal"):
        rs = [r for r in ref if r["mode"] == mode]
        print(f"references ({mode}): {sum(r['pass'] for r in rs)}/{len(rs)} entities pass")
    print("disagreements:")
    for d in summ["disagreements"]:
        print("  ", d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
