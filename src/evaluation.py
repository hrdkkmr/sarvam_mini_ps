"""Checker evaluation (is the checker right?) and wait-k aggregation."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .dataset import ROOT, Clip
from .entity_checker import category_of, check_entity

VARIANTS_JSON = ROOT / "data" / "annotations" / "checker_variants.json"


def apply_variant(text: str, replace: list[list[str]]) -> str:
    for old, new in replace:
        if old not in text:
            raise ValueError(f"variant replacement source {old!r} not found")
        text = text.replace(old, new)
    return text


def evaluate_checker(clips: list[Clip], path: Path = VARIANTS_JSON) -> tuple[list[dict], dict]:
    """Run the checker on every (variant, entity) pair and compare with the gold label.

    Positive class for precision/recall = "entity is wrong" (an error the checker should flag).
    """
    by_id = {c.clip_id: c for c in clips}
    variants = json.loads(path.read_text(encoding="utf-8"))["variants"]
    rows = []
    for v in variants:
        clip = by_id[v["clip"]]
        text = apply_variant(clip.tgt_fluent, v["replace"])
        ids = {e["id"] for e in clip.entities}
        unknown = set(v["gold_fail"]) - ids
        if unknown:
            raise ValueError(f"{v['clip']}/{v['id']}: unknown gold ids {unknown}")
        for e in clip.entities:
            r = check_entity(e, text, "fluent")
            gold_ok = e["id"] not in v["gold_fail"]
            rows.append({"clip_id": clip.clip_id, "variant": v["id"], "hard": bool(v.get("hard")),
                         "entity_id": e["id"], "category": category_of(e),
                         "gold_correct": gold_ok, "checker_pass": r.passed,
                         "agree": gold_ok == r.passed, "reason": r.reason, "text": text})
    return rows, summarise_checker(rows)


def _prf(rows: list[dict]) -> dict:
    tp = sum((not r["gold_correct"]) and (not r["checker_pass"]) for r in rows)
    fp = sum(r["gold_correct"] and (not r["checker_pass"]) for r in rows)
    fn = sum((not r["gold_correct"]) and r["checker_pass"] for r in rows)
    tn = sum(r["gold_correct"] and r["checker_pass"] for r in rows)
    n = len(rows)
    return {"n": n, "accuracy": (tp + tn) / n if n else float("nan"),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "error_precision": tp / (tp + fp) if tp + fp else float("nan"),
            "error_recall": tp / (tp + fn) if tp + fn else float("nan")}


def summarise_checker(rows: list[dict]) -> dict:
    out = {"overall": _prf(rows),
           "non_hard_variants": _prf([r for r in rows if not r["hard"]]),
           "hard_variants": _prf([r for r in rows if r["hard"]]),
           "by_category": {}}
    cats = defaultdict(list)
    for r in rows:
        cats[r["category"]].append(r)
    for c, rs in sorted(cats.items()):
        out["by_category"][c] = _prf(rs)
    out["n_variants"] = len({(r["clip_id"], r["variant"]) for r in rows})
    out["disagreements"] = [{k: r[k] for k in ("clip_id", "variant", "entity_id", "gold_correct",
                                                "checker_pass", "reason")}
                            for r in rows if not r["agree"]]
    return out
