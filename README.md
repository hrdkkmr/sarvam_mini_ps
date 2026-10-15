# Sarvam mini PS: Hindi–English simultaneous translation, data engine and wait-k study

Inter IIT Tech Meet 15.0, Sarvam.ai mini problem statement, Parts B–E (ML track).

> **Current state (15 Oct 2026):** all code, tests, research write-ups and the checker
> evaluation are complete. **The six required recordings have not been made yet.** Until they
> are, timing-dependent results are computed from clearly labelled *placeholder* timings and are
> written to `results/placeholder/`. See `FINAL_STATUS.md` for what you must do.

> **Methodological limitation (read before quoting any number):** the wait-k experiment is a
> *timing simulation*. The English is a fixed reference translation prepared with the whole
> sentence visible; only its release times change with the policy. It does not reproduce the
> errors a real streaming model makes when it generates from a source prefix. The "simulated
> entity accuracy" is a transparent stress test (an entity spoken before its deciding Hindi word
> is replaced by a hand-written premature guess). It is not the accuracy of any model.

## Layout

```
data/RECORDING_GUIDE.md        prompts + checklist for the six clips
data/SCHEMA.md                 annotation / alignment / manifest formats
data/annotations/clips.json    transcripts, literal + fluent translations, entity annotations
data/annotations/checker_variants.json   hand-labelled variants used to measure the checker
data/audio/raw/                YOUR recordings go here (clip01.wav ...)
data/audio/, data/alignments/, data/manifests/   generated
src/                           library code (see report/PERSONAL_TECHNICAL_GUIDE.md Ch. 8)
scripts/                       command-line steps, run_all.py runs everything
tests/                         77 unit tests
results/                       generated metrics, plots, audits
report/                        Part B/C write-ups, PDF builder, personal guide, viva bank
RESULTS.md                     every reported number + the command that produced it (generated)
SOURCE_NOTES.md, REQUIREMENTS_CHECKLIST.md, FINAL_STATUS.md
```

## Setup (Windows PowerShell)

```powershell
cd E:\Hardik\Programming\sarvam_mini_ps
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install torch --index-url https://download.pytorch.org/whl/cpu    # skip if torch is installed
pip install -r requirements.txt
python -m pytest -q                   # expect: 77 passed
```

The `.venv` in this folder was created with `--system-site-packages` to reuse the existing
torch 2.14 CPU install. The first alignment run downloads the 1.2 GB MMS aligner from Hugging
Face (cached in `%USERPROFILE%\.cache\huggingface`).

If you see garbled Devanagari in the console, run `$env:PYTHONIOENCODING="utf-8"` first.

## Workflow

| Step | Command | Output |
|---|---|---|
| 1. Record six clips (20–40 s) | see `data/RECORDING_GUIDE.md`; save `data/audio/raw/clip01.wav` … | |
| 2. Import + quality check | `python scripts/prepare_audio.py` | `data/audio/clipNN.wav` (24 kHz PCM16), `data/manifests/audio_qc.csv` |
| 3. Make transcripts verbatim | edit `data/annotations/clips.json` while listening; `python scripts/validate_dataset.py` | 0 errors |
| 4. Forced alignment | `python scripts/run_alignment.py` | `data/alignments/clipNN.json` + Audacity label files |
| 5. 30-boundary audit | `python scripts/audit_boundaries.py make-sheet`, mark onsets in Audacity, then `... score` | `results/boundary_audit.csv` |
| 6. Checker accuracy | `python scripts/evaluate_checker.py` | `results/checker_summary.json` |
| 7. Wait-k / EAW + plot | `python scripts/evaluate_waitk.py` | `results/metrics*.csv`, `results/latency_vs_entity_accuracy.png` |
| 8. RESULTS.md + PDF | `python scripts/write_results_md.py`; `python report/build_report.py` | `RESULTS.md`, `report/submission_report.pdf` |
| All of it | `python scripts/run_all.py` | all of the above that the inputs allow |

## Running on a new clip (interview)

1. Save the recording as `data/audio/raw/clip07.wav`.
2. Add a `clip07` object to `data/annotations/clips.json` (copy clip01 and replace the sentences,
   translations and entities; the schema is in `data/SCHEMA.md`). For a quick demo, entities
   may be an empty list.
3. `python scripts/prepare_audio.py` (it will complain that clip07 is not 20–40 s if it isn't;
   that is a warning, not a crash), then `python scripts/run_alignment.py --clips clip07`.
4. Open `data/audio/clip07.wav` in Audacity and import `data/alignments/clip07.audacity.txt`
   (File > Import > Labels) to show the word boundaries.
5. Check a translation directly:
   ```powershell
   python -c "from src.entity_checker import check_entity; print(check_entity({'id':'x','type':'amount','expected':{'value':5e7}}, 'It costs five crore rupees'))"
   ```
6. `python scripts/evaluate_waitk.py` re-runs every policy, including the new clip.

## What is and is not measured

| Quantity | Status |
|---|---|
| Checker accuracy on 415 hand-labelled decisions | measured (labels are the author's, not independent) |
| Word-based AL and evidence-safe rates for wait-k / EAW-lex | computed from the transcripts and translations; valid once the transcripts are verified |
| Seconds-based latency, EAW-pause, the plot | **placeholder timings until recordings exist** |
| Alignment error (30 boundaries) | **pending** recordings + manual marking |
| English speech durations | fixed 0.40 s/word estimate, not TTS measurements |
| Translation-model accuracy | not measured: no MT/S2ST model is run |
