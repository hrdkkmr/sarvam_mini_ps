"""Validate annotations against the Sarvam Part A rules and build the §5.2 JSONL manifest.

Usage:  python scripts/validate_dataset.py
Checks (errors make the exit code non-zero; warnings are printed):
  transcript (IndicVoices Level 1 / Sarvam §3): no Latin letters, no digits, no brackets,
      every sentence ends with sentence-final punctuation;
  entity annotations: every src_phrase / en_phrase resolves; every Hindi amount annotated in an
      entity parses (src/number_parser.py) to the value the entity expects;
  timings (§5.2): ordered, non-negative, inside the clip; source of every timing recorded;
  status: unverified transcripts / unreviewed translations are reported as warnings.
Writes data/manifests/part_a_manifest.jsonl only for clips that have audio and automatic or
manual timings (records without real audio are never written).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import soundfile as sf  # noqa: E402

from src.dataset import build_clip, load_clips  # noqa: E402
from src.number_parser import parse_hi_amount  # noqa: E402
from src.text_utils import SENT_FINAL, hi_tokens  # noqa: E402


def main() -> int:
    errors, warnings, records = [], [], []
    for raw in load_clips():
        cid = raw["clip_id"]
        for i, s in enumerate(raw["sentences"]):
            t = s["hi_text"]
            if re.search(r"[A-Za-z]", t):
                errors.append(f"{cid} s{i}: Latin letters in Hindi transcript (write English words in Devanagari)")
            if re.search(r"[0-9०-९]", t):
                errors.append(f"{cid} s{i}: digits in transcript (write numbers as spoken words)")
            if re.search(r"[\[\]()]", t):
                warnings.append(f"{cid} s{i}: brackets found (noise tags are optional; bracketed Latin forms are not allowed)")
            if not t.rstrip().endswith(SENT_FINAL):
                errors.append(f"{cid} s{i}: sentence does not end with sentence-final punctuation")
        try:
            clip = build_clip(raw)
        except ValueError as exc:
            errors.append(f"{cid}: {exc}")
            continue
        for e in clip.entities:
            exp = e["expected"]
            val = exp.get("value", exp.get("final") if exp.get("kind") == "amount" else None)
            if e["type"] in ("amount",) or (e["type"] == "correction" and exp["kind"] == "amount"):
                words = [t["w"] for t in hi_tokens(e["src_phrase"])]
                got = parse_hi_amount(words)
                if got is None or abs(got - val) > 1e-6:
                    errors.append(f"{cid} {e['id']}: Hindi '{e['src_phrase']}' parses to {got}, annotation says {val}")
        st = raw["status"]
        if st["transcript"] != "verbatim_verified":
            warnings.append(f"{cid}: transcript status '{st['transcript']}' (not yet checked against audio)")
        if st["translation"] != "human_reviewed":
            warnings.append(f"{cid}: translation status '{st['translation']}'")
        w = clip.src_words
        if any(a["start"] < 0 or a["end"] <= a["start"] for a in w) or \
                any(b["start"] < a["end"] - 1e-6 for a, b in zip(w, w[1:])):
            errors.append(f"{cid}: word timings not ordered / non-negative")
        audio = ROOT / "data" / "audio" / f"{cid}.wav"
        if not audio.exists():
            warnings.append(f"{cid}: no audio yet; manifest record not written")
            continue
        info = sf.info(str(audio))
        dur = info.frames / info.samplerate
        if (info.samplerate, info.channels, info.subtype) != (24000, 1, "PCM_16"):
            errors.append(f"{cid}: audio is {info.samplerate} Hz/{info.channels} ch/{info.subtype}, need 24000/1/PCM_16")
        if w[-1]["end"] > dur + 1e-3:
            errors.append(f"{cid}: word times exceed clip duration")
        if clip.timing_source == "placeholder_estimate":
            warnings.append(f"{cid}: audio exists but no alignment yet; manifest record not written")
            continue
        # sentence time spans from word times
        sents, k = [], 0
        for s in raw["sentences"]:
            n = len(hi_tokens(s["hi_text"]))
            sents.append({"hi_text": s["hi_text"], "hi_start": w[k]["start"], "hi_end": w[k + n - 1]["end"],
                          "en_text": s["en_fluent"], "en_alt": [s["en_literal"]]})
            k += n
        records.append({
            "id": f"rec-{cid}", "audio": f"audio/{cid}.wav", "duration": round(dur, 3),
            "speaker_id": raw["speaker_id"],
            "source": {"corpus": "own-recordings-mini-ps", "source_file": f"raw/{cid}",
                       "start": 0.0, "end": round(dur, 3), "synthetic": False},
            "sentences": sents,
            "hi_words": [{"w": a["w"], "start": a["start"], "end": a["end"]} for a in w],
            "translation_method": "LLM draft (Claude, this project) reviewed by the student"
                                  if st["translation"] == "human_reviewed" else
                                  "LLM draft (Claude, this project); human review PENDING",
            "timing_source": clip.timing_source,
        })
    out = ROOT / "data" / "manifests" / "part_a_manifest.jsonl"
    if records:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        print(f"wrote {len(records)} records to {out}")
    for m in warnings:
        print("WARNING:", m)
    for m in errors:
        print("ERROR:", m)
    print(f"{len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
