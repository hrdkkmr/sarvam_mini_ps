# Annotation schema (`data/annotations/clips.json`)

One JSON document `{"schema_version", "clips": [...]}`. A clip has:

| Field | Type | Meaning |
|---|---|---|
| `clip_id` | str | `clip01` … `clip06`; audio is `data/audio/<clip_id>.wav` |
| `speaker_id` | str | `spk-0001` (one speaker per clip) |
| `language`, `script` | str | `hi-IN with English code-mixing`; Devanagari, English words written in Devanagari as spoken, numbers as words |
| `status.audio` | enum | `pending_recording` → `recorded` (set by `prepare_audio.py`) |
| `status.transcript` | enum | `scripted_unverified` (the prompt text) → `verbatim_verified` (you listened and corrected it) |
| `status.translation` | enum | `llm_draft_unreviewed` → `human_reviewed` |
| `status.entities` | enum | `author_annotated_unreviewed` → `human_reviewed` |
| `topic` | str | short description |
| `sentences[]` | list | one per Hindi sentence |
| `sentences[].hi_text` | str | **verbatim** Hindi, IndicVoices Level 1 style; ends with । or ? |
| `sentences[].en_literal` | str | word-by-word gloss in Hindi order, disfluencies kept (stored in the manifest as `en_alt`) |
| `sentences[].en_fluent` | str | target translation (manifest `en_text`); keeps lakh/crore; drops abandoned values |
| `entities[]` | list | see below |
| `reviewer_notes` | str | free text |

No normalised transcript is stored: the normalisation used for matching (`fold_hi` in
`src/text_utils.py`: nukta removal, chandrabindu→anusvara) is computed on the fly and never
overwrites the verbatim text.

## Entities

| Field | Meaning |
|---|---|
| `id` | unique, e.g. `c01_corr` |
| `type` | `person`, `place`, `org` (category *name*), `amount`, `digits`, `time`, `negation`, `correction` |
| `src_phrase` | Hindi words in the transcript whose **last** word is the *determining word*: the earliest source word after which the English entity is fully determined (e.g. करोड़; the corrected digit). `src_occurrence` (default 1) picks among repeats |
| `en_phrase` | the words in `en_fluent` that express the entity; the first token is the *commit point*. `en_occurrence` (default 1) |
| `premature_en` | what a system would plausibly say if it committed `en_phrase` before hearing the determining word (hand-written; `null` = nothing sensible → `<unk>`) |
| `expected` | structured check: `{"variants": [...]}` (names) · `{"value": float}` (amount) · `{"digits": "..."}` · `{"hhmm": "4:30"}` · `{"predicates": [...], "polarity": "negative"\|"affirmative"}` · `{"kind": amount\|digits\|time, "final": ..., "abandoned": ...}` |
| `confidence` | `high` / `medium`: annotator confidence |
| `note` | ambiguity notes |

Spans of different entities must not overlap in the English (checked in `src/dataset.py`).

## Word timings (`data/alignments/<clip>.json`)

`{"clip_id", "audio", "timing_source": "mms_fa_auto", "aligner", "model", "model_revision",
"romaniser", "transcript_status", "words": [{"w": Devanagari word, "roman": uroman string,
"start": s, "end": s, "score": mean CTC posterior}]}`. Hand-made timings go in
`<clip>.manual.json` with the same `words` format and are labelled `manual`. Without either file
the code uses `placeholder_estimate` timings and never presents them as measured.

## Manifest (`data/manifests/part_a_manifest.jsonl`)

Sarvam §5.2 format, written by `scripts/validate_dataset.py` only for clips with real audio and
real timings. Extra key `timing_source`.
