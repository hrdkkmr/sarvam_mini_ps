import numpy as np
import pytest

from src.alignment import ctc_viterbi, words_from_path
from src.latency_metrics import al_time, al_words, average_proportion, end_offset


def test_al_words_rejects_bad_policies():
    with pytest.raises(ValueError):
        al_words([3, 2, 4], 4)          # decreasing
    with pytest.raises(ValueError):
        al_words([1, 2, 3], 4)          # never reads the whole source


def test_al_time_hand_example():
    # source 4.0 s, 4 target words, delays 1,2,3,4 s -> gamma = 1 word/s
    # AL = mean over tau=4 of [D_i - (i-1)] = mean(1,1,1,1) = 1.0 s
    assert al_time([1.0, 2.0, 3.0, 4.0], 4.0) == pytest.approx(1.0)


def test_al_time_stops_at_tau():
    # the second delay already reaches the source end: tau = 2
    # AL = ((2 - 0) + (4 - 1*2)) / 2 = 2.0   (gamma = 2 words / 4 s)
    assert al_time([2.0, 4.0], 4.0) == pytest.approx(2.0)


def test_al_time_first_delay_beyond_source():
    assert al_time([5.0, 5.0], 4.0) == 5.0


def test_average_proportion_wait1_example_from_stacl():
    # STACL Sec 4.1: wait-1 with |x|=|y|=2 has AP 0.75
    assert average_proportion([1, 2], 2) == pytest.approx(0.75)


def test_end_offset():
    assert end_offset(10.5, 9.0) == pytest.approx(1.5)


def test_ctc_viterbi_toy():
    # vocab: 0 blank, 1 'a', 2 'b'. Frames clearly say: blank a a blank b b blank
    seq = [0, 1, 1, 0, 2, 2, 0]
    lp = np.full((len(seq), 3), np.log(0.05))
    for t, c in enumerate(seq):
        lp[t, c] = np.log(0.9)
    path = ctc_viterbi(lp, [1, 2], blank=0)
    ext = np.array([0, 1, 0, 2, 0])
    assert list(ext[path]) == seq
    spans = words_from_path(path, [1, 1], np.exp(lp), ext, sec_per_frame=0.02)
    assert spans[0][:2] == pytest.approx((0.02, 0.06))
    assert spans[1][:2] == pytest.approx((0.08, 0.12))


def test_ctc_viterbi_repeated_label_needs_blank():
    # 'aa' must pass through a blank between the two a's
    seq = [1, 0, 1]
    lp = np.full((3, 2), np.log(0.05))
    for t, c in enumerate(seq):
        lp[t, c] = np.log(0.9)
    path = ctc_viterbi(lp, [1, 1], blank=0)
    assert list(path) == [1, 2, 3]
