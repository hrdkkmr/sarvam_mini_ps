# Final status (15 Oct 2026, updated after the k = 1–10 sweep)

## Update: wait-k sweep, operating point and submission package (this session)

**Reused unchanged:** `src/latency_metrics.py` (STACL AL and SimulEval AL; verified against the unit tests, including the Part A
value 2.625), `src/adaptive_policy.py::waitk_schedule`, `src/entity_checker.py`, `src/number_parser.py`, the premature-commitment stress test in
`src/waitk_simulator.py`, the six annotated text samples in `data/annotations/clips.json` (no annotation or status was changed), and the EAW variants.

**Changed / added:**
- `src/waitk_simulator.py`: `WAITK_SWEEP = 1..10`; `DEFAULT_POLICIES` now has wait-1…wait-10 + EAW + sentence + whole-clip.
- `src/sweep.py` (new): `run_sweep`, `aggregate`, Pareto frontier, knee, near-equivalent alternatives, utility sensitivity,
  dominance of reference policies, CSV loader. The selection rule is documented in its docstring.
- `scripts/evaluate_waitk.py`: writes to `results/` (the old `results/placeholder/` folder was removed with `git rm`; it remains in git
  history). Every row carries `timing_source` and `seconds_status`. It writes `k_sensitivity.csv` and `selected_operating_point.json`, checks for
  non-finite values, and plots **from the CSV/JSON after writing them**.
- `src/plotting.py`: clearer labels on the existing trade-off plot ("Text-based wait-k simulation", "ESTIMATED" seconds axis), plus
  new `k_sweep.png` (three small multiples, no dual axis) and `pareto_frontier.png`.
- `scripts/write_results_md.py`, `report/build_report.py`: read `results/`; RESULTS.md has a new sweep/selection section.
- `report/build_submission.py` (new): renders `submission/submission_report.md` and `.docx` from one content list. All numbers are
  read from `results/`. It renders a PDF with MS Word to count pages, writes `submission/README.md` and zips the folder.
- `scripts/run_all.py`: added the submission step. `tests/test_sweep.py` (new, 8 tests); `tests/test_waitk.py` monotonicity test extended to k = 1..10.
- Docs: `FINAL_REVIEW.md` (pre-edit audit), README, REQUIREMENTS_CHECKLIST (E1), RECORDING_GUIDE (output path), personal guide
  **Chapter 13** (new), viva questions 68–75 (new). `requirements.txt`: added python-docx and pypdfium2. `.gitignore`: allows
  `submission/submission_report.pdf` and ignores `submission_package.zip`.
- Environment: `pip install python-docx` into `.venv` (python-docx was missing).

**Commands executed this session (all succeeded):**
- `.venv\Scripts\python -m pytest -q` → **85 passed** (77 existing + 8 new).
- `.venv\Scripts\python scripts/evaluate_waitk.py`
- `.venv\Scripts\python scripts/write_results_md.py`, `.venv\Scripts\python report/build_report.py` (3 pages)
- `.venv\Scripts\python scripts/run_all.py` → `SUMMARY: tests=ok, validate=ok, checker=ok, waitk=ok, results_md=ok, report=ok, submission=ok`
  (prepare_audio, alignment and the boundary audit were skipped: no recordings)
- `.venv\Scripts\python report/build_submission.py --pdf --zip` → "DOCX renders to 3 pages in Word"; `submission_package.zip` (1.4 MB)

**QC performed:** the per-clip CSV contains wait-k rows for k = 1…10 (6 clips each). There are no non-finite metric values. The selected point was re-derived
by the tests from the documented rule. Figures are produced from the written CSVs. The DOCX reopens with python-docx, has 3 embedded images,
and every Markdown text fragment and table cell appears in it. The Word-rendered PDF was inspected visually. Hibiki and STACL statements were checked
against the supplied PDFs (contextual alignment with MADLAD-3B, δ_ctx = 2 s, Table 4 values; wait-k, prefix-to-prefix, AL).

**Results (from `results/metrics_aggregate.csv` / `selected_operating_point.json`):**

| policy | AL (words) | AL onset (s, ESTIMATED) | evidence-safe = simulated acc. | fixed-ref. acc. |
|---|---|---|---|---|
| wait-1 | −0.05 | 1.03 | 46.0% | 100% |
| wait-3 | 1.89 | 1.81 | 54.0% | 100% |
| wait-5 | 3.86 | 2.56 | 67.6% | 100% |
| **wait-6** | **4.86** | **2.92** | **73.0%** | 100% |
| wait-7 | 5.85 | 3.26 | 75.7% | 100% |
| wait-9 | 7.84 | 3.98 | 86.5% | 100% |
| wait-10 | 8.83 | 4.35 | 86.5% | 100% |
| sentence-by-sentence | 6.92 | 5.80 | 97.3% | 100% |

(All ten k values are in RESULTS.md.)

- **Selected k = 6.** Rule: knee of the Pareto frontier on (evidence-safe rate, AL in words). Pareto k = 1–9; k = 10 is dominated by k = 9.
  Alternatives: wait-5 and wait-7. The **knee is weak** (distance 0.0295 < one-entity effect 0.0667), so this is a band, not an optimum.
  The utility sensitivity flips k = 1 (α ≤ 0.4) → 6 (α = 0.5) → 9 (α ≥ 0.6). Compared with wait-1: +4.91 words AL, +27.0 points evidence-safe.
  The same rule on estimated seconds also gives wait-6.
- Fixed-reference accuracy is 100% for every policy (by construction). Simulated accuracy equals the evidence-safe rate for every policy.
- On words, EAW-pause k=3 dominates wait-6 and sentence-by-sentence dominates wait-9/10. On estimated seconds, nothing dominates wait-k.
- **Estimated (not measured):** every seconds column (`AL_decision_s`, `AL_onset_s`, `first_output_s`, `end_offset_s`) and EAW-pause.
  Source timings are placeholders from character counts, the English duration is a fixed 0.40 s/word, compute = 0, and no TTS was run.

**Still incomplete (audio requirements):** six natural recordings; transcripts verified against audio; forced alignment; the 30-boundary manual audit;
human review of translations and checker labels; re-running the sweep on real timings. All data statuses remain unverified.

**Final file locations:** `submission/submission_report.docx`, `submission/submission_report.md`, `submission/submission_report.pdf`,
`submission/RESULTS.md`, `submission/README.md`, `submission/figures/*.png`, `submission/data/*`, `submission_package.zip` (repository root);
the source outputs are in `results/`. Note: `report/submission_report.pdf` (Parts B–E, 3 pages) is still produced by `report/build_report.py`. The new
`submission/` report covers only the ML track (Part E). Decide which one you submit as the single ≤ 4-page PDF.

---

## Earlier status (before the sweep; kept for the record)

### Bottom line
Everything that can be done without your voice is done and verified: the code (alignment, checker, simulator, metrics, plots, report builder),
77 passing unit tests, Parts B and C write-ups, the checker evaluation, a 3-page PDF, the personal guide and the viva bank.
**The six recordings do not exist yet.** So the alignment audit is pending, and every seconds-based latency number is computed from
*placeholder* timings estimated from text (at the time kept in `results/placeholder/`, now `results/` with per-row tags; marked in red on the plot and in the PDF).

### Files created
- Top level: `README.md`, `requirements.txt`, `.gitignore`, `SOURCE_NOTES.md`, `REQUIREMENTS_CHECKLIST.md`, `RESULTS.md` (generated), `FINAL_STATUS.md`
- `src/`: `text_utils`, `number_parser`, `entity_checker`, `dataset`, `latency_metrics`, `adaptive_policy`, `waitk_simulator`, `evaluation`, `alignment`, `audio_utils`, `plotting`
- `scripts/`: `prepare_audio`, `run_alignment`, `validate_dataset`, `audit_boundaries`, `evaluate_checker`, `evaluate_waitk`, `write_results_md`, `run_all`
- `tests/`: `test_number_parser`, `test_entity_checker`, `test_waitk`, `test_metrics`
- `data/`: `RECORDING_GUIDE.md`, `SCHEMA.md`, `annotations/clips.json` (6 clips: transcripts, literal and fluent translations, 37 entities), `annotations/checker_variants.json` (66 labelled variants), `audio/raw/` (empty, for you)
- `report/`: `RESEARCH_PROPOSALS.md` (Part B), `DATASET_DESIGN.md` (Part C + Mermaid), `figures/pipeline.png`, `build_report.py`, `make_figures.py`, `submission_report.pdf` (3 pages), `PERSONAL_TECHNICAL_GUIDE.md` (12 chapters), `VIVA_QUESTIONS.md` (67 Q)
- `results/`: `checker_eval.csv`, `checker_summary.json`, `reference_check.csv`, `placeholder/{metrics.csv, metrics_aggregate.csv, entity_timing.csv, simulated_outputs.jsonl, latency_vs_entity_accuracy.png}`
- Not modified: your original files (`mini_ps.txt`, the PDFs, the notebook, `evaluator.rst`, `IndicVoices-master.zip`).
- Environment: `.venv/` (created with `--system-site-packages`; added transformers 4.57.6, uroman 1.3.1.1, soundfile 0.13.1). The MMS aligner (revision 49402e95…) is cached in the Hugging Face cache.

### Commands executed (all succeeded)
- `.venv\Scripts\python scripts/run_all.py`: tests OK, validate OK (0 errors, 18 warnings: transcripts unverified, translations unreviewed, no audio), checker OK, waitk OK (placeholder), RESULTS.md OK, report OK (3 pages). prepare_audio, alignment and audit were skipped because there is no audio.
- `python -m pytest -q`: **77 passed** (Bash and PowerShell).
- Aligner smoke test on an English Windows-TTS file: 15 words aligned in 1.6 s on CPU with plausible boundaries. It was used **only** to test code; it is not a deliverable and not in the project.
- End-to-end script smoke test in a scratch copy (stand-in audio → prepare → align → audit sheet/score → validate → simulate): all scripts ran. Mismatched audio gave a mean alignment score of 0.22, so the low-confidence flag works.

### Tests passed / failed
77 / 0.

### Experiments completed
| Experiment | Result | Status |
|---|---|---|
| Checker vs hand labels (415 decisions, 66 variants) | accuracy 97.8%, error recall 100%, error precision 74.3%, 9 false alarms (all on 'hard' paraphrases) | measured; labels are the author's, and the set was used during development |
| Checker on references | fluent 37/37, literal 30/37 | measured |
| Wait-k/EAW word-level AL + evidence-safe rates | e.g. wait-3 1.89 words / 54%; EAW-pause k=3 4.05 / 73%; sentence 6.92 / 97% | text-level: valid once transcripts are verified |
| Seconds-based latency, EAW-pause, plot | see `RESULTS.md` | **placeholder timings: rerun after recording** |
| Part A example AL (wait-3) | 2.625 words | unit-tested |

### Blocked / pending
1. Six recordings (Part D requirement).
2. Verbatim transcripts checked against the audio.
3. Forced alignment on the recordings, then the 30-boundary manual audit (MAE / median / >50 ms / >100 ms).
4. Final wait-k plot on real timings.
5. Human review of the LLM-drafted translations and of the checker gold labels.

### Exact actions you must take
1. **Record** six clips following `data/RECORDING_GUIDE.md` and save them as `data/audio/raw/clip01.wav` … `clip06.wav`.
2. `.venv\Scripts\python scripts\prepare_audio.py`: every clip must be 20–40 s with no problems.
3. Listen and **edit `data/annotations/clips.json`** so that each `hi_text` is exactly what you said. Update `en_*`, `src_phrase` and `en_phrase` if the wording changed. Set `status.transcript = "verbatim_verified"` and, after reading them, `status.translation = "human_reviewed"`. Then `.venv\Scripts\python scripts\validate_dataset.py` must report 0 errors.
4. `.venv\Scripts\python scripts\run_alignment.py`.
5. `.venv\Scripts\python scripts\audit_boundaries.py make-sheet`, then open each clip in Audacity (spectrogram view, zoom in) and type the onset of each listed word into `manual_onset_s` **before** importing the automatic labels. Then run `... audit_boundaries.py score`.
6. `.venv\Scripts\python scripts\run_all.py`, then `.venv\Scripts\python report\build_report.py --name "Your Name"`. Copy `report/submission_report.pdf` to `<your_name>_mini_ps.pdf` and check it is ≤ 4 pages (the script prints the page count).
7. Write the Part A appendix by hand (wait-3 schedule and AL = 2.625 for the bank-account sentence; the derivation is in the guide, Ch. 4.1).
8. Initialise git, commit, push, and put the link in the report (`git init`, `git add .`, `git commit`). The papers and the zip are git-ignored because they are third-party.
9. Read `report/PERSONAL_TECHNICAL_GUIDE.md` and `report/VIVA_QUESTIONS.md`; practise "Running on a new clip" from the README.

### Limitations to disclose in the interview
- The wait-k study is a **timing simulation over a fixed reference translation**. It is not a streaming model; the "simulated entity accuracy" uses hand-written premature guesses and equals the evidence-safe rate by construction.
- Seconds-based numbers are placeholders until real alignment exists. English word duration is a fixed 0.40 s estimate, and compute latency is assumed to be 0.
- Translations are LLM drafts (allowed by the mini PS) pending your review. The checker gold labels are the author's own, not independent, and were used during development (one bug fixed).
- The risk lexicon and thresholds (2-word lookback, 0.3 s pause, 6-word cap) are untuned engineering choices written while looking at these clips.
- 6 clips, 1 speaker, 37 entities: no statistical significance (the 95% interval for 54% is about 38–69%).
- The MMS-FA weights are CC-BY-NC-4.0. uroman romanisation (schwa retention) biases word ends, so the audit measures onsets.
- The 200-hour allocation and validation thresholds are proposals, not measurements. Hindi-specific and code-mixed hours in IndicVoices are unknown.
- Source-triggered EAW does **not** protect negation (5/11 for every variant). This is a reported negative result.

### Final submission checklist
- [ ] 6 recordings, 20–40 s, in `data/audio/raw/` and converted in `data/audio/`
- [ ] transcripts verified (`status.transcript = verbatim_verified` ×6)
- [ ] `run_alignment.py` done; `data/alignments/*.json` exist
- [ ] 30 boundaries marked and scored (`results/boundary_audit.csv`)
- [ ] `run_all.py` all OK; `RESULTS.md` regenerated (it no longer says "No measured timing results yet")
- [ ] PDF rebuilt with your name, ≤ 4 pages, renamed `<your_name>_mini_ps.pdf`
- [ ] Part A handwritten appendix
- [ ] repository pushed; link in the report
- [ ] translations and checker labels reviewed by you
