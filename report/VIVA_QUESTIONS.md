# Viva question bank (67 questions)

Tags: **[code]** about our exact implementation, **[math]** metrics/derivations, **[research]** papers/datasets,
**[adv]** adversarial challenges. Each answer is meant to be spoken in 30–60 s. "FU" = likely follow-up.
"✗" = a common wrong answer and why it is wrong.

---

## Beginner

**1. What problem are we solving?**
A Hindi speaker (with English mixed in) talks on a call. The system must speak the English translation *while* they talk,
with numbers, names, negations and corrections intact. Sarvam scores translation quality, intent, entities, latency and audio quality.
Before the mid-term, teams build the data; after it, they fine-tune a given streaming speech-to-speech checkpoint.
✗ "It's speech recognition." It's speech-to-speech translation with a latency constraint.

**2. What is simultaneous translation?**
Translating while the source is still arriving, so the system must decide when it has heard enough to commit each output word. The contrast is
consecutive or offline translation, which waits for the full sentence.
FU: *Why not just translate sentence by sentence?* Latency: our sentence baseline has an AL of 6.9 words, against 1.9 for wait-3.

**3. What is wait-k?** [research]
STACL's policy: read k source words, then alternate one write and one read. g(t) = min(k + t − 1, |x|). Small k means low lag and more anticipation.
✗ "The model waits k seconds." It waits k *words*.

**4. What is a forced aligner?**
Given audio *and* its transcript, it finds when each word was spoken. Ours uses a CTC acoustic model (MMS) and Viterbi decoding over the transcript's
characters.
FU: *Difference from ASR?* ASR must also guess the words. Alignment only places known words in time.

**5. Why do we need word timestamps?**
(1) Sarvam requires Hindi word timings in every record, and they are audited. (2) They are the timeline for the wait-k simulation: an English word can only be
committed after the Hindi words it depends on have ended. (3) Later, to build training pairs that teach the model when to speak.

**6. What is entity accuracy?**
The fraction of annotated critical facts (names, amounts, digit strings, times, negation polarity, corrected values) that come out correctly in the English.
Ours is checked deterministically from structured annotations.

**7. What is a self-correction and why does it matter?**
"पाँच लाख… नहीं नहीं, पाँच करोड़": the speaker replaces a value. Sarvam: speaking the abandoned value as fact is wrong. A streaming system that speaks
early will say "five lakh" and cannot take it back.

**8. What is IndicVoices Level 1 transcription?** [research]
"Transcription performed exactly as spoken" (IndicVoices §6): disfluencies, repetitions and fillers kept. Sarvam adds that English words are written in
Devanagari, numbers as words, and every sentence ends with sentence-final punctuation.

**9. Literal vs fluent translation?**
Literal keeps Hindi order and disfluencies ("payment not did"). Fluent is natural English with the corrected meaning. Fluent is the training target and literal is
kept as an alternative. Our checker fails 7/37 entities on literal glosses because "not" comes after the verb.

**10. Why is the hidden test hard for a model trained on synthetic data?** [research]
The hidden test is real recordings with noise, telephone audio, code-switch hesitations and corrections. TTS is clean, evenly paced and template-like.

---

## Intermediate

**11. Derive Average Lagging.** [math]
An ideal translator writes target word t after (t − 1)/r source words, where r = |y|/|x|. The lag of word t is g(t) − (t − 1)/r. Average it up to the cut-off τ = first t with
g(t) = |x|, since after that the tail needs no more reading: AL = (1/τ) Σ_{t≤τ}[g(t) − (t − 1)/r] (STACL Eq. 9).
FU: *Why stop at τ?* Words after the source ends would add lag that is due to target length, not to waiting.

**12. Compute AL for wait-3 on "मैंने कल अपना पुराना बैंक खाता बंद करवा दिया".** [math]
|x| = 9, |y| = 8 ("Yesterday I got my old bank account closed"), g = 3, 4, 5, 6, 7, 8, 9, 9, τ = 7, 1/r = 9/8. Σg = 42, Σ(t − 1)·9/8 = 21 × 1.125 = 23.625, so AL = 18.375/7 = **2.625 words**.
FU: *wait-2 and wait-5?* 1.5625 and 4.75.

**13. Why is AL for wait-k not exactly k here?** [math]
Because |y| ≠ |x|. With r = 8/9 < 1 the ideal reads faster than one word per target word, so wait-k's lag shrinks along the sentence.
AL = k only when |x| = |y| (our unit test checks this).

**14. Can AL be negative? We got −5.0 for clip01.** [math][adv]
Yes. clip01 has 68 Hindi words and 51 English (r = 0.75). Wait-k reads one Hindi word per English word, while the length-normalised ideal reads 1.33,
so wait-k is "ahead" of the ideal. Negative AL here means the English is running ahead of its evidence. It is a warning, not a win.

**15. AL in seconds: what changes?** [math]
g(t) is replaced by the time D_t of source consumed when word t is committed, and |x| by the source duration: AL = (1/τ) Σ[D_i − (i − 1)|X|/|Y|], τ = first D_i ≥ |X|
(SimulEval ALScorer). Hand example in the guide: 0.996 s.

**16. What is LAAL and does it matter here?** [math][research]
Papi et al. 2022: replace |Y| by max(|Y_hyp|, |Y_ref|) so over-long outputs aren't rewarded. In our simulation the output *is* the reference, so AL = LAAL.
It would matter for a real model.

**17. What is End Offset?** [math]
The end of the last output speech minus the end of the source speech (Hibiki §4.3, SimulEval EndOffset). Sarvam explicitly counts speech after the speaker stops.

**18. Why do Hindi–English word orders differ, and what does that do to streaming?**
Hindi is mostly SOV with clause-final verbs and post-number scale words. English needs the verb early. A streaming system must either wait (latency) or
anticipate (risk). The verb "बंद करवा दिया" decides open vs closed only at the end.

**19. Why can a sentence-level model fail during streaming?** [research]
It was trained to see full sentences; given prefixes it never learned to anticipate, so it produces nonsense at small k (STACL Fig. 2c, "test-time wait-k").

**20. Why are numbers and negations especially important?**
A single-token error flips meaning (lakh vs crore = 100×; "not" reverses intent), and Sarvam gives 36 of 70 final KPI points to entity and intent.
BLEU barely moves for such errors.

**21. Why can synthetic audio be misleading?** [research]
The text can be right while the audio is wrong (TTS mispronounces numbers or skips words). It also lacks real prosody and hesitation, and its regularity lets the model learn
templates. So validate the audio itself (ASR round trip on entity spans) and test on real speech.

**22. How is MAE calculated in the boundary audit?** [math]
For each of the 30 word onsets, |auto − manual| in ms. MAE = mean of those; we also report the median (robust to one outlier), the max, and counts over 50 and 100 ms.
FU: *Why onsets?* CTC ends are fuzzy, and uroman schwas stretch words.

**23. Why must speakers be separated across splits?** [research]
Otherwise the model can memorise voices and recording conditions, so test scores overestimate performance on new callers. The same goes for prompt templates.

**24. Why is entity checking not the same as translation accuracy?**
The checker verifies a few annotated facts. A translation can pass every check and still be wrong elsewhere, or fail because of the checker's paraphrase gaps (our 9
false alarms). And our checker checks *references and simulated outputs*, not any model.

**25. What are precision and recall for the checker?** [math]
Positive class = "entity wrong". Error recall = caught real errors / all real errors = 26/26. Error precision = real errors / flagged = 26/35 = 74%. Accuracy = 406/415 = 97.8%.

**26. What does `fold_hi` do and why not store normalised text?** [code]
It removes nuktas, maps chandrabindu → anusvara and drops visarga, *only for matching* (lexicon lookup, transcript-vs-alignment). Sarvam needs verbatim text, so
normalised forms are never written back.

**27. How does `parse_hi_amount` handle "एक लाख पचास हज़ार"?** [code]
current = 1 → लाख: total += 1 × 10⁵, current = 0 → पचास: current = 50 → हज़ार: total += 50 × 10³ → 150,000. Any non-number word returns None, never a guess.

**28. How do you avoid summing "four four two seven" into 17?** [code]
`_digit_run_mask` marks runs of ≥ 2 single-digit words. `en_amounts` skips them and `en_digit_runs` turns them into the string "4427".

**29. How does the negation check work?** [code]
Punctuation becomes a clause break. For each predicate occurrence, look up to 4 words back for a negation cue without crossing a clause break; "not only" is excluded.
Pass if any occurrence has the expected polarity; affirmative controls must have no negated occurrence.

**30. How is a correction checked?** [code]
The final value must be present. The abandoned value must not be asserted: an occurrence counts unless it is directly rejected ("not five lakh"). In literal mode it is
allowed if the final value comes after it.

---

## Advanced

**31. What are the limitations of your wait-k simulator?** [adv]
The English is fixed (written with the full sentence visible), so it can't show generation errors from prefixes. Entity scoring under timing uses hand-written premature guesses.
English durations are a fixed 0.40 s. Compute latency is 0. Source words come from the transcript, not streaming ASR. Timings are placeholders until recordings exist.

**32. What if entity accuracy is unchanged for every k?** [adv]
That is exactly what happens on the fixed text (100% for every policy), because the text doesn't change. It measures the reference, not the policy. We therefore
report it as such and add a separately labelled stress test that asks whether each entity was committed after its determining Hindi word. We do not pretend the flat line is a finding.

**33. Isn't your "simulated accuracy" just the evidence-safe rate in disguise?** [adv]
Yes, by construction: an unsafe entity is replaced by its premature guess. The checker agreeing with it in all rows is only a consistency check. The
informative quantity is the evidence-safe rate per category, which says *where* each policy commits too early.

**34. What if AL decreases but wall-clock latency increases?** [adv][math]
Possible: AL counts source consumed at decision time, but the listener hears playback time. Speech queues (each English word takes 0.40 s), compute adds delay, and End Offset
grows if more English remains at the end. In our table, speech-onset AL exceeds decision AL for every policy. Report both.

**35. How can the policy tell a stable phrase from an amount being corrected?** [adv]
Causally, it can't be certain. EAW uses a short lookahead: after any number or scale word, wait until 2 more words have passed. If a correction marker (नहीं, सॉरी, मतलब, अरे) appears, keep waiting
until the new number plus 2 words. It fails for unmarked corrections ("पाँच लाख, पाँच करोड़").

**36. How would you calibrate the risk detector?** [adv]
Turn it into a probability: for prefixes of many training sentences, label whether the English entity/polarity token is the same with the full source. Fit a classifier on prefix
features and check calibration (reliability diagram, ECE). Choose the waiting threshold on a validation entity-accuracy vs LAAL curve. Our current detector is a rule; it is **not** a
calibrated uncertainty.

**37. How do you avoid leaking future information?** [adv][code]
Policies only index `src_words[:j]` for decisions at read position j. The pause rule uses the gap after the last read word, which is observable after waiting 0.3 s, and
we add that 0.3 s. `test_eaw_is_causal` changes later words and checks early decisions. The aligner is non-causal, but it is data preparation, not inference.
FU: *The risk detector uses the transcript, not ASR.* Yes, that is optimistic; a real system would see ASR errors.

**38. What is the difference between a policy simulation and model evaluation?** [adv]
A simulation fixes the content and varies when it is released, measuring a schedule. Model evaluation runs a model on prefixes, so the content itself changes with the
policy and quality, entity and latency interact.

**39. How would you evaluate statistically with six clips?** [math][adv]
Honestly: you can't claim significance. 37 entities, one speaker. A Wilson 95% interval for 54% (20/37) is about 38–69%. Compare policies *paired* on the same entities (McNemar)
and bootstrap over clips. Report intervals, not just point estimates.

**40. How could this become a real streaming system?** [adv]
Server per Sarvam §5.1 (asyncio, with separate read and write tasks so reading never blocks), causal front-end (resample to 16/24 kHz, VAD), the fine-tuned checkpoint generating audio
tokens incrementally, the EAW rule as a decoding constraint (suppress entity/negation tokens until triggers clear), output frames ≤ 1 s, `session_complete` within 30 s.

**41. What would invalidate your original hypothesis?** [adv]
If, on real timings, no EAW point lies above the wait-k curve at equal playback-time AL. Or if, with a real streaming model, entity gains disappear because the model already
anticipates correctly or errs in other ways. Partly invalidated already: source-triggered waiting doesn't protect negation.

**42. Why didn't EAW help negation?** [adv]
English commits "not" before the Hindi नहीं + verb is spoken ("I did *not* make that payment" vs "मैंने वो पेमेंट नहीं किया"). The trigger is a *heard* risky word, and none has been
heard yet. The fix is a target-side rule: don't commit polarity or the verb before the clause-final verb group is heard.

**43. Why is the time-based AL for decisions lower than for speech onsets?** [math]
Onsets = max(decision, end of previous English word). With 0.40 s per English word, speech backs up whenever decisions arrive faster than 2.5 words/s.

**44. Why use a fixed 0.40 s per English word?** [adv]
The mini PS allows a fixed duration. 0.40 s ≈ 150 wpm. It is labelled an estimate, and you can vary it with `--tgt-word-s`. Bulbul timings would be better.

**45. Why does wait-k drift on long multi-sentence clips?** [math]
Its position rule assumes about one source word per target word. If the English is shorter (clip01: 51 vs 68), English index t corresponds to Hindi position about t/r, but wait-k
reads only k + t − 1, so the gap grows: clip01's negation is committed 16 words too early under wait-3. STACL mentions a "catch-up" variant; a fixed ratio prior would help.

**46. Explain the CTC Viterbi recursion.** [code][math]
States = blank-interleaved labels. dp[t, s] = max(dp[t−1, s], dp[t−1, s−1], dp[t−1, s−2] if skip allowed) + log p(t, ext[s]). Skipping a blank is allowed only between different
non-blank labels. Backtrack from the best of the last two states. Complexity O(T·S).
FU: *Why the blank between repeats?* CTC collapses repeats, so "aa" without a blank would decode as "a".

**47. Why didn't you use the supplied torchaudio notebook as is?** [research][adv]
Its model is English-only (`WAV2VEC2_ASR_BASE_960H`, uppercase letters), so it cannot spell Hindi even romanised, and it warns that the APIs are removed in torchaudio 2.9. We kept its
algorithm and used the multilingual MMS forced-alignment weights.

**48. What does romanisation do to timing?** [research]
uroman keeps schwas (अपना → "apanaa"), so the aligner must fit extra vowels and may stretch or shift boundaries, especially word ends. We keep the Devanagari, store the romanisation
separately, and audit onsets.

**49. Why MMS-FA and not WhisperX for Hindi?** [research]
WhisperX's default Hindi alignment model card reports 72.62% WER on Common Voice Hindi and states no licence. MMS-FA was trained for alignment across 1,000+ languages (licence CC-BY-NC-4.0).

**50. What licence issues exist in your dataset plan?** [research]
IndicVoices and -R: CC BY 4.0 but gated, so read the gate terms. Kathbath: the card is inconsistent (cc-by-4.0 vs CC0). Sarvam API outputs: competition use only, no redistribution.
MMS-FA weights are non-commercial. Your own recordings need explicit consent covering sharing with Sarvam.

**51. How are hours counted?** [research]
Real audio: union of source intervals (overlapping cuts count once). Synthetic: every distinct file, including the same text in another voice. Augmentation: zero.
Our entity-rich 20 h is a tag on records inside the real/synthetic pools, never extra copies.

**52. How many hours of code-mixed Hindi does IndicVoices have?** [research][adv]
Unknown. The cards give no Hindi figure and no code-mixing statistic, and even totals differ by version (12,000 / 7,348 / 23.7K h). That's our first open question, answered by scanning a
sample of transcripts.

**53. How did Hibiki build aligned training data?** [research]
Whisper transcripts → MADLAD translation → per-word contextual alignment (Eq. 6) → Whisper timestamps on both sides with a 2 s safety lag → silence insertion or alignment-aware TTS
choosing the best of 6–8 samples by WER, then speaker similarity.

**54. What does Hibiki's Table 4 show?** [research]
No lag: ASR-BLEU 4.2. Constant 2 s: 10.0. Constant 10 s: 22.5 (LAAL 9.0). Sentence alignment: 25.6 (LAAL 21.5). Contextual alignment: 26.6 (LAAL 5.0). So *how* targets are timed
matters more than a constant delay.

**55. How can a dataset pass the audit but train a worse model?** [research]
All corrections follow one template, so the model learns the marker, not the meaning. Fluent targets place entities before their evidence, which teaches risky anticipation. TTS hours
dominate. Speaker or template leakage inflates validation.

**56. What thresholds did you propose, and are they from literature?** [adv]
CER ≤ 15% (synthetic) / 30% (real), alignment mean score ≥ 0.5, ≤ 10% low-score words, median onset error ≤ 50 ms, chrF ≥ 40 and all entity checks passing. They are **engineering
starting points**, explicitly not published values, to be calibrated against human ratings.

---

## Adversarial (challenging our claims)

**57. "Your checker is 97.8% accurate", on labels you wrote yourself?** [adv]
Fair. The gold labels are mine, written before running it, but not independent. The set was also used during development (it exposed one bug I fixed). So 97.8% is optimistic and in-domain.
A second annotator and new held-out variants are the fix.

**58. Your recordings don't exist yet. What is actually measured?** [adv]
Measured: checker accuracy, and all text-level quantities (word AL, evidence-safe rates for wait-k and EAW-lex). Placeholder: seconds-based latency, EAW-pause, the plot.
Pending: the alignment audit. Everything placeholder is written to `results/placeholder/` and the plot title says so in red.

**59. Isn't the premature guess ("five lakh") something you invented to make waiting look good?** [adv]
It is hand-written and disclosed. But it is the most plausible prefix hypothesis given what has been heard ("…पाँच लाख"). The rate that matters, *evidence-safe*, doesn't depend on the guess
at all: it is just whether the commit came before the determining word.

**60. Your risk lexicon was written while looking at these clips. Overfitting?** [adv]
Yes, a real threat. The lexicon is small and generic (numbers, नहीं/मत, सॉरी/मतलब/अरे), but it should be validated on new clips. In the interview, run it on a new clip.

**61. Why should anyone believe EAW helps if it costs latency?** [adv]
They shouldn't yet. EAW-pause k=3 (AL 4.05 words, 73% safe) and wait-5 (3.86 words, 68%) are close. Wait-7 is 76% at 5.85. On word AL, EAW sits slightly above the wait-k curve, but
on speech-onset seconds it is slightly below (placeholder timings). The supported claim is narrower: it helps self-corrections specifically.

**62. You said entities are 36 points. Isn't latency 16 points, so why wait?** [adv]
Scores are relative to other teams. A wrong amount or a lost negation probably costs both entity *and* intent points, while a sub-second extra wait on only the risky words costs a little
latency. That trade-off is exactly the open question we name ("how many seconds is one avoided entity error worth").

**63. Isn't your English translation itself unverified, LLM-generated?** [adv]
Yes. It is labelled `llm_draft_unreviewed` until I review it. The mini PS allows LLM translation. The entity annotations, not the prose, drive the checker, and I validate that Hindi amounts parse
to the annotated values.

**64. Why should 0.3 s be the pause threshold, 2 the lookback, and 6 the cap?** [adv]
They are untuned engineering choices. The ablation plan varies them. With six clips I'd overfit by tuning, so I didn't tune.

**65. "STACL proves wait-k works for Hindi."** [adv][research]
No. STACL evaluates zh↔en and de↔en text MT. It shows the method and the metric, not Hindi results. Likewise Hibiki is Fr→En only.

**66. The mini PS says SimulEval defines AL. You say STACL. Who's right?** [research]
STACL defines AL (§4.2, Eqs. 8–9, ACL 2019). SimulEval (2020) is a toolkit that implements AL (and AP, DAL, LAAL) with time delays for speech. Cite STACL for the definition and SimulEval for
the implementation convention.

**67. What would you do differently with one more week?** [adv]
Record and align; run the audit; get second-annotator labels; add target-side polarity holding; measure TTS durations; build a prefix-decoding MT baseline so that entity accuracy reflects real
generation, not a fixed reference.
