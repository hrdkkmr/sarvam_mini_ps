# Final review: audit before the k-sweep changes (15 Oct 2026)

Internal audit written **before** editing, from the repository at commit `e4e95d8` (clean working tree).

## 1. What already works
- `src/waitk_simulator.py`: deterministic timing simulation. The English is the fixed fluent reference
  translation and only release times change. It produces a per-entity safety record and a premature-commitment stress-test output.
- `src/adaptive_policy.py::waitk_schedule`: STACL Eq. 6, `g(t) = min(k + t - 1, |x|)`; `k=None` = full context.
- `src/latency_metrics.py`: `al_words` (STACL Eq. 9, source words), `al_time` (SimulEval ALScorer, seconds),
  `end_offset`, `average_proportion`. Unit-tested, including the Part A example (wait-3 AL = 2.625) and AL = k when |x| = |y|.
- `src/entity_checker.py` + `src/number_parser.py`: deterministic checker for amounts, digits, names, negation and corrections.
  It was measured against 415 hand-labelled decisions (97.8 % accuracy, error recall 100 %).
- `scripts/evaluate_waitk.py`: runs wait-k for k ∈ {1, 2, 3, 5, 7}, EAW-lex/pause (k = 2, 3), sentence-by-sentence and whole-clip, then writes CSVs and one plot.
- `scripts/run_all.py`: one-command pipeline. `pytest`: **77 passed** (re-run at the start of this session).

## 2. Results that already exist
`results/checker_eval.csv`, `results/checker_summary.json`, `results/reference_check.csv`,
`results/placeholder/{metrics.csv, metrics_aggregate.csv, entity_timing.csv, simulated_outputs.jsonl, latency_vs_entity_accuracy.png}`,
`report/submission_report.pdf` (3 pages, built by `report/build_report.py`).

## 3. Which results are actual measurements
- Checker accuracy against the author's hand labels (`checker_summary.json`). This is a real measurement of the checker. The labels are not independent.
- Checker on the reference translations (fluent 37/37, literal 30/37).
- **Word-based AL and the evidence-safe rate of wait-k** are exact computations on the annotated text
  (transcript word counts, reference word counts, annotated `src_idx`/`tgt_idx`). They do not depend on timings.
  They are only as valid as the scripted, not yet verified, transcripts.

## 4. Which results are simulations or placeholder estimates
- **All seconds-based numbers** (`AL_decision_s`, `AL_onset_s`, `first_output_s`, `end_offset_s`). Source word times are
  `placeholder_estimate` values derived from character counts (`src/dataset.py`). English speech uses a fixed 0.40 s/word estimate.
  Compute latency is 0, and no TTS was run.
- **EAW-pause** depends on the placeholder pause lengths.
- **Simulated entity accuracy** comes from a stress test with hand-written premature guesses. In the current annotations every premature
  guess fails the checker, so it equals the evidence-safe rate. It is not the accuracy of any model.
- **Fixed-reference entity accuracy** is 100 % for every policy **by construction**, because the text never changes.

## 5. Files that need modification
- `src/waitk_simulator.py`: extend the wait-k set to k = 1…10 (keeping EAW and the baselines).
- New `src/sweep.py`: reusable sweep, aggregation, Pareto frontier, knee point and utility sensitivity.
- `scripts/evaluate_waitk.py`: use the sweep. Write `results/metrics.csv`, `metrics_aggregate.csv`, `k_sensitivity.csv`
  and `selected_operating_point.json`, then plot **from the written CSVs**.
- `src/plotting.py`: label the existing plot more clearly; add `k_sweep.png` and `pareto_frontier.png`.
- `scripts/write_results_md.py`, `report/build_report.py`: read the new result location.
- New `report/build_submission.py` → `submission/` (Markdown + DOCX with identical content generated from one block list).
- New tests: `tests/test_sweep.py`.
- Docs: `RESULTS.md` (regenerated), `FINAL_STATUS.md`, `README.md`, personal guide and viva bank (new sections only).

Output-location decision: the old script wrote every timing-dependent file to `results/placeholder/` whenever timings
were not measured. The brief asks for `results/metrics.csv` etc. These files are now written to `results/`, and every
row carries `timing_source` and `seconds_status` columns. Every figure says "estimated" on seconds axes. The stale
`results/placeholder/` folder is removed, and git history keeps it.

## 6. Correctness issues found
- None in the metric implementations. `al_words` matches STACL Eq. 9 (hand-checked Part A example).
  `al_time` matches the SimulEval ALScorer formula recorded in `SOURCE_NOTES.md` §S5.
- **Disclosure issue (not a bug):** simulated accuracy is identical to the evidence-safe rate, because every annotated
  premature guess is wrong. The two must not be presented as independent evidence.
- **Plot clarity:** the old plot's y-axis says "Entities correct in simulated output". It needs "simulated" in the title and
  "estimated" on the seconds axis (the old title says "NOT A MEASUREMENT", which is correct but terse).
- **Hibiki:** the repository does **not** implement contextual alignment (no MT model, no log-likelihood
  differences). Hibiki can only be presented as the research inspiration, not as a compared method.
- `python-docx` was not installed in `.venv`. It was installed in this session (`pip install python-docx`) and added to `requirements.txt`.
