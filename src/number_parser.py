"""Deterministic number parsing for Hindi (Devanagari words) and English translations.

Supported (tested) subset
-------------------------
Hindi : cardinals 0-99 (each has its own word in Hindi), सौ/हज़ार/लाख/करोड़/अरब scales,
        fractions डेढ़ (1.5), ढाई (2.5), साढ़े X (X+0.5), सवा X (X+0.25), पौने X (X-0.25),
        Devanagari and ASCII digits, and runs of single digits read out one by one
        (phone / account numbers, e.g. "नौ आठ सात छह" -> "9876").
English: number words 0-99, hundred, thousand, lakh/lac, crore/cr, million, billion,
        "and a half", "k" suffix (25k), digits with Indian or Western grouping (5,00,00,000 /
        50,000,000), decimals (1.5 crore), "rs"/"₹"/"rupees" ignored, digit runs including
        "oh", "double X", "triple X", hyphenated digit groups (98765-43218).
English times: H:MM, "half past H", "quarter past/to H", "H thirty/fifteen/forty-five",
        "H o'clock", "H am/pm", "at H".

NOT supported (returns nothing rather than guessing): ordinals, "half a lakh", Roman
numerals, English number words written in Devanagari (वन, टू ...), Hindi "पौने" before a
scale without a number, dates, "4.30" as a time (parsed as the amount 4.3), number words in
other Indian languages.
"""
from __future__ import annotations

import re

from .text_utils import en_words, fold_hi, hi_tokens

# ---------------------------------------------------------------------------------------
# Hindi lexicon
# ---------------------------------------------------------------------------------------
_HI_0_99 = (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस तीस इकतीस बत्तीस तैंतीस "
    "चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस चालीस इकतालीस बयालीस तैंतालीस चवालीस पैंतालीस "
    "छियालीस सैंतालीस अड़तालीस उनचास पचास इक्यावन बावन तिरेपन चौवन पचपन छप्पन सत्तावन अट्ठावन "
    "उनसठ साठ इकसठ बासठ तिरेसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर सत्तर इकहत्तर बहत्तर "
    "तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उनासी अस्सी इक्यासी बयासी तिरासी चौरासी "
    "पचासी छियासी सत्तासी अट्ठासी नवासी नब्बे इक्यानवे बानवे तिरानवे चौरानवे पचानवे छियानवे "
    "सत्तानवे अट्ठानवे निन्यानवे"
).split()
assert len(_HI_0_99) == 100, len(_HI_0_99)

HI_NUM: dict[str, float] = {fold_hi(w): float(i) for i, w in enumerate(_HI_0_99)}
# common spelling variants
for _w, _v in {"पांच": 5, "छः": 6, "छे": 6, "पन्द्रह": 15, "ज़ीरो": 0, "जीरो": 0, "सून्य": 0,
               "बाइस": 22, "तेइस": 23, "सत्ताइस": 27, "अट्ठाइस": 28, "बावन": 52}.items():
    HI_NUM[fold_hi(_w)] = float(_v)

HI_SCALE = {fold_hi(w): v for w, v in {"सौ": 100, "हज़ार": 1_000, "हजार": 1_000, "लाख": 100_000,
                                         "करोड़": 10_000_000, "करोड": 10_000_000,
                                         "अरब": 1_000_000_000}.items()}
HI_FRACTION = {fold_hi("डेढ़"): 1.5, fold_hi("ढाई"): 2.5}
HI_FRAC_MOD = {fold_hi("साढ़े"): 0.5, fold_hi("सवा"): 0.25, fold_hi("पौने"): -0.25}
_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _hi_basic(word: str) -> float | None:
    f = fold_hi(word)
    if f in HI_NUM:
        return HI_NUM[f]
    if f in HI_FRACTION:
        return HI_FRACTION[f]
    d = word.translate(_DEV_DIGITS).replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", d):
        return float(d)
    return None


def is_hi_number_word(word: str) -> bool:
    f = fold_hi(word)
    return _hi_basic(word) is not None or f in HI_SCALE or f in HI_FRAC_MOD


def is_hi_single_digit(word: str) -> bool:
    v = _hi_basic(word)
    return v is not None and fold_hi(word) not in HI_FRACTION and v == int(v) and 0 <= v <= 9 \
        and not re.fullmatch(r"\d{2,}", word.translate(_DEV_DIGITS))


def parse_hi_amount(words: list[str]) -> float | None:
    """Parse a contiguous Hindi number phrase, e.g. ['साढ़े', 'बारह', 'लाख'] -> 1250000.

    Returns None if any word is not a number word or the phrase is malformed.
    """
    if not words:
        return None
    total, current, pending_mod, seen = 0.0, 0.0, 0.0, False
    for w in words:
        f = fold_hi(w)
        if f in HI_FRAC_MOD:
            if pending_mod:
                return None
            pending_mod = HI_FRAC_MOD[f]
            continue
        b = _hi_basic(w)
        if b is not None:
            current += b + pending_mod
            pending_mod = 0.0
            seen = True
            continue
        if f in HI_SCALE:
            if pending_mod:
                return None
            scale = HI_SCALE[f]
            if scale == 100:
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0.0
            seen = True
            continue
        return None
    if pending_mod:
        return None
    return total + current if seen else None


def hi_spans(text: str) -> list[dict]:
    """Find number spans in a Hindi transcript.

    A run of >=2 consecutive single-digit words is a *digit string* (phone/account number,
    punctuation between groups allowed). Any other maximal run of number words is an
    *amount* parsed with parse_hi_amount.
    Returns [{"kind": "digits"|"amount", "start": i, "end": j (exclusive), "value": ...}].
    """
    htoks = hi_tokens(text)
    toks = [t["w"] for t in htoks]
    spans, i = [], 0
    while i < len(toks):
        if is_hi_single_digit(toks[i]):
            j = i
            # a run continues across ',' but never across a sentence end
            while j < len(toks) and is_hi_single_digit(toks[j]) and \
                    (j == i or not any(c in htoks[j - 1]["punct"] for c in "।?!.")):
                j += 1
            if j - i >= 2:
                digits = "".join(str(int(_hi_basic(t))) for t in toks[i:j])
                spans.append({"kind": "digits", "start": i, "end": j, "value": digits})
                i = j
                continue
        if is_hi_number_word(toks[i]):
            j = i
            while j < len(toks) and is_hi_number_word(toks[j]):
                j += 1
            val = parse_hi_amount(toks[i:j])
            spans.append({"kind": "amount", "start": i, "end": j, "value": val})
            i = j
            continue
        i += 1
    return spans


# ---------------------------------------------------------------------------------------
# English
# ---------------------------------------------------------------------------------------
EN_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
EN_TENS = {w: 10 * (i + 2) for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split())}
EN_SCALE = {"thousand": 1e3, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5,
            "million": 1e6, "crore": 1e7, "crores": 1e7, "cr": 1e7, "billion": 1e9}
EN_DIGIT_WORDS = {**{w: str(i) for w, i in EN_UNITS.items() if i < 10}, "oh": "0", "o": "0"}
CURRENCY = {"rs", "rs.", "inr", "rupees", "rupee", "₹"}


def _en_numeric(tok: str) -> float | None:
    t = tok.lstrip("₹").replace(",", "")
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(k)?", t)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1000 if m.group(2) else v


def _is_en_digit_token(tok: str) -> bool:
    return tok in EN_DIGIT_WORDS or re.fullmatch(r"\d", tok) is not None


def en_digit_runs(text: str, min_len: int = 4) -> list[str]:
    """Digit strings read out in English: 'nine eight seven six, five four ...', 'double
    five', '98765-43218', '9876543218'. Commas / hyphens between groups do not break a run;
    a sentence end (. ? !) does. Returns runs with at least min_len digits."""
    raw = re.sub(r"(?<=\d)-(?=\d)", " ", text)   # 98765-43218 -> two groups
    raw = re.sub(r"(?<!\d)[.?!](?!\d)", " | ", raw)   # sentence end -> explicit break token
    ws = [w for t in raw.split() for w in (["|"] if t == "|" else en_words(t))]
    runs, cur, i = [], "", 0
    while i < len(ws):
        w = ws[i]
        mult = {"double": 2, "triple": 3}.get(w)
        if mult and i + 1 < len(ws) and _is_en_digit_token(ws[i + 1]):
            cur += EN_DIGIT_WORDS.get(ws[i + 1], ws[i + 1]) * mult
            i += 2
            continue
        if _is_en_digit_token(w):
            cur += EN_DIGIT_WORDS.get(w, w)
        elif re.fullmatch(r"\d{2,}", w):
            cur += w
        else:
            if len(cur) >= min_len:
                runs.append(cur)
            cur = ""
        i += 1
    if len(cur) >= min_len:
        runs.append(cur)
    return runs


def _digit_run_mask(ws: list[str]) -> list[bool]:
    """Mark tokens that belong to a run of >=2 single-digit words (these are digit strings,
    not amounts: 'four four two seven' must not be summed to 17)."""
    mask = [False] * len(ws)
    i = 0
    while i < len(ws):
        if ws[i] in EN_DIGIT_WORDS and ws[i] not in ("o",):
            j = i
            while j < len(ws) and (ws[j] in EN_DIGIT_WORDS or ws[j] in ("double", "triple")):
                j += 1
            if j - i >= 2:
                for k in range(i, j):
                    mask[k] = True
            i = max(j, i + 1)
        else:
            i += 1
    return mask


def en_amounts(text: str) -> list[float]:
    """All amount values expressed in an English text (excluding digit strings)."""
    ws = en_words(text)
    mask = _digit_run_mask(ws)
    vals: list[float] = []
    total = current = 0.0
    active = False

    def flush():
        nonlocal total, current, active
        if active:
            vals.append(total + current)
        total = current = 0.0
        active = False

    i = 0
    while i < len(ws):
        w = ws[i]
        if mask[i]:
            flush(); i += 1; continue
        num = _en_numeric(w)
        if num is not None and not re.fullmatch(r"\d{1,2}:\d{2}", w):
            if active and current and not total:
                flush()           # two bare numbers in a row are two amounts
            current += num
            active = True
        elif w in EN_UNITS and w != "o":
            current += EN_UNITS[w]; active = True
        elif w in EN_TENS:
            current += EN_TENS[w]; active = True
        elif w == "hundred" and active:
            current = (current or 1) * 100
        elif w in EN_SCALE and active:
            total += (current or 1) * EN_SCALE[w]
            current = 0.0
        elif w == "and" and active and i + 2 < len(ws) and ws[i + 1] == "a" and ws[i + 2] == "half":
            current += 0.5
            i += 3
            continue
        elif w == "and" and active and i + 1 < len(ws) and (ws[i + 1] in EN_UNITS or ws[i + 1] in EN_TENS):
            pass                  # "one hundred and five"
        elif w in CURRENCY:
            pass                  # "Rs 5 crore", "5 crore rupees"
        else:
            flush()
        i += 1
    flush()
    return vals


_HOUR_WORD = {**{w: v for w, v in EN_UNITS.items() if 1 <= v <= 12}}


def _hour(tok: str) -> int | None:
    if tok in _HOUR_WORD:
        return _HOUR_WORD[tok]
    if re.fullmatch(r"\d{1,2}", tok) and 1 <= int(tok) <= 12:
        return int(tok)
    return None


def en_times(text: str) -> list[str]:
    """Clock times as 'H:MM' (12-hour, no am/pm disambiguation)."""
    ws = en_words(text)
    out = []
    for i, w in enumerate(ws):
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", w)
        if m:
            out.append(f"{int(m.group(1))}:{m.group(2)}")
            continue
        nxt = ws[i + 1] if i + 1 < len(ws) else ""
        nxt2 = ws[i + 2] if i + 2 < len(ws) else ""
        if w == "half" and nxt == "past" and _hour(nxt2):
            out.append(f"{_hour(nxt2)}:30")
        elif w == "quarter" and nxt == "past" and _hour(nxt2):
            out.append(f"{_hour(nxt2)}:15")
        elif w == "quarter" and nxt == "to" and _hour(nxt2):
            out.append(f"{(_hour(nxt2) - 2) % 12 + 1}:45")
        elif _hour(w) and nxt in ("thirty", "fifteen") and not (i > 0 and ws[i - 1] in ("past", "to")):
            out.append(f"{_hour(w)}:{30 if nxt == 'thirty' else 15}")
        elif _hour(w) and nxt == "forty" and nxt2 == "five":
            out.append(f"{_hour(w)}:45")
        elif _hour(w) and nxt in ("o'clock", "oclock", "am", "pm", "a.m", "p.m"):
            out.append(f"{_hour(w)}:00")
        elif w == "at" and _hour(nxt) and nxt2 not in ("thirty", "fifteen", "forty", ":"):
            out.append(f"{_hour(nxt)}:00")
    # "at four o'clock" is found twice; de-duplicate consecutive identical hits
    dedup = []
    for t in out:
        if not dedup or dedup[-1] != t:
            dedup.append(t)
    return dedup
