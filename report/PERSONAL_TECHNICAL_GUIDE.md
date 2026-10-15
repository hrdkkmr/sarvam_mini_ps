# Personal technical guide: Sarvam mini PS (for your own understanding and the viva)

This guide is for you, not the judges. It explains the problem from first principles, then
walks through every part of the code that actually exists in this folder. Where something is
a proposal, a placeholder or pending, it says so. Section references like [Sarvam §5.1] point to
`Sarvam.pdf`; [STACL Eq. 9] to `P19-1289.pdf`; [Hibiki §3.2] to `labiausse25a.pdf`.

**State when written (15 Oct 2026):** code complete and tested (77 tests). No recordings yet,
so every *seconds*-based number comes from placeholder timings. Checker accuracy is measured.
Word-based AL and the "evidence-safe" rates depend only on text and are already meaningful.

---

## Chapter 1: Understanding the problem

### 1.1 What the system receives and emits
A caller speaks Hindi mixed with English. The listener hears English speech *while the caller
is still talking* [Sarvam §2]. Input: mono 16-bit PCM at 24 kHz. Output: English speech in the same
format [Sarvam §4]. One speaker per session, 10–60 s, possibly noisy or telephone audio.
Content includes names, places, organisations, amounts in rupees/lakh/crore, numbers, dates,
times, phone/account numbers, products, negations, conditions and self-corrections [Sarvam §4].

### 1.2 How the audio arrives
The organiser's harness is a WebSocket *client*; your container is the *server* [Sarvam §5.1].
1. Client sends a JSON text frame `session_start` (session_id, sample_rate 24000, encoding pcm_s16le, hi→en).
2. Client sends **binary audio frames of 80 ms each**: 24,000 samples/s × 0.08 s = 1,920 samples × 2 bytes = **3,840 bytes**.
   Frame k is sent at t = k × 80 ms, *in real time*. The last frame is zero-padded.
3. Right after the last Hindi frame: JSON `input_end` with `valid_samples` (how many samples were real speech).
4. After that the client keeps sending **silent 80 ms frames in real time** until you send `session_complete`.
5. Server → client: binary English PCM frames (each at most 1 s), then exactly one JSON `session_complete`.

### 1.3 What a "streaming session" means
One WebSocket connection = one session. You never see the whole utterance in advance; you see a
growing prefix, 80 ms at a time. Anything you send is final (**no take-backs**). The playback
rule is: *each output frame starts when it arrives or when the previous one finishes, whichever
is later; gaps are heard as silence*. All timing is measured on this playback timeline [Sarvam §5.1].

### 1.4 Offline vs simultaneous translation
Offline (consecutive) translation reads the whole sentence, then translates. It has the best context but a
latency of at least one sentence. Simultaneous translation must decide *when* it has heard enough.
The hard part is the **read/write policy**, not only the translation itself.

### 1.5 Why Hindi–English code-mixing is hard
- **Word order:** Hindi is mostly SOV, English SVO. In "मैंने कल अपना पुराना बैंक खाता बंद करवा दिया"
  the meaning-deciding verb group "बंद करवा दिया" (got closed) comes last [Sarvam §2]. Until then the
  account could have been opened, closed or checked.
- **Scale after number:** "पाँच … करोड़": the scale word arrives after the digit.
- **Negation late:** "पेमेंट नहीं किया": नहीं sits just before the clause-final verb.
- **Self-corrections:** "पाँच लाख… नहीं नहीं, पाँच करोड़". The first value must not be spoken as fact [Sarvam FAQ].
- **Code-mixing:** English words inside Hindi ("बिज़नेस लोन", "ट्रांसफ़र") must come out correctly
  [Sarvam FAQ]. Transcripts write them in Devanagari [Sarvam §3], which complicates alignment and ASR.
- **Ambiguous words:** "कल" means both *yesterday* and *tomorrow*; tense later decides (clip04).
- **Little data:** almost no public Hindi–English speech-to-speech data, so you build it [Sarvam §2].

### 1.6 Complete session walkthrough (first frame → session_complete)
t = 0: `session_start`, then frame 0. The server must already be *reading* every frame: if a frame cannot be delivered
within 1 s of its scheduled time because the server is not reading, the session fails [rule 3]. The server buffers audio,
runs (causal) pre-processing such as resampling/VAD, and feeds the model. The model decides to emit English
tokens/audio at some point. Emitted audio is queued for playback. Speaking is slower than deciding, so
output queues up. At `input_end` the speaker has finished. Remaining English must be generated and
sent, then `session_complete` within 30 s. "Speech after the speaker stops counts toward latency."
**What matters most for latency:** (1) how long the policy waits before committing (algorithmic lag);
(2) compute time per step (the model must run faster than real time, or a backlog grows);
(3) *playback queueing*: if English speech is longer than the gaps allow, each word starts late;
(4) the tail after `input_end` (End Offset).

### 1.7 Rules most easily misunderstood
- **Cascade ban** [Sarvam §3 Part B]: no external ASR/MT/LLM/TTS producing text or speech that feeds or replaces the checkpoint.
  Pre-processing (resampling, denoising, VAD) and decoding logic (including speculative decoding
  verified by the checkpoint) are allowed.
- **Causality** [§10]: only audio already received. No reading ahead, no fingerprinting test audio, no network.
- **Only the Part A dataset** may be used for fine-tuning. English targets in supervised pairs must be **Bulbul v3, voice
  shubh, en-IN, 24 kHz** [§3 Part B].
- **Hours:** real audio = union of source intervals (re-cuts count once). Every synthetic file counts,
  even the same text in another voice. Augmentation adds no hours [§3].
- **Scorer integrity** [§10]: filler speech or reading out alternatives can lead to disqualification.
- **Real recordings** only from datasets whose licence allows redistribution [§3, §10].
- **Format:** exactly one server→client text frame (`session_complete`), and nothing after it.

### 1.8 KPIs and points [Sarvam §7, §9.1]
Mid-term: dataset audit 12, pipeline reproducibility 3, report 5. Final: translation quality 12,
**intent accuracy 18**, **entity accuracy 18**, **latency 16**, audio quality 6, report 5, presentation 5.
Entity + intent = 36 points, more than latency. KPIs are scored *relative* to other teams and the base checkpoint.

### 1.9 Specified by Sarvam vs assumed by us
| Specified | Our assumption |
|---|---|
| Frame size, timing, playback rule, no take-backs, finish within 30 s | Exact latency formula Sarvam uses (we use STACL/SimulEval AL + End Offset) |
| Record format, Level 1 transcripts, hour counting | How entity accuracy is scored internally (we built our own checker) |
| Equivalent number forms are correct; corrections must not speak the abandoned value as fact | Whether "five lakh, sorry, five crore" counts as an error (open question) |

---

## Chapter 2: Speech pipeline fundamentals

### 2.1 Samples, rate, channels, frames
Audio is a sequence of amplitude samples. **Sample rate** = samples per second (24,000 here). **16-bit PCM** stores each
sample as an integer in [−32768, 32767]. Mono = 1 channel. A **frame** (in the protocol) is a fixed chunk of samples, here 80 ms =
1,920 samples. A WAV file is PCM plus a header. The protocol sends *headerless* PCM.

### 2.2 Resampling
Changing the rate (e.g. 48 kHz → 24 kHz, or 24 kHz → 16 kHz for the aligner model) requires a low-pass filter to avoid aliasing,
then decimation or interpolation. `src/audio_utils.resample` uses `scipy.signal.resample_poly` (polyphase filtering with ratio up/down).

### 2.3 ASR vs MT vs TTS vs S2ST
ASR: speech → text in the same language. MT: text → text across languages. TTS: text → speech.
Speech-to-speech translation (S2ST) maps speech → speech. A *cascade* chains ASR → MT → TTS. An *end-to-end* model (like
Hibiki, and Sarvam's base checkpoint) does it in one network. Sarvam's final system must be the fine-tuned checkpoint, not a cascade.

### 2.4 Causal vs non-causal processing
Causal processing uses only past and present input. Non-causal processing (e.g. a bidirectional encoder over the whole utterance, or
normalising by the whole clip's mean) uses the future and is forbidden at inference. Our EAW policy is causal by construction, and
`test_eaw_is_causal` checks this. Our aligner is **non-causal** (it sees the whole clip), which is fine because alignment is
offline data preparation, not inference.

### 2.5 Chunking, buffering, end-of-speech
A streaming model consumes chunks (80 ms frames, possibly grouped). Buffering more improves context but adds lag. End-of-speech is explicit
here (`input_end`), but within a session pauses indicate clause or sentence ends. A VAD (e.g. Silero) detects them, and observing a
pause of length p costs p seconds of waiting. Our EAW-pause policy adds exactly that cost.

### 2.6 Where latency accumulates
(1) Frame transport and buffering; (2) model compute per step; (3) policy waiting (the algorithmic lag measured by AL);
(4) generation speed of output audio; (5) playback queueing; (6) the tail after the speaker stops.

### 2.7 Concrete example
The speaker says "पाँच लाख… नहीं नहीं, पाँच करोड़" between 10.0 s and 12.4 s. If the model spoke "five" at 10.6 s and
"lakh" at 11.0 s, it can never retract them. A model that waits until करोड़ ends (12.4 s) and 2 more words (about 13.0 s) says
"five crore" correctly, but its English for this phrase starts about 2 s later. Whether that costs latency points depends on how
much English is still queued.

---

## Chapter 3: Simultaneous translation and wait-k

### 3.1 Notation
Source x = (x₁…x_|x|) Hindi words; target y = (y₁…y_|y|) English words. A **policy** g(t) = number of
source words read before writing target word t [STACL Def. 1]. g is non-decreasing, and 0 ≤ g(t) ≤ |x|.

### 3.2 Deriving wait-k
"Wait k words, then alternate one read with one write." Before y₁ we have read k words. Before y₂, k+1 words. And so on,
until the source is exhausted: **g(t) = min(k + t − 1, |x|)** [STACL Eq. 6]. The mini PS says "English word i is spoken once k + i
Hindi words have been heard". That is the same rule with i counted from 0.
Cut-off τ = min{t : g(t) = |x|} = |x| − k + 1 [STACL Eq. 5]. After τ, the rest (the "tail") is generated with the full source.

### 3.3 Worked example (the Part A sentence)
x = मैंने(1) कल(2) अपना(3) पुराना(4) बैंक(5) खाता(6) बंद(7) करवा(8) दिया(9), |x| = 9.
y = Yesterday(1) I(2) got(3) my(4) old(5) bank(6) account(7) closed(8), |y| = 8, r = |y|/|x| = 8/9.

| t | y_t | wait-2 g | wait-3 g | wait-5 g |
|---|---|---|---|---|
| 1 | Yesterday | 2 (…कल) | 3 | 5 |
| 2 | I | 3 | 4 | 6 |
| 3 | got | 4 | 5 | 7 (…बंद) |
| 4 | my | 5 | 6 | 8 |
| 5 | old | 6 | 7 | 9 |
| 6 | bank | 7 | 8 | 9 |
| 7 | account | 8 | 9 | 9 |
| 8 | closed | 9 | 9 | 9 |

Observations: under wait-2 and wait-3 the English verb "got" must be committed after only 4–5 Hindi words, *before*
"बंद करवा दिया". A real wait-k model must **anticipate** "got … closed". If it guessed "opened", that is an irreversible error. Only
wait-5 has heard बंद when "got" is written. "closed" itself is written only after all 9 words in every case.
AL (STACL Eq. 9, computed in Ch. 4): wait-2 = 1.5625, wait-3 = **2.625**, wait-5 = 4.75 words.

### 3.4 Word tokenisation
Source words are whitespace tokens of the verbatim Devanagari transcript with punctuation stripped (`hi_tokens`). This is exactly
the list the aligner aligns, so index i in the transcript = index i in the timings. Target words are whitespace tokens of the
fluent English (`en_tokens`). "Twenty-five" is one token. Different tokenisations change |x|, |y| and AL, so always state the
tokenisation (we do).

### 3.5 Word-order mismatch, anticipation, premature output
Anticipation = writing a target word whose source evidence has not arrived. STACL argues that prefix-to-prefix training teaches
anticipation from patterns (e.g. "X zài Y …" → "X met …") [STACL §3.1, Fig. 2]. A full-sentence model decoded with test-time
wait-k cannot anticipate and produces nonsense at small k [STACL Fig. 2c]. Anticipation of verbs is a gamble. Anticipating
amounts or negation is dangerous because it cannot be retracted.

### 3.6 EOS and source completion
When the speaker stops (`input_end`), g jumps to |x| and the remaining English is the tail. In our simulator, the last target word
always waits for the full source (`g[-1] = |x|`): a streaming system cannot know the speaker has finished before `input_end`.
For the Part A example this convention changes nothing (wait-k already reaches 9). For k = 1 it changes the last value from 8 to 9.

### 3.7 Why a fixed-reference simulator is not a streaming translator
We take the final fluent translation (written with the whole sentence visible) and only decide *when* each word is released. A real
streaming model would *generate different words* from a prefix: it might say "opened" before hearing बंद, or restructure the sentence.
So a timing simulation measures **latency of a schedule**, not translation quality. If the English is fixed, the checker on the
final text gives the same score for every k. That is why we added an explicit, labelled stress test (Ch. 9.2).

### 3.8 Answering Part A's question: when can "पाँच लाख… नहीं नहीं, पाँच करोड़" be spoken?
Safely, only after करोड़ has been heard. Ideally also after a short lookahead (1–2 words or a pause) to make sure no further
correction follows. To teach a model to wait only when it must: (1) training targets whose English timing respects entity evidence
(the entity floor in Proposal 1), (2) many examples with corrections in which the English amount appears only after the corrected value, and
(3) contrastive examples where nothing follows, so it learns *not* to wait there. Our EAW rule is a hand-written version of
this behaviour.

---

## Chapter 4: Latency metrics

### 4.1 Average Lagging, derived [STACL §4.2]
Idea: measure how far behind an *ideal* simultaneous translator we are, in source words. The ideal "wait-0" writes target word t when
(t − 1)/r source words have been read (it reads at the target rate). Lag of word t = g(t) − (t − 1)/r. Average this lag only up to
the cut-off τ, because after the source ends the tail can be produced without further reading:

**AL = (1/τ) Σ_{t=1..τ} [ g(t) − (t − 1)/r ],  r = |y|/|x|,  τ = min{t : g(t) = |x|}**  [STACL Eq. 9]

For |x| = |y| (r = 1), wait-k gives g(t) − (t − 1) = k for every t ≤ τ, so AL = k exactly (`test_waitk_al_equals_k_when_lengths_equal`).

**Hand computation, wait-3, Part A example:** g = 3, 4, 5, 6, 7, 8, 9, 9. τ = 7 (first g = 9). r = 8/9, so 1/r = 1.125.
Σ_{t=1..7} g(t) = 3+4+5+6+7+8+9 = 42. Σ_{t=1..7} (t − 1) = 21, and 21 × 1.125 = 23.625. AL = (42 − 23.625)/7 = **2.625 words**.
(The test `test_wait3_al_part_a_by_hand` asserts this.)

Note: when the English is shorter than the Hindi (r < 1), (t − 1)/r grows *faster* than t, so AL < k, and it can be **negative**.
Our clip01 (51 English vs 68 Hindi words) has AL = −5.0 words under wait-3: wait-k reads one Hindi word per English word, while
the length-normalised ideal reads 1.33. Negative AL means "ahead of the ideal", which here means *anticipating*. It is not good news.

### 4.2 AL in seconds (SimulEval convention)
For speech, replace g(t) with the *time* D_t of source audio consumed when target word t is committed, and |x| with the source
duration |X| in seconds:
**AL = (1/τ) Σ_{i=1..τ} [ D_i − (i − 1)·|X|/|Y| ]**, τ = first i with D_i ≥ |X|; if D₁ > |X|, AL = D₁ (`ALScorer`, verified
in SimulEval's `latency_scorer.py`).
**Hand example:** 9 source words ending at 0.4, 0.7, 1.1, 1.6, 1.9, 2.3, 2.6, 3.0, 3.4 s (|X| = 3.4 s), |Y| = 8, wait-3 → D = 1.1, 1.6, 1.9,
2.3, 2.6, 3.0, 3.4, 3.4. |X|/|Y| = 0.425 s. τ = 7. Σ D₁..₇ = 15.9. 0.425 × (0+1+…+6) = 8.925. AL = 6.975/7 = **0.996 s**.

### 4.3 LAAL [Papi et al. 2022]
AL uses |Y| (reference length in SimulEval when available). A system that *over-generates* (longer output) would get credit, because the
ideal rate assumes the wrong length. LAAL uses max(|Y_hyp|, |Y_ref|) instead. In our simulator hypothesis = reference, so AL = LAAL.

### 4.4 Average Proportion [STACL Eq. 7]
AP = (1/(|x||y|)) Σ g(t): the fraction of the read/write area. Flaw: wait-1 gives AP 1.0, 0.75, …, approaching 0.5 as the length grows,
although the lag is always one word [STACL §4.1]. We compute it only for completeness (`test_average_proportion_wait1_example_from_stacl`).

### 4.5 DAL (in `evaluator.rst`)
Differentiable AL (Cherry & Foster 2019, not re-verified here) forces each target word to take at least 1/γ of source time, so
committing many words at once is penalised. We do not implement it.

### 4.6 Wall-clock, first-output, End Offset
- **Decision delay** D_t: when the policy commits word t (here, the end time of the last read source word, plus any pause wait).
- **Speech onset** s_t = max(D_t, s_{t−1} + duration): when the listener actually hears it (playback rule). We report AL on both.
- **First-output latency** (SimulEval StartOffset): onset of the first English word.
- **End Offset** [Hibiki §4.3; SimulEval EndOffset]: end of the last English word − end of source speech. Sarvam explicitly counts
  speech after the speaker stops [§5.1].
- **Wall-clock end-to-end** additionally includes compute. We set compute = 0 (no model runs), so ours are lower bounds.

### 4.7 Translation quality vs entity accuracy
BLEU/COMET measure overall similarity to references. Entity accuracy asks whether specific facts survive. A translation can lose one
digit and keep BLEU almost unchanged. AL says nothing about either.

### 4.8 Common metric mistakes
(1) Reporting word lag in milliseconds (we never do). (2) Averaging past τ (it double-counts the tail). (3) Using decision time when
the listener hears playback time. (4) Using hypothesis length in AL (rewards over-generation; this is why LAAL exists). (5) Forgetting
the EOS convention, so the policy "finishes" before the speaker. (6) Computing AL per sentence vs per session inconsistently (ours is per clip).
(7) Not stating the tokenisation.

---

## Chapter 5: Dataset design (details in `report/DATASET_DESIGN.md`)

### 5.1 Why data dominates
The base checkpoint is fixed and everyone gets the same one [Sarvam §3]. Differences between teams come from the Part A data and how
it is turned into training pairs. A model learns timing *from the targets*: Hibiki shows the alignment strategy alone moves ASR-BLEU
from 4.2 (no lag) to 26.6 (contextual alignment) [Hibiki Table 4].

### 5.2 Existing vs collected vs synthetic
Existing (IndicVoices/-R): natural, many speakers, CC BY 4.0, but the code-mixed share is unknown and the hours are version-dependent (12,000 vs
7,348 vs 23.7K h depending on README, arXiv and HF card). Collected: exactly the style we need, costly, needs consent. Synthetic: controllable
(rare entities, corrections), cheap, but distribution-shifted and each file counts toward 200 h. Sarvam API outputs cannot be
redistributed [§10].

### 5.3 The 200-hour proposal
80 h consented natural + 40 h licensed existing + 60 h synthetic + a 20 h entity-rich *tag* inside those pools. This is not
measured; it is a starting point to be tested by the real/synthetic/mixed experiment.

### 5.4 Synthetic speech: why it helps and where it fails
It helps by covering rare patterns and giving exact text–audio correspondence. It fails through clean prosody, no code-switch hesitation,
mispronounced names and numbers, and its regularity (the model learns the template). Hibiki notes its own model imitates its
pseudo-target generator (47.9 vs 35.5 ASR-BLEU) [Hibiki §4.6.2].

### 5.5 Contamination and leakage
The same speaker in train and test lets the model exploit voice. The same prompt or template in both lets it exploit text. Split by
speaker *and* template.

### 5.6 A representative test set
Real recordings, speakers not seen in training, telephone and noise conditions, natural code-mixing, an entity-rich subset with
structured labels, and corrections. It must reflect the hidden test [Sarvam §6].

---

## Chapter 6: Transcription and word alignment

### 6.1 Verbatim vs normalised
IndicVoices **Level 1**: "transcription is performed exactly as spoken" [IndicVoices §6]. It includes disfluencies and repetitions. Level 2
standardises spellings. The IndicVoices JSON has parallel `verbatim` and `normalized` fields (from the data-prep scripts in the zip).
Sarvam requires Level 1 with English words in Devanagari and numbers as words [§3]. We store only verbatim text. Normalisation for
matching (`fold_hi`) is computed on the fly and never saved over the transcript.

### 6.2 Forced alignment vs ASR
ASR guesses the words. Forced alignment is *given* the words and finds when each was spoken. It is much easier and more accurate when
the transcript is right, and produces garbage when it is not. Our smoke test with mismatched audio gave a mean word score of 0.22.

### 6.3 How CTC forced alignment works (our `src/alignment.py`)
1. A wav2vec2-style acoustic model outputs, for every 20 ms frame t, a probability distribution over characters plus a **blank** (CTC).
2. Build the label sequence of the transcript (romanised characters) and interleave blanks: [b, c₁, b, c₂, …, c_L, b] (S = 2L + 1 states).
3. **Viterbi** dynamic programme: dp[t, s] = best log-probability of being in state s at frame t. Transitions: stay (s→s), advance
   (s−1→s), or skip a blank (s−2→s), allowed only if c_s is not blank and differs from c_{s−2}. Repeated characters such as "aa"
   *must* have a blank between them, otherwise CTC would collapse them (`test_ctc_viterbi_repeated_label_needs_blank`).
4. Backtrack from the best final state (last char or final blank) to get one state per frame.
5. Word start = first frame of its first character; end = last frame of its last character; seconds = frames × (samples/frames)/16000.
   Score = mean posterior of its character frames.
The tutorial's trellis [S6] is a simplified form of this (no explicit blank states). Ours is the standard CTC topology, as used
by `torchaudio.functional.forced_align`. Complexity: O(T·S) time with numpy vectorised over S, about 1.6 s for 6 s of audio on CPU.

### 6.4 What an aligner needs
(1) A model whose output vocabulary can spell your transcript. (2) An accurate transcript. (3) Reasonable audio. The supplied tutorial's model
has an English-only uppercase vocabulary and cannot spell Hindi. MMS-FA uses lowercase romanised characters, so we romanise
Devanagari with **uroman** (`lcode=hin`).

### 6.5 Devanagari, transliteration and code-switching risks
uroman keeps inherent schwas: अपना → "apanaa" (spoken "apnaa"), करवा → "karavaa". The model must squeeze extra vowels into the audio,
which biases boundaries. English words in Devanagari are romanised phonetically (ऑफिस → "ophis"), which differs from how the model may
have learned English. Nasals and nuktas are approximated (बैंक → "baimk"). **Word starts are more reliable than ends**, so the
audit uses onsets. The original Devanagari is always kept; the romanisation is stored separately as `roman`.

### 6.6 Interpreting confidence
`score` = mean frame posterior of the word's characters. Low values (< 0.3) flag words where the model is unsure: transcript errors,
noise, or romanisation mismatch. It is not calibrated, and a high score does not prove a correct boundary.

### 6.7 Why automatic timestamps can be wrong
Wrong transcript; romanisation mismatch; CTC "peaky" behaviour (characters occupy one frame and blanks fill the rest, so the end is
fuzzy); long pauses absorbed into adjacent words; 20 ms resolution.

### 6.8 The 30-boundary audit
`audit_boundaries.py make-sheet` picks 5 onsets per clip: the determining words of up to 3 entities (the timings the wait-k results depend on most)
plus evenly spaced words. You mark the **onset** of each in Audacity *without* importing the automatic labels first, to avoid
anchoring bias. `score` computes |auto − manual| in ms: **MAE** = mean of the absolute errors; **median** = the middle value (robust to one
huge error); max; counts over 50 ms and 100 ms (the tolerances we state; 20 ms is one model frame). Limitations: one annotator, no
inter-annotator agreement, 30 points (expect wide uncertainty).

### 6.9 Alternatives
- **WhisperX:** Hindi default model `theainerd/Wav2Vec2-large-xlsr-hindi`; its card reports 72.62% WER on CV Hindi and no licence.
  Rejected.
- **torchaudio MMS_FA bundle:** the same weights as ours, but torchaudio's alignment API was removed in 2.9 and we have torch 2.14.
- **MFA:** an HMM-GMM aligner that needs a pronunciation dictionary. No Hindi model was confirmed; training needs data plus a lexicon that
  covers English loanwords in Devanagari. Could be more precise at boundaries if trained.
- **Manual (Audacity):** the gold standard for 6 clips, but slow; that is what the audit does for 30 points.

---

## Chapter 7: Translation references and hard entities

### 7.1 Literal vs fluent
**Literal** (`en_literal`) is a word-by-word gloss in Hindi order with disfluencies ("Amount about five lakh… no no, sorry, five crore rupees of is").
It is useful for teaching and analysis, and stored as `en_alt` in the manifest. **Fluent** (`en_fluent`) is natural English with the corrected meaning
("The amount is five crore rupees"). This is the target. For a streaming model, the best target is fluent *but* close to the Hindi
order where English permits, because a target that reorders heavily forces anticipation.

### 7.2 Numbers, lakh, crore
1 lakh = 100,000; 1 crore = 10,000,000 = 100 lakh. Sarvam: amounts keep the speaker's units; equivalent forms count as correct
(25,000 = 25k) [§3, FAQ]. Hindi has a separate word for each number 0–99 (पच्चीस = 25, सैंतालीस = 47), so the parser needs a 100-entry table.
Fractions: डेढ़ = 1.5, ढाई = 2.5, साढ़े X = X + 0.5, सवा X = X + 0.25, पौने X = X − 0.25. Scale words come *after* the number.

### 7.3 Names and phone numbers
Names are checked by exact (case-insensitive) match against allowed variants (Bangalore/Bengaluru; SBI/State Bank of India), with
dots and spaced capitals collapsed ("S.B.I.", "S B I"). Phone and account numbers are checked as *digit strings*: "nine eight seven six…",
"98765-43218" and "double four two seven" all become the same string. Digit runs must not merge across sentence ends (a bug we found
with the evaluation set).

### 7.4 Negation and scope
"I did not make that payment" vs "I made that payment" differ by one word with opposite meaning. Our checker looks for a negation cue
(not, never, no, n't, cannot, nothing…) within 4 words *before* the predicate and in the same clause (it stops at but/and/because/if or a punctuation
mark), and excludes "not only". Its weakness is that negation expressed after the predicate or lexically ("made *no such* payment",
"*unable*", "*unlikely*", "*unless*") is missed. These produce false alarms, never false passes, in our set.

### 7.5 Self-corrections and disfluencies
"पाँच लाख… नहीं नहीं, सॉरी, पाँच करोड़": the speaker's final meaning is 5 crore. Sarvam: "The references encode the corrected meaning. Speaking the
abandoned value as fact is wrong." Our correction check: the final value must be present, and the abandoned value must not be *asserted*. Explicit
rejection ("five crore, not five lakh") is allowed. In literal mode, the abandoned value may appear as long as the final value comes after it.

### 7.6 Why the final interpretation may differ from an early phrase
Because the speaker had not finished deciding. The first value was real speech, but it is not the intended fact. This is the core streaming
hazard: at the moment "पाँच लाख" is heard, every local cue says "five lakh". Only later context reverses it.

### 7.7 Entity accuracy, precision, recall, false positives
For the checker evaluation, the positive class = "this entity is wrong in the translation".
- **Accuracy** = fraction of (variant, entity) decisions where the checker agrees with the gold label.
- **Error precision** = TP/(TP+FP): of the errors it flags, how many are real. A false positive is a false alarm on a correct paraphrase.
- **Error recall** = TP/(TP+FN): of real errors, how many it catches. A false negative is a missed error, the dangerous kind.
Our checker: recall 100% (26/26), precision 74% (9 false alarms). It is conservative.

### 7.8 Why BLEU alone is inadequate
BLEU counts n-gram overlap. Changing "crore" to "lakh" changes one token out of dozens, so BLEU barely moves, while the meaning changes by 100×.
Dropping "not" likewise. Entity- and polarity-specific checks are needed.

### 7.9 What a rule-based checker can and cannot establish
It *can* deterministically verify that the structured facts we annotated are expressed in the English, with known, inspectable failure modes. It
*cannot* judge unannotated meaning, paraphrases outside its grammar, or translation quality. It is only as good as the annotations, and our gold
labels for evaluating it were written by the same author (no independent annotator). That is a threat to validity.

---

## Chapter 8: Implementation walkthrough (the code that exists)

Data flow: `clips.json` → `dataset.build_clip` (tokens, timings, entity indices) → `waitk_simulator.simulate` (policy → schedule → times →
premature substitution → checker) → CSVs → plot, RESULTS.md and PDF.

### `src/text_utils.py`
- `PUNCT`, `SENT_FINAL`: punctuation characters, including the Devanagari danda "।" and the hesitation mark "…".
- `split_punct(tok)` peels leading and trailing punctuation off a token.
- `hi_tokens(text)` → `[{"w", "punct"}]`. A standalone punctuation token (e.g. "…" separated by spaces) is attached to the previous word.
  *This defines source word indices everywhere.*
- `fold_hi(word)`: NFD-decompose and remove the nukta (U+093C), map precomposed nukta letters, chandrabindu (ँ) → anusvara (ं),
  drop visarga. Used *only* for matching (lexicon lookup, transcript-vs-alignment comparison).
- `en_tokens`, `en_norm_token` (lowercase, strip punctuation, strip possessive "'s"), `en_words` (also splits hyphens, but keeps digit
  groups like "25,000", "4:30").
- `find_subseq(hay, needle, start)`: naive O(n·m) search, fine for clips of about 70 words.
Common error: changing tokenisation silently changes every index. Tests and the dataset loader will then fail loudly (phrase not found).

### `src/number_parser.py`
- `_HI_0_99` is a string with 100 Hindi number words; an `assert` checks the count is exactly 100. `HI_NUM` maps folded word → value, plus
  spelling variants (पांच, छः, पन्द्रह, ज़ीरो…).
- `HI_SCALE` (सौ, हज़ार/हजार, लाख, करोड़/करोड, अरब), `HI_FRACTION` (डेढ़, ढाई), `HI_FRAC_MOD` (साढ़े +0.5, सवा +0.25, पौने −0.25).
- `parse_hi_amount(words)`: classic accumulator. `current` collects the number below the current scale; "सौ" multiplies `current` by 100;
  a bigger scale adds `current × scale` to `total` and resets. A fraction modifier must be followed by a number. Any non-number word → `None`
  (never guess). Examples: एक लाख पचास हज़ार → 1×10⁵ + 50×10³ = 150,000; पौने तीन सौ → (3 − 0.25)×100 = 275.
- `hi_spans(text)`: scans the transcript. A run of ≥ 2 single-digit words (not crossing a sentence end) is a digit string; other runs of number
  words are amounts. Used by tests and for the Hindi-side consistency check in `validate_dataset.py`.
- English: `EN_UNITS`, `EN_TENS`, `EN_SCALE` (thousand, lakh/lakhs/lac, million, crore/cr, billion), `CURRENCY` words ignored.
- `en_digit_runs(text)`: first turns sentence-final punctuation into a break token "|" (decimal points are protected by look-around), then
  walks the words: digit words, single digits, "double/triple X", and multi-digit groups extend the current run. Anything else ends it.
  Runs of ≥ 4 digits are returned.
- `_digit_run_mask` marks runs of ≥ 2 digit words so that `en_amounts` does not add "four four two seven" into 17.
- `en_amounts(text)`: the same accumulator as the Hindi one, plus numeric tokens (₹5,00,00,000, 1.5, 25k), "and a half", and "one hundred and five".
  Two bare numbers in a row are flushed as two amounts.
- `en_times(text)`: H:MM, half past, quarter past/to, "four thirty", o'clock/am/pm, "at four" (the last one is guarded so "at four thirty" is
  not also read as 4:00).
Documented unsupported forms are in the module docstring ("half a lakh", ordinals, "4.30" as a time, English number words in Devanagari).

### `src/entity_checker.py`
- `CheckResult(entity_id, category, passed, reason, detail)`; `reason` is machine-readable (`found`, `not_found`, `polarity_wrong`,
  `predicate_not_found`, `final_missing`, `abandoned_asserted`, `final_only`).
- `check_name`: normalise (drop dots, join spaced capitals) and look for any variant as a word subsequence.
- `check_amount` / `check_digits` / `check_time`: membership of the expected value in the parsed sets (amounts compared with a
  relative tolerance of 1e-6).
- `check_negation`: punctuation → "but" (a clause break), find all predicate occurrences, test each with `_negated_at` (cue within
  `NEG_WINDOW = 4` words before, stop at clause breaks, exclude "not only"). Pass if *any* occurrence has the expected polarity.
  Affirmative entities pass only if *no* occurrence is negated.
- `_value_positions(kind, value, text)`: slides a 14-token window and records where the value becomes present. A hit must *persist* when
  3 more tokens are visible, which removes transient false hits ("at four" inside "at four thirty").
- `_is_rejected`: is the abandoned value directly preceded by "not", "instead of" or "rather than"?
- `check_correction(mode)`: fails with `final_missing` or `abandoned_asserted`. Literal mode forgives abandoned values that precede a final value.
- `check_entity` dispatches by type. `check_all` maps over entities.
Complexity: O(n²) worst case in `_value_positions` (it re-parses windows), negligible at these sizes.

### `src/dataset.py`
- `Clip` dataclass: `src_words` (with start/end), `tgt_tokens`, both translations, entities with resolved `src_idx`/`tgt_idx`,
  `timing_source`, `src_sent_last` (cumulative source words per sentence), `tgt_sent` (sentence index per target token).
- `placeholder_timings`: **not from audio.** 0.075 s per character (min 0.18 s), a 0.04 s gap, and extra pauses after punctuation
  (… 0.6 s, , 0.25 s, । 0.45 s).
- `load_timings`: prefers `data/alignments/<clip>.json` (`mms_fa_auto`), then `.manual.json`, else placeholder. It refuses alignments
  whose word list no longer matches the transcript.
- `resolve_src_index`: the index of the **last** word of the `src_phrase` occurrence, i.e. the determining word.
- `resolve_tgt_index`: the index of the **first** token of `en_phrase` (supports `en_occurrence`), i.e. the commit point.
- `build_clip` also checks that entity spans do not overlap in the English (this caught a real bug where the phone number's phrase also
  matched sentence 2).

### `src/latency_metrics.py`
`al_words` (STACL Eq. 9, validates the policy), `al_time` (SimulEval ALScorer), `average_proportion` (STACL Eq. 7), `end_offset`.
All have hand-calculated unit tests in `tests/test_metrics.py` and `tests/test_waitk.py`.

### `src/adaptive_policy.py`
- `risky_source(word)`: Hindi number/scale/fraction word, negation particle (नहीं, नही, ना, न, मत), or correction marker (सॉरी, मतलब,
  अरे, मिनट, sorry, यानी).
- `risky_target(tokens, t)`: digit, number word, scale, "hundred"/"half", negation cue, or a capitalised non-sentence-initial word (proxy
  for a name; "I" excluded).
- `waitk_schedule(n_src, n_tgt, k)`: STACL Eq. 6; `k=None` = full sentence.
- `eaw_schedule(src_words, tgt_tokens, k, use_pause, post_wait=2, max_extra=6, pause_s=0.3)`: for each target token start from
  max(previous read, wait-k read). If the token is risky, (a) keep reading while any of the last `post_wait` read words is risky;
  (b) if `use_pause`, keep reading until the silence after the last read word is ≥ 0.3 s; both capped at `wait-k + max_extra`.
  It returns the schedule, a flag saying whether a pause was used (the simulator adds 0.3 s for observing it), and a reason per token.
- Causality: decisions at read position j depend only on words < j and on the gap *after* word j−1, which is observable after
  waiting `pause_s`. `test_eaw_is_causal` changes later words and checks that early decisions do not change.

### `src/waitk_simulator.py`
- `Policy(name, kind, k)` with kinds `waitk`, `eaw_lex`, `eaw_pause`, `sentence` (each English sentence waits for the end of its Hindi
  sentence), `full` (whole clip). `schedule()` applies the EOS convention `g[-1] = |x|`.
- `premature_output(clip, g)`: for each entity, safe ⇔ `g[tgt_idx] ≥ src_idx + 1`. Unsafe entities have their English span replaced by
  `premature_en` (or `<unk>`). Entities are processed right-to-left so earlier indices stay valid.
- `simulate(clip, policy, tgt_word_s=0.40, compute_s=0)`: decision times = end of word g(t) (+ pause), made non-decreasing; onsets =
  max(decision, previous onset + 0.40 s); then all metrics, and the checker on both the fixed reference and the simulated output.
Common errors avoided: an entity counted against the wrong occurrence (fixed with `en_occurrence` and the overlap check); decisions
going backwards in time (clamped).

### `src/evaluation.py`
`apply_variant` (string replacement; fails if the text to replace is absent, so a stale variant cannot silently test nothing),
`evaluate_checker` (one row per variant × entity), `_prf` (confusion counts, accuracy, error precision/recall), `summarise_checker`
(overall, hard/non-hard, per category, disagreements).

### `src/alignment.py`
`ctc_viterbi` (Ch. 6.3), `words_from_path`, `MMSAligner` (loads tokenizer and model through transformers; `romanise` = uroman + keep a–z and the apostrophe;
`emissions` = zero-mean/unit-variance normalisation → logits → log-softmax; `align` maps words → character ids, runs Viterbi and returns
`WordAlign`s), `write_alignment`, `write_audacity_labels`.
Dependencies: torch, transformers, uroman. It downloads 1.2 GB once.

### `src/audio_utils.py`
`load_mono` (soundfile, ffmpeg fallback for m4a), `resample` (polyphase), `quality_report` (duration, peak/RMS dBFS, clipped fraction,
near-silent 20 ms frames < −50 dBFS), `CHECKS` + `check` (engineering thresholds), `write_pcm16`.

### `src/plotting.py`
Two panels sharing the y-axis (entity accuracy %): x = AL in words and x = AL of speech onsets in seconds. One colour per policy family,
k labels, a dashed line for the fixed-text accuracy, and a red title when timings are placeholders.

### Scripts
`prepare_audio.py` → `run_alignment.py` → `validate_dataset.py` (also writes the §5.2 manifest only for real audio + real timings) →
`audit_boundaries.py make-sheet | score` → `evaluate_checker.py` → `evaluate_waitk.py` (writes to `results/placeholder/` unless *all* clips
have automatic timings) → `write_results_md.py` → `report/build_report.py`. `run_all.py` chains them and skips the steps whose inputs are absent.

### Why this design fits the deadline
Pure Python plus numpy, no training, CPU only, deterministic, every number regenerated by a script, and placeholder results
physically separated from measured ones.

---

## Chapter 9: Experimental results

### 9.1 Setup and commands
6 clips (scripted; recordings pending), 37 annotated entities (13 name, 7 amount, 2 digits, 4 corrections, 10 negations + 1 affirmative
control). Commands: `python scripts/evaluate_checker.py`, `python scripts/evaluate_waitk.py`, `python scripts/write_results_md.py`.
All numbers below are copied from `RESULTS.md` as generated on 15 Oct 2026.

### 9.2 Checker evaluation (measured)
66 variants × entities = 415 decisions. Accuracy 97.8%; error recall 100% (26/26); error precision 74.3% (9 false alarms); non-hard variants 100%;
hard variants 86.2%. By category: amount 100% (79), digits 100% (20), names 100% (151), negation 95.9% (121, 5 FP), correction 90.9% (44, 4 FP).
All 9 disagreements are false alarms: lexical or post-verb negation (no such / unless / unable / unlikely / rather than), retracted abandoned
values (×3), and "4.30". The references themselves pass 37/37 (fluent) and 30/37 (literal: Hindi-order glosses put "not" after the verb).
**Caveat:** I used the variant set during development and fixed one real bug it exposed (digit runs crossing a sentence end), so it is not a clean
held-out test. Gold labels are mine.

### 9.3 Wait-k simulation (placeholder timings; word-level columns are text-only)
| policy | AL words | AL decision s | AL speech s | End offset s | evidence-safe |
|---|---|---|---|---|---|
| wait-1 | −0.05 | 0.26 | 1.03 | 2.46 | 46% |
| wait-3 | 1.89 | 1.00 | 1.81 | 3.02 | 54% |
| wait-5 | 3.86 | 1.76 | 2.56 | 3.65 | 68% |
| wait-7 | 5.85 | 2.53 | 3.26 | 4.25 | 76% |
| EAW-lex k=3 | 2.46 | 1.25 | 2.66 | 3.93 | 62% |
| EAW-pause k=3 | 4.05 | 1.84 | 3.40 | 4.56 | 73% |
| sentence-by-sentence | 6.92 | 2.77 | 5.80 | 7.94 | 97% |
Simulated entity accuracy equals the evidence-safe rate in every row. That is expected by construction (an unsafe entity is replaced by a wrong
guess), and it also confirms that the checker scores those substitutions consistently. Fixed-text accuracy is 100% for every policy.

### 9.4 Interpretation (what is justified)
- **Latency buys safety monotonically** for wait-k (`test_larger_k_never_less_safe`).
- **Corrections:** wait-3 0/4 → EAW-lex 2/4 → EAW-pause 3/4. Digits 0/2 → 1/2. The lexical trigger ("a number was just heard, wait 2 words")
  is audible and catches "…नहीं नहीं, सॉरी, …".
- **Negation:** 5/11 for wait-3, EAW-lex and EAW-pause alike. English puts "not" early ("I did *not* make…") while Hindi puts नहीं just before
  the final verb. When the English negation is due, the Hindi negation hasn't been spoken, so nothing heard can trigger a wait. This is the
  main *negative* result: source-triggered waiting cannot protect polarity. Target-side holding is required.
- **Sentence-by-sentence** is almost perfectly safe (36/37). Its single failure (clip02's corrected digit) shows that even full sentences are not
  enough when the correction comes in the *next* sentence.
- **Speech onsets lag decisions** for every policy (English queues at 0.40 s per word). Waiting more increases End Offset, which Sarvam scores.
- **Per-clip AL depends on the length ratio**: clip01 AL is negative (−5.0 words, English shorter), clip05 is +8.8 (English longer). Means
  over clips hide this.

### 9.5 What cannot be concluded
Any real model's accuracy (the text is fixed). Statistical significance: 37 entities, 1 speaker. A 95% Wilson interval for 20/37 (54%) is about
38–69%, and for 28/37 (76%) about 60–87%, so wait-3 vs wait-7 overlap substantially. Paired tests on the same entities (McNemar) would be the right
comparison, but with this n they have little power. Seconds-based numbers until real timings exist. Generalisation beyond scripted
banking/phone content.

### 9.6 Threats to validity
Placeholder timings; scripted prompts; one speaker; author-written translations, premature guesses and gold labels; the risk lexicon was written
while looking at these clips (overfitting); fixed 0.40 s English word duration; zero compute latency; no ASR noise in the source words.

### 9.7 Reproduction
`.venv\Scripts\python scripts/run_all.py`. After recording: `prepare_audio.py`, fix the transcripts, `run_alignment.py`, the audit, then `run_all.py`.

---

## Chapter 10: Paper walkthroughs

### STACL (Ma et al., ACL 2019)
**Question:** simultaneous MT with controllable latency despite word-order differences. **Method:** prefix-to-prefix training; policy g(t); wait-k
(Eq. 6); Transformer with masked encoder self-attention so source word i only attends to words ≤ g(t) (§5.2). **Findings:** genuine wait-k
beats test-time wait-k at small k; it anticipates verbs (Fig. 2). **Equations:** Eq. 6 (wait-k), Eqs. 7–9 (AP, AL). **Limitations:** text only, zh/de↔en,
fixed latency regardless of content. **For us:** the baseline policy and the AL definition. **Does not prove:** anything about Hindi, speech timing, or
entity errors caused by anticipation.

### Hibiki (Labiausse et al., ICML 2025)
**Question:** high-fidelity, voice-preserving simultaneous S2ST. **Method:** decoder-only multistream model (from Moshi) producing text and audio tokens;
**contextual alignment** (Eq. 6: per target word, the source prefix length that maximises the jump in MADLAD-3B log-likelihood); lifted to audio with
Whisper timestamps, a ≥ 2 s lag and spike cutting; silence insertion or alignment-aware TTS (6–8 samples, choose by WER then speaker similarity);
speaker-similarity conditioning with classifier-free guidance (§3.3). **Data:** about 40K h synthetic Fr–En, about 900 h fine-tuning. **Findings:** best ASR-BLEU
among compared streaming systems; Table 4 alignment ablation; End Offset and LAAL reported. **Limitations:** Fr→En only; it imitates MADLAD
(47.9 vs 35.5 ASR-BLEU). **For us:** how to build timing targets (Proposal 1), synthetic pipeline design (Proposal 3). **Does not prove:** that the
method works for Hindi code-mixing or preserves entities.

### SimulEval (Ma et al., EMNLP 2020 demos) and `evaluator.rst`
A toolkit: an agent (your policy) is fed source incrementally, and the evaluator records delays and scores quality (BLEU, ASR-BLEU) and latency (AL, AP,
DAL, LAAL, Start/End Offset). The `.rst` documents the evaluator classes. The formulas are in `latency_scorer.py`, which I checked online. **For us:** the time-domain
AL convention and End Offset.

### torchaudio forced-alignment tutorial
CTC emissions from `WAV2VEC2_ASR_BASE_960H`; trellis; backtracking; merging characters and words at "|". **Limitation:** English-only, uppercase
vocabulary, and the API is deprecated and removed in torchaudio 2.9. **For us:** the algorithm, re-implemented with full blank states on the MMS model.

### IndicVoices (Javed et al., 2024) and repo
**Question:** an inclusive multilingual Indian speech dataset. **Method:** Kathbath app for collection, prompt banks per domain, read/extempore/conversational
tasks, Shoonya transcription with Level 1 (verbatim) and Level 2 (standardised), maker–checker–superchecker QC, audio rated Excellent/Acceptable/
NotAcceptable. **Numbers:** depend on the version (README 12,000 h; arXiv 7,348 h; HF card 23.7K h). **For us:** transcription conventions, QC design,
prompt banks for entity-rich scripts. **Does not prove:** how much code-mixed Hindi–English it has, or how English words are scripted.

---

## Chapter 11: Alternatives and trade-offs

| Choice | Option A | Option B | Cost / complexity | Reliability | Data need | Fit for this assignment |
|---|---|---|---|---|---|---|
| Policy | fixed wait-k | adaptive (EAW, learned R/W, Hibiki-style implicit) | A trivial; B moderate (rules) to high (learned) | A predictable; B content-aware | A none; learned B needs aligned data | wait-k as baseline + rule-based EAW as the hypothesis test |
| Unit | sentence-level | incremental | sentence: simple, high lag | sentence: highest accuracy | same | sentence is a baseline |
| Architecture | ASR+MT+TTS cascade | end-to-end S2ST | cascade: modular; forbidden in the final system | error compounding vs data hunger | E2E needs paired speech | Sarvam mandates E2E; cascades only for data building |
| Transcripts | human | ASR-generated | human slow and expensive | human accurate on code-mixing | — | ASR draft + human correction |
| Alignment | MMS-FA (CTC) | MFA / WhisperX / manual | MMS easy; MFA needs a lexicon | MMS onsets OK, ends weaker | MFA training data | MMS-FA + manual audit |
| Speech data | natural | synthetic | natural costly | natural matches the test | — | real-first mix |
| Entity check | rules | learned classifier / LLM judge | rules cheap and transparent | rules brittle on paraphrase; LLM non-deterministic | classifier needs labels | rules, with measured failure modes |
| Latency | word-based AL | wall-clock / playback | trivial vs needs timings | word AL ignores durations | timings | report both, never mixed |
| Evaluation | timing simulator | real streaming model | simulator free | simulator cannot show generation errors | model + GPU | simulator now, model after the mid-term |

---

## Chapter 12: Improvements after the deadline

**Immediate (days):** record the six clips; verify transcripts; run alignment and the audit; regenerate all results; get a second person to label the
checker variants (inter-annotator agreement); measure English word durations with a real TTS instead of the fixed 0.40 s; add target-side
polarity holding to EAW and an ablation; add a wait-k "catch-up" variant with a fixed, data-independent length ratio.

**Medium (weeks):** an entity-rich minimal-pair test set of more than 200 items with several speakers; an ASR round trip for TTS entity verification;
compute LM-jump alignments (Hibiki Eq. 6) with IndicTrans2 and compare them with the entity floor; build a true incremental text baseline (an MT model
decoding from source prefixes) so that entity accuracy reflects real premature lexical choices.

**Ambitious:** a calibrated risk model (a probability that the next English token's content will change given more source), trained from prefix
translations, with a waiting threshold chosen on a validation curve; implement it as a decoding constraint on the base checkpoint; evaluate on
speaker-disjoint real recordings with significance tests and LAAL/End Offset on the playback timeline.
