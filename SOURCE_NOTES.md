# Source notes

What each source actually says, and what this project uses it for. Every local file below was
opened and read; nothing was inferred from its filename alone. "Verified online" means I opened
the URL in this session (15 Oct 2026). "Not re-verified" means the citation comes from the
official mini-PS reference list and I did not open the primary source here.

## 1. Local files in the project folder

| Local file | Real type / size | What it actually is |
|---|---|---|
| `Inter IIT Tech Meet 15.0_ Sarvam.ai Mini PS.pdf` | PDF, 4 pages, 145 KB | Official mini problem statement (Parts A–E, submission rules, reference list) |
| `Sarvam.pdf` | PDF, 16 pages, 5.1 MB | Official Sarvam high-prep problem statement ("Cross-Language Communication: Real-time Speech-to-Speech Translation") |
| `mini_ps.txt` | UTF-8 text, 7 KB | **Your own Part B/C draft notes** (four recommended questions B1–B4, C1–C3 headings). Not an official document. Its claims were checked (see §3) and the recommendations are reused in `report/RESEARCH_PROPOSALS.md`. Part A answers are not in this folder; nothing was overwritten. |
| `P19-1289.pdf` | PDF, 12 pages, 1.8 MB | STACL, ACL 2019 (PDF title metadata confirms) |
| `labiausse25a.pdf` | PDF, 14 pages, 1.7 MB | Hibiki, ICML 2025 (PMLR 267) proceedings version |
| `High-Fidelity Simultaneous Speech-To-Speech Translation.pdf` | PDF, 14 pages, 2.3 MB | **The same Hibiki paper.** Different file hash, identical extracted text (checked with `cmp`). Treated as a duplicate. |
| `evaluator.rst` | reStructuredText, 1.7 KB | A page of the SimulEval documentation (Evaluator: quality scorers, ALScorer, APScorer, DALScorer, custom scorers). It lists class names only, not formulas. |
| `forced_alignment_tutorial.ipynb` | Jupyter notebook, 22 KB | torchaudio tutorial "Forced Alignment with Wav2Vec2" (Moto Hira). Uses the **English-only** `WAV2VEC2_ASR_BASE_960H` model and an English transcript. It warns that the torchaudio alignment APIs were deprecated in 2.8 and removed in 2.9. It is **not** the multilingual (MMS) tutorial. |
| `IndicVoices-master.zip` | ZIP, 77 MB, 627 files | Snapshot of the AI4Bharat IndicVoices GitHub repo: README, data-prep scripts, NeMo config, per-language SentencePiece tokenizers, character dictionaries, and the Excel prompt banks used for collection (22 languages). **No audio and no LICENSE file in the archive.** |

Unreadable or missing: none. The Devanagari in the Sarvam PDF partly loses matras during text
extraction (for example "मन कल अपना पराना बक खाता बद करवा दिया"). The correct sentence
(मैंने कल अपना पुराना बैंक खाता बंद करवा दिया) was reconstructed from the English gloss on the same page.

## 2. Source-by-source notes

### S1. Sarvam problem statement (`Sarvam.pdf`)
- **What it specifies (used everywhere):** Hindi with English mixed in, to English speech. Mono 16-bit 24 kHz in both directions (§3, §4).
  Part A record: verbatim Hindi transcript in IndicVoices Level 1 style, with English words in Devanagari as spoken, numbers as spoken words, and sentence-final punctuation on every sentence; Hindi word-level alignment "audited at the mid-term"; sentence-level English translations in which amounts keep the speaker's units.
  Hours: for real recordings, the union of source intervals; each synthetic file counts; augmentation does not count. At most 200 h; clips of at most 60 s. §5.2 JSONL manifest format.
- **Protocol (§5.1):** 80 ms PCM frames (3,840 bytes) in real time; `input_end` with `valid_samples`; silence frames continue; output frames of at most 1 s; playback rule "each frame starts when it arrives or when the previous one finishes, whichever is later"; no take-backs; `session_complete` within 30 s of `input_end`; "speech after the speaker stops counts toward latency".
- **KPIs (§7, §9.1):** translation quality 12, intent accuracy 18, entity accuracy 18, latency 16, audio quality 6, plus a mid-term dataset audit of 12 points. KPIs are relative to other teams and the base checkpoint.
- **FAQ:** equivalent number forms count as correct (25,000 = 25k); "The references encode the corrected meaning. Speaking the abandoned value as fact is wrong."
- **Used for:** the record schema, the playback rule in the simulator, the entity categories, and the correction scoring rule.
- **Does not say:** the exact latency formula used to score teams. Our AL definitions therefore come from STACL and SimulEval, not from Sarvam.

### S2. Mini PS (`Inter IIT Tech Meet 15.0_ Sarvam.ai Mini PS.pdf`)
- Defines Parts A–E and the deliverables (see `REQUIREMENTS_CHECKLIST.md`). ML track: "English word i is spoken once k + i Hindi words have been heard; give each English word a fixed duration or measure it from TTS audio. Score each run with your Part C entity checker."
- Says "the SimulEval paper defines Average Lagging". As checked in §3, AL is defined in STACL; SimulEval implements it.

### S3. STACL: Ma, Huang, Xiong, Zheng, Liu, Zheng, Zhang, He, Liu, Li, Wu, Wang (ACL 2019, pp. 3025–3036), `P19-1289.pdf`
- **Question:** how to translate before the sentence ends despite word-order differences (SOV to SVO).
- **Method:** prefix-to-prefix training. Policy g(t) = number of source words read for target word t (Def. 1, p. 3). wait-k: g(t) = min(k + t − 1, |x|) (Eq. 6, p. 4). Cut-off τ = min{t : g(t) = |x|} (Eq. 5). Test-time wait-k with a full-sentence model is much worse at small k (Fig. 2c, Sec. 3.2).
- **Metrics (Sec. 4, pp. 4–5):** CW, AP (Eq. 7, with its length-sensitivity flaw: wait-1 has AP 1, 0.75, …, 0.5), and **Average Lagging** AL = (1/τ) Σ_{t≤τ} [g(t) − (t−1)/r] with r = |y|/|x| (Eq. 9). For |x| = |y|, AL(wait-k) = k.
- **Used for:** `waitk_schedule`, `al_words`, unit tests (AL = k; AP = 0.75 example), and the Part A appendix example.
- **Limits for us:** zh↔en and de↔en text only. Word-based latency ignores speech durations. It does not show what wait-k does to numbers and negations.

### S4. Hibiki: Labiausse, Mazaré, Grave, Défossez, Zeghidour (ICML 2025, PMLR 267), `labiausse25a.pdf`
- **Question:** high-fidelity simultaneous speech-to-speech translation with a single decoder-only multistream model.
- **Contextual alignment (Sec. 3.2.1, p. 4):** for target word T_j, a_j^ctx = argmax_i [log p̂(T_j | S_≤i, T_<j) − log p̂(T_j | S_≤i−1, T_<j)] (Eq. 6), using MADLAD-3B. That is, the source word whose arrival most increases the likelihood of the target word.
- **Audio domain (Sec. 3.2.2):** Whisper timestamps on both sides; the target must lag the contextual alignment by at least δ_ctx = 2 s. Silence insertion has known limits (hard cuts; it can make the target arbitrarily late). Alignment-aware TTS with 6–8 generations per input, selected by WER and then speaker similarity.
- **Data scale (Sec. 4.2):** about 40K hours per language of synthetic Fr–En (Whisper large-v3 transcripts, then MADLAD translation, then TTS); fine-tuning on about 900 h.
- **Ablation (Table 4, p. 8):** no lag gives ASR-BLEU 4.2 at LAAL 2.46; constant 2 s lag gives 10.0 at 2.49; constant 10 s lag gives 22.5 at 9.02; sentence alignment gives 25.6 at 21.49; contextual alignment (Hibiki) gives 26.6 at 5.0.
- **Latency metrics (Sec. 4.3):** End Offset and LAAL (following Papi et al. 2022), computed on Whisper word timestamps of the generated speech.
- **Limitations (Sec. 4.6.2, p. 9):** a single language pair (Fr→En). It reaches 47.9 ASR-BLEU against MADLAD outputs but 35.5 against ground truth, so it imitates its pseudo-target generator.
- **Used for:** the B1 proposal (perplexity-based word timing as a training target), the B3 synthetic-data argument, and the End Offset metric.
- **Does not prove:** anything about Hindi–English, code-mixing, Indian number formats or entity accuracy. Entities are not evaluated separately.

### S5. SimulEval documentation (`evaluator.rst`) and source code (verified online)
- The `.rst` lists `ALScorer`, `APScorer`, `DALScorer` and BLEU scorers but shows no formulas.
- **Verified online** in `simuleval/evaluator/scorers/latency_scorer.py` (GitHub, facebookresearch/SimulEval): AL = (1/τ) Σ_{i≤τ} [D_i − (i−1)·|X|/|Y|], with τ the first i where D_i ≥ |X|; it returns D_1 if D_1 > |X|. |Y| is the reference length when `use_ref_len` is set, otherwise the hypothesis length. LAAL replaces |Y| by max(|Y_hyp|, |Y_ref|). StartOffset = first delay. EndOffset = last delay (or end of the last output interval for speech) minus source length.
- Paper: Ma, Dousti, Wang, Gu, Pino, "SimulEval: An Evaluation Toolkit for Simultaneous Translation", EMNLP 2020 System Demonstrations, pp. 144–150 (verified on the ACL Anthology).
- **Used for:** `al_time` and `end_offset` in `src/latency_metrics.py`.

### S6. torchaudio forced-alignment tutorial (`forced_alignment_tutorial.ipynb`)
- CTC trellis: k(t+1, j+1) = max(k(t, j)·p(t+1, c_{j+1}), k(t, j+1)·p(t+1, blank)), then backtracking, merging repeated labels, and merging into words at "|".
- **Model and language requirement:** `WAV2VEC2_ASR_BASE_960H`, an English character vocabulary in capital letters. It cannot align Devanagari as written.
- **Used for:** the algorithm in `src/alignment.py` (implemented as a full CTC Viterbi with blank states, in numpy). We did not use torchaudio because of the 2.9 removal warning and torch 2.14 on this machine.

### S7. IndicVoices repository (`IndicVoices-master.zip`) and paper
- README (local, Feb 2026 snapshot): "12000 hours … read (8%), extempore (76%) and conversational (15%) … 22563 speakers … 208 districts … 22 languages … 3200 hours have already been transcribed".
- Data-prep scripts read per-utterance JSON with parallel `verbatim` and `normalized` segment lists (each with start and end). This confirms the dataset ships both a verbatim and a normalised transcript. `clean_text` strips bracketed tags and *removes Latin letters* (`[a-zA-Z]` is replaced by a space, marked "Only for Indic Voices").
- Paper (verified online): Javed et al., "IndicVoices: Towards building an Inclusive Multilingual Speech Dataset for Indian Languages", arXiv:2403.01926 (2024). Sec. 6 says: "In Level 1, transcription is performed exactly as spoken". Level 2 standardises spellings. QC uses a maker–checker–superchecker workflow, with audio rated Excellent, Acceptable or NotAcceptable. The arXiv abstract gives **7,348 h, 16,237 speakers, 145 districts, 1,639 h transcribed**.
- HF dataset card `ai4bharat/IndicVoices` (verified online): **CC BY 4.0**, gated (you must agree to share contact information), **23.7K h total / 11.2K h transcribed**, no Hindi-specific figure, no mention of code-mixing.
- **Licence note:** the GitHub snapshot has no LICENSE file. The data licence comes from the HF card. CC BY 4.0 permits redistribution with attribution. The gate is an access condition, and its terms should be read before redistributing.
- **Used for:** the Level 1 transcript conventions, the dataset-design pipeline, and the "dataset totals change between versions" finding in B3.
- **Does not establish:** how much *code-mixed* Hindi–English speech it contains, or how English words are scripted inside Hindi transcripts (the paper's transcription section does not say).

### S8. IndicVoices-R (verified online: HF card `ai4bharat/indicvoices_r`)
- A TTS dataset derived from IndicVoices: **1,704 h, 22 languages, 10,496 speakers, 48 kHz, CC-BY-4.0, gated**. Per-language hours range from 9 to 175 h; the Hindi figure is not stated on the card.
- **Used for:** Part C as a candidate source of cleaner read and extempore Hindi, and as the training source for an Indic TTS. *Not* code-mixed by construction.

### S9. IndicTrans2 (verified online: github.com/AI4Bharat/IndicTrans2)
- MIT licence for code and checkpoints. Indic–En models at 1B and a distilled 200M. Covers 22 scheduled languages including hin_Deva. Code-mixed input is not mentioned.
- **Used for:** Part C as a translation-reference option (with a back-translation check). Not run here: the drafts were written by an LLM, which the mini PS explicitly allows.

### S10. MMS forced aligner (verified online: HF `MahmoudAshraf/mms-300m-1130-forced-aligner`, revision 49402e95…)
- "a conversion from torchaudio to HF Transformers for the MMS-300M checkpoint trained on forced alignment dataset". **CC-BY-NC-4.0**. Romanised input. Vocabulary (inspected): 31 entries, `<blank>` = 0, lowercase a–z and the apostrophe, with no `<star>` token.
- Underlying paper (not re-verified here): Pratap et al., "Scaling Speech Technology to 1,000+ Languages" (MMS), 2023.
- **Used for:** `src/alignment.py` emissions. The NC licence is fine for research and data creation. Using it to build a commercially redistributed dataset should be checked.

### S11. WhisperX alignment defaults (verified online: `whisperx/alignment.py`)
- Hindi default alignment model: `theainerd/Wav2Vec2-large-xlsr-hindi`. Its model card (verified) reports **72.62% WER on Common Voice Hindi** and states no licence. It was fine-tuned on the "Multilingual and code-switching ASR challenges for low resource Indian languages" data.
- **Used for:** the decision *not* to use WhisperX's default Hindi aligner.

### S12. Kathbath / IndicSUPERB (verified online: HF `ai4bharat/Kathbath`)
- 1,684 h of labelled speech in 12 Indian languages, gated. The licence is inconsistent on the card: the metadata says cc-by-4.0 and the text says CC0 for "the packaging". No Hindi hours are given.
- **Used for:** Part C, as an example of why the licence must be read rather than assumed.

### S13. LAAL: Papi, Gaido, Negri, Turchi, "Over-Generation Cannot Be Rewarded: Length-Adaptive Average Lagging for Simultaneous Speech Translation", AutoSimTrans 2022, pp. 12–17 (verified on the ACL Anthology)
- AL rewards outputs longer than the reference. LAAL uses max(|Y_hyp|, |Y_ref|).
- **Used for:** explaining why our AL equals LAAL (the hypothesis is the reference).

### S14. Montreal Forced Aligner (search only)
- I could not confirm a pretrained Hindi MFA acoustic model in this session. MFA 3.x documents `mfa adapt` and `mfa train` for new languages. **Not used.** It would need a Hindi pronunciation dictionary covering English loanwords in Devanagari.

### Sources cited from the mini-PS reference list but not re-verified in this session
Moshi (Défossez et al., 2024); StreamSpeech (Zhang et al., ACL 2024); Seamless (Barrault et al., 2023); Whisper-Streaming / local agreement (Macháček et al., 2023); Silero VAD; DeepFilterNet; Bulbul v3 (Sarvam API docs). These are mentioned only as context, and no numerical claim is attributed to them.

## 3. Claims checked against the original source

| Claim (where seen) | Check | Verdict |
|---|---|---|
| "The SimulEval paper defines Average Lagging" (mini PS, Part A getting-started) | STACL Sec. 4.2, Eqs. 8–9 (P19-1289, pp. 4–5) define AL. SimulEval (2020) implements it in `ALScorer` and applies it to speech with time delays. | **Misattribution.** Cite STACL for the definition and SimulEval for the implementation/convention. |
| "The torchaudio multilingual forced-alignment tutorial works on Hindi once romanised" (mini PS, Part D) | The supplied notebook is the *English* wav2vec2 tutorial. It cannot align Hindi even after romanisation, because its vocabulary is uppercase English letters trained on LibriSpeech. Its APIs are removed in torchaudio ≥ 2.9. | **Misleading for the supplied file.** The multilingual MMS_FA approach works (we use its HF port). |
| IndicVoices "12000 hours … 3200 transcribed" (local README) | arXiv abstract: 7,348 h / 1,639 h transcribed. HF card: 23.7K h / 11.2K h transcribed. | **Version-dependent.** Always cite the version and date. Never quote hours without the release. |
| "The current Hugging Face card reports a CC BY 4.0 licence" (your `mini_ps.txt`) | HF card, opened 15 Oct 2026: CC BY 4.0, gated. | **Correct**, with the caveat that the gate's access terms also apply. |
| "Hibiki uses a translation model's perplexity to estimate delays" (your `mini_ps.txt`) | Sec. 3.2.1, Eq. 6: the argmax of the *increase* in log-likelihood under MADLAD-3B as the source prefix grows, then δ_ctx = 2 s added in the audio domain. | **Correct in spirit, imprecise:** it is the per-word *jump* in log-likelihood, not perplexity, plus a fixed safety lag. |
| "WhisperX supports Hindi word alignment" (common in AI-assistant answers) | It does, through a community wav2vec2 model whose card reports 72.62% WER on CV Hindi and has no licence. | **Technically true, practically misleading.** |
