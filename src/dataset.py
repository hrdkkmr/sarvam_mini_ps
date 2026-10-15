"""Load clip annotations and word timings; resolve entity positions.

Timing sources, in order of preference (recorded in every output row as `timing_source`):
  "mms_fa_auto"            : data/alignments/<clip>.json written by scripts/run_alignment.py
  "manual"                 : data/alignments/<clip>.manual.json (hand-marked, e.g. Audacity)
  "placeholder_estimate"   : NOT FROM AUDIO. Durations estimated from character counts so
                             that the pipeline can be exercised before recordings exist.
                             Results computed from these must never be reported as measured.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .text_utils import SENT_FINAL, en_tokens, en_norm_token, find_subseq, fold_hi, hi_tokens

ROOT = Path(__file__).resolve().parents[1]
CLIPS_JSON = ROOT / "data" / "annotations" / "clips.json"
ALIGN_DIR = ROOT / "data" / "alignments"

# placeholder timing model (documented engineering guess, NOT a measurement)
PH_SEC_PER_CHAR = 0.075
PH_MIN_WORD = 0.18
PH_GAP = 0.04
PH_PAUSE = {"…": 0.6, ",": 0.25, "।": 0.45, "?": 0.45, ".": 0.45}


@dataclass
class Clip:
    clip_id: str
    raw: dict
    src_words: list[dict]            # [{"w","punct","start","end"}]
    tgt_tokens: list[str]            # fluent English, whitespace tokens
    tgt_literal: str
    tgt_fluent: str
    entities: list[dict]
    timing_source: str
    sentence_ends: list[int] = field(default_factory=list)   # source word idx ending a sentence
    src_sent_last: list[int] = field(default_factory=list)   # per sentence: count of src words up to its end
    tgt_sent: list[int] = field(default_factory=list)        # per target token: sentence index

    @property
    def src_end_time(self) -> float:
        return self.src_words[-1]["end"]


def load_clips(path: Path = CLIPS_JSON) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["clips"]


def clip_hi_text(raw: dict) -> str:
    return " ".join(s["hi_text"] for s in raw["sentences"])


def placeholder_timings(words: list[dict], t0: float = 0.3) -> list[dict]:
    t, out = t0, []
    for w in words:
        dur = max(PH_MIN_WORD, PH_SEC_PER_CHAR * len(w["w"]))
        out.append({**w, "start": round(t, 3), "end": round(t + dur, 3)})
        t += dur + PH_GAP + max((PH_PAUSE.get(c, 0.0) for c in w["punct"]), default=0.0)
    return out


def load_timings(raw: dict, prefer: str | None = None) -> tuple[list[dict], str]:
    words = hi_tokens(clip_hi_text(raw))
    candidates = [("mms_fa_auto", ALIGN_DIR / f"{raw['clip_id']}.json"),
                  ("manual", ALIGN_DIR / f"{raw['clip_id']}.manual.json")]
    if prefer:
        candidates = [c for c in candidates if c[0] == prefer] + [c for c in candidates if c[0] != prefer]
    for source, p in candidates:
        if p.exists():
            al = json.loads(p.read_text(encoding="utf-8"))
            aw = al["words"]
            if [fold_hi(a["w"]) for a in aw] != [fold_hi(w["w"]) for w in words]:
                raise ValueError(f"{p}: aligned words do not match the transcript in clips.json; "
                                 "re-run scripts/run_alignment.py after editing the transcript")
            return [{**w, "start": a["start"], "end": a["end"]} for w, a in zip(words, aw)], source
    return placeholder_timings(words), "placeholder_estimate"


def resolve_src_index(src_words: list[dict], phrase: str, occurrence: int = 1) -> int:
    """Index of the LAST word of the occurrence-th match of phrase: the source word whose
    arrival makes the entity determinable ("determining index")."""
    hay = [fold_hi(w["w"]) for w in src_words]
    needle = [fold_hi(t["w"]) for t in hi_tokens(phrase)]
    i, n = -1, 0
    while n < occurrence:
        i = find_subseq(hay, needle, i + 1)
        if i < 0:
            raise ValueError(f"source phrase {phrase!r} (occurrence {occurrence}) not in transcript")
        n += 1
    return i + len(needle) - 1


def resolve_tgt_index(tgt_tokens: list[str], phrase: str, occurrence: int = 1) -> int:
    """Index of the FIRST target token of the occurrence-th match of phrase in the fluent
    translation (the commit point). Matching ignores case and punctuation."""
    hay = [en_norm_token(t) for t in tgt_tokens]
    needle = [en_norm_token(t) for t in phrase.split()]
    i = -1
    for _ in range(occurrence):
        i = find_subseq(hay, needle, i + 1)
        if i < 0:
            raise ValueError(f"target phrase {phrase!r} (occurrence {occurrence}) not in fluent translation")
    return i


def build_clip(raw: dict, prefer_timing: str | None = None) -> Clip:
    words, source = load_timings(raw, prefer_timing)
    fluent = " ".join(s["en_fluent"] for s in raw["sentences"])
    literal = " ".join(s["en_literal"] for s in raw["sentences"])
    tgt = en_tokens(fluent)
    ents = []
    for e in raw["entities"]:
        e = dict(e)
        e["src_idx"] = resolve_src_index(words, e["src_phrase"], e.get("src_occurrence", 1))
        e["tgt_idx"] = resolve_tgt_index(tgt, e["en_phrase"], e.get("en_occurrence", 1))
        ents.append(e)
    spans = sorted((e["tgt_idx"], e["tgt_idx"] + len(e["en_phrase"].split()), e["id"]) for e in ents)
    for (a0, a1, ida), (b0, b1, idb) in zip(spans, spans[1:]):
        if b0 < a1:
            raise ValueError(f"{raw['clip_id']}: target spans of {ida} and {idb} overlap")
    ends = [i for i, w in enumerate(words) if any(c in w["punct"] for c in SENT_FINAL)]
    src_last, tgt_sent, n_src = [], [], 0
    for si, s in enumerate(raw["sentences"]):
        n_src += len(hi_tokens(s["hi_text"]))
        src_last.append(n_src)
        tgt_sent += [si] * len(en_tokens(s["en_fluent"]))
    assert n_src == len(words) and len(tgt_sent) == len(tgt)
    return Clip(raw["clip_id"], raw, words, tgt, literal, fluent, ents, source, ends, src_last, tgt_sent)


def load_all(prefer_timing: str | None = None) -> list[Clip]:
    return [build_clip(r, prefer_timing) for r in load_clips()]
