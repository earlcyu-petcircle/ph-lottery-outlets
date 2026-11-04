"""
Atlas Grid, the story site's design (docs/index.html), for the static charts and maps.

White ground, near-black ink and one cobalt accent; headings in Bricolage Grotesque 800, text
in Public Sans and numbers in JetBrains Mono; bars flat cobalt on a 2px black baseline, with
mono value labels and no gridlines.

The fonts are static cuts committed in src/shared/fonts/ (rebuilt by fonts/build_fonts.py).
If they are missing, register_fonts() warns and the charts fall back to DejaVu Sans and DejaVu
Sans Mono, which matplotlib always has, so a chart still draws, in the wrong typeface.

Used by src/03_analyse/charts.py, maps.py and pcso_background.py.
"""
import warnings
from pathlib import Path

import matplotlib.font_manager as fm
from matplotlib.lines import Line2D

FONTS = Path(__file__).resolve().parent / "fonts"

# The site's :root tokens
BG, INK, INK_SOFT, MUTED = "#FFFFFF", "#111111", "#333333", "#555555"
ACCENT, GRID, RULE = "#1F4FE0", "#F3F5FB", "#DADDE6"

HEAD, BODY, MONO = "Bricolage Grotesque", "Public Sans", "JetBrains Mono"
_FALLBACK = {HEAD: "DejaVu Sans", BODY: "DejaVu Sans", MONO: "DejaVu Sans Mono"}
_registered = None


def register_fonts():
    """Add the committed fonts to matplotlib once; True when all three families are there."""
    global _registered
    if _registered is None:
        files = sorted(FONTS.glob("*.ttf"))
        for f in files:
            fm.fontManager.addfont(str(f))
        names = {fm.FontProperties(fname=str(f)).get_name() for f in files}
        _registered = {HEAD, BODY, MONO} <= names
        if not _registered:
            warnings.warn(f"Atlas fonts missing from {FONTS}; falling back to DejaVu Sans. "
                          "Run src/shared/fonts/build_fonts.py to rebuild them.")
    return _registered


def family(name):
    """The family to ask matplotlib for: the Atlas font, or its fallback."""
    return name if register_fonts() else _FALLBACK[name]


def style():
    """rc settings for plt.rc_context: the Atlas ground, ink and body font."""
    register_fonts()
    # DejaVu Sans after Public Sans supplies the glyphs Public Sans lacks, such as arrows
    return {"font.family": [family(BODY), "DejaVu Sans"], "font.size": 9, "text.color": INK, "axes.edgecolor": INK,
            "axes.labelcolor": INK_SOFT, "xtick.color": INK_SOFT, "ytick.color": INK_SOFT,
            "axes.titlecolor": INK, "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
            "legend.frameon": False}


def head(size, **kw):
    """Font settings for a heading: Bricolage Grotesque 800."""
    return {"fontfamily": family(HEAD), "fontweight": 800, "fontsize": size, "color": INK, **kw}


def mono(size, bold=False, **kw):
    """Font settings for numbers and kickers: JetBrains Mono 400 or 600."""
    return {"fontfamily": family(MONO), "fontweight": 600 if bold else 400, "fontsize": size, **kw}


def kicker(fig, x, y, text, **kw):
    """The site's mono kicker, e.g. 'PH / LOTTO OUTLETS / 2026', in cobalt capitals."""
    return fig.text(x, y, text.upper(), color=ACCENT, **mono(8, bold=True), **kw)


def heading(fig, title, subtitle=None, kick="PH / LOTTO OUTLETS / 2026", x=0.012):
    """The site's chart heading, a fixed size whatever the figure's height: a cobalt mono kicker,
    a Bricolage title and a muted subtitle (a string, or lines joined by newlines). Returns the
    figure fraction left below it, for tight_layout's rect top."""
    h = fig.get_figheight()
    y = lambda inches: 1 - inches / h
    kicker(fig, x, y(0.16), kick, va="top")
    fig.text(x, y(0.36), title, va="top", **head(13))
    if not subtitle:
        return y(0.72)
    fig.text(x, y(0.68), subtitle, va="top", fontsize=8.5, color=MUTED, linespacing=1.45)
    return y(0.98 + 0.17 * subtitle.count("\n"))


def rule(fig, y, x0=0.0, x1=1.0, width=2.25):
    """A black rule across the figure at height y (figure fraction), like the site's 3px rules."""
    fig.add_artist(Line2D([x0, x1], [y, y], transform=fig.transFigure, color=INK, linewidth=width,
                          solid_capstyle="butt"))


def baseline(ax, y=0):
    """The 2px black baseline under bars (1.5pt, which is 2px at 96 dpi)."""
    ax.axhline(y, color=INK, linewidth=1.5, zorder=3, solid_capstyle="butt")


def bare(ax):
    """No spines, ticks or gridlines."""
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    ax.grid(False)
