"""
Shared model and spatial helpers for the barangay study.

  - NB2 count models with an estimated dispersion and an offset, started from a Poisson fit;
  - rate ratios by wealth quintile against the richest, with 95% intervals;
  - a contiguity matrix for barangays, Moran's I on residuals with a permutation test, and
    an eigenvector spatial filter (Griffith) for the spatial refit.
"""
import math
import warnings

import geopandas as gpd
import numpy as np
import pandas as pd
import scipy.sparse as sp
import shapely
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.sparse.linalg import LinearOperator, eigsh

from common import WORK, weighted_quantiles

warnings.filterwarnings("ignore")
QUINTILE_TERMS = ["q1", "q2", "q3", "q4"]  # richest quintile (q5) is the reference


def sig(x):
    return float(f"{x:.6g}")


def add_quintiles(df, value, weight, prefix="q", q=5):
    """Population-weighted quantiles of `value` (1 = poorest) as a label and dummy columns."""
    lab = weighted_quantiles(df[value].values, df[weight].values, q) + 1
    df[f"{prefix}uintile" if q == 5 else f"{prefix}tile"] = lab
    for k in range(1, q):
        df[f"{prefix}{k}"] = (lab == k).astype(float)
    return df


def zscore(s):
    return (s - s.mean()) / s.std()


def drop_empty_groups(df, outcome, group):
    """Fixed effects for a group with no events go to minus infinity; such groups add nothing
    to the conditional likelihood, so they are dropped (the standard treatment)."""
    keep = df.groupby(group)[outcome].transform("sum") > 0
    return df[keep].copy(), int(df.loc[~keep, group].nunique())


def fit_poisson(formula, df, offset):
    return smf.glm(formula, data=df, family=sm.families.Poisson(), offset=offset).fit()


def fit_nb2(formula, df, offset):
    """NB2 with the dispersion alpha estimated by maximum likelihood."""
    pois = fit_poisson(formula, df, offset)
    start = np.append(pois.params.values, 0.5)
    mod = smf.negativebinomial(formula, data=df, offset=offset, loglike_method="nb2")
    res = mod.fit(start_params=start, method="newton", maxiter=200, disp=0)
    if not res.mle_retvals.get("converged", False):
        res = mod.fit(start_params=start, method="bfgs", maxiter=2000, disp=0)
    if not res.mle_retvals.get("converged", False):
        raise RuntimeError(f"NB2 did not converge: {formula}")
    return res


def fit_logit(formula, df):
    return smf.glm(formula, data=df, family=sm.families.Binomial()).fit()


def ratio(res, term):
    lo, hi = res.conf_int().loc[term]
    return {"rr": sig(math.exp(res.params[term])), "lo": sig(math.exp(lo)), "hi": sig(math.exp(hi)),
            "p": sig(res.pvalues[term])}


def quintile_rrs(res, terms=QUINTILE_TERMS):
    return {t: ratio(res, t) for t in terms}


def alpha(res):
    return sig(res.params["alpha"]) if "alpha" in res.params else None


# ---------------------------------------------------------------------------
# Spatial weights, Moran's I and the eigenvector spatial filter
# ---------------------------------------------------------------------------
def contiguity(pcodes):
    """Binary symmetric contiguity between barangays: polygons within about 20 m of each
    other count as neighbours, which tolerates the small gaps in the boundary file."""
    geoms = gpd.read_parquet(WORK / "barangay_geoms.parquet").set_index("adm4_pcode")
    g = shapely.simplify(geoms.loc[list(pcodes)].geometry.values, 0.00005)
    tree = shapely.STRtree(g)
    i, j = tree.query(g, predicate="dwithin", distance=0.0002)
    keep = i != j
    n = len(g)
    C = sp.coo_matrix((np.ones(keep.sum()), (i[keep], j[keep])), shape=(n, n)).tocsr()
    C = ((C + C.T) > 0).astype(float)
    return C


def morans_i(z, C, perms=999, seed=20261029):
    """Moran's I of z on row-standardised C (isolates left out), with a permutation p-value."""
    deg = np.asarray(C.sum(axis=1)).ravel()
    ok = deg > 0
    C = C[ok][:, ok]
    z = np.asarray(z)[ok]
    W = sp.diags(1 / np.asarray(C.sum(axis=1)).ravel()) @ C
    z = z - z.mean()

    def stat(v):
        return float(v @ (W @ v) / (v @ v))

    obs = stat(z)
    rng = np.random.default_rng(seed)
    sims = np.array([stat(rng.permutation(z)) for _ in range(perms)])
    p = (1 + (np.abs(sims - sims.mean()) >= abs(obs - sims.mean())).sum()) / (perms + 1)
    return {"I": sig(obs), "expected": sig(-1 / (len(z) - 1)), "p_perm": sig(p),
            "n": int(len(z)), "isolates": int((~ok).sum())}


def spatial_filter(C, k=60, threshold=0.25):
    """Eigenvectors of M C M (M centres) with the largest Moran's I. Those whose Moran's I is
    at least `threshold` of the maximum are the candidate spatial filter (Griffith 2003)."""
    n = C.shape[0]

    def mv(v):
        v = np.asarray(v).ravel()
        v = v - v.mean()
        u = C @ v
        return u - u.mean()

    op = LinearOperator((n, n), matvec=mv, dtype=float)
    vals, vecs = eigsh(op, k=k, which="LA", v0=np.full(n, 1.0 / math.sqrt(n)) + 1e-3)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    keep = vals / vals[0] >= threshold
    return pd.DataFrame(vecs[:, keep], columns=[f"ev{i}" for i in range(int(keep.sum()))])
