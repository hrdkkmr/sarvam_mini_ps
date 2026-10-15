"""Import the six recordings: convert to mono 16-bit 24 kHz WAV and run quality checks.

Usage:  python scripts/prepare_audio.py
Input : data/audio/raw/clip01.<wav|flac|ogg|mp3|m4a> ... clip06.*   (your recordings)
Output: data/audio/clip01.wav ... (Sarvam format), data/manifests/audio_qc.csv,
        status.audio in data/annotations/clips.json set to "recorded".
Never creates audio: if a recording is missing it is reported as missing.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.audio_utils import TARGET_SR, check, load_mono, quality_report, resample, write_pcm16  # noqa: E402
from src.dataset import CLIPS_JSON  # noqa: E402

RAW = ROOT / "data" / "audio" / "raw"
OUT = ROOT / "data" / "audio"


def main() -> int:
    doc = json.loads(CLIPS_JSON.read_text(encoding="utf-8"))
    rows, missing, failed = [], [], []
    for clip in doc["clips"]:
        cid = clip["clip_id"]
        cands = sorted(p for p in RAW.glob(f"{cid}.*") if not p.name.endswith(".tmp_decode.wav"))
        if not cands:
            missing.append(cid)
            continue
        x, sr = load_mono(cands[0])
        q = quality_report(x, sr)
        problems = check(q)
        y = resample(x, sr, TARGET_SR)
        write_pcm16(OUT / f"{cid}.wav", y, TARGET_SR)
        clip["status"]["audio"] = "recorded"
        clip["audio"] = f"data/audio/{cid}.wav"
        clip["duration"] = round(len(y) / TARGET_SR, 3)
        rows.append({"clip_id": cid, "source_file": cands[0].name, **q,
                     "problems": "; ".join(problems) or "ok"})
        if problems:
            failed.append(cid)
        print(f"{cid}: {q['duration_s']:.2f} s, RMS {q['rms_dbfs']} dBFS -> {'; '.join(problems) or 'ok'}")
    if rows:
        (ROOT / "data" / "manifests").mkdir(parents=True, exist_ok=True)
        with open(ROOT / "data" / "manifests" / "audio_qc.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        CLIPS_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if missing:
        print(f"MISSING recordings (put them in {RAW}): {', '.join(missing)}")
    if failed:
        print(f"Quality problems (re-record or justify): {', '.join(failed)}")
    return 1 if missing or failed else 0


if __name__ == "__main__":
    sys.exit(main())
