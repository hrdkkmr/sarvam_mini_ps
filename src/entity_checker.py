"""Deterministic checker: does an English translation preserve the annotated entities?

Each entity in data/annotations/clips.json has a type and a structured `expected` field.
`check_entity(entity, english, mode)` returns a CheckResult with verdict PASS / FAIL and a
machine-readable reason. Anything the parsers cannot interpret is a FAIL with reason
"not_found" -- an unknown amount is never silently marked correct.

Categories (the `category` used for per-category accuracy):
  name      : person / place / organisation names         expected = {"variants": [...]}
  amount    : money / quantities in lakh, crore, thousand  expected = {"value": float}
  digits    : phone / account numbers                      expected = {"digits": "9876..."}
  time      : clock times                                  expected = {"hhmm": "4:30"}
  negation  : polarity of a predicate                      expected = {"predicates": [...],
                                                                       "polarity": "negative"}
  correction: final value present, abandoned value not     expected = {"kind": amount|digits|
              asserted as fact                                        time, "final", "abandoned"}

mode="fluent": an abandoned value anywhere counts as asserted unless it is directly marked
               as rejected ("not X", "instead of X", "rather than X").
mode="literal": literal translations keep disfluencies, so the abandoned value may appear
               as long as the final value appears *after* it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .number_parser import en_amounts, en_digit_runs, en_times
from .text_utils import en_words, find_subseq

NEG_CUES = {"not", "no", "never", "nothing", "none", "neither", "nor", "without", "cannot",
            "can't", "won't", "don't", "doesn't", "didn't", "isn't", "aren't", "wasn't",
            "weren't", "haven't", "hasn't", "hadn't", "shouldn't", "wouldn't", "couldn't", "mustn't"}
CLAUSE_BREAK = {"but", "and", "because", "so", "although", "though", "while", "if", "then"}
NEG_WINDOW = 4          # negation cue must be within this many words before the predicate
REJECT_MARKERS = (["not"], ["instead", "of"], ["rather", "than"])


@dataclass
class CheckResult:
    entity_id: str
    category: str
    passed: bool
    reason: str
    detail: dict = field(default_factory=dict)


def category_of(entity: dict) -> str:
    t = entity["type"]
    return "name" if t in ("person", "place", "org", "name") else t


# ---------------------------------------------------------------------------------------
def _norm_name(s: str) -> list[str]:
    s = s.replace(".", "")                     # S.B.I. -> SBI
    s = re.sub(r"\b([A-Z]) (?=[A-Z]\b)", r"\1", s)   # S B I -> SBI
    return en_words(s)


def check_name(exp: dict, text: str) -> tuple[bool, str, dict]:
    ws = _norm_name(text)
    for v in exp["variants"]:
        if find_subseq(ws, _norm_name(v)) >= 0:
            return True, "found", {"matched": v}
    return False, "not_found", {}


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(b))


def check_amount(exp: dict, text: str) -> tuple[bool, str, dict]:
    vals = en_amounts(text)
    ok = any(_close(v, exp["value"]) for v in vals)
    return ok, "found" if ok else "not_found", {"parsed_amounts": vals}


def check_digits(exp: dict, text: str) -> tuple[bool, str, dict]:
    runs = en_digit_runs(text)
    ok = exp["digits"] in runs
    return ok, "found" if ok else "not_found", {"digit_runs": runs}


def check_time(exp: dict, text: str) -> tuple[bool, str, dict]:
    times = en_times(text)
    ok = exp["hhmm"] in times
    return ok, "found" if ok else "not_found", {"times": times}


def _predicate_hits(ws: list[str], predicates: list[str]) -> list[int]:
    hits = []
    for p in predicates:
        pw = en_words(p)
        i = find_subseq(ws, pw)
        while i >= 0:
            hits.append(i)
            i = find_subseq(ws, pw, i + 1)
    return sorted(set(hits))


def _negated_at(ws: list[str], i: int) -> bool:
    """Is the predicate at index i negated by a cue in the same clause, <= NEG_WINDOW before?"""
    for j in range(i - 1, max(-1, i - 1 - NEG_WINDOW), -1):
        w = ws[j]
        if w in CLAUSE_BREAK:
            return False
        if w in NEG_CUES or w.endswith("n't"):
            # "not only ..." is not a negation of the predicate
            if w == "not" and j + 1 < len(ws) and ws[j + 1] == "only":
                return False
            return True
    return False


def check_negation(exp: dict, text: str) -> tuple[bool, str, dict]:
    # clause breaks from punctuation: insert a marker token where , ; . occur
    marked = re.sub(r"[,;.!?]", " but ", text)
    ws = en_words(marked)
    hits = _predicate_hits(ws, exp["predicates"])
    if not hits:
        return False, "predicate_not_found", {}
    neg = [_negated_at(ws, i) for i in hits]
    want_neg = exp.get("polarity", "negative") == "negative"
    ok = any(neg) if want_neg else not any(neg)
    return ok, "polarity_ok" if ok else "polarity_wrong", {"negated_hits": neg}


def _value_positions(kind: str, value, text: str) -> list[int]:
    """Whitespace-token indices at which an occurrence of `value` is completed.

    present(n) = the value is expressed inside the 14-token window ending at token n.
    An occurrence is recorded where present flips from False to True, i.e. at the token
    that completes the expression (e.g. 'crore' in 'five crore')."""
    toks = text.split()
    finder = {"amount": lambda t: any(_close(v, value) for v in en_amounts(t)),
              "digits": lambda t: value in en_digit_runs(t),
              "time": lambda t: value in en_times(t)}[kind]
    positions, last = [], False
    for n in range(1, len(toks) + 1):
        # must still be present when 3 more tokens are visible: "at four" inside
        # "at four thirty" is not an occurrence of 4:00
        now = finder(" ".join(toks[max(0, n - 14):n])) and finder(" ".join(toks[max(0, n - 14):n + 3]))
        if now and not last:
            positions.append(n - 1)
        last = now
    return positions


def _is_rejected(text: str, pos: int, kind: str, value) -> bool:
    """Is the abandoned value at token pos explicitly rejected ('not five lakh')?"""
    toks = [t.lower().strip(",.;!?") for t in text.split()]
    # search backwards from the end of the value for the start of its phrase
    for start in range(pos, max(-1, pos - 8), -1):
        before = toks[max(0, start - 2):start]
        for m in REJECT_MARKERS:
            if before[-len(m):] == m:
                return True
    return False


def check_correction(exp: dict, text: str, mode: str) -> tuple[bool, str, dict]:
    kind, final, abandoned = exp["kind"], exp["final"], exp["abandoned"]
    fin_pos = _value_positions(kind, final, text)
    ab_pos = _value_positions(kind, abandoned, text)
    detail = {"final_at": fin_pos, "abandoned_at": ab_pos}
    if not fin_pos:
        return False, "final_missing", detail
    asserted = [p for p in ab_pos if not _is_rejected(text, p, kind, abandoned)]
    if mode == "literal":
        asserted = [p for p in asserted if not any(f > p for f in fin_pos)]
    if asserted:
        return False, "abandoned_asserted", detail
    return True, "final_only", detail


def check_entity(entity: dict, text: str, mode: str = "fluent") -> CheckResult:
    t, exp = entity["type"], entity["expected"]
    cat = category_of(entity)
    if cat == "name":
        ok, why, d = check_name(exp, text)
    elif t == "amount":
        ok, why, d = check_amount(exp, text)
    elif t == "digits":
        ok, why, d = check_digits(exp, text)
    elif t == "time":
        ok, why, d = check_time(exp, text)
    elif t == "negation":
        ok, why, d = check_negation(exp, text)
    elif t == "correction":
        ok, why, d = check_correction(exp, text, mode)
    else:
        raise ValueError(f"unknown entity type {t!r}")
    return CheckResult(entity["id"], cat, ok, why, d)


def check_all(entities: list[dict], text: str, mode: str = "fluent") -> list[CheckResult]:
    return [check_entity(e, text, mode) for e in entities]
