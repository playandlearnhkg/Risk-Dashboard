"""
analysis.py — The tests Sigma's section 3 specifies, run over the panel
built by assemble.py.

Statistical stance (deliberately conservative, per "prefer REJECT or
CONDITIONAL over false positives"):

  * Earnings T+1 observations CLUSTER BY CALENDAR DATE — dozens of firms
    report the same evening and share the next day's market move. Treating
    them as independent is the single easiest way to manufacture a false
    positive here. Every confidence interval and p-value in this module is
    therefore computed with a DATE-CLUSTERED bootstrap (resample whole
    trading dates with replacement, not individual events).
  * Continuation rates are tested against a 50% null with a two-sided
    binomial test AND the clustered bootstrap; where the two disagree the
    clustered result is the one reported, since the binomial assumes
    independence the data does not have.
  * Transaction costs use each observation's OWN measured spread
    (Corwin-Schultz, falling back to Roll) rather than a global constant.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

RNG_SEED = 12345
N_BOOT = 2000

# --- Opening 5-minute pattern labels (Sigma section 2D) ---
PATTERN_STRONG = "Strong Continuation+"
PATTERN_MODERATE = "Moderate Continuation+"
PATTERN_INDECISION = "Indecision0"
PATTERN_REVERSAL = "Early Reversal-"


# ---------------------------------------------------------------------------
# Clustered inference
# ---------------------------------------------------------------------------

def clustered_bootstrap(
    values: pd.Series, clusters: pd.Series, stat=np.mean,
    n_boot: int = N_BOOT, seed: int = RNG_SEED,
) -> dict:
    """
    Bootstrap `stat` by resampling CLUSTERS (calendar dates) with
    replacement. Returns mean, 95% CI, and a two-sided p-value against 0.
    """
    df = pd.DataFrame({"v": values, "c": clusters}).dropna()
    if df.empty:
        return {"stat": np.nan, "lo": np.nan, "hi": np.nan, "p": np.nan, "n": 0,
                "n_clusters": 0}
    groups = [g["v"].to_numpy() for _, g in df.groupby("c", sort=False)]
    rng = np.random.default_rng(seed)
    k = len(groups)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, k, size=k)
        draws[b] = stat(np.concatenate([groups[i] for i in pick]))
    observed = stat(df["v"].to_numpy())
    # Two-sided p: how often the bootstrap distribution, recentred on the
    # null of 0, is at least as extreme as what we observed.
    centred = draws - draws.mean()
    p = float((np.abs(centred) >= abs(observed)).mean())
    return {"stat": float(observed), "lo": float(np.quantile(draws, 0.025)),
            "hi": float(np.quantile(draws, 0.975)), "p": p,
            "n": int(len(df)), "n_clusters": k}


def clustered_rate_vs_half(flags: pd.Series, clusters: pd.Series, **kw) -> dict:
    """Continuation rate vs the 50% null, with date-clustered inference."""
    res = clustered_bootstrap(flags.astype(float) - 0.5, clusters, **kw)
    out = dict(res)
    out["rate"] = res["stat"] + 0.5 if res["n"] else np.nan
    out["lo"] = res["lo"] + 0.5 if res["n"] else np.nan
    out["hi"] = res["hi"] + 0.5 if res["n"] else np.nan
    if res["n"]:
        succ = int(flags.sum())
        out["binom_p"] = float(stats.binomtest(succ, res["n"], 0.5).pvalue)
    else:
        out["binom_p"] = np.nan
    return out


# ---------------------------------------------------------------------------
# Section 2D — opening three 5-minute candles
# ---------------------------------------------------------------------------

def classify_opening_pattern(row: pd.Series) -> str:
    """
    Label the first three 5-minute candles relative to the gap direction.

    Sigma's definitions, made operational:
      Strong+   : all three candles close in the gap direction AND the
                  highs progress upward (gap up) / lows progress downward
                  (gap down)
      Moderate+ : >= 2 of 3 close in the gap direction and the third is
                  not a strong counter-move (its body < 50% of the mean
                  body of the other two)
      Reversal- : majority close against the gap, or a clear rejection
                  wick against the gap direction on the first candle
      Indecision: everything else (mixed closes, overlapping ranges,
                  small/doji bodies)
    """
    gap = row.get("gap")
    if pd.isna(gap) or gap == 0:
        return PATTERN_INDECISION
    need = ["c1_open", "c1_high", "c1_low", "c1_close",
            "c2_open", "c2_high", "c2_low", "c2_close",
            "c3_open", "c3_high", "c3_low", "c3_close"]
    if any(pd.isna(row.get(c)) for c in need):
        return None  # unmeasurable — excluded, never silently bucketed

    up = gap > 0
    bodies, dirs = [], []
    for i in (1, 2, 3):
        o, c = row[f"c{i}_open"], row[f"c{i}_close"]
        bodies.append(abs(c - o))
        dirs.append(1 if c > o else (-1 if c < o else 0))
    want = 1 if up else -1
    agree = sum(1 for d in dirs if d == want)
    against = sum(1 for d in dirs if d == -want)

    highs = [row[f"c{i}_high"] for i in (1, 2, 3)]
    lows = [row[f"c{i}_low"] for i in (1, 2, 3)]
    progressive = (highs[0] < highs[1] < highs[2]) if up else (lows[0] > lows[1] > lows[2])

    # Rejection wick on the opening candle, against the gap.
    c1o, c1c, c1h, c1l = (row["c1_open"], row["c1_close"],
                          row["c1_high"], row["c1_low"])
    rng = max(c1h - c1l, 1e-12)
    wick = ((c1h - max(c1o, c1c)) / rng) if up else ((min(c1o, c1c) - c1l) / rng)
    strong_rejection = wick > 0.6

    if agree == 3 and progressive:
        return PATTERN_STRONG
    if against >= 2 or strong_rejection:
        return PATTERN_REVERSAL
    if agree >= 2:
        others = [b for b, d in zip(bodies, dirs) if d == want]
        odd = [b for b, d in zip(bodies, dirs) if d != want]
        if not odd or (np.mean(others) > 0 and odd[0] < 0.5 * np.mean(others)):
            return PATTERN_MODERATE
    return PATTERN_INDECISION


def add_event_features(ev: pd.DataFrame) -> pd.DataFrame:
    """Derive quadrant, continuation flag, opening pattern and beta-filter flag."""
    df = ev.copy()
    df["gap_up"] = df["gap"] > 0
    df["intraday_up"] = df["o2c"] > 0
    df["quadrant"] = np.where(
        df["gap_up"],
        np.where(df["intraday_up"], "GapUp/IntraUp", "GapUp/IntraDown"),
        np.where(df["intraday_up"], "GapDown/IntraUp", "GapDown/IntraDown"),
    )
    # Continuation = intraday move in the same direction as the gap.
    df["continuation"] = df["gap_up"] == df["intraday_up"]
    # Signed return of trading the gap direction from open to close.
    df["signed_o2c"] = np.where(df["gap_up"], df["o2c"], -df["o2c"])

    df["pattern"] = df.apply(classify_opening_pattern, axis=1)
    df["pattern_plus"] = df["pattern"].isin([PATTERN_STRONG, PATTERN_MODERATE])

    # Section 2C: low quality if the stock moves opposite in sign to BOTH
    # the market and its sector on T+1.
    same_spy = np.sign(df["o2c"]) == np.sign(df["spy_o2c"])
    same_sector = np.sign(df["o2c"]) == np.sign(df["sector_o2c"])
    df["opposite_both"] = (~same_spy) & (~same_sector)
    df.loc[df["spy_o2c"].isna() | df["sector_o2c"].isna(), "opposite_both"] = pd.NA
    df["beta_ok"] = df["opposite_both"].apply(
        lambda x: pd.NA if pd.isna(x) else (not x))
    return df


# ---------------------------------------------------------------------------
# Section 3.1 — volatility elevation
# ---------------------------------------------------------------------------

def volatility_elevation(panel: pd.DataFrame, metrics: list[str]) -> pd.DataFrame:
    """
    For each event, compare the T+1 value of each metric with the MEDIAN
    of the same ticker's non-earnings days in the same calendar quarter
    (Sigma section 2A). Returns per-event ratios plus a summary.
    """
    df = panel.copy()
    df["quarter"] = df["date"].dt.to_period("Q")
    # Non-earnings baseline: exclude the event day and its immediate
    # neighbours so leakage from the announcement does not pollute it.
    near = df["is_t1"] | df["is_t1"].shift(1, fill_value=False) | \
        df["is_t1"].shift(-1, fill_value=False)
    base = df[~near]
    med = base.groupby(["ticker", "quarter"])[metrics].median()
    med.columns = [f"{m}_base" for m in metrics]

    ev = df[df["is_t1"]].merge(med, left_on=["ticker", "quarter"],
                               right_index=True, how="left")
    for m in metrics:
        ev[f"{m}_ratio"] = ev[m] / ev[f"{m}_base"]
    return ev


def summarise_volatility(ev: pd.DataFrame, metrics: list[str],
                         by: list[str] | None = None) -> pd.DataFrame:
    rows = []
    groups = ev.groupby(by) if by else [((), ev)]
    for key, g in groups:
        for m in metrics:
            r = g[f"{m}_ratio"].replace([np.inf, -np.inf], np.nan)
            boot = clustered_bootstrap(r - 1.0, g["date"])
            rec = {"metric": m, "n": int(r.notna().sum()),
                   "median_ratio": float(r.median()),
                   "mean_ratio": float(r.mean()),
                   "mean_excess": boot["stat"], "ci_lo": boot["lo"],
                   "ci_hi": boot["hi"], "p": boot["p"]}
            if by:
                keys = key if isinstance(key, tuple) else (key,)
                rec.update(dict(zip(by, keys)))
            rows.append(rec)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 3.2 — four-quadrant gap x intraday
# ---------------------------------------------------------------------------

def quadrant_table(ev: pd.DataFrame) -> pd.DataFrame:
    ct = pd.crosstab(ev["gap_up"], ev["intraday_up"])
    ct.index = ["GapDown", "GapUp"]
    ct.columns = ["IntraDown", "IntraUp"]
    return ct


def quadrant_stats(ev: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    rows = []
    groups = ev.groupby(by) if by else [((), ev)]
    for key, g in groups:
        g = g.dropna(subset=["continuation"])
        if g.empty:
            continue
        res = clustered_rate_vs_half(g["continuation"], g["date"])
        exp = clustered_bootstrap(g["signed_o2c"], g["date"])
        ct = quadrant_table(g)
        chi2 = p_chi2 = np.nan
        if ct.shape == (2, 2) and ct.to_numpy().min() > 0:
            chi2, p_chi2 = stats.chi2_contingency(ct)[:2]
        rec = {"n": res["n"], "n_dates": res["n_clusters"],
               "continuation_rate": res["rate"], "ci_lo": res["lo"],
               "ci_hi": res["hi"], "p_clustered": res["p"],
               "p_binomial": res["binom_p"], "chi2": chi2, "p_chi2": p_chi2,
               "mean_signed_o2c": exp["stat"], "signed_ci_lo": exp["lo"],
               "signed_ci_hi": exp["hi"], "signed_p": exp["p"]}
        if by:
            keys = key if isinstance(key, tuple) else (key,)
            rec.update(dict(zip(by, keys)))
        rows.append(rec)
    cols = (by or []) + [c for c in rows[0] if c not in (by or [])] if rows else []
    return pd.DataFrame(rows)[cols] if rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# Section 3.7 — transaction costs
# ---------------------------------------------------------------------------

def net_of_costs(ev: pd.DataFrame, spread_multiplier: float = 1.0,
                 impact_bps: float = 0.0) -> pd.Series:
    """
    Round-trip cost = 2 legs x (half-spread + impact), using each event's
    OWN measured spread. Corwin-Schultz is preferred (it is a high-low
    estimator, robust on volatile days); Roll is the fallback.

    spread_multiplier lets the caller run the sensitivity ladder without
    inventing a different spread series.
    """
    spread = ev["corwin_schultz_bps"].copy()
    spread = spread.fillna(ev["roll_spread_bps"])
    spread = spread.clip(lower=0, upper=500)  # guard against estimator blowups
    half_spread_bps = spread / 2.0
    per_leg = half_spread_bps * spread_multiplier + impact_bps
    return ev["signed_o2c"] - 2.0 * per_leg / 10_000.0


def cost_ladder(ev: pd.DataFrame) -> pd.DataFrame:
    scenarios = [
        ("gross (no costs)", 0.0, 0.0),
        ("measured spread", 1.0, 0.0),
        ("measured + 2bps impact", 1.0, 2.0),
        ("measured + 5bps impact", 1.0, 5.0),
        ("1.5x spread + 5bps", 1.5, 5.0),
    ]
    rows = []
    for name, mult, imp in scenarios:
        net = net_of_costs(ev, mult, imp)
        boot = clustered_bootstrap(net, ev["date"])
        wins = net > 0
        gains, losses = net[net > 0].sum(), -net[net < 0].sum()
        rows.append({
            "scenario": name, "n": boot["n"],
            "mean_net_bps": boot["stat"] * 10_000,
            "ci_lo_bps": boot["lo"] * 10_000, "ci_hi_bps": boot["hi"] * 10_000,
            "p": boot["p"], "win_rate": float(wins.mean()),
            "profit_factor": float(gains / losses) if losses > 0 else np.inf,
        })
    return pd.DataFrame(rows)


def expectancy_table(ev: pd.DataFrame, by: list[str],
                     spread_multiplier: float = 1.0,
                     impact_bps: float = 2.0) -> pd.DataFrame:
    """Win rate / mean net return / profit factor / n, grouped."""
    df = ev.copy()
    df["net"] = net_of_costs(df, spread_multiplier, impact_bps)
    rows = []
    for key, g in df.groupby(by):
        g = g.dropna(subset=["net"])
        if g.empty:
            continue
        boot = clustered_bootstrap(g["net"], g["date"])
        gains, losses = g.loc[g["net"] > 0, "net"].sum(), -g.loc[g["net"] < 0, "net"].sum()
        keys = key if isinstance(key, tuple) else (key,)
        rec = dict(zip(by, keys))
        rec.update({
            "n": boot["n"], "n_dates": boot["n_clusters"],
            "win_rate": float((g["net"] > 0).mean()),
            "mean_net_bps": boot["stat"] * 10_000,
            "ci_lo_bps": boot["lo"] * 10_000, "ci_hi_bps": boot["hi"] * 10_000,
            "p": boot["p"],
            "profit_factor": float(gains / losses) if losses > 0 else np.inf,
        })
        rows.append(rec)
    return pd.DataFrame(rows)
