"""
stage1.stats — trend tests, shape tests, effective sample size, gate evaluator.
==============================================================================

Everything here is implemented without scipy, so the whole Stage 1 pipeline
runs on numpy + pandas alone. Fewer dependencies means the pinned-version
reproducibility requirement (spec 5.6) is actually achievable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Normal distribution helpers (no scipy)
# ---------------------------------------------------------------------------

def norm_cdf(z: float) -> float:
    """Standard normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_sided_p(z: float) -> float:
    """Two-sided p-value for a z-statistic."""
    return 2.0 * (1.0 - norm_cdf(abs(z)))


# ---------------------------------------------------------------------------
# Jonckheere-Terpstra trend test (spec 5.3)
# ---------------------------------------------------------------------------

@dataclass
class JTResult:
    J: float
    z: float
    p_normal: float
    p_permutation: float | None
    n_groups: int
    n_total: int


def _mann_whitney_u(a: np.ndarray, b_sorted: np.ndarray) -> float:
    """
    U = #{(x, y) : x in a, y in b, x < y} + 0.5 * #{ties}

    Computed with searchsorted rather than a double loop, so the full 10-bucket
    JT statistic on ~10^5 observations runs in well under a second.
    """
    left = np.searchsorted(b_sorted, a, side="left")
    right = np.searchsorted(b_sorted, a, side="right")
    n_b = len(b_sorted)
    greater = n_b - right
    ties = right - left
    return float(greater.sum() + 0.5 * ties.sum())


def jonckheere_terpstra(
    groups: list[np.ndarray],
    permutations: int = 2000,
    seed: int = 0,
) -> JTResult:
    """
    Test for a monotone trend in central tendency across ORDERED groups.

    This is the primary shape evidence in Stage 1 (spec 5.3): a monotone
    gradient across ten ordered buckets is the signature of information, while
    a single strong bucket among nine noisy ones is the signature of mining.

    Returns both a normal-approximation p-value and a permutation p-value.
    The permutation value is the authoritative one: the closed-form variance
    below assumes no ties, and intraday returns tie constantly (zero moves,
    tick granularity). The normal z is reported for comparability only.
    """
    groups = [np.asarray(g, dtype=float) for g in groups]
    groups = [g[np.isfinite(g)] for g in groups]
    k = len(groups)
    sizes = np.array([len(g) for g in groups], dtype=float)
    n = float(sizes.sum())

    if k < 3 or (sizes < 2).any():
        return JTResult(np.nan, np.nan, np.nan, None, k, int(n))

    def _statistic(gs: list[np.ndarray]) -> float:
        total = 0.0
        presorted = [np.sort(g) for g in gs]
        for i in range(k - 1):
            for j in range(i + 1, k):
                total += _mann_whitney_u(gs[i], presorted[j])
        return total

    J = _statistic(groups)

    # Null moments, no-ties formulation.
    e_j = (n**2 - (sizes**2).sum()) / 4.0
    var_j = (n**2 * (2 * n + 3) - (sizes**2 * (2 * sizes + 3)).sum()) / 72.0
    z = (J - e_j) / math.sqrt(var_j) if var_j > 0 else float("nan")
    p_norm = two_sided_p(z) if math.isfinite(z) else float("nan")

    p_perm = None
    if permutations:
        rng = np.random.default_rng(seed)
        pooled = np.concatenate(groups)
        bounds = np.cumsum(sizes).astype(int)[:-1]
        count = 0
        for _ in range(permutations):
            shuffled = rng.permutation(pooled)
            parts = np.split(shuffled, bounds)
            if abs(_statistic(parts) - e_j) >= abs(J - e_j):
                count += 1
        p_perm = count / permutations

    return JTResult(J, z, p_norm, p_perm, k, int(n))


# ---------------------------------------------------------------------------
# Isotonic regression, shape classification (spec 3.4)
# ---------------------------------------------------------------------------

def isotonic_fit(y: np.ndarray, w: np.ndarray | None = None) -> np.ndarray:
    """
    Pool-adjacent-violators. Returns the best non-decreasing fit to y.

    Used to ask whether the bucket response is monotone or merely wiggly:
    comparing isotonic R^2 against linear R^2 separates "monotone gradient"
    from "one bucket did something".
    """
    y = np.asarray(y, dtype=float)
    n = len(y)
    w = np.ones(n) if w is None else np.asarray(w, dtype=float)

    values = list(y)
    weights = list(w)
    counts = [1] * n

    i = 0
    while i < len(values) - 1:
        if values[i] <= values[i + 1]:
            i += 1
            continue
        tw = weights[i] + weights[i + 1]
        values[i] = (values[i] * weights[i] + values[i + 1] * weights[i + 1]) / tw
        weights[i] = tw
        counts[i] += counts[i + 1]
        del values[i + 1], weights[i + 1], counts[i + 1]
        while i > 0 and values[i - 1] > values[i]:
            tw = weights[i - 1] + weights[i]
            values[i - 1] = (values[i - 1] * weights[i - 1] + values[i] * weights[i]) / tw
            weights[i - 1] = tw
            counts[i - 1] += counts[i]
            del values[i], weights[i], counts[i]
            i -= 1

    return np.repeat(values, counts)


def _r2(y: np.ndarray, fit: np.ndarray, w: np.ndarray) -> float:
    mean = np.average(y, weights=w)
    ss_res = float(np.sum(w * (y - fit) ** 2))
    ss_tot = float(np.sum(w * (y - mean) ** 2))
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


def shape_classification(bucket_means: np.ndarray,
                         bucket_counts: np.ndarray | None = None) -> dict:
    """
    Classify the bucket response curve as monotone, U-shaped, or noise.

    Reports isotonic R^2 (best monotone increasing), reverse-isotonic R^2 (best
    monotone decreasing), and linear R^2, all weighted by bucket size.
    """
    y = np.asarray(bucket_means, dtype=float)
    w = np.ones(len(y)) if bucket_counts is None else np.asarray(bucket_counts, float)
    x = np.arange(len(y), dtype=float)

    ok = np.isfinite(y)
    y, w, x = y[ok], w[ok], x[ok]
    if len(y) < 3:
        return {"r2_isotonic": np.nan, "r2_isotonic_desc": np.nan,
                "r2_linear": np.nan, "spearman_bucket": np.nan, "shape": "insufficient"}

    r2_iso = _r2(y, isotonic_fit(y, w), w)
    r2_iso_desc = _r2(y, -isotonic_fit(-y[::-1], w[::-1])[::-1], w)

    coef = np.polyfit(x, y, 1, w=np.sqrt(w))
    r2_lin = _r2(y, np.polyval(coef, x), w)

    rho = float(pd.Series(x).rank().corr(pd.Series(y).rank()))

    best_mono = max(r2_iso, r2_iso_desc)
    if best_mono > 0.7 and abs(rho) >= 0.6:
        shape = "monotone"
    elif best_mono > 0.7:
        shape = "monotone_weak_rank"
    elif r2_lin < 0.2 and best_mono < 0.5:
        shape = "noise"
    else:
        shape = "non_monotone"

    return {"r2_isotonic": r2_iso, "r2_isotonic_desc": r2_iso_desc,
            "r2_linear": r2_lin, "spearman_bucket": rho, "shape": shape}


# ---------------------------------------------------------------------------
# Effective sample size (spec 5.2)
# ---------------------------------------------------------------------------

@dataclass
class EffectiveSample:
    n_raw: int
    lag1_score: float
    lag1_target: float
    serial_factor: float
    n_eff_serial: int
    k_instruments: int
    rho_bar: float
    k_eff: float
    n_eff_total: int


def lag1_autocorr(s: pd.Series) -> float:
    x = s.dropna()
    if len(x) < 3:
        return float("nan")
    return float(x.autocorr(lag=1))


def effective_sample_size(
    scores: dict[str, pd.Series],
    targets: dict[str, pd.Series],
) -> EffectiveSample:
    """
    Deflate the raw bar count for serial and cross-sectional dependence.

    Two separate haircuts, and BOTH matter:

      serial: n_eff = n * (1 - rho1) / (1 + rho1), the standard effective size
              for the mean of an AR(1)-like series.

      cross:  K_eff = K / (1 + (K - 1) * rho_bar), where rho_bar is the mean
              pairwise correlation of CONTEMPORANEOUS forward returns.

    Ten correlated US large caps at rho_bar ~ 0.30 give K_eff ~ 2.7, not 10.
    Reporting n rather than n_eff is how intraday studies talk themselves into
    significance they do not have.
    """
    symbols = sorted(set(scores) & set(targets))
    n_raw = int(sum(
        (scores[s].notna() & targets[s].notna()).sum() for s in symbols
    ))

    ac_score = float(np.nanmean([lag1_autocorr(scores[s]) for s in symbols]))
    ac_target = float(np.nanmean([lag1_autocorr(targets[s]) for s in symbols]))

    # Use the score's persistence: it is what makes consecutive observations
    # non-independent for an IC estimate. Negative autocorrelation is clipped
    # to zero rather than credited as bonus information.
    rho1 = max(0.0, ac_score if np.isfinite(ac_score) else 0.0)
    serial_factor = (1.0 - rho1) / (1.0 + rho1)
    n_eff_serial = int(n_raw * serial_factor)

    k = len(symbols)
    rho_bar = float("nan")
    if k > 1:
        aligned = pd.DataFrame({s: targets[s] for s in symbols}).dropna()
        if len(aligned) > 30:
            corr = aligned.corr().to_numpy()
            iu = np.triu_indices(k, k=1)
            rho_bar = float(np.nanmean(corr[iu]))

    if k <= 1 or not np.isfinite(rho_bar):
        k_eff = float(max(k, 1))
    else:
        k_eff = k / (1.0 + (k - 1) * max(0.0, rho_bar))

    per_instrument = n_eff_serial / k if k else 0
    n_eff_total = int(per_instrument * k_eff)

    return EffectiveSample(
        n_raw=n_raw, lag1_score=ac_score, lag1_target=ac_target,
        serial_factor=serial_factor, n_eff_serial=n_eff_serial,
        k_instruments=k, rho_bar=rho_bar, k_eff=k_eff, n_eff_total=n_eff_total,
    )


def ic_t_statistic(ic: float, n_eff: int) -> float:
    """t ~ IC * sqrt(n_eff) for small IC. Used for the section 8.1 power table."""
    if not np.isfinite(ic) or n_eff < 3:
        return float("nan")
    return float(ic * math.sqrt(n_eff))


def required_n_for_ic(ic: float, t_target: float = 3.0) -> int:
    """Inverse of the above: n_eff needed to reach t_target at a given true IC."""
    if ic == 0:
        return 2**63 - 1
    return int((t_target / abs(ic)) ** 2)


# ---------------------------------------------------------------------------
# Gate evaluator (spec 6)
# ---------------------------------------------------------------------------

@dataclass
class Gate:
    code: str
    description: str
    value: object
    passed: bool | None      # None = not evaluable at this step


def evaluate_gates(results: dict) -> tuple[list[Gate], str]:
    """
    Apply the pre-registered section 6 gates to a results dict.

    Gates whose inputs are absent evaluate to None ("not yet tested") rather
    than to a pass. A gate that has not been run has not been passed, and the
    verdict logic below treats it that way.

    Returns (gates, verdict) where verdict is one of:
        DETECTED             all of G1..G7 pass
        NO_USEFUL_PREDICTIVITY  any of K1..K8 fires
        INCONCLUSIVE         neither; includes "not all gates run yet"
    """
    g = results.get
    gates: list[Gate] = []

    def add(code, desc, value, passed):
        gates.append(Gate(code, desc, value, passed))

    ic = g("mean_ic")
    ic_t = g("ic_t")
    consistency = g("consistency_ratio")
    jt_p = g("jt_p")
    bucket_rho = g("bucket_spearman")
    h2 = g("h2_spread")
    h2_lo, h2_hi = g("h2_ci_low"), g("h2_ci_high")
    h1_ok = g("h1_ordering_respected")
    perm_p = g("permutation_p")
    fdr_ok = g("survives_fdr")
    composite_wins = g("composite_beats_components")
    extreme_sig = g("extreme_vs_middle_significant")
    blocks_positive = g("blocks_with_sign")
    n_blocks = g("n_blocks")
    pipeline_ok = g("pipeline_gates_pass")

    def _none_or(fn, *vals):
        return None if any(v is None for v in vals) else fn(*vals)

    # --- Verdict A gates -----------------------------------------------------
    add("G1", "|mean IC| >= 0.010 on r_1", ic,
        _none_or(lambda v: abs(v) >= 0.010, ic))
    add("G2", "IC t >= 3.0 on n_eff", ic_t,
        _none_or(lambda v: abs(v) >= 3.0, ic_t))
    add("G3", "consistency ratio >= 0.65", consistency,
        _none_or(lambda v: v >= 0.65, consistency))
    add("G4", "JT p < 0.05 and bucket rho >= 0.60", (jt_p, bucket_rho),
        _none_or(lambda p, r: p < 0.05 and abs(r) >= 0.60, jt_p, bucket_rho))
    add("G5", "H2 > 0, CI excludes 0, H1 ordering holds", (h2, h2_lo, h2_hi, h1_ok),
        _none_or(lambda v, lo, hi, o: v > 0 and lo > 0 and bool(o),
                 h2, h2_lo, h2_hi, h1_ok))
    add("G6", "permutation p < 0.01 and survives FDR", (perm_p, fdr_ok),
        _none_or(lambda p, f: p < 0.01 and bool(f), perm_p, fdr_ok))
    add("G7", "composite beats best single component", composite_wins,
        _none_or(bool, composite_wins))

    # --- Verdict C kills -----------------------------------------------------
    add("K1", "|mean IC| < 0.005 or IC t < 1.5", (ic, ic_t),
        _none_or(lambda v, t: abs(v) < 0.005 or abs(t) < 1.5, ic, ic_t))
    add("K2", "consistency ratio < 0.50", consistency,
        _none_or(lambda v: v < 0.50, consistency))
    add("K3", "no monotonicity and no extreme-vs-middle effect", (jt_p, extreme_sig),
        _none_or(lambda p, e: p > 0.10 and not bool(e), jt_p, extreme_sig))
    add("K4", "H2 CI includes zero", (h2_lo, h2_hi),
        _none_or(lambda lo, hi: lo <= 0 <= hi, h2_lo, h2_hi))
    add("K5", "observed inside permutation null central 95%", perm_p,
        _none_or(lambda p: p > 0.05, perm_p))
    add("K6", "effect in <= 2 of the blocks", (blocks_positive, n_blocks),
        _none_or(lambda b, n: n >= 20 and b <= 2, blocks_positive, n_blocks))
    add("K7", "sign is the REVERSE of pre-registered H1", h1_ok,
        _none_or(lambda o: not bool(o), h1_ok))
    add("K8", "a pipeline validation gate failed", pipeline_ok,
        _none_or(lambda p: not bool(p), pipeline_ok))

    kills = [x for x in gates if x.code.startswith("K") and x.passed is True]
    a_gates = [x for x in gates if x.code.startswith("G")]

    if kills:
        verdict = "NO_USEFUL_PREDICTIVITY"
    elif all(x.passed is True for x in a_gates):
        verdict = "DETECTED"
    else:
        verdict = "INCONCLUSIVE"

    return gates, verdict


def format_gates(gates: list[Gate], verdict: str) -> str:
    """Render the gate table for the console and the results memo."""
    lines = ["", "  code  result   gate", "  " + "-" * 68]
    for gt in gates:
        if gt.passed is None:
            mark = "  --  "
        elif gt.code.startswith("K"):
            mark = " FIRED" if gt.passed else "  ok  "
        else:
            mark = " PASS " if gt.passed else " FAIL "
        val = gt.value
        if isinstance(val, float):
            val_s = f"{val:+.4f}"
        elif isinstance(val, tuple):
            val_s = ", ".join(
                f"{v:+.4f}" if isinstance(v, float) else str(v) for v in val
            )
        else:
            val_s = str(val)
        lines.append(f"  {gt.code:<5}{mark}  {gt.description}")
        lines.append(f"  {'':<5}{'':<7}  observed: {val_s}")
    lines.append("  " + "-" * 68)
    lines.append(f"  VERDICT: {verdict}")
    if verdict == "INCONCLUSIVE":
        lines.append("  (gates marked -- have not been evaluated at this step)")
    return "\n".join(lines)
