"""Entity accuracy vs latency plot (static PNG for the PDF report)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# reference categorical palette (dataviz skill, light mode), fixed order
FAMILY_STYLE = {
    "waitk": {"color": "#2a78d6", "marker": "o", "label": "wait-k"},
    "eaw_lex": {"color": "#eb6834", "marker": "s", "label": "EAW-lex (ours)"},
    "eaw_pause": {"color": "#1baf7a", "marker": "D", "label": "EAW-pause (ours)"},
    "sentence": {"color": "#52514e", "marker": "^", "label": "sentence-by-sentence"},
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"


def plot_tradeoff(agg: list[dict], out: Path, timing_source: str) -> None:
    """agg rows: policy, kind, k, AL_words, AL_onset_s, sim_entity_acc, fixed_text_acc."""
    rows = [r for r in agg if r["kind"] != "full"]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.6), sharey=True)
    panels = [("AL_words", "Average Lagging (source words, STACL Eq. 9)"),
              ("AL_onset_s", "Average Lagging of English speech onsets (s, estimated)")]
    for ax, (xkey, xlabel) in zip(axes, panels):
        for kind, st in FAMILY_STYLE.items():
            pts = sorted((r for r in rows if r["kind"] == kind), key=lambda r: r[xkey])
            if not pts:
                continue
            xs = [r[xkey] for r in pts]
            ys = [100 * r["sim_entity_acc"] for r in pts]
            ax.plot(xs, ys, color=st["color"], lw=2 if len(pts) > 1 else 0, marker=st["marker"],
                    ms=7, mec="white", mew=1.5, label=st["label"], zorder=3)
            off = (6, -12) if kind == "waitk" else (-8, 7)
            for r, x, y in zip(pts, xs, ys):
                lab = f"k={r['k']}" if r["k"] is not None else "sentence"
                ax.annotate(lab, (x, y), textcoords="offset points", xytext=off,
                            ha="left" if kind == "waitk" else "right",
                            fontsize=7.5, color=st["color"] if kind != "sentence" else MUTED)
        fixed = 100 * rows[0]["fixed_text_acc"]
        ax.axhline(fixed, color=MUTED, lw=1.2, ls="--", zorder=2)
        ax.text(ax.get_xlim()[0] + 0.02 * (ax.get_xlim()[1] - ax.get_xlim()[0]), fixed + 1.5,
                "fixed reference text: identical for every policy", ha="left", va="bottom",
                fontsize=7.5, color=MUTED)
        ax.set_xlabel(xlabel, fontsize=8.5, color=INK)
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(MUTED)
        ax.tick_params(colors=MUTED, labelsize=8)
    axes[0].set_ylabel("Entities correct in simulated output (%)", fontsize=8.5, color=INK)
    axes[0].set_ylim(0, 110)
    axes[0].legend(fontsize=7.5, frameon=False, loc="lower right", handlelength=2.5)
    title = "Entity accuracy vs latency, 6 clips"
    if timing_source != "mms_fa_auto":
        title += f"  [timings: {timing_source.upper()} - NOT A MEASUREMENT]"
    fig.suptitle(title, fontsize=10, color=INK if timing_source == "mms_fa_auto" else "#e34948")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
