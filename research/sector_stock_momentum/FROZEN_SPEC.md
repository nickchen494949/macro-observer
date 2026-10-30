# FROZEN SPEC — 动量板块×动量股策略

Written and committed **before** the post-audit rerun (2026-10-28). Any later change to anything below must be a
new commit with a reason; results produced under a changed spec are reported as such.

## Strategy (unchanged from the user's request)
- Universe at month-end t: S&P 500 members at t (point-in-time), price at t (a genuine month-end quote, i.e. traded
  within the last ~5 sessions of the month), full 12-1 window inside one price segment, sector known as of t.
- Signal: 12-1 momentum = P(t−1)/P(t−12) − 1.
- Sector score: equal-weighted mean momentum of the sector's eligible members (main); ETF variant: 12-1 momentum of
  the Select Sector SPDR that existed at t, with Telecommunication Services + Information Technology forming ONE
  bucket before 2018 (both were inside XLK).
- Pick: top sector, top stock inside it (n_sec × n_stk per sector in the grid); equal weight; always invested.
- Ties: value descending, then ticker ascending (no hash/set ordering anywhere).
- Hold t → t+1 close; sold at t+1 even if removed from the index.
- Terminal events: verified payout (data/exit_resolutions.csv) > last trade if the stock stopped trading in the
  month (`delisted_in_month`, then cash) > `source_gap` / `unresolved` (base 0 %, stress −30 % and −100 %).
- Costs: 10 bp × Σ|w_target − w_pre-trade|.

## Sample and evaluation
- Holding months 2009-01 … 2026-09 (213). IS = first 149 (to 2021-05), OOS = last 64.
- Grid (look 3/6/9/12 × sectors 1/2/3 × stocks 1/3/5/10 × score ew/etf) is SELECTED on IS months up to 2021-04 by
  Sharpe; the IS-selected config and the spec are evaluated on OOS once.
- Pre-declared diagnostics (not used for selection): all-config SEL-vs-OOS rank correlation, deflated Sharpe, paired
  stationary bootstrap (arithmetic AND CAGR differences, labelled as resample shares, not p-values), no-sector-filter
  comparison with the same number of stocks, concentration (top-5 months), periods to 2025-12.
- Note: the OOS period was already seen once before the audit (pre-audit run, commit ba751e7). It is therefore a
  **retrospective temporal holdout**, not an untouched one. The fixes below were driven by audit findings about data
  identity and determinism, not by OOS performance.

## Data rules (post-audit)
- Identity: rename aliases need same SEC CIK / Wikipedia evidence; acquirer-took-ticker cases are resolved in
  data/identity_resolutions.csv with evidence; market-cap plausibility and Yahoo-vs-WIKI cross-checks
  (identity_check.py) flag remaining suspects.
- Sectors: data/sector_overrides.csv (dated, with sources) > Wikipedia GICS > rename successor > Yahoo only if the
  ticker is priced from Yahoo (same company) > SEC SIC; 2016/2018/2023 GICS reshuffles rebuilt.
- One shared preprocessing path for backtest.py and pit_truncation_test.py.
