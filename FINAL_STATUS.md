# Final status (15 Oct 2026)

## Bottom line
Everything that can be done without your voice is done and verified: the code (alignment, checker, simulator, metrics, plots, report builder),
77 passing unit tests, Parts B and C write-ups, the checker evaluation, a 3-page PDF, the personal guide and the viva bank.
**The six recordings do not exist yet.** So the alignment audit is pending, and every seconds-based latency number is computed from
*placeholder* timings estimated from text (kept in `results/placeholder/`, marked in red on the plot and in the PDF).

## Files created
- Top level: `README.md`, `requirements.txt`, `.gitignore`, `SOURCE_NOTES.md`, `REQUIREMENTS_CHECKLIST.md`, `RESULTS.md` (generated), `FINAL_STATUS.md`
- `src/`: `text_utils`, `number_parser`, `entity_checker`, `dataset`, `latency_metrics`, `adaptive_policy`, `waitk_simulator`, `evaluation`, `alignment`, `audio_utils`, `plotting`
- `scripts/`: `prepare_audio`, `run_alignment`, `validate_dataset`, `audit_boundaries`, `evaluate_checker`, `evaluate_waitk`, `write_results_md`, `run_all`
- `tests/`: `test_number_parser`, `test_entity_checker`, `test_waitk`, `test_metrics`
- `data/`: `RECORDING_GUIDE.md`, `SCHEMA.md`, `annotations/clips.json` (6 clips: transcripts, literal and fluent translations, 37 entities), `annotations/checker_variants.json` (66 labelled variants), `audio/raw/` (empty, for you)
- `report/`: `RESEARCH_PROPOSALS.md` (Part B), `DATASET_DESIGN.md` (Part C + Mermaid), `figures/pipeline.png`, `build_report.py`, `make_figures.py`, `submission_report.pdf` (3 pages), `PERSONAL_TECHNICAL_GUIDE.md` (12 chapters), `VIVA_QUESTIONS.md` (67 Q)
- `results/`: `checker_eval.csv`, `checker_summary.json`, `reference_check.csv`, `placeholder/{metrics.csv, metrics_aggregate.csv, entity_timing.csv, simulated_outputs.jsonl, latency_vs_entity_accuracy.png}`
- Not modified: your original files (`mini_ps.txt`, the PDFs, the notebook, `evaluator.rst`, `IndicVoices-master.zip`).
- Environment: `.venv/` (created with `--system-site-packages`; added transformers 4.57.6, uroman 1.3.1.1, soundfile 0.13.1). The MMS aligner (revision 49402e95…) is cached in the Hugging Face cache.

## Commands executed (all succeeded)
- `.venv\Scripts\python scripts/run_all.py`: tests OK, validate OK (0 errors, 18 warnings: transcripts unverified, translations unreviewed, no audio), checker OK, waitk OK (placeholder), RESULTS.md OK, report OK (3 pages). prepare_audio, alignment and audit were skipped because there is no audio.
- `python -m pytest -q`: **77 passed** (Bash and PowerShell).
- Aligner smoke test on an English Windows-TTS file: 15 words aligned in 1.6 s on CPU with plausible boundaries. It was used **only** to test code; it is not a deliverable and not in the project.
- End-to-end script smoke test in a scratch copy (stand-in audio → prepare → align → audit sheet/score → validate → simulate): all scripts ran. Mismatched audio gave a mean alignment score of 0.22, so the low-confidence flag works.

## Tests passed / failed
77 / 0.

## Experiments completed
| Experiment | Result | Status |
|---|---|---|
| Checker vs hand labels (415 decisions, 66 variants) | accuracy 97.8%, error recall 100%, error precision 74.3%, 9 false alarms (all on 'hard' paraphrases) | measured; labels are the author's, and the set was used during development |
| Checker on references | fluent 37/37, literal 30/37 | measured |
| Wait-k/EAW word-level AL + evidence-safe rates | e.g. wait-3 1.89 words / 54%; EAW-pause k=3 4.05 / 73%; sentence 6.92 / 97% | text-level: valid once transcripts are verified |
| Seconds-based latency, EAW-pause, plot | see `RESULTS.md` | **placeholder timings: rerun after recording** |
| Part A example AL (wait-3) | 2.625 words | unit-tested |

## Blocked / pending
1. Six recordings (Part D requirement).
2. Verbatim transcripts checked against the audio.
3. Forced alignment on the recordings, then the 30-boundary manual audit (MAE / median / >50 ms / >100 ms).
4. Final wait-k plot on real timings.
5. Human review of the LLM-drafted translations and of the checker gold labels.

## Exact actions you must take
1. **Record** six clips following `data/RECORDING_GUIDE.md` and save them as `data/audio/raw/clip01.wav` … `clip06.wav`.
2. `.venv\Scripts\python scripts\prepare_audio.py`: every clip must be 20–40 s with no problems.
3. Listen and **edit `data/annotations/clips.json`** so that each `hi_text` is exactly what you said. Update `en_*`, `src_phrase` and `en_phrase` if the wording changed. Set `status.transcript = "verbatim_verified"` and, after reading them, `status.translation = "human_reviewed"`. Then `.venv\Scripts\python scripts\validate_dataset.py` must report 0 errors.
4. `.venv\Scripts\python scripts\run_alignment.py`.
5. `.venv\Scripts\python scripts\audit_boundaries.py make-sheet`, then open each clip in Audacity (spectrogram view, zoom in) and type the onset of each listed word into `manual_onset_s` **before** importing the automatic labels. Then run `... audit_boundaries.py score`.
6. `.venv\Scripts\python scripts\run_all.py`, then `.venv\Scripts\python report\build_report.py --name "Your Name"`. Copy `report/submission_report.pdf` to `<your_name>_mini_ps.pdf` and check it is ≤ 4 pages (the script prints the page count).
7. Write the Part A appendix by hand (wait-3 schedule and AL = 2.625 for the bank-account sentence; the derivation is in the guide, Ch. 4.1).
8. Initialise git, commit, push, and put the link in the report (`git init`, `git add .`, `git commit`). The papers and the zip are git-ignored because they are third-party.
9. Read `report/PERSONAL_TECHNICAL_GUIDE.md` and `report/VIVA_QUESTIONS.md`; practise "Running on a new clip" from the README.

## Limitations to disclose in the interview
- The wait-k study is a **timing simulation over a fixed reference translation**. It is not a streaming model; the "simulated entity accuracy" uses hand-written premature guesses and equals the evidence-safe rate by construction.
- Seconds-based numbers are placeholders until real alignment exists. English word duration is a fixed 0.40 s estimate, and compute latency is assumed to be 0.
- Translations are LLM drafts (allowed by the mini PS) pending your review. The checker gold labels are the author's own, not independent, and were used during development (one bug fixed).
- The risk lexicon and thresholds (2-word lookback, 0.3 s pause, 6-word cap) are untuned engineering choices written while looking at these clips.
- 6 clips, 1 speaker, 37 entities: no statistical significance (the 95% interval for 54% is about 38–69%).
- The MMS-FA weights are CC-BY-NC-4.0. uroman romanisation (schwa retention) biases word ends, so the audit measures onsets.
- The 200-hour allocation and validation thresholds are proposals, not measurements. Hindi-specific and code-mixed hours in IndicVoices are unknown.
- Source-triggered EAW does **not** protect negation (5/11 for every variant). This is a reported negative result.

## Final submission checklist
- [ ] 6 recordings, 20–40 s, in `data/audio/raw/` and converted in `data/audio/`
- [ ] transcripts verified (`status.transcript = verbatim_verified` ×6)
- [ ] `run_alignment.py` done; `data/alignments/*.json` exist
- [ ] 30 boundaries marked and scored (`results/boundary_audit.csv`)
- [ ] `run_all.py` all OK; `RESULTS.md` regenerated (it no longer says "No measured timing results yet")
- [ ] PDF rebuilt with your name, ≤ 4 pages, renamed `<your_name>_mini_ps.pdf`
- [ ] Part A handwritten appendix
- [ ] repository pushed; link in the report
- [ ] translations and checker labels reviewed by you
