# Part B: Research proposals

Citations [S#] refer to the appendix table at the end and to `SOURCE_NOTES.md`. Every claim
attributed to a paper was checked against the paper itself, with section, equation or table
numbers given. Statements without a citation are our own hypotheses or engineering choices.

---

## 1. Timing the English: training targets and word-level timing (official questions 2 + 3)

**Problem.** The base model must learn when an English word is safe to speak. Sentence-level
pairs ("Yesterday I got my old bank account closed") say nothing about *when* "closed" may be
spoken, and in Hindi the deciding verb बंद करवा दिया comes last [S1 §2].

**Recommendation.** Keep sentence-level translations as the targets, but derive a per-word
*earliest safe time* for every English word and place the Bulbul-synthesised English audio no
earlier than that time (with silence insertion first, and alignment-aware re-synthesis only if
time allows). Compute the safe time from two signals: (a) Hibiki-style contextual alignment,
the source prefix at which the log-likelihood of the English word jumps under an MT model
[S4 §3.2.1 Eq. 6]; (b) a hard floor from annotated entities, so that an English entity word is never placed before the Hindi
word that determines it (for example करोड़, or the corrected digit). Add a constant safety lag tuned on held-out data,
analogous to Hibiki's δ_ctx = 2 s [S4 §3.2.2].

**Alternatives considered.** (i) Constant lag: Hibiki's ablation shows a 2 s constant lag
collapses quality (ASR-BLEU 10.0) while a 10 s lag recovers it (22.5) but at LAAL 9.0 s,
against 26.6 at LAAL 5.0 s for contextual alignment [S4 Table 4]. (ii) Sentence alignment
(start each output sentence after its source sentence): ASR-BLEU 25.6 but LAAL 21.5 s [S4 Table 4].
(iii) Wait-k on words [S3]: simple, but as our simulation shows, its position-based schedule
drifts when the English is shorter than the Hindi (clip01: 51 English vs 68 Hindi words),
so later English words get further *ahead* of their Hindi evidence.

**Literal versus fluent targets.** For a model that cannot take back speech, train on
*fluent-but-monotone-friendly* targets: keep English clause order close to the Hindi where
English allows it, drop fillers and abandoned values, keep units (lakh, crore) [S1 §3]. Store the
literal gloss as `en_alt` for analysis. Our checker shows why literal glosses are poor targets:
7 of 37 entities fail on literal glosses because Hindi order puts "not" after the verb
("payment not did") (`results/reference_check.csv`).

**Evidence.** Hibiki: contextual alignment gives the best quality–latency trade-off of the
alignment strategies it tests [S4 Table 4]. STACL: training on prefixes (rather than test-time
wait-k on a full-sentence model) is what makes anticipation work [S3 Fig. 2, Sec. 3.2].

**Main risk.** A wrong alignment teaches the model to speak before it has heard the Hindi that
disambiguates the sentence. Under no take-backs that error is permanent.

**Cheapest experiment.** On our six clips, compute (a) the LM-jump alignment with an open MT
model (IndicTrans2-200M [S9]) and (b) the entity floor, and count how often (a) places an entity
word before its determining Hindi word. Abandon pure LM-based timing for entities if this happens for more than 10% of
entities (an engineering threshold).

**Question no source answers.** How large should the safety lag be for *code-mixed* Hindi,
where the "deciding word" is often an English verb written in Devanagari (रिवर्स कर दीजिए)
that an MT model trained on monolingual Hindi may score badly?

**Misleading claim checked.** "Hibiki uses the translation model's perplexity to estimate delays"
(our own draft notes). Eq. 6 [S4] uses the *increase* in log-likelihood of each target word as the
source prefix grows, and then adds a fixed 2 s lag. Delays are not set by perplexity directly.
Also misleading: "a word alignment is the true translation timing". An alignment is a supervision choice; Hibiki itself adds 2 s on top
because the estimate is noisy [S4 §3.2.2].

**Metrics.** Fraction of English entity words placed before their determining Hindi word;
LAAL / End Offset of the training targets; ASR-BLEU of a model trained on them.

**Abandon if.** The contextual alignment is no better than wait-k + entity floor on held-out entity accuracy at equal LAAL.

---

## 2. Hard content: lakh/crore, phone numbers, names, negations, self-corrections (official question 4)

**Problem.** Fluent English can still change the amount, drop "not", or speak the abandoned
value. Sarvam's FAQ: "Speaking the abandoned value as fact is wrong" [S1 FAQ]. Entity and intent
accuracy are 36 of the 70 final KPI points [S1 §9.1].

**Recommendation.** (1) Generate an entity-rich text subset from templates seeded with the
IndicVoices prompt banks (the local repo contains Hindi "Digital transactions", "Customer care
interactions", "Questions on named entities" sheets [S7]), with paired variants that differ in
exactly one fact (5 लाख vs 5 करोड़; नहीं present or absent; a corrected digit). (2) For every record,
store structured entity annotations (value, digits, polarity, final vs abandoned value), not only
text. (3) Verify TTS audio by ASR round trip *on the entity span*: transcribe the audio and
re-parse numbers with a deterministic Hindi number parser (our `src/number_parser.py` handles
0–99, सौ/हज़ार/लाख/करोड़, डेढ़/ढाई/साढ़े/सवा/पौने). Regenerate on mismatch.

**Evidence.** IndicVoices QC uses a maker–checker–superchecker workflow and an audio rating
[S7 Sec. 6]. Sarvam warns that TTS can mispronounce names and numbers, skip words or repeat them [S1 §3].
Our checker shows deterministic checks are reliable for amounts, digits and names (100% on
those categories in our labelled set) but conservative for paraphrased negation (5 false
alarms) (`RESULTS.md`).

**Main risk.** Text and audio disagree: the script says करोड़ and the TTS says लाख. Text-only
checks pass and the model learns the wrong amount.

**Cheapest experiment.** 50 minimal pairs, synthesised with two TTS voices, then ASR, then number
parser: measure the mismatch rate per entity type before trusting synthetic entity audio.

**Question no source answers.** How should a self-correction be scored if the system speaks
the abandoned value and then the corrected one? Our checker treats "five lakh, sorry, five
crore" as a failure; we (the annotators) judged it acceptable. The FAQ's "as fact" leaves this open.

**Misleading claim checked.** "A fluent translation is an accurate translation." Our clip02
fluent reference is fluent and speaks the corrected number, but a streaming system could only
produce it by waiting through the next sentence. Fluency says nothing about when evidence
arrived. The same fluent text with the abandoned digit is equally fluent and wrong.

**Metrics.** Per-category entity accuracy (amount, digits, names, negation, correction),
checker precision and recall against human labels, TTS entity mismatch rate.

**Abandon if.** The ASR round trip disagrees with human listeners on more than 5% of entity spans
(then human spot checks must replace it).

---

## 3. Data sources and the real/synthetic mix (official question 1)

**Problem.** At most 200 h; real audio only from datasets whose licence allows redistribution;
synthetic files each count; augmentation does not count [S1 §3].

**Recommendation.** Real-first, with targeted synthetic data: about 80 h of consented, natural
code-mixed recordings; about 40 h from CC BY 4.0 IndicVoices / IndicVoices-R after filtering for
utterances that contain English words; about 60 h synthetic aligned Hindi speech generated from
code-mixed text; about 20 h of entity- and correction-rich speech (real or synthetic, counted once
in whichever pool it is in). Details and accounting are in `report/DATASET_DESIGN.md`. This is a
proposal, not a measured optimum.

**Evidence.** IndicVoices: CC BY 4.0, gated, with read, extempore and conversational speech [S7].
IndicVoices-R: 1,704 h, CC BY 4.0, 48 kHz, intended for TTS [S8]. Hibiki trained on about 40K h
synthetic, then about 900 h fine-tuning, for Fr–En, which is evidence that a synthetic pipeline works for
*that* pair [S4 §4.2], not for Hindi.

**Main risk.** The model is good on clean scripted speech and fails on spontaneous code-mixing,
accents, telephone audio and corrections. The hidden test is real recordings [S1 §6].

**Cheapest experiment.** Train or fine-tune (or, before the checkpoint arrives, evaluate an ASR
proxy) on real-only, synthetic-only and mixed subsets of equal hours. Test on a held-out set of
*human-recorded* code-mixed clips with disjoint speakers.

**Question no source answers.** How many hours of the current IndicVoices release are Hindi
utterances that contain English words? The cards give no Hindi figure and no code-mixing
statistic [S7, S8]. This has to be measured by scanning transcripts.

**Misleading claim checked.** IndicVoices "has 12,000 hours". The local README says 12,000 h (3,200 h
transcribed). The arXiv abstract says 7,348 h (1,639 h). The current HF card says 23.7K h (11.2K h) [S7].
Hours depend on the release. A proposal must cite the version and use transcribed Hindi hours, not
headline totals.

**Metrics.** Entity accuracy, ASR-BLEU and latency on a real held-out set. The real−synthetic gap is measured
as the difference in those metrics.

**Abandon (the synthetic share) if.** Adding synthetic hours lowers real-test entity accuracy
or ASR-BLEU at equal real hours.

---

## 4. Latency and decoding-time choices (official question 6)

**Problem.** Latency is 16 KPI points and includes "how soon it finishes after the speaker
stops" [S1 §7]. Speaking early risks irreversible entity errors.

**Recommendation.** Report three numbers for every system, never one: Average Lagging in
source words (STACL Eq. 9 [S3]), AL/LAAL in seconds on the *playback* timeline (SimulEval
convention [S5, S13]), and End Offset [S4 §4.3]. Use wait-k as the baseline and add one decoding-time
control: hold back only when the next output is an entity or polarity word (Proposal 5).

**Evidence.** In our simulation (placeholder timings, transcript-level for word AL), raising k
from 3 to 7 raises the fraction of entities committed after their evidence from 54% to 76%, at
+4.0 words of AL. Sentence-by-sentence translation reaches 97% at 6.9 words.
Speech-onset AL is larger than decision AL for every policy, because spoken English queues behind
itself (playback rule [S1 §5.1]). This is a gap that word-based AL hides.

**Main risk.** A measurement bug makes a system look fast: for example, scoring decision time
instead of playback time, or ignoring that a long English answer finishes after the speaker.

**Cheapest experiment.** Our simulator: same clips, same text, vary only the policy; plot entity
accuracy against AL (`scripts/evaluate_waitk.py`).

**Question no source answers.** How many seconds of extra lag is one avoided entity error
worth under Sarvam's relative scoring? It depends on other teams' operating points.

**Misleading claims checked.** (a) "The SimulEval paper defines Average Lagging" (mini PS).
AL is defined in STACL Sec. 4.2 Eqs. 8–9 [S3]. SimulEval implements it with time delays [S5].
(b) "The smallest k is always best for real-time". Our wait-1 has the lowest AL but commits only
46% of entities after their evidence (placeholder run).

**Metrics.** AL (words), AL/LAAL (s, playback), End Offset, first-output latency, entity accuracy.

**Abandon if.** Policy differences disappear once measured in playback seconds on real
timings (that is, the queueing of English speech dominates the read schedule).

---

## 5. Original idea: entity-aware adaptive waiting (EAW)

**Hypothesis.** A simultaneous system should not wait equally for every word. It can emit
stable, low-risk content early and delay *irreversible commitments* (amounts, digits, names,
negation, the value after a correction marker) until the evidence that fixes them has arrived.
This is a hypothesis, not an established result.

**Why it might work here.** Hindi places scale words after the number (पाँच … करोड़), puts
corrections after a hesitation (…नहीं नहीं, सॉरी), and puts negation and the verb at the clause end.
Most English words (greetings, "I applied at", "my account number is") are safe early. Only a
small fraction is risky, so selective waiting should cost little average latency.

**Simple implementation (built: `src/adaptive_policy.py`).** Wait-k base schedule. Before
committing a risky English word (number, scale, negation cue, or capitalised non-initial word),
keep reading while any of the last 2 read Hindi words is risky (number, scale, negation
particle, correction marker). Variant *EAW-pause* also waits for a pause of at least 0.3 s (a proxy for a clause
end). The cap is 6 extra words. At end of input everything is released. Rules are causal: they never look at
unread words (`tests/test_waitk.py::test_eaw_is_causal`).

**Baselines.** wait-k for k ∈ {1, 2, 3, 5, 7}; sentence-by-sentence; whole clip.

**Ablation.** EAW-lex vs EAW-pause (does clause-end waiting add anything?). Lexical lookback window 1/2/3.
Target-side trigger only vs source-side trigger only.

**First-week experiment.** Done in simulation (Part E). Next: with the base checkpoint, implement the same
rule as a decoding constraint (suppress entity and negation tokens until the source trigger clears) and
measure entity accuracy against LAAL on real held-out clips.

**What we observed (placeholder timings; transcript-level results hold for EAW-lex).**
EAW fixes self-corrections (0/4 → 2/4 EAW-lex, 3/4 EAW-pause at k = 3) but not negations (5/11
in every variant). English commits "not" *before* the Hindi negation is spoken, so a lexical
trigger on heard words cannot fire. Waiting must therefore also be triggered by the *target*
side (do not commit polarity before the clause-final verb group is heard). This is the key result
of the idea: it shows where the hypothesis fails.

**When it fails.** (1) Negation and verb-final semantics (shown above). (2) Corrections without an
explicit marker ("पाँच लाख, पाँच करोड़"). (3) Number words used as articles (एक) trigger needless waits.
(4) Real ASR errors on the source side make the trigger unreliable. (5) With English shorter than Hindi,
wait-k drift puts the English so far ahead that a 6-word cap is insufficient (clip01 negation:
16 words short).

**Falsified if.** On real timings, EAW does not dominate wait-k: no EAW point lies above the
wait-k curve at equal playback-time AL. Or entity gains vanish once a real streaming model (not a
fixed reference) generates the text.

---

## Appendix: sources

| # | Source | Year | Verified | Licence / access | What it told us |
|---|---|---|---|---|---|
| S1 | Sarvam, *Inter IIT 15.0 problem statement* (local `Sarvam.pdf`) | 2026 | local file | competition document | Record format, protocol, KPIs, hour counting, correction rule |
| S2 | *Sarvam.ai Mini PS* (local PDF) | 2026 | local file | competition document | Parts A–E, deliverables |
| S3 | Ma et al., *STACL*, ACL 2019, pp. 3025–3036 (local `P19-1289.pdf`) | 2019 | local file | ACL Anthology | wait-k Eq. 6; AL Eq. 9; AP flaw |
| S4 | Labiausse et al., *High-Fidelity Simultaneous Speech-To-Speech Translation* (Hibiki), ICML 2025, PMLR 267 (local) | 2025 | local file | PMLR | Contextual alignment Eq. 6; δ_ctx; Table 4 ablation; End Offset/LAAL; Fr–En limitation |
| S5 | Ma et al., *SimulEval*, EMNLP 2020 Demos, pp. 144–150 + `latency_scorer.py` | 2020 | online | code licence not checked | AL/LAAL/EndOffset implementation conventions |
| S6 | torchaudio, *Forced Alignment with Wav2Vec2* tutorial (local notebook) | 2023 | local file | torchaudio licence not checked | CTC trellis/backtracking; English-only model; API removal in 2.9 |
| S7 | Javed et al., *IndicVoices*, arXiv:2403.01926; repo snapshot; HF card | 2024 | online + local | CC BY 4.0, gated | Level 1 transcription; QC workflow; verbatim+normalized fields; version-dependent hours |
| S8 | AI4Bharat, *IndicVoices-R* HF card | 2024 | online | CC BY 4.0, gated | 1,704 h, 48 kHz TTS data, 10,496 speakers |
| S9 | Gala et al., *IndicTrans2* (GitHub) | 2023 | online | MIT | Indic→En 1B / 200M models for references and back-translation |
| S10 | MMS-300m forced aligner (HF port of torchaudio MMS_FA) | 2023 | online | CC-BY-NC-4.0 | Romanised multilingual aligner used in Part D |
| S11 | WhisperX `alignment.py` + `theainerd/Wav2Vec2-large-xlsr-hindi` card | 2024 | online | WhisperX licence not checked; model card: none stated | Hindi default aligner reports 72.62% WER, so we did not use it |
| S12 | AI4Bharat, *Kathbath* HF card | 2023 | online | inconsistent: cc-by-4.0 vs CC0 text | Example of a licence that must be read, not assumed |
| S13 | Papi et al., *Over-Generation Cannot Be Rewarded: LAAL*, AutoSimTrans 2022, pp. 12–17 | 2022 | online | ACL Anthology | LAAL uses max(hyp, ref) length |
| S14 | Montreal Forced Aligner docs | 2026 | search only | not checked | No Hindi pretrained model confirmed; adaptation needed |
| S15 | Pratap et al., *Scaling Speech Technology to 1,000+ Languages* (MMS) | 2023 | not re-verified | CC-BY-NC (weights) | Origin of the multilingual alignment model |
| S16 | Défossez et al., *Moshi*; Zhang et al., *StreamSpeech*; Barrault et al., *Seamless*; Macháček et al., *Whisper-Streaming* | 2023–24 | not re-verified (mini-PS list) | various | Context only; no numbers attributed |
