"""
stage1.dataset — shared loading of validated bars and the derived score frame.

One place where raw bars become (features, DQ_pct, CONV_pct, r_h). Every CLI
uses it, so no analysis step can accidentally build its features differently
from the step that validated them.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

import pandas as pd

from stage1 import core


@dataclass
class Prepared:
    """The derived quantities every Stage 1 test consumes."""

    feats: pd.DataFrame
    dq: pd.Series
    dq_pct: pd.Series
    conv_pct: pd.Series
    r1: pd.Series
    r2: pd.Series
    r3: pd.Series
    blocks: pd.Series


def load_clean(directory: str | pathlib.Path) -> dict[str, pd.DataFrame]:
    """Load every validated instrument written by stage1.validate."""
    directory = pathlib.Path(directory)
    manifest = directory / "data_manifest.json"

    out: dict[str, pd.DataFrame] = {}
    if manifest.exists():
        with open(manifest) as fh:
            doc = json.load(fh)
        for entry in doc["instruments"]:
            out[entry["symbol"]] = pd.read_parquet(entry["clean_path"])
        return out

    for path in sorted(directory.glob("*.parquet")):
        out[path.stem.split("_")[0]] = pd.read_parquet(path)
    return out


def load_tick_sizes(directory: str | pathlib.Path) -> dict[str, float]:
    """Tick sizes as verified by the validator, keyed by symbol."""
    manifest = pathlib.Path(directory) / "data_manifest.json"
    if not manifest.exists():
        return {}
    with open(manifest) as fh:
        doc = json.load(fh)
    return {e["symbol"]: float(e["tick_size"]) for e in doc["instruments"]}


def global_block_map(bars: dict[str, pd.DataFrame],
                     sessions_per_block: int = 63) -> pd.Series:
    """
    Assign block ids on a CALENDAR basis shared by every instrument.

    Blocks are time periods (spec 4.1), so block 3 must mean the same dates for
    every instrument. Partitioning each instrument's own sessions independently
    would misalign them whenever their histories differ in length or start
    date, and would silently turn "20 blocks" into "20 instrument-blocks",
    which is a completely different and much weaker claim.
    """
    all_sessions = sorted(set().union(
        *(set(df.index.normalize().unique()) for df in bars.values())
    ))
    return pd.Series(
        [i // sessions_per_block for i in range(len(all_sessions))],
        index=pd.DatetimeIndex(all_sessions),
    )


def prepare(df: pd.DataFrame, tick: float,
            sessions_per_block: int = 63,
            block_map: pd.Series | None = None,
            bar_minutes: int = 5) -> Prepared:
    """
    Bars -> features, normalised scores, forward returns, block labels.

    All of it causal: features from bar t only, ATR from t-1 back, percentiles
    strictly prior and time-of-day bucketed, forward returns masked at the
    session boundary.
    """
    feats = core.candle_features(df, tick)

    if block_map is None:
        blocks = core.block_partition(df.index, sessions_per_block)
    else:
        blocks = pd.Series(
            block_map.reindex(df.index.normalize()).to_numpy(), index=df.index
        )

    return Prepared(
        feats=feats,
        dq=feats["DQ"],
        dq_pct=core.trailing_percentile(feats["DQ"]),
        conv_pct=core.trailing_percentile(feats["CONV"]),
        r1=core.forward_return(df, feats["atr_prev"], h=1, bar_minutes=bar_minutes),
        r2=core.forward_return(df, feats["atr_prev"], h=2, bar_minutes=bar_minutes),
        r3=core.forward_return(df, feats["atr_prev"], h=3, bar_minutes=bar_minutes),
        blocks=blocks,
    )


def split_holdout(df: pd.DataFrame, holdout_sessions: int = 252
                  ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Separate the sealed holdout (spec 4.3) from the evaluation history.

    The holdout is looked at ONCE, at execution step 14. Every earlier step
    must call this and use only the first element. A second look converts the
    holdout into training data and destroys its only function.
    """
    sessions = df.index.normalize().unique().sort_values()
    if len(sessions) <= holdout_sessions:
        return df.iloc[:0], df
    cutoff = sessions[-holdout_sessions]
    return df[df.index.normalize() < cutoff], df[df.index.normalize() >= cutoff]
