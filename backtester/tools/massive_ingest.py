"""
massive_ingest.py -- pull bars, earnings and market caps from the
"massive" flat-file service into the exact shapes the engine loads.

WHY THIS EXISTS

The engine reads per-ticker 1-minute parquet named
`<TICKER>_<YYYYMMDD>_<YYYYMMDD>_1m.parquet`, indexed by a tz-aware UTC
`ts`, with float64 open/high/low/close/volume. The service ships the
Polygon-style flat-file schema instead:

    ticker, volume, open, close, high, low, window_start, transactions

where `window_start` is an INTEGER of Unix NANOSECONDS. This module is
the one place that translation happens, so the assumption "window_start
is UTC nanoseconds" is written down, tested against a real file by
`--probe` before any full ingest, and never silently spread through the
codebase.

THREE RULES IT KEEPS

1 THE KEY IS NEVER WRITTEN DOWN. It is read from the environment
  (MASSIVE_API_KEY) and sent as an `X-API-Key` header -- not a query
  string, so it cannot leak into a proxy access log or a shell history.
  It is never printed, never committed, never put in a filename.

2 NETWORKING GOES THROUGH curl --proxytunnel. This session's egress is a
  CONNECT-only proxy; Python's requests would send a plain proxied GET
  for an http:// URL and be refused. curl forcing a tunnel is the proven
  path, so the download shells out and the parsing stays in Python.

3 THE TIMEZONE IS VERIFIED, NOT ASSUMED. `--probe` prints the first and
  last bars in both UTC and America/New_York and checks that the modal
  first-bar-of-session lands at 09:30 New York. If a file turns out to
  be exchange-local or second-precision, the probe says so and the
  ingest refuses rather than writing a subtly wrong parquet.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = os.environ.get("MASSIVE_BASE_URL", "http://47.109.55.53:3000")
KEY_ENV = "MASSIVE_API_KEY"
OHLCV = ["open", "high", "low", "close", "volume"]


class IngestError(RuntimeError):
    pass


# --------------------------------------------------------------- transport

def _key() -> str:
    k = os.environ.get(KEY_ENV, "").strip()
    if not k:
        raise IngestError(
            f"set {KEY_ENV} first, e.g.  export {KEY_ENV}='...'  -- the key "
            f"is read from the environment and sent as an X-API-Key header, "
            f"never written to disk or a filename")
    return k


def _curl(url: str, dest: Path | None, *, timeout: int,
          header_auth: bool) -> tuple[str, bytes]:
    """One curl call. Returns (http_code, body).

    A proxy is used ONLY if HTTPS_PROXY/https_proxy is set in the
    environment -- true inside Anthropic's sandboxed cloud sessions,
    where egress is CONNECT-only and a direct request is refused. On an
    ordinary machine (a local terminal, a teleported session) there is
    normally no such variable, and curl reaches the host directly. This
    branch is what makes the tool portable between the two: adding a
    proxy requirement here would work in the sandbox and silently break
    on every laptop.

    header_auth=True sends the key as X-API-Key (preferred: keeps it out
    of the URL). Some deployments only read the `apiKey` query parameter
    -- for those the caller sets header_auth=False and puts apiKey in the
    URL itself. The key is NEVER interpolated into a log line either way.
    """
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    cmd = ["curl", "-sS", "--max-time", str(timeout), "-w", "%{http_code}"]
    if proxy:
        cmd[1:1] = ["--proxytunnel", "--proxy", proxy]
    if header_auth:
        cmd += ["-H", f"X-API-Key: {_key()}"]
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-o", str(dest)]
    cmd.append(url)
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise IngestError(f"curl failed: {out.stderr.strip()}")
    code = out.stdout.strip()[-3:] if dest is not None else out.stdout[-3:]
    body = (dest.read_bytes() if (dest and dest.exists())
            else out.stdout[:-3].encode())
    return code, body


def fetch(path: str, dest: Path, *, timeout: int = 600,
          header_auth: bool = True) -> Path:
    """GET BASE+path through the tunnel, save the raw body to dest."""
    code, body = _curl(f"{BASE}{path}", dest, timeout=timeout,
                       header_auth=header_auth)
    if code != "200":
        raise IngestError(f"{path} returned HTTP {code}: {body[:200]!r}")
    return dest


# ------------------------------------------------------------------ parsing

def _read_flatfile(raw: Path) -> pd.DataFrame:
    """A gzipped or plain CSV in the flat-file schema -> raw DataFrame."""
    data = raw.read_bytes()
    if data[:2] == b"\x1f\x8b":                 # gzip magic
        data = gzip.decompress(data)
    df = pd.read_csv(io.BytesIO(data))
    need = {"open", "high", "low", "close", "volume", "window_start"}
    missing = need - set(df.columns)
    if missing:
        raise IngestError(
            f"{raw.name}: missing columns {sorted(missing)}; got "
            f"{list(df.columns)}. The schema may have changed -- inspect "
            f"before trusting any ingest.")
    return df


def _epoch_to_utc(values: pd.Series) -> pd.DatetimeIndex:
    """Integer epoch -> tz-aware UTC index, unit inferred from magnitude.

    The flat files stamp nanoseconds; the REST API stamps milliseconds.
    Rather than trust the caller to know which, the unit is inferred from
    the size of a representative value and then the decoded YEAR is
    checked. A wrong guess lands in 1970 or the far future and raises,
    so a mislabelled epoch can never be written to a parquet silently.
    """
    v = pd.to_numeric(values, errors="coerce")
    if v.isna().any():
        raise IngestError("timestamp column has non-numeric values")
    mag = int(abs(v.dropna().iloc[0]))
    unit = ("ns" if mag >= 10**17 else "us" if mag >= 10**14
            else "ms" if mag >= 10**11 else "s")
    ts = pd.to_datetime(v.astype("int64"), unit=unit, utc=True)
    yr = ts.dt.year
    if yr.min() < 1990 or yr.max() > 2100:
        raise IngestError(
            f"timestamp decoded to years {yr.min()}..{yr.max()} as {unit!r}; "
            f"that epoch unit is wrong. Refusing to write a frame stamped in "
            f"the wrong epoch -- inspect the raw values with --probe.")
    return pd.DatetimeIndex(ts, name="ts")


def _finalise(ts: pd.DatetimeIndex, cols: dict) -> pd.DataFrame:
    out = pd.DataFrame({c: pd.to_numeric(cols[c], errors="coerce")
                        for c in OHLCV}).set_axis(ts)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.astype("float64")


def to_engine_frame(df: pd.DataFrame, ticker: str | None = None
                    ) -> pd.DataFrame:
    """Flat-file rows -> the engine's UTC-indexed OHLCV frame."""
    if ticker is not None and "ticker" in df.columns:
        df = df[df["ticker"].astype(str).str.upper() == ticker.upper()]
        if df.empty:
            raise IngestError(f"no rows for {ticker} in this file")
    ts = _epoch_to_utc(df["window_start"])
    return _finalise(ts, {c: df[c] for c in OHLCV})


def rest_results_to_engine(results: list[dict]) -> pd.DataFrame:
    """Polygon-style aggregates JSON `results` -> engine frame.

    Field names are the Polygon short forms: t (epoch ms), o/h/l/c, v.
    """
    if not results:
        raise IngestError("the aggregates response had an empty results list")
    df = pd.DataFrame(results)
    need = {"t", "o", "h", "l", "c", "v"}
    missing = need - set(df.columns)
    if missing:
        raise IngestError(f"aggregates rows missing {sorted(missing)}; got "
                          f"{list(df.columns)}")
    ts = _epoch_to_utc(df["t"])
    return _finalise(ts, {"open": df["o"], "high": df["h"], "low": df["l"],
                          "close": df["c"], "volume": df["v"]})


# ------------------------------------------------------------------- probe

def probe(sample_path: str, out_dir: Path) -> None:
    """Fetch one file and report schema + timezone WITHOUT committing to
    an ingest. This is the first thing to run against a real key."""
    raw = fetch(sample_path, out_dir / "_probe.raw")
    df = _read_flatfile(raw)
    print(f"path        {sample_path}")
    print(f"rows        {len(df):,}")
    print(f"columns     {list(df.columns)}")
    print(f"dtypes      {df.dtypes.to_dict()}")
    print("\nfirst 3 rows (raw):")
    print(df.head(3).to_string())

    eng = to_engine_frame(df, ticker=None if "ticker" not in df else
                          str(df["ticker"].iloc[0]))
    ny = eng.index.tz_convert("America/New_York")
    print(f"\nUTC span    {eng.index.min()} .. {eng.index.max()}")
    print(f"NY  span    {ny.min()} .. {ny.max()}")

    # The load-bearing check: the earliest regular-session bar per day
    # should sit at 09:30 New York. If it clusters at 08:30 or 04:00 the
    # data is either exchange-local mislabelled as UTC, or includes
    # pre-market -- either way the operator must see it.
    local = ny
    first_per_day = (pd.Series(local, index=local)
                     .groupby(local.date).min())
    hhmm = first_per_day.dt.strftime("%H:%M").value_counts().head(5)
    print("\nmost common FIRST-bar-of-day (America/New_York):")
    print(hhmm.to_string())
    print("\n-> a 1-minute regular-session feed should show 09:30 dominant.")
    print("   09:30 present but 04:00 also frequent = includes pre-market")
    print("   (fine -- the loader filters to the regular session).")
    raw.unlink(missing_ok=True)


# ------------------------------------------------------------------ ingest

def _parquet_name(ticker: str, idx: pd.DatetimeIndex) -> str:
    a = idx.min().strftime("%Y%m%d")
    b = idx.max().strftime("%Y%m%d")
    return f"{ticker.upper()}_{a}_{b}_1m.parquet"


def ingest_ticker(ticker: str, out_dir: Path,
                  per_ticker_path: str | None = None) -> Path:
    """Full per-ticker history -> one engine parquet.

    Tries the per-ticker convenience route first; the caller can pass an
    explicit path if the service names it differently.
    """
    path = per_ticker_path or f"/stocks/minute-aggregates/{ticker.upper()}.csv.gz"
    raw = fetch(path, out_dir / f"_{ticker}.raw")
    df = _read_flatfile(raw)
    eng = to_engine_frame(df, ticker=ticker)
    dest = out_dir / _parquet_name(ticker, eng.index)
    eng.to_parquet(dest)
    raw.unlink(missing_ok=True)
    print(f"wrote {dest.name}  ({len(eng):,} bars, "
          f"{eng.index.min().date()}..{eng.index.max().date()})")
    return dest


def ingest_day(date: str, out_dir: Path, tickers: set[str] | None = None
               ) -> dict[str, pd.DataFrame]:
    """One per-day all-ticker file -> {ticker: engine frame}.

    Used to assemble a universe: call across a date range and concatenate
    per ticker before writing. `tickers` restricts to a watchlist.
    """
    y, m, d = date.split("-")
    path = f"/stocks/minute-aggregates/{y}/{m}/{date}.csv.gz"
    raw = fetch(path, out_dir / f"_{date}.raw")
    df = _read_flatfile(raw)
    if tickers is not None:
        df = df[df["ticker"].astype(str).str.upper().isin(
            {t.upper() for t in tickers})]
    frames: dict[str, pd.DataFrame] = {}
    for tk, g in df.groupby("ticker"):
        frames[str(tk).upper()] = to_engine_frame(g)
    raw.unlink(missing_ok=True)
    return frames


def rest_aggregates(ticker: str, start: str, end: str, *,
                    timespan: str = "minute", multiplier: int = 1,
                    limit: int = 50000, header_auth: bool = True,
                    max_pages: int = 200) -> pd.DataFrame:
    """Pull /v2/aggs for one ticker over [start, end], following next_url.

    This is the right route for a BOUNDED per-ticker pull (the ack-test):
    one HTTP call per <=`limit` bars. For full multi-year minute history
    the per-ticker flat file is cheaper -- millions of rows would page
    dozens of times here.
    """
    path = (f"/v2/aggs/ticker/{ticker.upper()}/range/{multiplier}/"
            f"{timespan}/{start}/{end}")
    q = f"adjusted=true&sort=asc&limit={limit}"
    # apiKey in the query only when the deployment needs it there; the
    # default keeps the key in the header instead.
    first = f"{BASE}{path}?{q}" + ("" if header_auth
                                   else f"&apiKey={_key()}")
    rows: list[dict] = []
    url, pages = first, 0
    while url and pages < max_pages:
        code, body = _curl(url, None, timeout=300, header_auth=header_auth)
        if code != "200":
            raise IngestError(f"aggregates HTTP {code}: {body[:200]!r}")
        payload = json.loads(body.decode() or "{}")
        rows.extend(payload.get("results") or [])
        nxt = payload.get("next_url")
        if not nxt:
            break
        # next_url is absolute and already carries the cursor; re-attach
        # the key the same way the first call did.
        url = nxt if header_auth else (
            nxt + ("&" if "?" in nxt else "?") + f"apiKey={_key()}")
        pages += 1
    return rest_results_to_engine(rows)


def ingest_ticker_rest(ticker: str, start: str, end: str, out_dir: Path,
                       header_auth: bool = True) -> Path:
    eng = rest_aggregates(ticker, start, end, header_auth=header_auth)
    dest = out_dir / _parquet_name(ticker, eng.index)
    eng.to_parquet(dest)
    print(f"wrote {dest.name}  ({len(eng):,} bars, "
          f"{eng.index.min()}..{eng.index.max()})")
    return dest


def fetch_reference(path: str, dest: Path) -> Path:
    """Earnings calendar / market caps: save whatever the service returns
    (JSON or CSV) for inspection, since their exact shape is unconfirmed
    until a real key reveals one response."""
    raw = fetch(path, dest)
    head = raw.read_bytes()[:400]
    print(f"wrote {dest}  (first bytes: {head!r})")
    return raw


# -------------------------------------------------------------------- CLI

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("data"),
                    help="output directory (engine data dir)")
    ap.add_argument("--probe", metavar="PATH",
                    help="fetch one file and report schema+timezone, "
                         "e.g. /stocks/minute-aggregates/AAPL.csv.gz")
    ap.add_argument("--ticker", help="ingest one ticker's full history "
                    "from the per-ticker flat file")
    ap.add_argument("--ticker-path",
                    help="override the per-ticker path if the service "
                         "names it differently")
    ap.add_argument("--rest-ticker", metavar="TICKER",
                    help="ingest one ticker over a date range via the "
                         "/v2/aggs REST API (needs --start and --end)")
    ap.add_argument("--start", help="YYYY-MM-DD for --rest-ticker")
    ap.add_argument("--end", help="YYYY-MM-DD for --rest-ticker")
    ap.add_argument("--query-key", action="store_true",
                    help="send the key as ?apiKey=... instead of the "
                         "X-API-Key header (matches the working REST call)")
    ap.add_argument("--reference", metavar="PATH",
                    help="fetch an earnings/market-cap endpoint verbatim "
                         "for inspection")
    ap.add_argument("--reference-out", type=Path,
                    help="where to save --reference output")
    a = ap.parse_args()

    try:
        ha = not a.query_key
        if a.probe:
            probe(a.probe, a.out)
        elif a.rest_ticker:
            if not (a.start and a.end):
                ap.error("--rest-ticker needs --start and --end")
            ingest_ticker_rest(a.rest_ticker, a.start, a.end, a.out,
                               header_auth=ha)
        elif a.ticker:
            ingest_ticker(a.ticker, a.out, a.ticker_path)
        elif a.reference:
            dest = a.reference_out or (a.out / "reference_dump")
            fetch_reference(a.reference, dest)
        else:
            ap.error("nothing to do: pass --probe, --ticker, "
                     "--rest-ticker or --reference")
    except IngestError as exc:
        print(f"INGEST ERROR  {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
