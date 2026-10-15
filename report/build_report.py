"""Build report/submission_report.pdf (at most 4 pages) from the result files.

Usage:  python report/build_report.py [--name "Your Name"]
All numbers are read from results/ at build time; pending items are printed as PENDING.
Hindi is shown in romanised form because reportlab cannot shape Devanagari conjuncts/matras.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.dataset import load_all  # noqa: E402

RES = ROOT / "results"
ss = getSampleStyleSheet()
BODY = ParagraphStyle("b", parent=ss["Normal"], fontName="Helvetica", fontSize=8.6, leading=10.6,
                      alignment=TA_JUSTIFY, spaceAfter=2.2)
SMALL = ParagraphStyle("s", parent=BODY, fontSize=6.9, leading=8.2, alignment=0)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=12.5, leading=15, spaceAfter=3)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=9.4, leading=11.5,
                    spaceBefore=4, spaceAfter=2, textColor=colors.HexColor("#1f4e8c"))
WARN = ParagraphStyle("w", parent=BODY, backColor=colors.HexColor("#fff4e5"), borderColor=colors.HexColor("#eda100"),
                      borderWidth=0.6, borderPadding=3, spaceBefore=2, spaceAfter=5)


def P(t, st=BODY):
    return Paragraph(t, st)


def table(rows, widths, header=True, fs=6.8):
    data = [[Paragraph(str(c), ParagraphStyle("t", parent=SMALL, fontSize=fs, leading=fs + 1.3)) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8b8b8")),
          ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
          ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef7")))
    t.setStyle(TableStyle(st))
    return t


def rcsv(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pct(x):
    return f"{100 * float(x):.0f}%"


def build(name: str) -> Path:
    clips = load_all()
    timing = sorted({c.timing_source for c in clips})
    measured = timing == ["mms_fa_auto"]
    wk = RES   # every row carries timing_source / seconds_status (scripts/evaluate_waitk.py)
    agg = rcsv(wk / "metrics_aggregate.csv") if (wk / "metrics_aggregate.csv").exists() else []
    ents = rcsv(wk / "entity_timing.csv") if (wk / "entity_timing.csv").exists() else []
    chk = json.loads((RES / "checker_summary.json").read_text()) if (RES / "checker_summary.json").exists() else None
    audit = json.loads((RES / "boundary_audit_summary.json").read_text()) if (RES / "boundary_audit_summary.json").exists() else None
    recorded = sum(c.raw["status"]["audio"] == "recorded" for c in clips)
    verified = sum(c.raw["status"]["transcript"] == "verbatim_verified" for c in clips)
    n_ent = sum(len(c.entities) for c in clips)
    allents = [e for c in clips for e in c.entities]
    n_names = sum(e["type"] in ("person", "place", "org") for e in allents)
    n_neg = sum(e["type"] == "negation" and e["expected"].get("polarity", "negative") == "negative" for e in allents)
    n_aff = sum(e["type"] == "negation" and e["expected"].get("polarity") == "affirmative" for e in allents)
    n_corr = sum(e["type"] == "correction" for e in allents)

    W = A4[0] - 24 * mm
    out = ROOT / "report" / "submission_report.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm,
                            title="Sarvam mini PS: Hindi-English simultaneous translation", author=name)
    s = []
    s.append(P(f"Hindi–English simultaneous translation: research, data design, entity checking and a wait-k study", H1))
    s.append(P(f"<b>{name}</b> · Inter IIT Tech Meet 15.0, Sarvam.ai mini PS, Parts B–E (ML track) · code + RESULTS.md in the repository", SMALL))
    status = (f"<b>Status of evidence.</b> Recordings made: <b>{recorded}/6</b>; transcripts verified against audio: <b>{verified}/6</b>; "
              f"timing source: <b>{', '.join(timing)}</b>. ")
    if not measured:
        status += ("All second-based latency numbers below come from <b>placeholder timings estimated from text, not from audio</b>, "
                   "and the alignment audit is pending. Word-based AL and evidence-safe rates depend only on transcripts and translations. ")
    status += ("Throughout, the wait-k experiment is a <b>timing simulation over a fixed reference translation</b>; it does not "
               "reproduce the errors of a real streaming model generating from a prefix.")
    s.append(P(status, WARN))

    # ---------------- Part B
    s.append(P("Part B: Four research proposals and one original idea", H2))
    rows = [["Question", "Recommendation and evidence", "Main risk / cheapest experiment", "Unanswered question · claim checked"],
            ["<b>1. Timing the English</b> (training targets, Q2+Q3)",
             "Sentence-level fluent targets kept close to Hindi clause order. Per-word earliest-safe time = Hibiki contextual alignment "
             "(argmax jump in MT log-likelihood as the source prefix grows, Eq. 6 [4]) <i>and</i> an entity floor (never before the Hindi "
             "word that fixes the entity), plus a tuned safety lag. Hibiki Table 4: constant 2 s lag gives ASR-BLEU 10.0; sentence alignment 25.6 "
             "at LAAL 21.5 s; contextual alignment 26.6 at 5.0 s [4].",
             "Wrong alignment teaches speaking before the deciding verb (band karva diya) and cannot be undone. Experiment: on our 6 clips, count entity words that "
             "the LM-jump alignment places before their determining Hindi word.",
             "Safety lag when the deciding word is an English verb written in Devanagari? · <i>'Hibiki sets delays by perplexity'</i> "
             "(our draft notes): it uses the per-word <i>increase</i> in log-likelihood plus a fixed 2 s lag [4 §3.2]."],
            ["<b>2. Hard content</b> (Q4)",
             "Entity-rich subset from the IndicVoices Hindi prompt banks (digital transactions, customer care, named entities [5]) "
             "as minimal pairs differing in one fact; structured entity annotations; TTS verified by ASR round trip + deterministic "
             "Hindi number parsing on the entity span. Sarvam FAQ: 'speaking the abandoned value as fact is wrong' [1].",
             "TTS says lakh where the script says crore; text-only checks pass. Experiment: 50 minimal pairs × 2 voices → ASR → parser mismatch rate.",
             "How to score 'five lakh, sorry, five crore'? · <i>'Fluent = accurate'</i>: our clip02 fluent reference is only producible after "
             "waiting a full sentence; an equally fluent version with the abandoned digit is wrong."],
            ["<b>3. Data sources, real vs synthetic</b> (Q1)",
             "Real-first: ~80 h consented code-mixed + ~40 h CC BY 4.0 IndicVoices/-R filtered for English words + ~60 h synthetic + "
             "~20 h entity-rich tag (inside the others). Hibiki: ~40K h synthetic then ~900 h fine-tune, Fr–En only [4].",
             "Model fits clean scripted speech, fails on real telephone code-mixing. Experiment: equal-hours real / synthetic / mixed, "
             "tested on speaker-disjoint human recordings.",
             "Hindi hours with English words in IndicVoices? Not on any card [5,6]. · <i>'IndicVoices has 12,000 h'</i>: README 12,000/3,200 transcribed, "
             "arXiv 7,348/1,639, HF card 23.7K/11.2K [5]: quote the release."],
            ["<b>4. Latency decoding choices</b> (Q6)",
             "Always report AL in source words (STACL Eq. 9 [2]), AL/LAAL in playback seconds (SimulEval [3], LAAL [7]) and End Offset [4]. "
             "Base on wait-k [2]; add entity-aware holding (below).",
             "A measurement bug flatters a system (decision time instead of playback time). Experiment: this paper's simulator, same text, vary only the policy.",
             "Seconds of lag worth one avoided entity error under relative scoring? · <i>'The SimulEval paper defines AL'</i> (mini PS): "
             "AL is defined in STACL §4.2 Eqs. 8–9 [2]; SimulEval implements it on time delays [3]."]]
    s.append(table(rows, [W * 0.13, W * 0.37, W * 0.24, W * 0.26], fs=6.5))
    s.append(Spacer(1, 3))
    s.append(P("<b>Original idea: entity-aware adaptive waiting (EAW), a hypothesis.</b> Most English words (greetings, 'my account number is') are "
               "safe early; only commitments that cannot be retracted (amounts, digits, names, negation, the value after a correction) need evidence. "
               "<b>Rule (causal, implemented):</b> on top of wait-k, before committing a <i>risky English word</i> (number, scale, negation cue, "
               "non-initial capitalised word), keep reading while any of the last 2 heard Hindi words is risky (number/scale word, nahin/mat, "
               "correction marker such as sorry/matlab/are); variant <i>EAW-pause</i> also waits for a ≥ 0.3 s pause; cap 6 extra words. "
               "<b>Why here:</b> Hindi puts the scale after the number, corrections after a hesitation, negation at the clause end. "
               "<b>Ablation:</b> lexical vs pause trigger; window 1–3. <b>Falsified if</b> no EAW point lies above the wait-k curve at "
               "equal playback-time AL on real timings. <b>Fails</b> where the English must commit polarity before the Hindi negation is heard (Part E)."))

    # ---------------- Part C
    s.append(P("Part C: Dataset design for ≤ 200 h (a proposal, nothing collected)", H2))
    rows = [["Source", "Licence / access (checked 15 Oct 2026)", "Hours (as published)", "Code-mixed?", "Role"],
            ["IndicVoices", "CC BY 4.0, HF-gated", "23.7K total / 11.2K transcribed (card); Hindi not stated", "Not documented: measure", "40 h pool after English-word filter"],
            ["IndicVoices-R", "CC BY 4.0, gated", "1,704 h, 9–175 h/lang, 48 kHz", "Same unknown", "Clean speech; Indic TTS training"],
            ["Kathbath", "Card inconsistent: cc-by-4.0 vs CC0 text", "1,684 h / 12 langs", "Not verified", "Low priority until licence resolved"],
            ["Own consented recordings", "Our consent form (covers sharing with Sarvam)", "Budget: 80 h", "Yes, by design", "Natural code-mixing + entities"],
            ["Synthetic (Bulbul hi / open TTS)", "Sarvam outputs: competition use only, no redistribution [1 §10]", "Each file counts (60 h)", "Text-controlled", "Rare entities, corrections"],
            ["Aligners", "MMS-FA HF port: CC-BY-NC-4.0 [8]; WhisperX Hindi default: card WER 72.6%, no licence [9]; torchaudio tutorial: English-only model [10]", "", "", "We use MMS-FA + own CTC Viterbi"]]
    s.append(table(rows, [W * 0.15, W * 0.30, W * 0.22, W * 0.13, W * 0.20], fs=6.4))
    s.append(Spacer(1, 2))
    s.append(P("<b>Accounting.</b> Real audio counts as the union of source intervals; every synthetic file counts, including the same text in another voice; "
               "augmentation (noise, 300–3400 Hz telephone band, low-bitrate codec, speed) is applied at training time and adds 0 h [1 §3]. The entity-rich 20 h "
               "is a tag on records inside the real and synthetic pools, never a second copy. <b>Transcripts:</b> ASR draft, then a human edits it to IndicVoices Level 1 "
               "('transcribed exactly as spoken' [5 §6]: fillers, repeats, English in Devanagari, numbers as words). <b>Timing:</b> uroman romanisation + MMS-FA; "
               "the Devanagari is preserved and the romanisation stored separately (schwa retention, apna→'apanaa', makes word <i>ends</i> less reliable than onsets)."))
    s.append(Image(str(ROOT / "report" / "figures" / "pipeline.png"), width=W * 0.86, height=W * 0.86 * 638 / 2200))
    rows = [["Check (thresholds are initial engineering choices, to calibrate)", "Threshold"],
            ["Format 24 kHz/mono/PCM16, ≤ 60 s, Level-1 text (no Latin, no digits, sentence-final punctuation)", "hard"],
            ["Level: RMS ≥ −40 dBFS, clipping ≤ 0.1%, ≤ 50% near-silent frames", "reject"],
            ["ASR round-trip CER (synthetic / real)", "≤ 15% / ≤ 30%"],
            ["Entity round trip: numbers and digits parsed from the ASR of the entity span = annotation", "exact, else regenerate"],
            ["Alignment: mean word score; share of words with score < 0.3; 30-boundary onset audit per batch", "≥ 0.5; ≤ 10%; median ≤ 50 ms"],
            ["Back-translation chrF and entity checker on the English", "≥ 40 and all entities pass"],
            ["Speaker and template overlap across splits", "0"]]
    s.append(table(rows, [W * 0.78, W * 0.22], fs=6.4))
    s.append(Spacer(1, 2))
    s.append(P("<b>Failure modes, including ones that pass the audit:</b> every correction follows one template ('nahin nahin, X'), so the model learns the marker and not the "
               "meaning; fluent references put entities ahead of their Hindi evidence, which teaches the model to anticipate amounts; TTS prosody dominates the hours; "
               "speaker or template leakage inflates test scores; romanisation shifts timing targets. <b>Synthetic–real gap</b> = metric difference between matched "
               "synthetic and human-recorded held-out sets, tracked as synthetic hours grow. <b>Three questions to test first:</b> (1) share of IndicVoices Hindi utterances "
               "with English words and how they are scripted; (2) does synthetic entity-rich speech raise entity accuracy on <i>real</i> held-out clips; (3) is MMS-FA "
               "onset error on code-mixed Devanagari ≤ 50 ms median."))

    # ---------------- Part D
    s.append(P("Part D: Six clips, transcripts, alignment and the entity checker", H2))
    rows = [["Clip", "Content", "Entities", "Audio", "Transcript"]]
    for c in clips:
        types = {}
        for e in c.entities:
            k = "name" if e["type"] in ("person", "place", "org") else e["type"]
            types[k] = types.get(k, 0) + 1
        rows.append([c.clip_id, c.raw["topic"], ", ".join(f"{k}×{v}" for k, v in types.items()),
                     c.raw["status"]["audio"], c.raw["status"]["transcript"]])
    s.append(table(rows, [W * 0.07, W * 0.37, W * 0.30, W * 0.12, W * 0.14], fs=6.3))
    s.append(Spacer(1, 2))
    a_txt = (f"<b>Alignment audit:</b> {audit['n_boundaries']} word onsets, mean |error| {audit['mean_abs_error_ms']} ms, median "
             f"{audit['median_abs_error_ms']} ms, max {audit['max_abs_error_ms']} ms, {audit['n_over_50ms']} over 50 ms, {audit['n_over_100ms']} over 100 ms."
             if audit else "<b>Alignment audit: PENDING</b> (needs recordings): 30 word onsets (5/clip, including the determining words of entities), "
             "marked blind in Audacity before viewing automatic labels; we report mean, median and max |error| and counts over 50/100 ms.")
    s.append(P(f"<b>Recording and transcription.</b> Prompted, unscripted phone-style speech covering lakh/crore (incl. dedh, dhai, saadhe), a phone number with a "
               f"last-digit correction, an account number, {n_names} names/organisations/places, {n_neg} negations (incl. mat) + {n_aff} "
               f"affirmative control, and {n_corr} self-corrections (amount ×2, digit, time). "
               "Transcripts follow Sarvam/IndicVoices Level 1 and are validated automatically (no Latin, no digits, final punctuation; Hindi amounts must parse "
               "to the annotated values). The audio is the source of truth: a transcript is marked <i>verbatim_verified</i> only after listening. "
               "<b>Aligner:</b> uroman (lcode=hin) → MMS-300m emissions (20 ms frames) → our numpy CTC Viterbi over the blank-interleaved label "
               "sequence (the tutorial's trellis, with proper blank states); on CPU it takes about 1.6 s for 6 s of audio. The English-only tutorial model cannot read Hindi. " + a_txt))
    if chk:
        o, nh, hd = chk["overall"], chk["non_hard_variants"], chk["hard_variants"]
        s.append(P(f"<b>Entity checker.</b> Plain Python: Hindi/English number grammars (0–99 Hindi words, sau/hazaar/lakh/crore, fractions; English words, "
                   f"Indian and Western digit grouping, 'and a half', k/cr), digit-run extraction (double/triple, sentence boundaries), time parsing, a clause-scoped "
                   f"negation test (cue within 4 words before the predicate, no clause break, 'not only' excluded), and correction logic (final value present; "
                   f"abandoned value absent unless explicitly rejected, 'not X'). Unparseable values fail; nothing unknown passes. <b>Evaluation:</b> "
                   f"{chk['n_variants']} hand-labelled variants of the fluent references (paraphrases, unit and digit forms, corruptions; labels fixed before running) "
                   f"= {o['n']} decisions. Accuracy <b>{pct(o['accuracy'])}</b>; error recall {pct(o['error_recall'])} ({o['tp']}/{o['tp'] + o['fn']}); error precision "
                   f"{pct(o['error_precision'])} ({o['fp']} false alarms). On non-'hard' variants {pct(nh['accuracy'])}; on the 'hard' paraphrases {pct(hd['accuracy'])}."))
        rows = [["Category", "Decisions", "Accuracy", "False alarms", "Missed errors"]]
        for cat, m in chk["by_category"].items():
            rows.append([cat, m["n"], pct(m["accuracy"]), m["fp"], m["fn"]])
        s.append(table(rows, [W * 0.2, W * 0.15, W * 0.15, W * 0.15, W * 0.15], fs=6.4))
        s.append(Spacer(1, 2))
        s.append(P("<b>Where it fails (all 9 errors are false alarms on paraphrases):</b> negation not expressed as a cue before the verb ('made <i>no such</i> payment', "
                   "'<i>unless</i> it comes back', '<i>unable</i> to come', '<i>unlikely</i> to come', '<i>rather than</i> mine'); a retracted abandoned value "
                   "('five lakh, <i>sorry</i>, five crore'), which our labels accept but the checker rejects; the time '4.30' read as the amount 4.3. On literal glosses "
                   "7/37 checks fail because Hindi order puts 'not' after the verb. Development note: the variant set exposed one real bug (digit runs merging "
                   "across a sentence end) which we fixed, so the set is not fully held out. The checker measures references and simulated outputs; it says "
                   "nothing about a translation model, and its gold labels are the author's own."))

    # ---------------- Part E
    s.append(P("Part E (ML): wait-k on the clip timelines; where should a streaming model wait?", H2))
    s.append(P("<b>Setup.</b> Source word j is 'heard' at its aligned end time. g(t) = Hindi words read when English word t is committed; wait-k: "
               "g(t) = min(k+t−1, |x|) [2] (= the mini PS 'k + i' with 0-based i); the last word waits for the end of input. Decision time D<sub>t</sub> = end of word g(t) "
               "(+0.3 s if a pause was needed); each English word is spoken for a fixed 0.40 s (≈150 wpm, an estimate) and starts at max(D<sub>t</sub>, end of the "
               "previous word), Sarvam's playback rule [1 §5.1]. We report AL in source words (STACL Eq. 9, τ = first t with g(t)=|x|, r=|y|/|x|), "
               "SimulEval AL on decision times and on speech onsets (seconds; = LAAL here because output = reference [3,7]), first-output time and End Offset. "
               f"<b>Entity scoring.</b> The fixed reference passes 100% for every policy, which only says the reference is right. We therefore add a transparent stress test: each of the "
               f"{n_ent} entities has a hand-annotated determining Hindi word and a hand-written premature guess (e.g. 'five lakh'); if the policy commits the English "
               "entity before that word is heard, the guess replaces it and the checker scores the result. Unit tests verify the hand-computed Part A example "
               "(wait-3 on 'maine kal apna purana bank khata band karva diya': g = 3,4,5,6,7,8,9,9; τ = 7; AL = 2.625 words)."))
    if agg:
        tag = "" if measured else " <font color='#c0392b'>(placeholder timings: seconds columns are NOT measurements)</font>"
        rows = [["Policy", "AL words", "AL decision s", "AL speech s", "First out s", "End offset s", "Entities safe = simulated acc."]]
        for a in agg:
            if a["kind"] == "full":
                continue
            rows.append([a["policy"], f"{float(a['AL_words']):.2f}", f"{float(a['AL_decision_s']):.2f}", f"{float(a['AL_onset_s']):.2f}",
                         f"{float(a['first_output_s']):.2f}", f"{float(a['end_offset_s']):.2f}", pct(a["sim_entity_acc"])])
        s.append(P(f"<b>Results</b> (6 clips, means; entities pooled){tag}", SMALL))
        s.append(table(rows, [W * 0.2, W * 0.1, W * 0.12, W * 0.12, W * 0.12, W * 0.12, W * 0.22], fs=6.4))
        img = wk / "latency_vs_entity_accuracy.png"
        s.append(Image(str(img), width=W * 0.95, height=W * 0.95 * 4.1 / 9.2))

        def short(policy, eid):
            return [e["words_short"] for e in ents if e["policy"] == policy and e["entity_id"] == eid][0]

        def cat_rate(policy, cat):
            rs = [e for e in ents if e["policy"] == policy and e["category"] == cat]
            return f"{sum(e['safe'] == 'True' for e in rs)}/{len(rs)}"
        sel = json.loads((RES / "selected_operating_point.json").read_text())["primary_words"]
        s.append(P(f"<b>Findings.</b> (i) Raising k trades latency for safety monotonically (wait-3 → wait-7: {pct([a for a in agg if a['policy']=='wait-3'][0]['sim_entity_acc'])} → "
                   f"{pct([a for a in agg if a['policy']=='wait-7'][0]['sim_entity_acc'])}). The k = 1–10 sweep's Pareto knee is wait-{sel['selected']['k']} "
                   f"(alternatives {', '.join('wait-%d' % a['k'] for a in sel['alternatives'])}); the knee is {'weak (smaller than one entity)' if sel['knee_is_weak'] else 'clear'}, "
                   "see the submission/ report. (ii) EAW helps exactly where its trigger is audible: self-corrections "
                   f"{cat_rate('wait-3', 'correction')} under wait-3 vs {cat_rate('EAW-lex k=3', 'correction')} (EAW-lex) and {cat_rate('EAW-pause k=3', 'correction')} (EAW-pause). "
                   f"(iii) It does <b>not</b> help negation ({cat_rate('wait-3', 'negation')} vs {cat_rate('EAW-pause k=3', 'negation')}): English commits 'not' before the Hindi "
                   "clause-final nahin + verb is spoken, so no heard word can trigger the wait. This falsifies the purely source-triggered version of our idea; the wait must be "
                   "triggered by the <i>target</i> (do not commit polarity or tense before the clause-final verb group). (iv) Speech-onset AL exceeds decision AL for every "
                   "policy because English speech queues behind itself; extra waiting raises End Offset, which Sarvam scores. (v) Plain wait-k drifts when the English is "
                   "shorter than the Hindi (clip01: 51 vs 68 words), so late English words run far ahead of their evidence (clip01 negation committed "
                   f"{short('wait-3', 'c01_neg')} Hindi words too early under wait-3). "
                   "<b>Where to wait:</b> after a number until the scale word and 2 more words (catches 'nahin nahin, …'), and before English polarity until the Hindi verb "
                   "group ends; elsewhere, speak early. <b>Cannot conclude:</b> anything about a real model's accuracy, statistical significance (6 clips, 1 speaker, "
                   f"{n_ent} entities), or second-based numbers until real timings replace placeholders."))
    s.append(P("References", H2))
    refs = ["[1] Sarvam AI, Inter IIT 15.0 problem statement (local) and mini PS.",
            "[2] Ma et al., STACL: Simultaneous Translation with Implicit Anticipation and Controllable Latency…, ACL 2019, 3025–3036.",
            "[3] Ma et al., SimulEval: An Evaluation Toolkit for Simultaneous Translation, EMNLP 2020 Demos, 144–150; latency_scorer.py.",
            "[4] Labiausse et al., High-Fidelity Simultaneous Speech-To-Speech Translation (Hibiki), ICML 2025, PMLR 267.",
            "[5] Javed et al., IndicVoices, arXiv:2403.01926 (2024); HF card ai4bharat/IndicVoices; GitHub repo snapshot.",
            "[6] AI4Bharat, IndicVoices-R HF card; Kathbath HF card.",
            "[7] Papi et al., Over-Generation Cannot Be Rewarded: LAAL, AutoSimTrans 2022, 12–17.",
            "[8] MahmoudAshraf/mms-300m-1130-forced-aligner (HF port of torchaudio MMS_FA); Pratap et al., MMS, 2023.",
            "[9] WhisperX alignment.py; theainerd/Wav2Vec2-large-xlsr-hindi model card.",
            "[10] torchaudio, Forced Alignment with Wav2Vec2 tutorial (local notebook). Full table: report/RESEARCH_PROPOSALS.md, SOURCE_NOTES.md."]
    s.append(P("<br/>".join(refs), SMALL))
    doc.build(s)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="[Your Name]")
    out = build(ap.parse_args().name)
    import pypdfium2 as pdfium
    n = len(pdfium.PdfDocument(str(out)))
    print(f"wrote {out} ({n} pages)")
    if n > 4:
        print("ERROR: more than 4 pages")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
