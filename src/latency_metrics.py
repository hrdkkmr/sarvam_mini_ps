"""Latency metrics. Every function states its source and its end-of-sequence convention.

Notation: x = source words (|x| of them), y = target words (|y|), g(t) = number of source
words read when target word t (1-indexed) is committed.

1. al_words  -- STACL (Ma et al., ACL 2019, Sec. 4.2, Eq. 9), unit = SOURCE WORDS:
       tau  = min{ t : g(t) = |x| }                         (cut-off step)
       r    = |y| / |x|
       AL   = (1/tau) * sum_{t=1..tau} [ g(t) - (t-1)/r ]
   For wait-k with |x| = |y|, AL = k exactly (paper, below Eq. 8).

2. al_time   -- SimulEval ALScorer (simuleval/evaluator/scorers/latency_scorer.py), unit =
   SECONDS when delays are times:
       AL = (1/tau) * sum_{i=1..tau} [ D_i - (i-1) * |X| / |Y| ]
       tau = first i with D_i >= |X|  (|X| = source duration); if D_1 >= |X| return D_1.
   |Y| is the target length. SimulEval uses the reference length when available; LAAL uses
   max(|Y_hyp|, |Y_ref|). In this simulator the hypothesis IS the reference translation, so
   AL == LAAL and we report one number.

3. end_offset -- SimulEval EndOffsetScorer / Hibiki "End Offset": time the output finishes
   minus source duration (seconds). first_output -- SimulEval StartOffset: delay of the
   first output (here: onset of the first English word, seconds from audio start).

Word-based lag is in words; time-based lag is in seconds. They are never mixed.
"""
from __future__ import annotations


def al_words(g: list[int], src_len: int) -> float:
    if not g:
        raise ValueError("empty policy")
    if any(b < a for a, b in zip(g, g[1:])):
        raise ValueError("g must be non-decreasing")
    if g[-1] != src_len:
        raise ValueError("policy must have read the full source by the last target word")
    r = len(g) / src_len
    tau = next(t for t, gt in enumerate(g, start=1) if gt == src_len)
    return sum(g[t - 1] - (t - 1) / r for t in range(1, tau + 1)) / tau


def al_time(delays: list[float], src_duration: float, tgt_len: int | None = None) -> float:
    """SimulEval-style AL on time delays D_i (seconds of source consumed at commit of word i)."""
    if not delays:
        raise ValueError("empty delays")
    tgt_len = tgt_len or len(delays)
    if delays[0] > src_duration:
        return delays[0]
    gamma = tgt_len / src_duration
    total, tau = 0.0, 0
    for i, d in enumerate(delays):          # i = (index - 1)
        total += d - i / gamma
        tau = i + 1
        if d >= src_duration:
            break
    return total / tau


def average_proportion(g: list[int], src_len: int) -> float:
    """AP (Cho & Esipova 2016), as given in STACL Eq. 7. Reported only for completeness."""
    return sum(g) / (src_len * len(g))


def end_offset(output_end: float, src_duration: float) -> float:
    return output_end - src_duration
