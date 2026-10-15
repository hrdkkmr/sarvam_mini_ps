import pytest

from src.adaptive_policy import eaw_schedule, risky_target, waitk_schedule
from src.dataset import load_all
from src.latency_metrics import al_words
from src.waitk_simulator import DEFAULT_POLICIES, Policy, simulate

# Part A appendix example: मैंने कल अपना पुराना बैंक खाता बंद करवा दिया (9 words)
# -> "Yesterday I got my old bank account closed" (8 words)


def test_wait3_schedule_part_a():
    assert waitk_schedule(9, 8, 3) == [3, 4, 5, 6, 7, 8, 9, 9]


def test_wait3_al_part_a_by_hand():
    # tau = 7 (first t with g(t)=9); r = 8/9
    # AL = (1/7) * sum_{t=1..7} [g(t) - (t-1)*9/8] = (42 - 21*1.125)/7 = 2.625
    assert al_words(waitk_schedule(9, 8, 3), 9) == pytest.approx(2.625)


def test_waitk_al_equals_k_when_lengths_equal():
    for k in (1, 2, 3, 5):
        g = waitk_schedule(10, 10, k)
        assert al_words(g, 10) == pytest.approx(k)


def test_full_sentence_schedule():
    assert waitk_schedule(5, 3, None) == [5, 5, 5]


def _words(ws, gap=0.1, dur=0.3):
    t, out = 0.0, []
    for w in ws:
        out.append({"w": w, "punct": "", "start": t, "end": t + dur})
        t += dur + gap
    return out


def test_eaw_waits_after_number_and_correction():
    src = _words("राशि पाँच लाख नहीं नहीं पाँच करोड़ रुपये का है".split())
    tgt = "The amount is five crore rupees".split()
    g, _, reasons = eaw_schedule(src, tgt, k=2, use_pause=False)
    # 'five' (t=4) is risky; under wait-2 it would be released after 5 words (... नहीं)
    assert waitk_schedule(len(src), len(tgt), 2)[3] == 5
    # EAW keeps reading until 2 words have passed since the last risky source word
    assert g[3] >= 9 and reasons[3].startswith("lex_wait")
    assert all(b >= a for a, b in zip(g, g[1:]))


def test_eaw_is_causal():
    """Changing words AFTER the read position must not change earlier decisions."""
    a = _words("मैं कल बैंक गया और वहाँ पाँच लाख जमा किए".split())
    b = _words("मैं कल बैंक गया और वहाँ कुछ नहीं हुआ ठीक".split())
    tgt = "I went to the bank yesterday and there".split()
    ga, _, _ = eaw_schedule(a, tgt, k=2, use_pause=False)
    gb, _, _ = eaw_schedule(b, tgt, k=2, use_pause=False)
    # the first 6 source words are identical; any decision taken with <= 6 words read must match
    for x, y in zip(ga, gb):
        if x <= 6 or y <= 6:
            assert x == y


def test_risky_target_detector():
    toks = "Yes, my name is Rahul and I did not pay five crore".split()
    flags = [risky_target(toks, i) for i in range(len(toks))]
    assert flags[toks.index("Rahul")] and flags[toks.index("not")] and flags[toks.index("five")]
    assert not flags[0] and not flags[toks.index("I")]


def test_simulation_on_annotated_clips_is_deterministic_and_valid():
    clips = load_all()
    for p in DEFAULT_POLICIES:
        for c in clips:
            r1, r2 = simulate(c, p), simulate(c, p)
            assert r1.g == r2.g and r1.onset_s == r2.onset_s
            assert r1.g[-1] == len(c.src_words)                     # EOS convention
            assert all(b >= a for a, b in zip(r1.onset_s, r1.onset_s[1:]))
            assert all(o >= d - 1e-9 for o, d in zip(r1.onset_s, r1.decision_s))


def test_whole_clip_policy_is_evidence_safe():
    for c in load_all():
        r = simulate(c, Policy("whole", "full"))
        assert r.metrics["evidence_safe"] == r.metrics["n_entities"]


def test_larger_k_never_less_safe():
    for c in load_all():
        safe = [simulate(c, Policy("w", "waitk", k)).metrics["evidence_safe"] for k in (1, 2, 3, 5, 7)]
        assert safe == sorted(safe)
