"""Render the Part C pipeline diagram to report/figures/pipeline.png (matplotlib only).

Usage: python report/make_figures.py
The Mermaid source of the same diagram is in report/DATASET_DESIGN.md §8.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures" / "pipeline.png"
STEPS = [
    ("1 Acquire", "own consented recordings\nIndicVoices/-R (CC BY)\nsynthetic TTS\nlicence + consent"),
    ("2 Normalise", "24 kHz mono PCM16\n<=60 s, 1 speaker\nlevel / clipping"),
    ("3 Transcribe", "ASR draft -> human\nLevel 1 verbatim\nEn words in Devanagari"),
    ("4 Align", "uroman + MMS-FA\nCTC Viterbi\nword scores"),
    ("5 Translate", "fluent + literal\nLLM / IndicTrans2\n-> human review"),
    ("6 Annotate", "amounts, digits,\nnames, negation,\nfinal vs abandoned"),
    ("7 Check", "ASR & entity round trip\nalign confidence\nback-translation"),
    ("8 Audit", "30-boundary audits\nfailed checks\n5% random sample"),
    ("9 Split", "speaker- and\ntemplate-disjoint"),
    ("10 Manifest", "§5.2 JSONL\nhour counter\nreproducible rebuild"),
]


def main() -> None:
    fig, ax = plt.subplots(figsize=(10, 2.9))
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 2)
    ax.axis("off")
    w, h = 0.88, 0.78
    pos = [(i % 5 + 0.06, 1.12 if i < 5 else 0.12) for i in range(10)]
    for (title, body), (x, y) in zip(STEPS, pos):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.04",
                                    fc="#eef4fc", ec="#2a78d6", lw=1.2))
        ax.text(x + w / 2, y + h - 0.12, title, ha="center", va="center", fontsize=8.5, weight="bold", color="#0b0b0b")
        ax.text(x + w / 2, y + h / 2 - 0.1, body, ha="center", va="center", fontsize=6.6, color="#333333")
    arrow = dict(arrowstyle="->", color="#52514e", lw=1.1)
    for i in range(4):
        ax.annotate("", (pos[i + 1][0], 1.51), (pos[i][0] + w, 1.51), arrowprops=arrow)
        ax.annotate("", (pos[i + 6][0], 0.51), (pos[i + 5][0] + w, 0.51), arrowprops=arrow)
    ax.annotate("", (pos[5][0] + w / 2, 0.12 + h), (pos[4][0] + w / 2, 1.12),
                arrowprops=dict(arrowstyle="->", color="#52514e", lw=1.1, connectionstyle="arc3,rad=0"))
    ax.annotate("", (pos[2][0] + w / 2, 1.12), (pos[6][0] + w / 2, 0.12 + h),
                arrowprops=dict(arrowstyle="->", color="#e34948", lw=1, ls="--", connectionstyle="arc3,rad=-0.25"))
    ax.text(2.05, 1.0, "fail -> redo", color="#e34948", fontsize=6.5)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT, dpi=220)
    plt.close(fig)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
