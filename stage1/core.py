"""
stage1.core — canonical numerical core for the Stage 1 predictivity test.
=========================================================================

Spec: docs/CANDLE_SCORING_STAGE1_PREDICTIVITY.md
Pre-registration: docs/preregistration.yaml

This module is the SINGLE SOURCE OF TRUTH for the scoring and statistics.
docs/stage1_reference.py is a thin shim over it that runs the section 5.6
self-test, so the validated implementation and the used implementation cannot
drift apart.

Written for auditability, not speed. The trailing percentile is deliberately
O(n*W) so that "strictly prior" is visible in the code rather than implied by a
library default.

Dependencies: numpy, pandas.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Fixed constants from the pre-registration. None of these are fitted.
K_TICK = 2.0
K_VOL = 0.10
ATR_N = 20
GAMMA = 1.0
PCT_WINDOW = 500
PCT_MIN_OBS = 250
TOD_SLOT_MINUTES = 30  # coarse time-of-day blocks; see _tod_key for why not 5
RHO = 0.70
BOOT_MEAN_BLOCK = 78  # one session of 5-minute bars


# ---------------------------------------------------------------------------
# 1. Candle geometry
# ---------------------------------------------------------------------------

def wilder_atr_prev(df: pd.DataFrame, n: int = ATR_N) -> pd.Series:
    """
    Wilder ATR over bars t-n .. t-1 — i.e. EXCLUDING bar t.

    The trailing .shift(1) is the whole point. An ATR that includes bar t and is
    then used to normalise bar t leaks that bar's own range into its own score.
    """
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    return atr.shift(1)


def candle_features(df: pd.DataFrame, tick_size: float) -> pd.DataFrame:
    """
    Section 1.2-1.4. Returns BD, CL, SA, WB, CONV, DIR, w_range, valid, DQ.

    Degenerate bars get NaN, never 0. A zero-range bar's score is unknown, not
    neutral; encoding it as 0 plants a phantom cluster at the exact centre of
    the distribution, which is where the "middle bucket" comparison lives.
    """
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]

    rng = h - l
    body = c - o
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l

    atr_prev = wilder_atr_prev(df)
    eps = np.maximum(K_TICK * tick_size, K_VOL * atr_prev)

    # Structural sanity — a feed that violates these is corrupt, not degenerate.
    sane = (
        o.notna() & h.notna() & l.notna() & c.notna()
        & (l <= np.minimum(o, c)) & (h >= np.maximum(o, c))
    )
    valid = sane & (rng > 0) & (rng >= eps)

    # Ratios are computed only where the range is strictly positive; everything
    # else is NaN by construction rather than by a later fillna.
    safe_rng = rng.where(rng > 0)
    out = pd.DataFrame(index=df.index)
    out["BD"] = (body / safe_rng).where(sane)
    out["CL"] = ((2 * c - h - l) / safe_rng).where(sane)
    out["SA"] = ((lower - upper) / safe_rng).where(sane)
    out["WB"] = ((upper + lower) / safe_rng).where(sane)
    out["CONV"] = 1.0 - out["WB"]
    out["DIR"] = (out["BD"] + out["CL"] + out["SA"]) / 3.0
    out["w_range"] = (rng / (rng + eps)).where(sane)
    out["valid"] = valid
    out["atr_prev"] = atr_prev

    out["DQ"] = (out["DIR"] * out["CONV"].pow(GAMMA) * out["w_range"]).where(valid)
    return out


def group_score_merge(df: pd.DataFrame, k: int, tick_size: float) -> pd.Series:
    """
    Section 1.6 Method M: collapse k bars into one synthetic candle, score it
    with the identical single-bar machinery. Never spans a session boundary.
    """
    sess = _session_key(df.index)
    merged = pd.DataFrame(
        {
            "open": df["open"].shift(k - 1),
            "high": df["high"].rolling(k).max(),
            "low": df["low"].rolling(k).min(),
            "close": df["close"],
        }
    )
    same_session = sess == sess.shift(k - 1)
    feats = candle_features(merged, tick_size)
    return feats["DQ"].where(same_session)


def group_score_agg(dq: pd.Series, index: pd.DatetimeIndex, k: int) -> pd.Series:
    """Section 1.6 Method A: recency-weighted mean of the last k single-bar DQ."""
    sess = _session_key(index)
    weights = RHO ** np.arange(k)
    num = sum(w * dq.shift(i) for i, w in enumerate(weights))
    same_session = sess == sess.shift(k - 1)
    return (num / weights.sum()).where(same_session)


# ---------------------------------------------------------------------------
# 2. Causal normalisation
# ---------------------------------------------------------------------------

def _session_key(index: pd.DatetimeIndex) -> pd.Series:
    """Trading date. Replace with an exchange calendar for overnight sessions."""
    return pd.Series(index.normalize(), index=index)


def _tod_key(index: pd.DatetimeIndex, slot_minutes: int = TOD_SLOT_MINUTES) -> pd.Series:
    """
    Time-of-day slot, coarsened to `slot_minutes` blocks.

    Bucketing by time-of-day is mandatory intraday — an unbucketed score is
    substantially a clock. But bucketing by the EXACT bar slot is a trap: with
    78 five-minute slots per session, a 500-observation reference window needs
    500 SESSIONS (~2 years) of history per slot before a single bar is scored.
    Coarsening to 30-minute blocks cuts the warm-up by 6x while still removing
    the intraday seasonality, which is what the bucketing is for.
    """
    minutes = index.hour * 60 + index.minute
    return pd.Series(minutes // slot_minutes, index=index)


def trailing_percentile(
    s: pd.Series,
    window: int = PCT_WINDOW,
    min_obs: int = PCT_MIN_OBS,
    by_time_of_day: bool = True,
) -> pd.Series:
    """
    Section 1.5. Percentile rank of s[t] within the trailing `window` VALID
    observations of the same time-of-day slot, STRICTLY BEFORE t.

    The current bar is never a member of its own reference distribution, which
    is why the kernel compares x[:-1] against x[-1] rather than ranking x whole.
    A pandas .rolling().rank(pct=True) includes the current value and is wrong
    here; a full-sample .quantile() is catastrophically wrong.
    """

    def _kernel(x: np.ndarray) -> float:
        return float((x[:-1] < x[-1]).mean())

    def _one_group(g: pd.Series) -> pd.Series:
        clean = g.dropna()
        if len(clean) <= min_obs:
            return pd.Series(np.nan, index=g.index)
        ranked = clean.rolling(window + 1, min_periods=min_obs + 1).apply(
            _kernel, raw=True
        )
        return ranked.reindex(g.index)

    if not by_time_of_day:
        return _one_group(s)

    tod = _tod_key(s.index)
    parts = [_one_group(s[tod == slot]) for slot in tod.unique()]
    return pd.concat(parts).reindex(s.index)


# ---------------------------------------------------------------------------
# 3. Forward returns
# ---------------------------------------------------------------------------

def forward_return(
    df: pd.DataFrame, atr_prev: pd.Series, h: int = 1
) -> pd.Series:
    """
    Section 2.1-2.2. (C[t+h] - C[t]) / ATR_20(t-1), NaN if t and t+h are in
    different sessions.

    The same-session mask is not optional. An overnight gap carries 3-10x a
    single intraday bar's variance; letting a handful of them into the sample
    lets them dominate whichever bucket they land in.
    """
    c = df["close"]
    sess = _session_key(df.index)
    same_session = sess.shift(-h) == sess
    return ((c.shift(-h) - c) / atr_prev).where(same_session)


# ---------------------------------------------------------------------------
# 4. Bucket statistics
# ---------------------------------------------------------------------------

@dataclass
class BucketStat:
    bucket: object
    n: int
    frac_bullish: float   # f_q
    concordance: float
    pi_0: float           # drift-corrected baseline
    lift: float           # concordance - pi_0
    mean_r: float
    median_r: float


def _scored_subset(score: pd.Series, score_pct: pd.Series, r: pd.Series):
    """
    The rows any bucket statistic is entitled to use: scored, normalised, and
    with a defined forward return. Every baseline must be computed on THIS set —
    comparing a filtered conditional rate against an unfiltered baseline
    fabricates lift out of nothing.
    """
    mask = score.notna() & score_pct.notna() & r.notna()
    return score[mask], score_pct[mask], r[mask]


def p_up_baseline(score: pd.Series, score_pct: pd.Series, r: pd.Series) -> float:
    """P(r > 0) on the scored subset, zero moves excluded. Feeds pi_0(q)."""
    _, _, rr = _scored_subset(score, score_pct, r)
    nonzero = rr != 0
    return float((rr[nonzero] > 0).mean())


def bucket_table(
    score: pd.Series, score_pct: pd.Series, r: pd.Series, n_buckets: int = 10
) -> pd.DataFrame:
    """
    Section 3.1 + 3.5. Decile ladder with the drift-corrected baseline.

    pi_0(q) = f_q * P(r > 0) + (1 - f_q) * P(r < 0)

    The naive 50% baseline is wrong and biased upward in any drifting sample:
    if P(r>0) > 0.5 and bullish bars are more common, concordance exceeds 50%
    with zero predictivity. A 5-year US equity sample produces exactly that and
    it looks like an edge.
    """
    s, sp, rr = _scored_subset(score, score_pct, r)

    nonzero = rr != 0
    p_up = float((rr[nonzero] > 0).mean())
    p_dn = 1.0 - p_up

    edges = np.linspace(0.0, 1.0, n_buckets + 1)
    labels = list(range(1, n_buckets + 1))
    buckets = pd.cut(sp, bins=edges, labels=labels, include_lowest=True)

    rows = []
    for q in labels:
        sel = (buckets == q) & nonzero
        n = int(sel.sum())
        if n == 0:
            continue
        s_q, r_q = s[sel], rr[sel]
        f_q = float((s_q > 0).mean())
        conc = float((np.sign(r_q) == np.sign(s_q)).mean())
        pi0 = f_q * p_up + (1.0 - f_q) * p_dn
        rows.append(
            BucketStat(q, n, f_q, conc, pi0, conc - pi0,
                       float(r_q.mean()), float(r_q.median()))
        )
    return pd.DataFrame([r.__dict__ for r in rows])


def quadrant_table(feats: pd.DataFrame, conv_pct: pd.Series, r: pd.Series) -> pd.DataFrame:
    """
    Section 3.2. Q1 clean bull / Q2 messy bull / Q3 messy bear / Q4 clean bear.

    H2, the Q1-minus-Q4 spread, is the headline statistic: being a difference,
    the market's unconditional drift cancels out of it.
    """
    mask = feats["valid"] & feats["DIR"].notna() & conv_pct.notna() & r.notna()
    mask &= feats["DIR"] != 0
    d, cp, rr = feats["DIR"][mask], conv_pct[mask], r[mask]

    decisive = cp >= 0.5
    quad = pd.Series(index=d.index, dtype=object)
    quad[(d > 0) & decisive] = "Q1_clean_bull"
    quad[(d > 0) & ~decisive] = "Q2_messy_bull"
    quad[(d < 0) & ~decisive] = "Q3_messy_bear"
    quad[(d < 0) & decisive] = "Q4_clean_bear"

    out = rr.groupby(quad).agg(n="size", mean_r="mean", median_r="median")
    return out.reindex(["Q1_clean_bull", "Q2_messy_bull", "Q3_messy_bear", "Q4_clean_bear"])


def quadrant_spread(feats: pd.DataFrame, conv_pct: pd.Series, r: pd.Series) -> float:
    """H2: mean r in Q1 minus mean r in Q4."""
    t = quadrant_table(feats, conv_pct, r)
    return float(t.loc["Q1_clean_bull", "mean_r"] - t.loc["Q4_clean_bear", "mean_r"])


# ---------------------------------------------------------------------------
# 5. Inference
# ---------------------------------------------------------------------------

def information_coefficient(score: pd.Series, r: pd.Series) -> float:
    """
    Spearman IC, computed as Pearson correlation of ranks so the module needs
    only numpy and pandas.

    Rank correlation rather than Pearson: intraday returns are fat-tailed, and
    three news bars must not be allowed to set the result.
    """
    mask = score.notna() & r.notna()
    if mask.sum() < 30:
        return np.nan
    return float(score[mask].rank().corr(r[mask].rank()))


def permutation_null(
    score: pd.Series, r: pd.Series, stat_fn, draws: int = 1000, seed: int = 0
) -> tuple[float, np.ndarray, float]:
    """
    Section 5.4. Shuffle scores while preserving both marginal distributions.

    Returns (observed, null_distribution, two_sided_empirical_p).
    """
    rng = np.random.default_rng(seed)
    mask = score.notna() & r.notna()
    s, rr = score[mask], r[mask]

    observed = stat_fn(s, rr)
    null = np.empty(draws)
    values = s.to_numpy()
    for i in range(draws):
        shuffled = pd.Series(rng.permutation(values), index=s.index)
        null[i] = stat_fn(shuffled, rr)
    p = float((np.abs(null) >= abs(observed)).mean())
    return observed, null, p


def stationary_bootstrap_ci(
    frame: pd.DataFrame,
    stat_fn,
    mean_block: int = BOOT_MEAN_BLOCK,
    draws: int = 2000,
    alpha: float = 0.05,
    seed: int = 0,
) -> tuple[float, float]:
    """
    Politis-Romano stationary block bootstrap. Resamples contiguous blocks of
    expected length `mean_block` so that serial dependence survives resampling.

    An i.i.d. bootstrap on intraday bars understates every standard error here.
    """
    rng = np.random.default_rng(seed)
    n = len(frame)
    p_jump = 1.0 / mean_block
    stats = np.empty(draws)

    for d in range(draws):
        idx = np.empty(n, dtype=int)
        cur = rng.integers(n)
        for i in range(n):
            idx[i] = cur
            cur = rng.integers(n) if rng.random() < p_jump else (cur + 1) % n
        stats[d] = stat_fn(frame.iloc[idx])

    return float(np.quantile(stats, alpha / 2)), float(np.quantile(stats, 1 - alpha / 2))


def block_partition(index: pd.DatetimeIndex, sessions_per_block: int = 63) -> pd.Series:
    """Section 4.1: consecutive, non-overlapping evaluation blocks."""
    sess = _session_key(index)
    codes = pd.factorize(sess)[0]
    return pd.Series(codes // sessions_per_block, index=index)

# ---------------------------------------------------------------------------
# 6. Pipeline gates (section 5.6)
# ---------------------------------------------------------------------------

def synthetic_bars(
    n_sessions: int = 300,
    bars_per_session: int = 78,
    ticks_per_bar: int = 40,
    tick: float = 0.01,
    seed: int = 42,
    drift_per_bar: float = 0.0,
) -> pd.DataFrame:
    """
    Random-walk bars with realistic intrabar geometry and NO predictability.

    OHLC is built from a simulated tick path, so body/shadow ratios have a
    realistic joint distribution rather than the degenerate one you get from
    drawing O/H/L/C independently. `drift_per_bar` lets the null carry an
    upward drift, which is what makes the naive-50%-baseline bug visible.
    """
    rng = np.random.default_rng(seed)
    total = n_sessions * bars_per_session
    sigma = 0.05

    steps = rng.normal(drift_per_bar / ticks_per_bar, sigma, size=(total, ticks_per_bar))
    path = 100.0 + np.cumsum(steps.ravel()).reshape(total, ticks_per_bar)

    opens = path[:, 0]
    closes = path[:, -1]
    highs = path.max(axis=1)
    lows = path.min(axis=1)

    # Business days only. Calendar days would put bars on weekends, which the
    # validator rejects outright for an RTH equity session — correctly.
    days = pd.bdate_range("2020-01-06", periods=n_sessions)
    stamps = [
        pd.date_range(day + pd.Timedelta(hours=9, minutes=30),
                      periods=bars_per_session, freq="5min")
        for day in days
    ]
    index = pd.DatetimeIndex(np.concatenate(stamps))

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes}, index=index
    )
    return df.round(int(-np.log10(tick)))


def _prepare(df: pd.DataFrame, tick: float):
    feats = candle_features(df, tick)
    dq_pct = trailing_percentile(feats["DQ"])
    conv_pct = trailing_percentile(feats["CONV"])
    r1 = forward_return(df, feats["atr_prev"], h=1)
    return feats, dq_pct, conv_pct, r1

