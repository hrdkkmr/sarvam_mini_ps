"""Audio I/O, resampling and basic quality checks (numpy/scipy/soundfile only).

Sarvam Part A format: mono, 16-bit PCM, 24 kHz WAV. The aligner needs 16 kHz mono float.
Formats soundfile can read: WAV, FLAC, OGG/Opus, MP3 (libsndfile >= 1.1). Phone recordings
in M4A/AAC need ffmpeg first (see README).
"""
from __future__ import annotations

import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

TARGET_SR = 24_000


def load_mono(path: Path) -> tuple[np.ndarray, int]:
    path = Path(path)
    try:
        x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    except Exception as exc:                       # e.g. .m4a
        if shutil.which("ffmpeg") is None:
            raise RuntimeError(f"cannot read {path.name} ({exc}). Install ffmpeg "
                               "(winget install Gyan.FFmpeg) or export WAV from Audacity.") from exc
        tmp = path.with_suffix(".tmp_decode.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), str(tmp)], check=True)
        x, sr = sf.read(str(tmp), dtype="float32", always_2d=True)
        tmp.unlink()
    return x.mean(axis=1), sr


def resample(x: np.ndarray, sr: int, target: int) -> np.ndarray:
    if sr == target:
        return x
    f = Fraction(target, sr).limit_denominator(1000)
    return resample_poly(x, f.numerator, f.denominator).astype(np.float32)


def quality_report(x: np.ndarray, sr: int) -> dict:
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    frame = int(0.02 * sr)
    n = len(x) // frame
    fr = x[: n * frame].reshape(n, frame) if n else np.zeros((0, frame))
    fr_db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-9) if n else np.array([])
    return {
        "duration_s": round(len(x) / sr, 3),
        "sample_rate_in": sr,
        "peak_dbfs": round(20 * np.log10(peak + 1e-9), 2),
        "rms_dbfs": round(20 * np.log10(rms + 1e-9), 2),
        "clipped_fraction": round(float(np.mean(np.abs(x) >= 0.999)), 6),
        "silent_frame_fraction": round(float(np.mean(fr_db < -50)) if n else 1.0, 3),
    }


# Engineering thresholds (to be calibrated; not published values)
CHECKS = {
    "duration_s": (20.0, 40.0),          # mini PS requirement
    "max_clipped_fraction": 0.001,
    "min_rms_dbfs": -40.0,
    "max_silent_frame_fraction": 0.5,
}


def check(q: dict) -> list[str]:
    problems = []
    lo, hi = CHECKS["duration_s"]
    if not lo <= q["duration_s"] <= hi:
        problems.append(f"duration {q['duration_s']} s outside [{lo}, {hi}]")
    if q["clipped_fraction"] > CHECKS["max_clipped_fraction"]:
        problems.append(f"clipping {q['clipped_fraction']:.4%}")
    if q["rms_dbfs"] < CHECKS["min_rms_dbfs"]:
        problems.append(f"too quiet (RMS {q['rms_dbfs']} dBFS)")
    if q["silent_frame_fraction"] > CHECKS["max_silent_frame_fraction"]:
        problems.append(f"{q['silent_frame_fraction']:.0%} of 20 ms frames are near-silent")
    return problems


def write_pcm16(path: Path, x: np.ndarray, sr: int = TARGET_SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    peak = np.max(np.abs(x)) if len(x) else 0
    if peak > 1.0:
        x = x / peak
    sf.write(str(path), x, sr, subtype="PCM_16")
