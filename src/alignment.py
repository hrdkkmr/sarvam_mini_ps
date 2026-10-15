"""CTC forced alignment of a Devanagari transcript to audio.

Pipeline (same algorithm family as the supplied torchaudio tutorial, adapted to Hindi):
  1. romanise each Devanagari word with uroman (MMS forced-alignment models use a romanised
     character vocabulary; the original Devanagari word is kept and only the romanisation
     is aligned),
  2. frame-wise log-probabilities (emissions) from the MMS-300m forced-alignment wav2vec2
     model (MahmoudAshraf/mms-300m-1130-forced-aligner, the HF port of torchaudio's
     MMS_FA bundle; CC-BY-NC-4.0 weights) at 16 kHz, one frame per 20 ms,
  3. CTC Viterbi alignment (ctc_viterbi below) over the blank-interleaved label sequence,
  4. word start = first frame of its first character, end = last frame of its last
     character; score = mean posterior of its character frames.

Why not torchaudio.functional.forced_align: the supplied tutorial notes the torchaudio
alignment APIs were deprecated in 2.8 and removed in 2.9, and this machine has torch 2.14.
The Viterbi recursion is ~40 lines of numpy, which also makes it explainable in a viva.

Known timing risks: uroman keeps inherent schwas (अपना -> "apanaa") so romanised words are
longer than what is spoken; nasalisation/nukta are approximated; English words written in
Devanagari are romanised phonetically (ऑफिस -> "ophis"); the model frame rate limits
resolution to 20 ms; CTC peaky behaviour makes word ENDs less reliable than STARTs.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MODEL_ID = "MahmoudAshraf/mms-300m-1130-forced-aligner"
SAMPLE_RATE = 16_000


@dataclass
class WordAlign:
    w: str
    roman: str
    start: float
    end: float
    score: float


def ctc_viterbi(log_probs: np.ndarray, tokens: list[int], blank: int = 0) -> np.ndarray:
    """Most likely CTC path for `tokens` through `log_probs` (T x V, log-softmaxed).

    The label sequence is extended with blanks: [b, t1, b, t2, b, ..., tL, b] (S = 2L+1).
    State s at frame t may come from s (stay), s-1 (advance), or s-2 (skip a blank, allowed
    only if ext[s] is not blank and ext[s] != ext[s-2]). Returns for each frame the index of
    the state (in the extended sequence) on the best path.
    """
    T = log_probs.shape[0]
    L = len(tokens)
    S = 2 * L + 1
    if T < L:
        raise ValueError(f"audio too short: {T} frames for {L} labels")
    ext = np.full(S, blank, dtype=np.int64)
    ext[1::2] = tokens
    skip_ok = np.zeros(S, dtype=bool)
    skip_ok[2:] = (ext[2:] != blank) & (ext[2:] != ext[:-2])

    NEG = -1e30
    dp = np.full(S, NEG)
    dp[0] = log_probs[0, ext[0]]
    dp[1] = log_probs[0, ext[1]]
    back = np.zeros((T, S), dtype=np.int8)        # 0 stay, 1 from s-1, 2 from s-2
    for t in range(1, T):
        stay = dp
        adv = np.concatenate(([NEG], dp[:-1]))
        skp = np.where(skip_ok, np.concatenate(([NEG, NEG], dp[:-2])), NEG)
        cand = np.stack([stay, adv, skp])
        choice = cand.argmax(axis=0)
        dp = cand[choice, np.arange(S)] + log_probs[t, ext]
        back[t] = choice
    # the path must end in the last label or the final blank
    s = S - 1 if dp[S - 1] >= dp[S - 2] else S - 2
    path = np.empty(T, dtype=np.int64)
    for t in range(T - 1, -1, -1):
        path[t] = s
        s -= int(back[t, s])
    if path[0] > 1:
        raise RuntimeError("alignment failed: path does not start at the beginning")
    return path


def words_from_path(path: np.ndarray, word_char_counts: list[int], probs: np.ndarray,
                    tokens_ext: np.ndarray, sec_per_frame: float) -> list[tuple[float, float, float]]:
    """Map the state path back to (start_s, end_s, score) per word."""
    # label index (0..L-1) of each frame, -1 for blank frames
    lab = np.where(path % 2 == 1, (path - 1) // 2, -1)
    out, first = [], 0
    for n in word_char_counts:
        idx = np.where((lab >= first) & (lab < first + n))[0]
        if len(idx) == 0:
            raise RuntimeError("a word received no frames")
        score = float(np.mean(probs[idx, tokens_ext[path[idx]]]))
        out.append((idx[0] * sec_per_frame, (idx[-1] + 1) * sec_per_frame, score))
        first += n
    return out


class MMSAligner:
    def __init__(self, model_id: str = MODEL_ID, device: str = "cpu"):
        import torch
        from transformers import AutoModelForCTC, AutoTokenizer
        import uroman

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCTC.from_pretrained(model_id).to(device).eval()
        self.device = device
        self.vocab = self.tokenizer.get_vocab()
        self.blank = self.vocab.get("<blank>", self.vocab.get("<pad>", 0))
        self.star = self.vocab.get("<star>")
        self.uroman = uroman.Uroman()
        self.model_id = model_id

    def romanise(self, word: str) -> str:
        r = self.uroman.romanize_string(word, lcode="hin").lower()
        r = re.sub(r"[^a-z' ]", "", r).replace(" ", "")
        return r

    def emissions(self, wav: np.ndarray) -> np.ndarray:
        torch = self.torch
        x = torch.from_numpy(wav.astype(np.float32))[None].to(self.device)
        x = (x - x.mean()) / (x.std() + 1e-7)        # wav2vec2 feature normalisation
        with torch.inference_mode():
            logits = self.model(x).logits[0]
        return torch.log_softmax(logits.float(), dim=-1).cpu().numpy()

    def align(self, wav16k: np.ndarray, words: list[str]) -> list[WordAlign]:
        romans = [self.romanise(w) for w in words]
        tokens, counts = [], []
        for r in romans:
            ids = [self.vocab[c] for c in r if c in self.vocab]
            if not ids:                       # nothing alignable: use the <star> wildcard
                if self.star is None:
                    raise ValueError("word with no alignable characters and no <star> token")
                ids = [self.star]
            tokens += ids
            counts.append(len(ids))
        lp = self.emissions(wav16k)
        if self.star is not None:
            # <star> may match anything: give it the best non-blank score at each frame
            lp = lp.copy()
            lp[:, self.star] = np.max(np.delete(lp, self.blank, axis=1), axis=1)
        path = ctc_viterbi(lp, tokens, self.blank)
        ext = np.full(2 * len(tokens) + 1, self.blank)
        ext[1::2] = tokens
        sec_per_frame = len(wav16k) / SAMPLE_RATE / lp.shape[0]
        spans = words_from_path(path, counts, np.exp(lp), ext, sec_per_frame)
        return [WordAlign(w, r, round(float(s), 3), round(float(e), 3), round(float(sc), 4))
                for w, r, (s, e, sc) in zip(words, romans, spans)]


def write_alignment(path: Path, clip_id: str, audio: str, words: list[WordAlign], meta: dict) -> None:
    data = {"clip_id": clip_id, "audio": audio, "timing_source": "mms_fa_auto", **meta,
            "words": [w.__dict__ for w in words]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def write_audacity_labels(path: Path, words: list[WordAlign]) -> None:
    """Audacity label track (File > Import > Labels): start<TAB>end<TAB>label."""
    path.write_text("".join(f"{w.start:.3f}\t{w.end:.3f}\t{w.w}\n" for w in words), encoding="utf-8")
