"""Rule-based risk detectors and the entity-aware adaptive waiting (EAW) read schedule.

This is a deterministic heuristic, NOT a calibrated uncertainty model. It only uses
information a streaming system would have at decision time:
  * the source words read so far (in a real system these would come from a streaming
    recogniser; here they come from the verbatim transcript -- an optimistic assumption),
  * the timing of words read so far (pauses), and
  * the target word the system is about to commit (a real system knows its own candidate).
It never looks at source words that have not yet been read.

Rules
-----
R1  risky_target(token): number word / digit / scale word (lakh, crore, thousand ...),
    negation cue (not, no, never, n't ...), or a capitalised word that is not
    sentence-initial (proxy for a name).
R2  risky_source(word): Hindi number / scale / fraction word, negation particle
    (नहीं, ना, न, मत), or self-correction marker (सॉरी, मतलब, अरे, मिनट, sorry).
EAW-lex   : before committing a risky target word, keep reading while any of the last
            POST_WAIT read source words is risky (i.e. wait until POST_WAIT words have passed
            since the last risky source word -- this is the window in which "नहीं नहीं, ..."
            corrections and post-number scale words arrive).
EAW-pause : EAW-lex, then additionally keep reading until a pause >= PAUSE_S has been
            observed after the last read word (a proxy for a clause end; Hindi clauses are
            verb-final, so a clause end usually means the verb and its negation are heard).
            Observing a pause costs PAUSE_S of wall-clock time, which is added to the decision.
Both  : extra reading is capped at MAX_EXTRA words beyond the wait-k schedule; at the end of
        input everything remaining is released (no extra waiting is possible after input_end).
"""
from __future__ import annotations

import re

from .number_parser import EN_DIGIT_WORDS, EN_SCALE, EN_TENS, EN_UNITS, is_hi_number_word
from .entity_checker import NEG_CUES
from .text_utils import fold_hi, en_norm_token

POST_WAIT = 2
MAX_EXTRA = 6
PAUSE_S = 0.30

HI_NEG = {fold_hi(w) for w in ("नहीं", "नही", "ना", "न", "मत")}
HI_CORR = {fold_hi(w) for w in ("सॉरी", "मतलब", "अरे", "मिनट", "sorry", "यानी")}


def risky_source(word: str) -> bool:
    f = fold_hi(word)
    return is_hi_number_word(word) or f in HI_NEG or f in HI_CORR


def risky_target(tokens: list[str], t: int) -> bool:
    raw = tokens[t]
    w = en_norm_token(raw)
    if not w:
        return False
    if re.search(r"\d", w) or w in EN_UNITS or w in EN_TENS or w in EN_SCALE or w in EN_DIGIT_WORDS \
            or w in ("hundred", "half"):
        return True
    if w in NEG_CUES or w.endswith("n't"):
        return True
    sentence_initial = t == 0 or tokens[t - 1].rstrip("\"')").endswith((".", "?", "!"))
    return raw[:1].isupper() and not sentence_initial and w != "i"


def waitk_schedule(n_src: int, n_tgt: int, k: int | None) -> list[int]:
    """STACL Eq. 6: g(t) = min(k + t - 1, |x|), t = 1..|y|. k=None means full sentence."""
    if k is None:
        return [n_src] * n_tgt
    return [min(k + t - 1, n_src) for t in range(1, n_tgt + 1)]


def _pause_after(src_words: list[dict], j: int) -> float:
    """Silence after the j-th read word (j = count, 1-indexed). Last word: infinite."""
    if j >= len(src_words):
        return float("inf")
    return src_words[j]["start"] - src_words[j - 1]["end"]


def eaw_schedule(src_words: list[dict], tgt_tokens: list[str], k: int, use_pause: bool,
                 post_wait: int = POST_WAIT, max_extra: int = MAX_EXTRA,
                 pause_s: float = PAUSE_S) -> tuple[list[int], list[bool], list[str]]:
    """Return (g, pause_wait_flags, reasons) for the entity-aware adaptive policy."""
    n = len(src_words)
    base = waitk_schedule(n, len(tgt_tokens), k)
    g, waited_pause, reasons = [], [], []
    prev = 0
    for t, b in enumerate(base):
        j = max(prev, b)
        why = "waitk"
        used_pause = False
        if risky_target(tgt_tokens, t):
            cap = min(n, b + max_extra)
            while j < cap and any(risky_source(src_words[i]["w"]) for i in range(max(0, j - post_wait), j)):
                j += 1
                why = "lex_wait"
            if use_pause:
                while j < cap and _pause_after(src_words, j) < pause_s:
                    j += 1
                    why = "pause_wait"
                used_pause = j < n and _pause_after(src_words, j) >= pause_s
            if j == cap and cap < n and why != "waitk":
                why += "_capped"
        g.append(j)
        waited_pause.append(used_pause)
        reasons.append(why)
        prev = j
    return g, waited_pause, reasons
