"""Tokenisation and normalisation shared by every module.

Source (Hindi) tokenisation: split the verbatim transcript on whitespace; leading/trailing
punctuation is stripped from each token and kept separately. This is exactly the word list
that is forced-aligned, so word index i in the transcript == word index i in the alignment.

Target (English) tokenisation: split the translation on whitespace. Punctuation stays
attached for display but is stripped for matching. One whitespace token == one "target word"
for wait-k and Average Lagging.
"""
from __future__ import annotations

import re
import unicodedata

# Punctuation that may be attached to a Hindi/English token. "…" is a hesitation mark.
PUNCT = "।॥,.?!;:…\"'“”‘’()[]{}-–—"
SENT_FINAL = ("।", "?", "!", ".")


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def split_punct(tok: str) -> tuple[str, str, str]:
    """Return (leading punct, core word, trailing punct)."""
    start, end = 0, len(tok)
    while start < end and tok[start] in PUNCT:
        start += 1
    while end > start and tok[end - 1] in PUNCT:
        end -= 1
    return tok[:start], tok[start:end], tok[end:]


def hi_tokens(text: str) -> list[dict]:
    """Tokenise a verbatim Devanagari transcript into words.

    Returns a list of {"w": core word, "punct": trailing punctuation}. Tokens that are pure
    punctuation (e.g. a stand-alone "…") are attached to the previous word's punct.
    """
    out: list[dict] = []
    for raw in nfc(text).split():
        _, core, trail = split_punct(raw)
        if not core:
            if out:
                out[-1]["punct"] += raw
            continue
        out.append({"w": core, "punct": trail})
    return out


# Devanagari folding used only for *matching* (lexicon lookup), never for stored transcripts.
_NUKTA_MAP = {"क़": "क", "ख़": "ख", "ग़": "ग", "ज़": "ज", "ड़": "ड", "ढ़": "ढ", "फ़": "फ", "य़": "य"}


def fold_hi(word: str) -> str:
    """Fold common Devanagari spelling variants: nukta, chandrabindu->anusvara, visarga."""
    w = nfc(word)
    w = unicodedata.normalize("NFD", w).replace("़", "")  # strip nukta
    w = unicodedata.normalize("NFC", w)
    for k, v in _NUKTA_MAP.items():
        w = w.replace(k, v)
    w = w.replace("ँ", "ं").replace("ः", "")
    return w


def en_tokens(text: str) -> list[str]:
    return nfc(text).split()


def en_norm_token(tok: str) -> str:
    """Lowercase and strip surrounding punctuation (keeps internal ' and : and ,)."""
    _, core, _ = split_punct(tok.replace("’", "'"))
    core = core.lower()
    return core[:-2] if core.endswith("'s") else core    # possessive: crore's -> crore


def en_words(text: str) -> list[str]:
    """Normalised English word list for matching. Splits 'four-thirty' style hyphens."""
    out = []
    for t in en_tokens(text):
        core = en_norm_token(t)
        if not core:
            continue
        # keep digit groupings like 25,000 / 1.5 / 4:30 intact, split word-hyphens
        if re.fullmatch(r"[\d,.:₹]+", core):
            out.append(core)
        else:
            out.extend(p for p in re.split(r"-", core) if p)
    return out


def find_subseq(hay: list[str], needle: list[str], start: int = 0) -> int:
    """Index of first occurrence of needle in hay at/after start, else -1."""
    n = len(needle)
    for i in range(start, len(hay) - n + 1):
        if hay[i:i + n] == needle:
            return i
    return -1
