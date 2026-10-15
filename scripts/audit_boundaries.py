"""Thirty-boundary manual audit of the automatic word timings.

Step 1 (make the sheet, BEFORE looking at the automatic labels, to avoid anchoring):
    python scripts/audit_boundaries.py make-sheet
  -> data/annotations/boundary_audit_sheet.csv : 5 word ONSETS per clip (30 total). The
     automatic times are deliberately NOT in this file. Fill `manual_onset_s` by placing the
     Audacity cursor at the start of the word's first sound (spectrogram view, zoomed in) and
     copying the time from the Selection toolbar (format hh:mm:ss + milliseconds).
Step 2 (score):
    python scripts/audit_boundaries.py score
  -> results/boundary_audit.csv and results/boundary_audit_summary.json
     |auto - manual| in ms, mean, median, max, count above the 50 ms and 100 ms tolerances.

Boundary = onset (start time) of a word. Selection is deterministic: the determining word of
up to three annotated entities per clip (the timings that matter most for the wait-k
simulation), then evenly spaced words to make five per clip.
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dataset import ALIGN_DIR, build_clip, load_clips  # noqa: E402

SHEET = ROOT / "data" / "annotations" / "boundary_audit_sheet.csv"
OUT_CSV = ROOT / "results" / "boundary_audit.csv"
OUT_JSON = ROOT / "results" / "boundary_audit_summary.json"
PER_CLIP = 5
TOLERANCES_MS = (50, 100)     # stated tolerances; 20 ms = one model frame


def select_indices(clip) -> list[int]:
    n = len(clip.src_words)
    chosen = []
    for e in clip.entities:
        if e["src_idx"] not in chosen and len(chosen) < 3:
            chosen.append(e["src_idx"])
    step = n / (PER_CLIP + 1)
    for k in range(1, 3 * PER_CLIP):
        if len(chosen) >= PER_CLIP:
            break
        i = min(n - 1, int(round(k * step)) % n)
        if i not in chosen and i != 0:
            chosen.append(i)
    return sorted(chosen[:PER_CLIP])


def make_sheet() -> int:
    if SHEET.exists():
        print(f"{SHEET} exists; refusing to overwrite your manual entries. Delete it first.")
        return 1
    rows = []
    for raw in load_clips():
        clip = build_clip(raw)
        for i in select_indices(clip):
            rows.append({"boundary_id": f"{clip.clip_id}_w{i:03d}", "clip_id": clip.clip_id,
                         "word_index": i, "word": clip.src_words[i]["w"],
                         "previous_word": clip.src_words[i - 1]["w"] if i else "",
                         "manual_onset_s": "", "reviewer_note": ""})
    SHEET.parent.mkdir(parents=True, exist_ok=True)
    with open(SHEET, "w", newline="", encoding="utf-8-sig") as f:   # BOM so Excel shows Devanagari
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} boundaries to {SHEET}")
    return 0


def parse_time(s: str) -> float:
    s = s.strip()
    if ":" in s:                       # hh:mm:ss.mmm or mm:ss.mmm
        parts = [float(p) for p in s.split(":")]
        sec = 0.0
        for p in parts:
            sec = sec * 60 + p
        return sec
    return float(s)


def score() -> int:
    if not SHEET.exists():
        print("no sheet; run `make-sheet` first")
        return 1
    with open(SHEET, encoding="utf-8-sig") as f:
        sheet = list(csv.DictReader(f))
    filled = [r for r in sheet if r["manual_onset_s"].strip()]
    if not filled:
        print("sheet has no manual_onset_s values yet")
        return 1
    rows = []
    for r in filled:
        p = ALIGN_DIR / f"{r['clip_id']}.json"
        if not p.exists():
            print(f"no automatic alignment for {r['clip_id']}; skipping")
            continue
        al = json.loads(p.read_text(encoding="utf-8"))
        aw = al["words"][int(r["word_index"])]
        if aw["w"] != r["word"]:
            raise ValueError(f"{r['boundary_id']}: word mismatch {aw['w']} vs {r['word']}")
        manual = parse_time(r["manual_onset_s"])
        err = abs(aw["start"] - manual) * 1000
        rows.append({"boundary_id": r["boundary_id"], "clip_id": r["clip_id"], "word": r["word"],
                     "transition": f"{r['previous_word']} | {r['word']}",
                     "auto_onset_s": aw["start"], "manual_onset_s": round(manual, 3),
                     "abs_error_ms": round(err, 1), "aligner_score": aw.get("score"),
                     "reviewer_note": r["reviewer_note"]})
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    errs = [r["abs_error_ms"] for r in rows]
    summ = {"n_boundaries": len(errs), "boundary_type": "word onset",
            "mean_abs_error_ms": round(statistics.mean(errs), 1),
            "median_abs_error_ms": round(statistics.median(errs), 1),
            "max_abs_error_ms": round(max(errs), 1),
            **{f"n_over_{t}ms": sum(e > t for e in errs) for t in TOLERANCES_MS},
            "note": "manual reference = one annotator (the student), Audacity cursor placement"}
    OUT_JSON.write_text(json.dumps(summ, indent=2), encoding="utf-8")
    print(json.dumps(summ, indent=2))
    if len(errs) < 30:
        print(f"WARNING: only {len(errs)} of 30 boundaries scored")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit({"make-sheet": make_sheet, "score": score}.get(cmd, lambda: print(__doc__) or 2)())
