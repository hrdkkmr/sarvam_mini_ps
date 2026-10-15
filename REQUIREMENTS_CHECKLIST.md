# Requirements checklist

Source of truth: `Inter IIT Tech Meet 15.0_ Sarvam.ai Mini PS.pdf` (4 pages). Requirement text
is quoted or closely paraphrased from it. Status values: **complete**, **partial**, **blocked**
(needs your input), **not implemented**. Updated 15 Oct 2026.

## Part A: Understanding the problem (10 pts)
| # | Requirement | Status | Where / note |
|---|---|---|---|
| A1 | What the system does; where points are won and lost | partial | Your own Part A (not in this folder). Background is in `report/PERSONAL_TECHNICAL_GUIDE.md` Ch. 1 |
| A2 | Walk through one session to `session_complete`; what matters for latency | partial | Guide Ch. 1.6 (your Part A remains the submitted answer) |
| A3 | Most important or most easily misunderstood rules | partial | Guide Ch. 1.7 |
| A4 | "पाँच लाख… नहीं नहीं, पाँच करोड़": when to speak the amount; teaching a model to wait | partial | Guide Ch. 3.7, B2/original idea in `report/RESEARCH_PROPOSALS.md` |
| A5 | Handwritten appendix: wait-3 schedule and AL for "मैंने कल अपना पुराना बैंक खाता बंद करवा दिया" | **blocked (handwritten)** | Machine check: `tests/test_waitk.py::test_wait3_al_part_a_by_hand` gives AL = 2.625. **You must write it by hand.** |

## Part B: Research and ideas (40 pts)
| # | Requirement | Status | Where |
|---|---|---|---|
| B1 | Four open questions (or own), each a short proposal: recommendation, evidence, main risk, cheapest experiment | complete | `report/RESEARCH_PROPOSALS.md` §1–4 |
| B2 | Per proposal: one question no source answers | complete | same |
| B3 | Per proposal: one claim found wrong or misleading when checked | complete | same + `SOURCE_NOTES.md` §3 (genuine checks only) |
| B4 | Source table in the appendix (aim ≥ 10), one line each | complete | `RESEARCH_PROPOSALS.md` appendix (≥ 10 rows; verification status per row) |
| B5 | One original idea: why it works here, first-week test, when it fails | complete | `RESEARCH_PROPOSALS.md` §5 (entity-aware adaptive waiting) + implemented as EAW |

## Part C: Designing the dataset (25 pts)
| # | Requirement | Status | Where |
|---|---|---|---|
| C1 | Sources and generation: datasets, TTS, text sources, licences, usable hours; how others made code-mixed or entity-heavy speech; 200 h split | complete (as a proposal) | `report/DATASET_DESIGN.md` §1–3. Hours for Hindi-only subsets are marked "not stated" where the cards do not give them |
| C2 | Transcripts, timings, translations: tools, reported accuracy, where humans are needed | complete | §4 |
| C3 | Validation: ASR round-trip, alignment confidence, back-translation; thresholds | complete | §5 (thresholds labelled as engineering choices) |
| C4 | Real-world conditions: synthetic–real gap, noise/telephone/codec, disfluencies; how to measure the gap | complete | §6 |
| C5 | Failure modes; passing the audit while training a worse model | complete | §7 |
| C6 | Pipeline as one diagram + three open questions to test first | complete | §8 (Mermaid source + `report/figures/pipeline.png`), §9 |

## Part D: Build and measure (10 pts)
| # | Requirement | Status | Where |
|---|---|---|---|
| D1 | Record 6 clips (20–40 s) of natural code-mixed Hindi with lakh/crore, phone number, names, negation, self-corrections | **blocked: needs your recordings** | Prompts, checklist and import script ready: `data/RECORDING_GUIDE.md`, `scripts/prepare_audio.py` |
| D2 | Verbatim transcripts in IndicVoices Level 1 style | partial | Scripted transcripts in L1 style exist in `data/annotations/clips.json`, status `scripted_unverified`. They must be corrected against your audio. |
| D3 | Word-level timings with an open aligner | partial (code done and tested; not yet run on your audio) | `src/alignment.py`, `scripts/run_alignment.py`. Smoke-tested on an English TTS file only |
| D4 | Check 30 boundaries by hand and report the error | **blocked** | `scripts/audit_boundaries.py make-sheet / score` |
| D5 | Translate each sentence literally and fluently | complete (LLM draft, review pending) | `clips.json` `en_literal` / `en_fluent`, status `llm_draft_unreviewed` |
| D6 | Checker for amounts, numbers, names, negations in the English | complete | `src/entity_checker.py`, `src/number_parser.py`, 77 unit tests |
| D7 | Report the checker's accuracy and where it fails | complete | `RESULTS.md`, `results/checker_summary.json`, error analysis in the report |

## Part E: ML track (15 pts)
| # | Requirement | Status | Where |
|---|---|---|---|
| E1 | Simulate wait-k on your clips for several k (Part C timings as the Hindi timeline) | partial | Implemented for k = 1, 2, 3, 5, 7 + EAW + sentence/whole-clip baselines. Currently runs on **placeholder timings** → `results/placeholder/`. Re-run after alignment |
| E2 | Fixed English word duration or TTS-measured | complete | Fixed 0.40 s per word (estimate), CLI flag `--tgt-word-s` |
| E3 | Score each run with the entity checker | complete | fixed-text and ambiguity-sensitive simulated scores |
| E4 | Plot entity accuracy vs latency | partial | Plot generated from placeholder timings (labelled in red). Final plot after recordings |
| E5 | "Where should a streaming model wait?" | complete (answer from transcript-level analysis; timing numbers pending) | Report §E, Guide Ch. 9 |

## Submission (Sec. 2)
| # | Requirement | Status | Note |
|---|---|---|---|
| S1 | One PDF, ≤ 4 pages (or an LLM-generated artifact) | complete for current state | `report/submission_report.pdf`, rebuilt by `report/build_report.py`. Copy and rename it to `<your_name>_mini_ps.pdf` |
| S2 | Repository with scripts, clips and RESULTS.md listing every number with its command | partial | Repository-ready directory. Clips pending. `RESULTS.md` is auto-generated. Not yet a git repo / pushed (your action) |
| S3 | File name `<your_name>_mini_ps.pdf` | **blocked** | needs your name |
| S4 | Individual work; in the interview you run the code on a **new clip** and explain it | prepared | `README.md` "Running on a new clip" + `report/PERSONAL_TECHNICAL_GUIDE.md` |

## Extra deliverables requested in the build brief
| Item | Status |
|---|---|
| `SOURCE_NOTES.md`, `REQUIREMENTS_CHECKLIST.md`, `README.md`, `requirements.txt`, `.gitignore` | complete |
| Unit tests (number parsing, corrections, phone numbers, negation, metrics, wait-k) | complete (77 passing) |
| One-command runner `scripts/run_all.py` | complete |
| `report/PERSONAL_TECHNICAL_GUIDE.md`, `report/VIVA_QUESTIONS.md` (≥ 60 Q) | complete |
| `FINAL_STATUS.md` | complete |
