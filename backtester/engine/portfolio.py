"""
portfolio.py -- STEP 4, not yet implemented.

Responsibilities when built:
  * capital tracking and daily equity
  * fixed-fractional and fixed-notional sizing
  * max_concurrent_positions, with an EX-ANTE selection rule when a
    session produces more signals than slots (never by realised P&L)
  * max_gross_exposure, applied pro-rata
  * costs charged on notional at entry and exit
  * realistic stop fills: the intended level, or the bar open when the
    bar gapped through it -- whichever is worse for the position
"""
