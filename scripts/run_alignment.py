"""Forced-align every recorded clip's verbatim transcript with MMS-300m (CTC, romanised).

Usage:  .venv\\Scripts\\python scripts/run_alignment.py [--clips clip01 clip02]
Output: data/alignments/<clip>.json  (timing_source = "mms_fa_auto")
        data/alignments/<clip>.audacity.txt  (import as a label track to inspect)
Clips without audio are skipped and reported; no timings are invented.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.alignment import MODEL_ID, SAMPLE_RATE, MMSAligner, write_alignment, write_audacity_labels  # noqa: E402
from src.audio_utils import load_mono, resample  # noqa: E402
from src.dataset import ALIGN_DIR, clip_hi_text, load_clips  # noqa: E402
from src.text_utils import hi_tokens  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", nargs="*")
    args = ap.parse_args()
    clips = [c for c in load_clips() if not args.clips or c["clip_id"] in args.clips]
    todo = [c for c in clips if (ROOT / "data" / "audio" / f"{c['clip_id']}.wav").exists()]
    skipped = [c["clip_id"] for c in clips if c not in todo]
    if skipped:
        print("No audio (run scripts/prepare_audio.py first):", ", ".join(skipped))
    if not todo:
        return 1
    aligner = MMSAligner()
    try:
        from huggingface_hub import HfApi
        revision = HfApi().model_info(MODEL_ID).sha
    except Exception:                               # offline: record what we can
        revision = "unknown(offline)"
    import uroman
    for c in todo:
        cid = c["clip_id"]
        wav_path = ROOT / "data" / "audio" / f"{cid}.wav"
        x, sr = load_mono(wav_path)
        x16 = resample(x, sr, SAMPLE_RATE)
        words = [t["w"] for t in hi_tokens(clip_hi_text(c))]
        al = aligner.align(x16, words)
        dur = len(x) / sr
        bad = [w for w in al if not (0 <= w.start < w.end <= dur + 1e-3)]
        if bad or any(a.start < b.end - 1e-6 for b, a in zip(al, al[1:])):
            print(f"{cid}: WARNING timing constraint violated: {bad[:3]}")
        meta = {"aligner": "CTC Viterbi (src/alignment.py) on MMS-300m emissions",
                "model": MODEL_ID, "model_revision": revision,
                "romaniser": f"uroman {getattr(uroman, '__version__', '1.3.1.1')} lcode=hin",
                "transcript_status": c["status"]["transcript"]}
        write_alignment(ALIGN_DIR / f"{cid}.json", cid, str(wav_path.relative_to(ROOT)), al, meta)
        write_audacity_labels(ALIGN_DIR / f"{cid}.audacity.txt", al)
        low = [w.w for w in al if w.score < 0.3]
        print(f"{cid}: {len(al)} words aligned, mean score {sum(w.score for w in al)/len(al):.3f}, "
              f"low-score words: {low[:8]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
