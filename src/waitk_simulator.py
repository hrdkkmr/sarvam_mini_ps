"""Deterministic timing simulation of simultaneous translation policies on recorded clips.

WHAT THIS IS: the English text is the fixed fluent reference translation, prepared in
advance with the whole sentence visible. The simulator only decides WHEN each English word
would be committed and spoken. It is a timing simulation, not a streaming translation model:
it cannot reproduce errors caused by generating from a source prefix.

Two entity scores are therefore reported:
  fixed_text_acc  -- checker on the unmodified reference. Identical for every policy by
                     construction; it measures the reference, not the policy.
  sim_entity_acc  -- ambiguity-sensitive stress test. Each annotated entity has a
                     determining source word (src_idx, e.g. the करोड़ in "पाँच करोड़" or the
                     corrected digit) and a commit point in the English (tgt_idx = first
                     token of en_phrase). If the policy commits the English phrase before the
                     determining word has been read, the phrase is replaced by the annotated
                     `premature_en` (the best guess available from the prefix, e.g. "five
                     lakh"), or by "<unk>" if no guess is possible (a name not yet heard).
                     The checker is then run on that output. The premature guesses are
                     hand-written, not model outputs.
  evidence_safe   -- fraction of entities committed after their determining word.

Conventions (all documented in RESULTS.md and the report):
  * source word j is "read" at its aligned END time.
  * g(t) = number of source words read when target word t is committed.
  * EOS: the last target word is committed only after the full source is read
    (g(|y|) = |x|), because the system cannot know the speaker has finished earlier.
  * decision time D_t = end time of source word g(t) (+ PAUSE_S if the decision needed a
    pause to be observed) + compute latency (0 by default: no model is run).
  * speech: each English word lasts TGT_WORD_S seconds (fixed estimate, ~150 words/min);
    onset_t = max(D_t, end of previous English word) -- the Sarvam playback rule
    "each frame starts when it arrives or when the previous one finishes".
    These speech times are ESTIMATES, not TTS measurements.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .adaptive_policy import PAUSE_S, eaw_schedule, waitk_schedule
from .dataset import Clip
from .entity_checker import check_all
from .latency_metrics import al_time, al_words, average_proportion, end_offset

TGT_WORD_S = 0.40


@dataclass
class Policy:
    name: str
    kind: str              # "waitk" | "eaw_lex" | "eaw_pause" | "sentence" | "full"
    k: int | None = None

    def schedule(self, clip: Clip) -> tuple[list[int], list[bool]]:
        n, m = len(clip.src_words), len(clip.tgt_tokens)
        if self.kind == "waitk":
            g, p = waitk_schedule(n, m, self.k), [False] * m
        elif self.kind == "full":
            g, p = waitk_schedule(n, m, None), [False] * m
        elif self.kind == "sentence":
            g, p = [clip.src_sent_last[s] for s in clip.tgt_sent], [False] * m
        else:
            g, p, _ = eaw_schedule(clip.src_words, clip.tgt_tokens, self.k,
                                   use_pause=self.kind == "eaw_pause")
        g = list(g)
        g[-1] = n                        # EOS convention
        return g, p


WAITK_SWEEP = tuple(range(1, 11))       # k = 1..10, evaluated automatically (src/sweep.py)

DEFAULT_POLICIES = [Policy(f"wait-{k}", "waitk", k) for k in WAITK_SWEEP] + \
    [Policy(f"EAW-lex k={k}", "eaw_lex", k) for k in (2, 3)] + \
    [Policy(f"EAW-pause k={k}", "eaw_pause", k) for k in (2, 3)] + \
    [Policy("sentence-by-sentence", "sentence", None), Policy("whole-clip", "full", None)]


@dataclass
class RunResult:
    clip_id: str
    policy: str
    kind: str
    k: int | None
    timing_source: str
    g: list[int]
    decision_s: list[float]
    onset_s: list[float]
    metrics: dict
    entity_rows: list[dict] = field(default_factory=list)
    sim_text: str = ""


def premature_output(clip: Clip, g: list[int]) -> tuple[str, list[dict]]:
    toks = list(clip.tgt_tokens)
    rows = []
    for e in sorted(clip.entities, key=lambda e: -e["tgt_idx"]):
        read_at_commit = g[e["tgt_idx"]]                 # words read
        safe = read_at_commit >= e["src_idx"] + 1
        rows.append({"entity_id": e["id"], "type": e["type"], "src_idx": e["src_idx"],
                     "tgt_idx": e["tgt_idx"], "read_at_commit": read_at_commit,
                     "words_short": max(0, e["src_idx"] + 1 - read_at_commit), "safe": safe})
        if not safe:
            span = len(e["en_phrase"].split())
            repl = (e.get("premature_en") or "<unk>").split()
            toks[e["tgt_idx"]:e["tgt_idx"] + span] = repl
    return " ".join(toks), rows[::-1]


def simulate(clip: Clip, policy: Policy, tgt_word_s: float = TGT_WORD_S,
             compute_s: float = 0.0) -> RunResult:
    g, pause_flags = policy.schedule(clip)
    n = len(clip.src_words)
    src_dur = clip.src_end_time
    decision = [clip.src_words[gt - 1]["end"] + (PAUSE_S if pf and gt < n else 0.0) + compute_s
                for gt, pf in zip(g, pause_flags)]
    # decisions cannot go backwards in time
    for i in range(1, len(decision)):
        decision[i] = max(decision[i], decision[i - 1])
    onset, prev_end = [], 0.0
    for d in decision:
        s = max(d, prev_end)
        onset.append(s)
        prev_end = s + tgt_word_s
    sim_text, ent_rows = premature_output(clip, g)
    fixed = check_all(clip.entities, clip.tgt_fluent, "fluent")
    simc = check_all(clip.entities, sim_text, "fluent")
    fixed_by_id = {f.entity_id: f for f in fixed}
    sim_by_id = {s.entity_id: s for s in simc}
    for r in ent_rows:
        f, s = fixed_by_id[r["entity_id"]], sim_by_id[r["entity_id"]]
        r.update(category=s.category, fixed_pass=f.passed, sim_pass=s.passed, sim_reason=s.reason)
    m = {
        "n_src_words": n, "n_tgt_words": len(g), "src_duration_s": round(src_dur, 3),
        "AL_words": al_words(g, n),
        "AP": average_proportion(g, n),
        "AL_decision_s": al_time(decision, src_dur),
        "AL_onset_s": al_time(onset, src_dur),
        "first_output_s": onset[0],
        "end_offset_s": end_offset(prev_end, src_dur),
        "n_entities": len(ent_rows),
        "evidence_safe": sum(r["safe"] for r in ent_rows),
        "fixed_text_pass": sum(r["fixed_pass"] for r in ent_rows),
        "sim_pass": sum(r["sim_pass"] for r in ent_rows),
    }
    return RunResult(clip.clip_id, policy.name, policy.kind, policy.k, clip.timing_source,
                     g, decision, onset, m, ent_rows, sim_text)
