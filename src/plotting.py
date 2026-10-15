"""Static PNG plots for the report. Every function takes rows READ BACK FROM THE RESULT CSVs
(see scripts/evaluate_waitk.py), never hand-typed values."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# reference categorical palette (dataviz skill, light mode), fixed order
FAMILY_STYLE = {
    "waitk": {"color": "#2a78d6", "marker": "o", "label": "wait-k"},
    "eaw_lex": {"color": "#eb6834", "marker": "s", "label": "EAW-lex (ours, heuristic)"},
    "eaw_pause": {"color": "#1baf7a", "marker": "D", "label": "EAW-pause (ours, heuristic)"},
    "sentence": {"color": "#52514e", "marker": "^", "label": "sentence-by-sentence"},
}
INK, MUTED, GRID, WARN = "#0b0b0b", "#52514e", "#e4e3df", "#c0392b"
BLUE = FAMILY_STYLE["waitk"]["color"]
SIM_TAG = "Text-based wait-k simulation (6 annotated Hindi text samples, no audio)"


def _style(ax):
    ax.grid(color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)


def _sec_label(timing_source: str) -> str:
    return "" if timing_source == "mms_fa_auto" else " - ESTIMATED (placeholder timings, 0.40 s/English word)"


def _subtitle(fig, timing_source: str, extra: str = "") -> None:
    measured = timing_source == "mms_fa_auto"
    fig.text(0.5, 0.915, SIM_TAG if not measured else "Wait-k simulation on aligned recordings",
             ha="center", fontsize=8, color=MUTED)
    if extra:
        fig.text(0.5, 0.872, extra, ha="center", fontsize=7.5, color=WARN if not measured else MUTED)


def _save(fig, out: Path, top: float = 0.875) -> None:
    fig.tight_layout()
    fig.subplots_adjust(top=top)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)


def plot_tradeoff(agg: list[dict], out: Path, timing_source: str) -> None:
    """Main trade-off graph: simulated entity accuracy vs AL (words) and vs AL of speech onsets (s)."""
    rows = [r for r in agg if r["kind"] != "full"]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.1), sharey=True)
    panels = [("AL_words", "Average Lagging (source words, STACL Eq. 9)"),
              ("AL_onset_s", "AL of English speech onsets (s)" + ("" if timing_source == "mms_fa_auto" else ", ESTIMATED"))]
    for ax, (xkey, xlabel) in zip(axes, panels):
        for kind, st in FAMILY_STYLE.items():
            pts = sorted((r for r in rows if r["kind"] == kind), key=lambda r: r[xkey])
            if not pts:
                continue
            xs = [r[xkey] for r in pts]
            ys = [100 * r["sim_entity_acc"] for r in pts]
            ax.plot(xs, ys, color=st["color"], lw=2 if len(pts) > 1 else 0, marker=st["marker"],
                    ms=7 if kind != "waitk" else 6, mec="white", mew=1.5, label=st["label"], zorder=3)
            if kind == "waitk":
                for r, x, y in zip(pts, xs, ys):
                    if r["k"] in ((1, 3, 5, 7, 9, 10) if xkey == "AL_words" else (1, 3, 9)):
                        ax.annotate(f"k={r['k']}", (x, y), textcoords="offset points", xytext=(5, -11),
                                    fontsize=7, color=MUTED)
            elif kind == "sentence":
                ax.annotate("sentence", (xs[0], ys[0]), textcoords="offset points", xytext=(-7, -3),
                            ha="right", va="top", fontsize=7, color=MUTED)
        fixed = 100 * rows[0]["fixed_text_acc"]
        ax.axhline(fixed, color=MUTED, lw=1.2, ls="--", zorder=2)
        ax.text(ax.get_xlim()[0] + 0.02 * (ax.get_xlim()[1] - ax.get_xlim()[0]), fixed + 1.2,
                f"fixed-reference acc. = {fixed:.0f}% for all policies (text never changes)",
                ha="left", va="bottom", fontsize=7, color=MUTED)
        ax.set_xlabel(xlabel, fontsize=8.5, color=INK if xkey == "AL_words" or timing_source == "mms_fa_auto" else WARN)
        _style(ax)
    axes[0].set_ylabel("Simulated entity accuracy (%)\n(premature-commitment stress test)", fontsize=8.5, color=INK)
    axes[0].set_ylim(0, 112)
    axes[0].legend(fontsize=7, frameon=False, loc="lower right", handlelength=2.5)
    fig.suptitle("Simulated entity accuracy vs latency", fontsize=10.5, color=INK, y=0.985)
    _subtitle(fig, timing_source, "Right panel: estimated latency, not a measurement" if timing_source != "mms_fa_auto" else "")
    _save(fig, out, top=0.83)


def plot_k_sweep(agg: list[dict], out: Path, timing_source: str) -> None:
    """Three small multiples over k (no dual axis): entity rates, AL in words, AL in seconds."""
    wk = sorted((r for r in agg if r["kind"] == "waitk"), key=lambda r: r["k"])
    ks = [r["k"] for r in wk]
    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.5))
    ax = axes[0]
    ax.plot(ks, [100 * r["evidence_safe_rate"] for r in wk], color=BLUE, lw=2, marker="o", ms=6,
            mec="white", mew=1.5, label="evidence-safe = simulated acc.", zorder=3)
    ax.plot(ks, [100 * r["fixed_text_acc"] for r in wk], color=MUTED, lw=1.2, ls="--",
            label="fixed-reference acc. (constant)", zorder=2)
    ax.set_ylim(0, 110)
    ax.set_ylabel("% of 37 entities", fontsize=8.5)
    ax.set_title("Entity metrics", fontsize=9, color=INK)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    ax = axes[1]
    ax.plot(ks, [r["AL_words"] for r in wk], color=BLUE, lw=2, marker="o", ms=6, mec="white", mew=1.5)
    ax.set_ylabel("source words", fontsize=8.5)
    ax.set_title("Average Lagging (words)", fontsize=9, color=INK)
    ax = axes[2]
    est = timing_source != "mms_fa_auto"
    ax.plot(ks, [r["AL_onset_s"] for r in wk], color=BLUE, lw=2, marker="o", ms=6, mec="white", mew=1.5,
            ls="--" if est else "-", label="AL of speech onsets")
    ax.plot(ks, [r["end_offset_s"] for r in wk], color=FAMILY_STYLE["sentence"]["color"], lw=1.5, marker="^",
            ms=6, mec="white", mew=1.5, ls="--" if est else "-", label="End Offset")
    ax.set_ylabel("seconds", fontsize=8.5)
    ax.set_title("Latency in seconds" + (" (ESTIMATED)" if est else ""), fontsize=9, color=WARN if est else INK)
    ax.legend(fontsize=7, frameon=False, loc="upper left")
    for a in axes:
        a.set_xticks(ks)
        a.set_xlabel("k (Hindi words read before the first English word)", fontsize=7.5)
        _style(a)
    fig.suptitle("Wait-k sweep, k = 1 to 10", fontsize=10.5, color=INK, y=0.985)
    _subtitle(fig, timing_source, ("Seconds" + _sec_label(timing_source)) if est else "")
    _save(fig, out, top=0.76)


def plot_pareto(agg: list[dict], selection: dict, out: Path, timing_source: str) -> None:
    """Pareto frontier of the wait-k sweep (accuracy metric vs AL in words), selected point ringed."""
    acc, lat = selection["accuracy_metric"], selection["latency_metric"]
    wk = sorted((r for r in agg if r["kind"] == "waitk"), key=lambda r: r["k"])
    front = set(selection["pareto_k"])
    alts = {a["k"] for a in selection["alternatives"]}
    sel_k = selection["selected"]["k"]
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    fp = [r for r in wk if r["k"] in front]
    ax.plot([r[lat] for r in fp], [100 * r[acc] for r in fp], color=BLUE, lw=2, zorder=2,
            label="Pareto frontier (wait-k)")
    lo, hi = min(fp, key=lambda r: r[lat]), max(fp, key=lambda r: r[acc])
    ax.plot([lo[lat], hi[lat]], [100 * lo[acc], 100 * hi[acc]], color=MUTED, lw=1, ls=":", zorder=1,
            label="chord used for the knee test")
    for r in wk:
        on = r["k"] in front
        ax.plot(r[lat], 100 * r[acc], marker="o", ms=8, mec=BLUE if on else MUTED, mew=1.5,
                mfc=BLUE if on else "white", ls="none", zorder=3)
        ax.annotate(f"k={r['k']}", (r[lat], 100 * r[acc]), textcoords="offset points", xytext=(6, -12),
                    fontsize=7.5, color=INK if r["k"] in alts | {sel_k} else MUTED)
    ax.plot([], [], marker="o", mfc="white", mec=MUTED, ls="none", label="dominated wait-k")
    s = next(r for r in wk if r["k"] == sel_k)
    ax.plot(s[lat], 100 * s[acc], marker="o", ms=17, mfc="none", mec=INK, mew=1.8, ls="none", zorder=4,
            label=f"selected: wait-{sel_k} ({'weak ' if selection.get('knee_is_weak') else ''}knee)")
    for r in wk:
        if r["k"] in alts:
            ax.plot(r[lat], 100 * r[acc], marker="o", ms=13, mfc="none", mec=INK, mew=1, ls="none", zorder=4)
    ax.plot([], [], marker="o", ms=10, mfc="none", mec=INK, mew=1, ls="none", label="near-equivalent alternatives")
    sent = [r for r in agg if r["kind"] == "sentence"]
    for r in sent:
        ax.plot(r[lat], 100 * r[acc], marker="^", ms=8, color=FAMILY_STYLE["sentence"]["color"], mec="white",
                ls="none", zorder=3, label="sentence-by-sentence (reference, not a k)")
    ax.set_xlabel("Average Lagging (source words, STACL Eq. 9)  - lower is better", fontsize=8.5)
    ax.set_ylabel("Evidence-safe entity rate (%)  - higher is better\n(= simulated entity accuracy here)", fontsize=8.5)
    ax.set_ylim(35, 105)
    ax.legend(fontsize=7, frameon=False, loc="lower right")
    _style(ax)
    fig.suptitle("Pareto frontier and selected operating point", fontsize=10.5, color=INK, y=0.985)
    _subtitle(fig, timing_source, "")
    _save(fig, out, top=0.91)
