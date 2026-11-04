#!/usr/bin/env python3
"""
The two background charts in section 1 of docs/paper.md, saved to results/figures/:

  net_receipts_chart()   the statutory split of PCSO's net receipts under RA 1169, Section 6, as
                         amended by Batas Pambansa Blg. 42 (1979): 55% prizes, 30% charity fund,
                         15% operations (paper reference [11]) (pcso_net_receipts_split.png)
  gaming_revenue_chart() PCSO gaming revenue in 2024 by game: PHP 62.35 billion, of which the
                         Small Town Lottery PHP 31.76 billion and Lotto with digit games PHP 29.72
                         billion, from PCSO's 2024 year-end accomplishment report (reference [3])
                         (pcso_gaming_revenue_2024.png)

The figures are typed in from the cited sources, not computed from the data. Run by
03_analyse.sh; also runs on its own:  .venv/bin/python src/03_analyse/pcso_background.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

import atlas
from analysis_samples import FIGURES

# (share of net receipts %, label, colour): RA 1169 s 6 as amended by BP 42
NET_RECEIPTS = [(55, "Prizes", atlas.ACCENT), (30, "Charity fund", atlas.INK),
                (15, "Operations", atlas.RULE)]
# PHP billion, 2024: PCSO Accomplishment Report 2024, Year-end
GAMING_TOTAL = 62.35
GAMING = [("Small Town Lottery", 31.76), ("Lotto with digit games", 29.72)]


def _figure(size):
    fig = Figure(figsize=size, dpi=200)
    FigureCanvasAgg(fig)
    return fig


def _source(fig, text):
    fig.text(0.03, 0.03, text, color=atlas.MUTED, **atlas.mono(6.5))


def net_receipts_chart():
    with plt.rc_context(atlas.style()):
        fig = _figure((6.4, 3.9))
        top = atlas.heading(fig, "Where PCSO's net receipts go, by law",
                            "Section 6 of the PCSO Charter (RA 1169), as amended in 1979.\n"
                            "40% of the charity fund goes to PhilHealth (RA 11223, 2019).", x=0.03)
        ax = fig.add_axes((0.03, 0.1, 0.44, top - 0.13))
        shares = [s for s, _, _ in NET_RECEIPTS]
        ax.pie(shares, colors=[c for _, _, c in NET_RECEIPTS], startangle=90, counterclock=False,
               wedgeprops={"width": 0.36, "edgecolor": atlas.BG, "linewidth": 2})
        ax.text(0, 0, "Net\nreceipts", ha="center", va="center", linespacing=1.1, **atlas.head(10))
        ax.set_aspect("equal")
        y = top - 0.2
        for share, label, colour in NET_RECEIPTS:
            fig.patches.append(plt.Rectangle((0.53, y - 0.012), 0.022, 0.034, transform=fig.transFigure,
                                             color=colour, figure=fig))
            fig.text(0.575, y + 0.005, f"{share}%", va="center", **atlas.mono(15, bold=True), color=atlas.INK)
            fig.text(0.70, y + 0.005, label, va="center", fontsize=10, color=atlas.INK_SOFT)
            y -= 0.15
        _source(fig, "Source: Batas Pambansa Blg. 42 (1979), amending RA 1169, s 6 [11].")
        path = FIGURES / "pcso_net_receipts_split.png"
        fig.savefig(path)
    return path


def gaming_revenue_chart():
    rows = GAMING + [("Other games", round(GAMING_TOTAL - sum(v for _, v in GAMING), 2))]
    with plt.rc_context(atlas.style()):
        fig = _figure((6.4, 2.9))
        top = atlas.heading(fig, "PCSO gaming revenue, 2024: PHP 62.35 billion",
                            "Small Town Lottery brings in more than Lotto, and this study maps only Lotto.",
                            x=0.03)
        ax = fig.add_axes((0.3, 0.16, 0.56, top - 0.2))
        ys = range(len(rows))[::-1]
        ax.barh(list(ys), [v for _, v in rows], height=0.6, color=atlas.ACCENT, zorder=2)
        for y, (label, v) in zip(ys, rows):
            ax.text(v + 0.6, y, f"PHP {v:.2f} bn", va="center", **atlas.mono(8, bold=True), color=atlas.INK)
        ax.set_yticks(list(ys), [label for label, _ in rows], fontsize=9, color=atlas.INK_SOFT)
        atlas.bare(ax)
        ax.axvline(0, color=atlas.INK, linewidth=1.5, zorder=3)
        ax.set_xticks([])
        ax.set_xlim(0, 36)
        ax.set_ylim(-0.6, len(rows) - 0.4)
        _source(fig, "Source: PCSO Accomplishment Report 2024, Year-end [3]. Other games: the remainder.")
        path = FIGURES / "pcso_gaming_revenue_2024.png"
        fig.savefig(path)
    return path


if __name__ == "__main__":
    print(net_receipts_chart())
    print(gaming_revenue_chart())
