"""
stage1.step5 — the core predictivity test (execution step 5).

Per-block Spearman IC of DQ against r_1, the consistency ratio across
non-overlapping blocks, the decile ladder with the drift-corrected baseline,
the quadrant spread H2, and a pre-registered gate evaluation.

    python -m stage1.step5 --data data/clean --out results/step5

This step is the whole study in compressed form. If mean IC across 20 blocks is
0.002 with a consistency ratio of 0.55, the answer is already known and the
remaining steps are documentation.

The sealed holdout is excluded here and stays sealed until execution step 14.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

from stage1 import core, stats
from stage1.dataset import (global_block_map, load_clean, load_tick_sizes,
                            prepare, split_holdout)

MIN_BARS_PER_BLOCK = 200


def per_block_ic(dq: pd.Series, r: pd.Series, blocks: pd.Series) -> pd.DataFrame:
    """
    Spearman IC within each non-overlapping block (spec 4.1).

    The distribution across blocks is the headline output, not the pooled
    number. A pooled IC driven by 2 blocks out of 20 is a regime artefact, and
    the pooled figure conceals that completely.
    """
    frame = pd.DataFrame({"dq": dq, "r": r, "block": blocks}).dropna()
    rows = []
    for b, g in frame.groupby("block"):
        if len(g) < MIN_BARS_PER_BLOCK:
            continue
        rows.append({
            "block": int(b),
            "n": len(g),
            "start": str(g.index[0].date()),
            "end": str(g.index[-1].date()),
            "ic": core.information_coefficient(g["dq"], g["r"]),
        })
    return pd.DataFrame(rows)


def consistency(ic_by_block: pd.Series, expected_sign: int = 1) -> dict:
    """
    Fraction of blocks whose IC carries the pre-registered sign, plus an exact
    binomial p-value against a coin flip.

    The expected sign is fixed in the pre-registration (H1: higher DQ implies
    higher forward return, so positive). Discovering the sign from the data and
    then testing it is circular.
    """
    ic = ic_by_block.dropna()
    n = len(ic)
    if n == 0:
        return {"n_blocks": 0, "blocks_with_sign": 0, "consistency_ratio": np.nan,
                "binomial_p": np.nan}

    hits = int((np.sign(ic) == expected_sign).sum())
    # Exact two-sided binomial against p=0.5, computed directly.
    from math import comb
    tail = sum(comb(n, k) for k in range(hits, n + 1)) / (2.0 ** n)
    p = min(1.0, 2.0 * min(tail, 1.0 - tail + comb(n, hits) / 2.0**n))

    return {"n_blocks": n, "blocks_with_sign": hits,
            "consistency_ratio": hits / n, "binomial_p": float(min(1.0, p))}


def pooled_statistics(dq, dq_pct, conv_pct, feats, r1, n_eff, seed=0) -> dict:
    """Decile ladder, monotonicity, quadrant spread, extreme-vs-middle."""
    out: dict = {}

    table = core.bucket_table(dq, dq_pct, r1)
    out["bucket_table"] = table

    # The bucket straddling DQ = 0 has an arbitrary sign; spec 3.5(e) excludes
    # it from the shape evidence.
    clean = table[(table["frac_bullish"] <= 0.001) | (table["frac_bullish"] >= 0.999)]
    out["zero_crossing_buckets_excluded"] = int(len(table) - len(clean))

    shape = stats.shape_classification(clean["mean_r"].to_numpy(),
                                       clean["n"].to_numpy())
    out.update({f"shape_{k}": v for k, v in shape.items()})
    out["bucket_spearman"] = shape["spearman_bucket"]

    # Jonckheere-Terpstra across the ordered deciles.
    s, sp, rr = core._scored_subset(dq, dq_pct, r1)
    edges = np.linspace(0.0, 1.0, 11)
    labels = list(range(1, 11))
    bucket_id = pd.cut(sp, bins=edges, labels=labels, include_lowest=True)
    keep = set(clean["bucket"].tolist())
    groups = [rr[bucket_id == q].to_numpy() for q in labels if q in keep]
    jt = stats.jonckheere_terpstra(groups, permutations=1000, seed=seed)
    out["jt_J"], out["jt_z"] = jt.J, jt.z
    out["jt_p_normal"], out["jt_p"] = jt.p_normal, jt.p_permutation

    # Quadrant.
    quad = core.quadrant_table(feats, conv_pct, r1)
    out["quadrant_table"] = quad
    out["h2_spread"] = core.quadrant_spread(feats, conv_pct, r1)

    means = quad["mean_r"]
    out["h1_ordering_respected"] = bool(
        means.get("Q1_clean_bull", np.nan) > means.get("Q2_messy_bull", np.nan)
        > 0 > means.get("Q3_messy_bear", np.nan) > means.get("Q4_clean_bear", np.nan)
    )

    # Extremes vs middle, on magnitude (the middle is where sign is least
    # defined, so concordance there is not the right comparison).
    ext = rr[(sp <= 0.10) | (sp >= 0.90)]
    mid = rr[(sp >= 0.40) & (sp <= 0.60)]
    out["extreme_abs_mean"] = float(ext.abs().mean()) if len(ext) else np.nan
    out["middle_abs_mean"] = float(mid.abs().mean()) if len(mid) else np.nan
    out["extreme_n"], out["middle_n"] = int(len(ext)), int(len(mid))

    # Permutation null on the pooled IC.
    observed, null, p = core.permutation_null(
        dq, r1, core.information_coefficient, draws=1000, seed=seed)
    out["pooled_ic"] = observed
    out["permutation_p"] = p
    out["permutation_null_sd"] = float(np.std(null))

    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage 1 Step 5: core IC test")
    ap.add_argument("--data", default="data/clean")
    ap.add_argument("--out", default="results/step5")
    ap.add_argument("--sessions-per-block", type=int, default=63)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    bars = load_clean(args.data)
    ticks = load_tick_sizes(args.data)
    if not bars:
        print("no clean data found; run stage1.validate first")
        return 1

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 74)
    print("STAGE 1 - STEP 5: SINGLE-BAR DQ INFORMATION COEFFICIENT ON r_1")
    print("=" * 74)
    print("  Sealed holdout excluded. Blocks are non-overlapping.\n")

    # Evaluation history only; the holdout is separated before anything is
    # computed and is not reopened here.
    evaluation = {sym: split_holdout(raw)[0] for sym, raw in sorted(bars.items())}
    block_map = global_block_map(evaluation, args.sessions_per_block)

    all_dq, all_r1, all_blocks = [], [], []
    scores, targets, per_block_frames = {}, {}, []
    feats_all, dqpct_all, convpct_all = [], [], []

    for sym, df in evaluation.items():
        p = prepare(df, ticks.get(sym, 0.01), args.sessions_per_block,
                    block_map=block_map)

        ic_tbl = per_block_ic(p.dq, p.r1, p.blocks)
        ic_tbl.insert(0, "symbol", sym)
        per_block_frames.append(ic_tbl)

        scores[sym], targets[sym] = p.dq, p.r1
        all_dq.append(p.dq)
        all_r1.append(p.r1)
        all_blocks.append(p.blocks)
        feats_all.append(p.feats)
        dqpct_all.append(p.dq_pct)
        convpct_all.append(p.conv_pct)

        c = consistency(ic_tbl["ic"])
        print(f"  {sym:<8} blocks: {c['n_blocks']:>3}   "
              f"mean IC: {ic_tbl['ic'].mean():+.5f}   "
              f"consistency: {c['consistency_ratio']:.2f}")

    block_table = pd.concat(per_block_frames, ignore_index=True)
    dq = pd.concat(all_dq)
    r1 = pd.concat(all_r1)
    feats = pd.concat(feats_all)
    dq_pct = pd.concat(dqpct_all)
    conv_pct = pd.concat(convpct_all)
    blocks_all = pd.concat(all_blocks)

    # Consistency is a statement about CALENDAR blocks (spec 4.1), so pool the
    # instruments inside each block first. Counting instrument-blocks would
    # inflate the block count by the number of instruments and turn a
    # 20-calendar-block requirement into a much weaker claim.
    calendar_ic = per_block_ic(dq, r1, blocks_all)

    es = stats.effective_sample_size(scores, targets)
    cons = consistency(calendar_ic["ic"])
    mean_ic = float(calendar_ic["ic"].mean())
    ic_t = stats.ic_t_statistic(mean_ic, es.n_eff_total)

    pooled = pooled_statistics(dq, dq_pct, conv_pct, feats, r1,
                               es.n_eff_total, seed=args.seed)

    print(f"\n  POOLED ACROSS {len(bars)} INSTRUMENT(S)")
    print(f"    calendar blocks       : {cons['n_blocks']}"
          f"   (instrument-blocks: {len(block_table)})")
    print(f"    mean IC across blocks : {mean_ic:+.5f}")
    print(f"    pooled IC             : {pooled['pooled_ic']:+.5f}")
    print(f"    n_eff                 : {es.n_eff_total:,}")
    print(f"    IC t-statistic        : {ic_t:+.2f}")
    print(f"    consistency ratio     : {cons['consistency_ratio']:.3f}"
          f"  ({cons['blocks_with_sign']}/{cons['n_blocks']}, "
          f"binomial p = {cons['binomial_p']:.4f})")
    print(f"    permutation p         : {pooled['permutation_p']:.4f}")
    print(f"    JT p (permutation)    : {pooled['jt_p']}")
    print(f"    bucket Spearman       : {pooled['bucket_spearman']:+.3f}")
    print(f"    response shape        : {pooled['shape_shape']}")
    print(f"    H2 quadrant spread    : {pooled['h2_spread']:+.5f}")
    print(f"    H1 ordering respected : {pooled['h1_ordering_respected']}")
    print(f"    extreme |mean r|      : {pooled['extreme_abs_mean']:.5f}"
          f"  (n={pooled['extreme_n']:,})")
    print(f"    middle  |mean r|      : {pooled['middle_abs_mean']:.5f}"
          f"  (n={pooled['middle_n']:,})")

    print("\n  Decile ladder (zero-crossing bucket flagged, excluded from shape):")
    print(pooled["bucket_table"].round(4).to_string(index=False))
    print("\n  Quadrant:")
    print(pooled["quadrant_table"].round(5).to_string())

    results = {
        "mean_ic": mean_ic,
        "ic_t": ic_t,
        "consistency_ratio": cons["consistency_ratio"],
        "n_blocks": cons["n_blocks"],
        "blocks_with_sign": cons["blocks_with_sign"],
        "n_eff": es.n_eff_total,
        "jt_p": pooled["jt_p"],
        "bucket_spearman": pooled["bucket_spearman"],
        "h2_spread": pooled["h2_spread"],
        "h1_ordering_respected": pooled["h1_ordering_respected"],
        "permutation_p": pooled["permutation_p"],
    }

    gates, verdict = stats.evaluate_gates(results)
    print(stats.format_gates(gates, verdict))

    print("\n  Gates G5-G7 need the bootstrap CI, FDR correction and component")
    print("  comparison from execution steps 7, 12 and 13. They read '--' here")
    print("  by design: a gate that has not been run has not been passed.")

    block_table.to_csv(out_dir / "block_ic_by_instrument.csv", index=False)
    calendar_ic.to_csv(out_dir / "block_ic_calendar.csv", index=False)
    pooled["bucket_table"].to_csv(out_dir / "decile_ladder.csv", index=False)
    pooled["quadrant_table"].to_csv(out_dir / "quadrant.csv")
    with open(out_dir / "summary.json", "w") as fh:
        json.dump({"results": results, "verdict": verdict,
                   "n_eff_detail": stats.__dict__ and es.__dict__}, fh,
                  indent=2, default=str)
    print(f"\n  written -> {out_dir}/")

    if verdict == "NO_USEFUL_PREDICTIVITY":
        print("\n  K-gate fired. Per the pre-registration, the study stops here.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
