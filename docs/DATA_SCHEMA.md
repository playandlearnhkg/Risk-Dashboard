# Stage 1 — Data Schema and Preparation Guide

Everything you need to drop local data in and run Steps 1 → 5.
Companion to `CANDLE_SCORING_STAGE1_PREDICTIVITY.md` and `preregistration.yaml`.

---

## 1. Directory structure

```
Risk-Dashboard/
├── data/
│   ├── manifest.yaml            <- you write this
│   ├── raw/                     <- you drop files here
│   │   ├── SPY_5min.csv
│   │   ├── TLT_5min.csv
│   │   ├── GLD_5min.csv
│   │   └── FXE_5min.csv
│   └── clean/                   <- written by stage1.validate, do not hand-edit
│       ├── SPY_5min.parquet
│       └── data_manifest.json   <- stamped facts + sha256 of every source file
└── results/
    └── step5/                   <- written by stage1.step5
```

`data/` and `results/` are gitignored. The source files stay on your machine;
only their hashes are recorded.

---

## 2. File format

CSV or Parquet, one file per instrument per timeframe. Naming is free —
the manifest points at the paths.

### Required columns

| Canonical | Accepted aliases (case-insensitive) | Type |
|---|---|---|
| `timestamp` | `time`, `datetime`, `date`, `t`, `ts`, `bar_time` | see §3 |
| `open` | `o` | float |
| `high` | `h` | float |
| `low` | `l` | float |
| `close` | `c` | float |

### Optional

| Canonical | Aliases | Notes |
|---|---|---|
| `volume` | `v`, `vol` | Not used by any Stage 1 test. Load it anyway — the validator uses it to detect synthetic fill bars |

Any column not in this list is ignored. A **missing** required column is a hard
load failure — the loader will not guess which column is which, because a
silently mismapped column is worse than a failed load.

### Minimal example

```csv
timestamp,open,high,low,close,volume
2019-01-02T09:30:00-05:00,249.56,250.01,249.31,249.88,4821300
2019-01-02T09:35:00-05:00,249.88,250.14,249.72,249.95,2210400
```

---

## 3. Timestamp requirements

**Preferred: ISO 8601 with an explicit UTC offset.** `2019-01-02T09:30:00-05:00`

Three accepted forms, in order of preference:

| Form | Example | Manifest setting |
|---|---|---|
| ISO with offset | `2019-01-02T09:30:00-05:00` | nothing extra |
| Epoch integer | `1546439400000` | `timestamp_unit: ms` (or `s`) |
| Naive wall clock | `2019-01-02 09:30:00` | nothing extra — localised to `timezone` |

Rules:

- **One row per bar, no duplicates.** Duplicates are dropped and counted; a
  large count is a red flag you should investigate rather than accept.
- **Sorted ascending** (the loader sorts anyway and reports that it had to).
- **DST is handled for you** if you use offset-aware or epoch timestamps. Naive
  timestamps that land on a nonexistent or ambiguous DST hour raise an error
  rather than being silently shifted — a shifted bar is a misaligned bar.
- **Extended hours may be present.** They are filtered out; you do not need to
  pre-trim.

### Bar label convention — the one that matters most

Declare in the manifest whether a stamp marks the bar's **open** or its **close**:

```
open-labelled  : 09:30 bar covers 09:30-09:35, last RTH bar is 15:55
close-labelled : 09:35 bar covers 09:30-09:35, last RTH bar is 16:00
```

**The validator infers this from your data and aborts if it disagrees with your
declaration.** Both must agree. An off-by-one here shifts every feature one bar
relative to its target, which is indistinguishable from a genuine edge in the
output — it is the single most likely source of a large false positive in this
study.

If you do not know your vendor's convention: count the bars in a normal
session and look at the last stamp. 78 bars ending at 15:55 is open-labelled;
78 bars ending at 16:00 is close-labelled.

---

## 4. The manifest

`data/manifest.yaml`:

```yaml
instruments:
  - symbol: SPY
    path: raw/SPY_5min.csv          # relative to the manifest, or absolute
    timezone: America/New_York
    bar_label: open                 # open | close  — VERIFIED against the data
    session_start: "09:30"
    session_end: "16:00"
    tick_size: 0.01
    adjustment: multiplicative      # multiplicative | none  (additive is rejected)
    vendor: your_vendor_name
    # timestamp_unit: ms            # only if timestamps are epoch integers
```

Repeat the block per instrument. Every field is checked.

---

## 5. Data requirements (history Option A, locked)

| Requirement | Value |
|---|---|
| Instruments | SPY, TLT, GLD, FXE (default; substitute before Step 3, see §7) |
| Timeframe | 5-minute, RTH only |
| **History per instrument** | **≥ 1,762 sessions ≈ 7 years** |
| Breakdown | 250 warm-up + 1,260 evaluation (20 blocks × 63) + 252 sealed holdout |
| Adjustment | Multiplicative or unadjusted. **Additive is rejected** — it corrupts intrabar ratios |
| Degenerate bars | Must be < 5% of bars, or the instrument is dropped |

The 1-minute series is only needed at execution step 11. Do not prepare it yet.

---

## 6. Red flags — any of these makes a dataset unusable

The validator checks all of them and aborts:

| Check | Why it is fatal |
|---|---|
| Declared vs inferred bar label mismatch | Manufactures a fake edge |
| `low > min(open, close)` or `high < max(open, close)` | Corrupt feed; every ratio is meaningless |
| Non-positive prices | Corrupt or badly adjusted |
| Weekend timestamps in an RTH equity session | Wrong session definition or wrong timezone |
| Modal bars/session ≠ expected for the declared window | Session window or bar size misdeclared |
| Declared tick size >10× from inferred | The §1.4 noise floor would be wrong |
| Degenerate bars > 5% | Too illiquid for this timeframe |
| `adjustment: additive` | Corrupts intrabar geometry |

Warnings (reported, not fatal — judgement required):

- Repeated identical OHLC runs → the vendor may be forward-filling empty bars,
  which fabricates geometry out of nothing
- Many zero-volume bars → same concern
- Overnight moves > 20% → check the series is split-adjusted
- Fewer than 1,762 sessions → Step 2 decides whether it is fatal

---

## 7. Substituting instruments

The default set is ETFs on one shared 09:30–16:00 session: no continuous-contract
roll splices, no index membership, aligned time-of-day buckets.

If you substitute:

- **Legitimate:** swapping instruments to obtain adequate power at Step 2.
  Power is about data adequacy, not results.
- **Not legitimate:** swapping after seeing any IC, bucket or quadrant number.
  That voids the pre-registration and requires a fresh one.
- **Continuous futures** are fine but the roll bar must be excluded — the splice
  creates a bar whose geometry is an artefact of the join.
- **Prefer low mutual correlation.** Four equity ETFs will collapse `K_eff`
  toward 1 and waste three quarters of the data.

Edit `docs/preregistration.yaml` → `data.instruments`, and note the substitution
in the commit message.

---

## 8. Commands

```bash
cd Risk-Dashboard
pip install numpy pandas pyarrow pyyaml
export PYTHONPATH=.

# Step 1 — load and validate. Aborts on any red flag in section 6.
python -m stage1.validate --manifest data/manifest.yaml --out data/clean

# Step 2 — n_eff, K_eff, block budget. Can end the study with Verdict B.
python -m stage1.power --data data/clean

# Step 3 — pipeline gates on YOUR data. Hard gate; nothing downstream counts
#          until these pass.
python -m stage1.gates --data data/clean

# Step 5 — the core test: per-block IC, decile ladder, quadrant, gate table.
python -m stage1.step5 --data data/clean --out results/step5
```

Supporting commands:

```bash
python docs/stage1_reference.py          # section 5.6 self-test on synthetic bars
python tests/test_stage1.py              # 20 unit tests, no pytest needed
python tests/make_fixture.py --sessions 600   # synthetic data in this schema
```

After Step 1 passes, copy the stamped values from
`data/clean/data_manifest.json` into the `data:` section of
`docs/preregistration.yaml` and set `manifest_status: VERIFIED`.

---

## 9. What each step can return

| Step | Outcome | Meaning |
|---|---|---|
| 1 | exit 0 / 1 | Data usable / red flag found |
| 2 | exit 0 / 2 | Proceed / **Verdict B — underpowered, stop** |
| 3 | exit 0 / 1 | Pipeline trustworthy / K8 fires, everything void |
| 5 | exit 0 / 2 | Continue to step 6 / **Verdict C — no useful predictivity, stop** |

A non-zero exit at Step 2 or Step 5 is a legitimate, complete result. The study
is designed to end there more often than not.
