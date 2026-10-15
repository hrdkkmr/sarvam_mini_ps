"""One command to rebuild everything that can be rebuilt from the current inputs.

Usage:  .venv\\Scripts\\python scripts/run_all.py [--skip-align] [--skip-report]

Steps (each is also runnable on its own):
  1. pytest                                   unit tests
  2. scripts/prepare_audio.py                 only if data/audio/raw has recordings
  3. scripts/run_alignment.py                 only if prepared audio exists
  4. scripts/validate_dataset.py              Sarvam/IndicVoices format checks + manifest
  5. scripts/evaluate_checker.py              checker accuracy on labelled variants
  6. scripts/evaluate_waitk.py                wait-k / EAW simulation + plot
  7. scripts/audit_boundaries.py score        only if the manual sheet has entries
  8. scripts/write_results_md.py              RESULTS.md from the result files
  9. report/build_report.py                   report/submission_report.pdf
A failing step is reported and the remaining steps still run; the exit code is non-zero.
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(name: str, args: list[str]) -> bool:
    print(f"\n=== {name}: {' '.join(args)}")
    r = subprocess.run([PY, *args], cwd=ROOT)
    ok = r.returncode == 0
    print(f"=== {name}: {'OK' if ok else f'FAILED (exit {r.returncode})'}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-align", action="store_true")
    ap.add_argument("--skip-report", action="store_true")
    a = ap.parse_args()
    status = {}
    status["tests"] = run("tests", ["-m", "pytest", "-q"])
    raw = list((ROOT / "data" / "audio" / "raw").glob("clip*.*"))
    if raw:
        status["prepare_audio"] = run("prepare_audio", ["scripts/prepare_audio.py"])
    else:
        print("\n=== prepare_audio: SKIPPED (no recordings in data/audio/raw)")
    if list((ROOT / "data" / "audio").glob("clip*.wav")) and not a.skip_align:
        status["alignment"] = run("alignment", ["scripts/run_alignment.py"])
    else:
        print("=== alignment: SKIPPED (no prepared audio)" if not a.skip_align else "=== alignment: SKIPPED (flag)")
    status["validate"] = run("validate", ["scripts/validate_dataset.py"])
    status["checker"] = run("checker", ["scripts/evaluate_checker.py"])
    status["waitk"] = run("waitk", ["scripts/evaluate_waitk.py"])
    sheet = ROOT / "data" / "annotations" / "boundary_audit_sheet.csv"
    if sheet.exists() and any(r.get("manual_onset_s", "").strip()
                              for r in csv.DictReader(open(sheet, encoding="utf-8-sig"))):
        status["audit"] = run("audit", ["scripts/audit_boundaries.py", "score"])
    else:
        print("=== boundary audit: SKIPPED (manual sheet not filled)")
    status["results_md"] = run("results_md", ["scripts/write_results_md.py"])
    if not a.skip_report:
        status["report"] = run("report", ["report/build_report.py"])
    print("\nSUMMARY:", ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in status.items()))
    return 0 if all(status.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
