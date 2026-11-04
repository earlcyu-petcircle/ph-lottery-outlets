#!/usr/bin/env python3
"""
Colour-blind checks for the map palette in map_layers.py, the method of the Atlas palette
review (4 Nov 2026):

- Colour difference is Euclidean distance in OKLab x 100 (about 1 is a just-visible step).
- Colour-blind vision is simulated with Machado, Oliveira and Fernandes (2009) at severity 100,
  through colorspacious, for deuteranopia, protanopia and tritanopia.
- Each check reports its worst case across normal vision and the three simulations.
  8 or more is the target, 6 to 8 the floor.

Checks: the outlet ramp (light to dark in every vision, closest adjacent steps), the wealth
scale (closest adjacent steps, the two poles at matching depth), the 9 bivariate cells (closest
pair), and the categorical set (closest adjacent pair, and the closest pair among the colours a
map puts side by side).

Usage:  .venv/bin/python src/shared/palette_check.py
"""
import itertools
import warnings

import numpy as np
from colorspacious import cspace_convert

import atlas
import map_layers as ml

VISIONS = {"normal": None, "deutan": "deuteranomaly", "protan": "protanomaly", "tritan": "tritanomaly"}
_M1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929], [0.2119034982, 0.6806995451, 0.1073969566],
                [0.0883024619, 0.2817188376, 0.6299787005]])
_M2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468], [1.9779984951, -2.4285922050, 0.4505937099],
                [0.0259040371, 0.7827717662, -0.8086757660]])


def _oklab(hex_colour, vision):
    rgb = np.array([int(hex_colour.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)])
    if VISIONS[vision]:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            rgb = cspace_convert(rgb, {"name": "sRGB1+CVD", "cvd_type": VISIONS[vision], "severity": 100}, "sRGB1")
        rgb = np.clip(rgb, 0, 1)
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return _M2 @ np.cbrt(_M1 @ lin)


def delta_e(a, b, vision="normal"):
    return float(np.linalg.norm(_oklab(a, vision) - _oklab(b, vision)) * 100)


def _worst(pairs):
    """The smallest difference over the pairs and the four visions, with where it happens."""
    return min((delta_e(a, b, v), f"{na}/{nb}", v) for (na, a), (nb, b) in pairs for v in VISIONS)


def _named(colours):
    return [(c, c) for c in colours]


def checks(rate=None, rwi=None, biv=None, categorical=None, map_categorical=None, no_outlet=None):
    rate = rate or ml.RATE
    rwi = rwi or ml.RWI
    biv = biv or ml.BIV
    categorical = categorical or atlas.CATEGORICAL
    map_categorical = map_categorical or list(ml.LISA.values())
    no_outlet = no_outlet or ml.RATE_NONE
    ramp = [no_outlet, *rate]
    monotone = all(all(_oklab(b, v)[0] < _oklab(a, v)[0] for a, b in itertools.pairwise(ramp)) for v in VISIONS)
    return {
        "Outlet ramp light to dark in all 4 visions": "yes" if monotone else "no",
        "Outlet ramp, closest adjacent steps": _worst(itertools.pairwise(_named(ramp))),
        "Wealth scale, closest adjacent steps": _worst(itertools.pairwise(_named(rwi))),
        "Wealth poles at matching depth": _worst([((rwi[i], rwi[i]), (rwi[-1 - i], rwi[-1 - i])) for i in range(3)]),
        "Bivariate, closest of 9 cells": _worst(itertools.combinations(biv.items(), 2)),
        "Categorical, adjacent": _worst(itertools.pairwise(_named(categorical))),
        "Map categorical, any pair": _worst(itertools.combinations(_named(map_categorical), 2)),
    }


def show(results):
    for name, r in results.items():
        print(f"{name}: {r if isinstance(r, str) else f'{r[0]:.1f} ({r[2]}, {r[1]})'}")


if __name__ == "__main__":
    show(checks())
