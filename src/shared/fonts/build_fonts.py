#!/usr/bin/env python3
"""
Rebuild the Atlas Grid chart fonts in this folder from Google Fonts.

The story site (docs/index.html) loads Bricolage Grotesque, Public Sans and JetBrains Mono from
Google Fonts. Matplotlib cannot pick a weight out of a variable font, so this script downloads
the three variable fonts from the google/fonts repository at a pinned commit and cuts the
static weights the charts use. The cut files and the fonts' Open Font Licences are committed,
so the charts need no download; this script is only for rebuilding them.

Usage:  .venv/bin/python src/shared/fonts/build_fonts.py
"""
import io
from pathlib import Path

import requests
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
COMMIT = "2fe1e8c6b137fb13041a7cfca6fdcd8a910ea4dc"  # google/fonts main, 4 Nov 2026
BASE = f"https://raw.githubusercontent.com/google/fonts/{COMMIT}/ofl"
# output file -> (folder, variable font, family, style, axis coordinates); the site's weights
CUTS = {
    "BricolageGrotesque-ExtraBold.ttf": ("bricolagegrotesque", "BricolageGrotesque[opsz,wdth,wght].ttf",
                                         "Bricolage Grotesque", "ExtraBold", {"wght": 800, "opsz": 24, "wdth": 100}),
    "PublicSans-Regular.ttf": ("publicsans", "PublicSans[wght].ttf", "Public Sans", "Regular", {"wght": 400}),
    "PublicSans-SemiBold.ttf": ("publicsans", "PublicSans[wght].ttf", "Public Sans", "SemiBold", {"wght": 600}),
    "JetBrainsMono-Regular.ttf": ("jetbrainsmono", "JetBrainsMono[wght].ttf", "JetBrains Mono", "Regular",
                                  {"wght": 400}),
    "JetBrainsMono-SemiBold.ttf": ("jetbrainsmono", "JetBrainsMono[wght].ttf", "JetBrains Mono", "SemiBold",
                                   {"wght": 600}),
}
LICENCES = {"bricolagegrotesque": "OFL-BricolageGrotesque.txt", "publicsans": "OFL-PublicSans.txt",
            "jetbrainsmono": "OFL-JetBrainsMono.txt"}


def fetch(path):
    r = requests.get(f"{BASE}/{path}", timeout=60)
    r.raise_for_status()
    return r.content


def _name(font, family, style, weight):
    """Plain names for the static cut, so matplotlib finds it by family and weight."""
    table = font["name"]
    full = f"{family} {style}"
    for nid, value in ((1, family), (2, "Regular"), (4, full), (6, full.replace(" ", "")),
                       (16, family), (17, style)):
        table.setName(value, nid, 3, 1, 0x409)
    font["OS/2"].usWeightClass = weight


def main():
    for out, (folder, name, family, style, axes) in CUTS.items():
        font = TTFont(io.BytesIO(fetch(f"{folder}/{name}")))
        static = instantiateVariableFont(font, axes)
        _name(static, family, style, axes["wght"])
        static.save(HERE / out)
        print(f"wrote {out}")
    for folder, out in LICENCES.items():
        (HERE / out).write_bytes(fetch(f"{folder}/OFL.txt"))
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
