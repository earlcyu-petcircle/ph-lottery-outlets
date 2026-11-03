"""
Model and spatial helpers for the step 3 analysis.

Every model here estimates an association between wealth and outlet density: how many
outlets per person sit in richer against poorer places, holding the listed controls fixed.
Every estimate describes where outlets sit relative to wealth; none says why they are there.

  fit_nb2          negative binomial (NB2) count model with estimated dispersion
  fit_logit        logistic model of whether a unit has any outlet
  grid_weights     neighbours on the RWI tile grid (the 8 tiles around each tile)
  polygon_weights  neighbours among polygons that share a boundary point (queen contiguity)
  morans_i         global Moran's I with a permutation test
  local_morans     local Moran's I (LISA) clusters with conditional permutation tests
  eigenvector_filter  Moran eigenvectors for a spatial-filtering refit
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import optimize, sparse, stats
from scipy.sparse.linalg import LinearOperator, eigsh
from scipy.special import gammaln

SEED = 20261103


def design(df, terms, fe=None):
    """Design matrix: a constant, the named terms and one dummy per level of `fe` but the first."""
    parts = [pd.Series(1.0, index=df.index, name="const"), df[terms].astype(float)]
    if fe is not None:
        parts.append(pd.get_dummies(df[fe], prefix="fe", drop_first=True, dtype=float))
    return pd.concat(parts, axis=1)


def _nb2_loglik(y, mu, alpha):
    r = 1.0 / alpha
    return (gammaln(y + r) - gammaln(r) - gammaln(y + 1)
            - r * np.log1p(alpha * mu) + y * np.log(alpha * mu / (1 + alpha * mu))).sum()


def fit_nb2(y, X, offset, groups):
    """
    NB2 count model, Var(y) = mu + alpha mu^2, with alpha estimated by maximum likelihood.

    alpha is profiled: for each alpha the coefficients come from the GLM fit, and alpha is the
    value that maximises the full NB2 likelihood. This gives the joint maximum-likelihood
    estimates (the NB2 information matrix is block-diagonal in coefficients and alpha), and it
    converges reliably with ~90 province intercepts where a joint Newton fit does not.
    Standard errors are clustered on `groups`.
    """
    y = np.asarray(y, dtype=float)

    def negll(log_alpha):
        a = np.exp(log_alpha)
        mu = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=a), offset=offset).fit().mu
        return -_nb2_loglik(y, mu, a)

    opt = optimize.minimize_scalar(negll, bounds=(-8, 4), method="bounded", options={"xatol": 1e-4})
    alpha = float(np.exp(opt.x))
    res = sm.GLM(y, X, family=sm.families.NegativeBinomial(alpha=alpha), offset=offset).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(np.asarray(groups))[0]})
    res.nb2_alpha = alpha
    res.nb2_loglik = -opt.fun
    return res


def fit_logit(y, X, groups):
    """Logistic model with cluster-robust standard errors."""
    return sm.GLM(np.asarray(y, dtype=float), X, family=sm.families.Binomial()).fit(
        cov_type="cluster", cov_kwds={"groups": pd.factorize(np.asarray(groups))[0]})


def drop_constant_groups(df, fe, outcome):
    """Rows of groups whose outcome never varies (all 0 or all 1): a logit cannot use them."""
    s = df.groupby(fe)[outcome].transform(lambda v: v.nunique() > 1)
    return df[s]


def nb_mid_quantile_residuals(y, mu, alpha):
    """
    Mid-quantile residuals for an NB2 fit: the normal quantile of the midpoint of the NB
    probability step at each count. For sparse counts they are close to normal under the model,
    unlike Pearson or deviance residuals, and they need no random draw.
    """
    y = np.asarray(y, dtype=float)
    n, p = 1 / alpha, 1 / (1 + alpha * np.asarray(mu))
    lo, hi = stats.nbinom.cdf(y - 1, n, p), stats.nbinom.cdf(y, n, p)
    return stats.norm.ppf(np.clip((lo + hi) / 2, 1e-12, 1 - 1e-12))


def binary_mid_quantile_residuals(y, p):
    y = np.asarray(y, dtype=float)
    lo = np.where(y > 0, 1 - p, 0.0)
    hi = np.where(y > 0, 1.0, 1 - p)
    return stats.norm.ppf(np.clip((lo + hi) / 2, 1e-12, 1 - 1e-12))


def grid_weights(tx, ty):
    """Binary weights between tiles that touch on the zoom-14 grid (up to 8 neighbours)."""
    tx, ty = np.asarray(tx, dtype=np.int64), np.asarray(ty, dtype=np.int64)
    pos = pd.Series(np.arange(len(tx)), index=tx * 100000 + ty)
    rows, cols = [], []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == dy == 0:
                continue
            j = pos.reindex((tx + dx) * 100000 + ty + dy).to_numpy()
            ok = ~np.isnan(j)
            rows.append(np.flatnonzero(ok))
            cols.append(j[ok].astype(int))
    rows, cols = np.concatenate(rows), np.concatenate(cols)
    return sparse.csr_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(tx), len(tx)))


def polygon_weights(gdf):
    """Binary queen-contiguity weights: polygons that share at least one boundary point."""
    g = gdf.reset_index(drop=True)
    pairs = g.sjoin(g[["geometry"]], predicate="intersects", how="inner")
    pairs = pairs[pairs.index != pairs.index_right]
    i, j = pairs.index.to_numpy(), pairs.index_right.to_numpy()
    w = sparse.csr_matrix((np.ones(len(i)), (i, j)), shape=(len(g), len(g)))
    w.data[:] = 1.0
    return w


def row_standardise(w):
    deg = np.asarray(w.sum(axis=1)).ravel()
    return sparse.diags(np.where(deg > 0, 1 / np.maximum(deg, 1), 0)) @ w


def morans_i(values, w, permutations=999, seed=SEED):
    """Global Moran's I on row-standardised weights, with a two-sided permutation p-value."""
    wr = row_standardise(w)
    z = np.asarray(values, dtype=float)
    z = z - z.mean()
    scale = len(z) / wr.sum()

    def moran(v):
        return scale * (v @ (wr @ v)) / (v @ v)

    obs = moran(z)
    rng = np.random.default_rng(seed)
    sims = np.array([moran(rng.permutation(z)) for _ in range(permutations)])
    p = (1 + np.sum(np.abs(sims - sims.mean()) >= abs(obs - sims.mean()))) / (permutations + 1)
    return {"morans_i": float(obs), "expected": float(-1 / (len(z) - 1)), "perm_mean": float(sims.mean()),
            "perm_sd": float(sims.std()), "z": float((obs - sims.mean()) / sims.std()), "p_value": float(p),
            "n": int(len(z)), "n_without_neighbours": int((np.asarray(w.sum(axis=1)).ravel() == 0).sum())}


def local_morans(values, w, permutations=999, alpha=0.05, seed=SEED):
    """
    Local Moran's I with conditional permutation p-values (each unit's value held fixed, its
    neighbours drawn at random from the rest). Returns the cluster label per unit:
    "High-High", "Low-Low", "High-Low", "Low-High" where p < alpha, else "Not significant"
    ("No neighbours" for isolates).
    """
    w = sparse.csr_matrix(w)
    z = np.asarray(values, dtype=float)
    z = (z - z.mean()) / z.std()
    n = len(z)
    deg = np.diff(w.indptr)
    lag = row_standardise(w) @ z
    local = z * lag
    rng = np.random.default_rng(seed)
    exceed = np.zeros(n)
    kmax = deg.max()
    for k in range(1, kmax + 1):
        idx = np.flatnonzero(deg == k)
        if len(idx) == 0:
            continue
        for start in range(0, len(idx), 2000):
            chunk = idx[start:start + 2000]
            # draw k neighbours from the other n-1 units, per permutation
            draws = rng.integers(0, n - 1, size=(len(chunk), permutations, k))
            draws += draws >= chunk[:, None, None]
            sim_lag = z[draws].mean(axis=2)
            sim = z[chunk, None] * sim_lag
            exceed[chunk] = np.minimum((sim >= local[chunk, None]).sum(1), (sim <= local[chunk, None]).sum(1))
    p = (exceed + 1) / (permutations + 1)
    label = np.full(n, "Not significant", dtype=object)
    sig = (p < alpha) & (deg > 0)
    label[sig & (z > 0) & (lag > 0)] = "High-High"
    label[sig & (z < 0) & (lag < 0)] = "Low-Low"
    label[sig & (z > 0) & (lag < 0)] = "High-Low"
    label[sig & (z < 0) & (lag > 0)] = "Low-High"
    label[deg == 0] = "No neighbours"
    return pd.DataFrame({"local_i": local, "p_value": p, "cluster": label})


def eigenvector_filter(w, k=100, min_moran=0.25, seed=SEED):
    """
    Moran eigenvectors of M W M (M centres a vector, W symmetric binary): the spatial patterns
    the map can hold, ordered by their Moran's I. The ones with I above `min_moran` (Griffith's
    usual cut-off for positive dependence) are returned as extra covariates, so a refit with them
    soaks up broad spatial structure the controls leave behind.
    """
    w = sparse.csr_matrix((w + w.T) / 2)
    n = w.shape[0]

    def mwm(v):
        v = v - v.mean()
        u = w @ v
        return u - u.mean()

    op = LinearOperator((n, n), matvec=mwm, dtype=float)
    # A seeded start vector: ARPACK's own random start makes the eigenvectors, and so the refit's
    # last digits, differ from run to run.
    v0 = np.random.default_rng(seed).standard_normal(n)
    vals, vecs = eigsh(op, k=min(k, n - 2), which="LA", tol=1e-6, maxiter=n * 10, v0=v0)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    moran = vals * n / w.sum()
    keep = moran > min_moran
    return vecs[:, keep], moran[keep]
