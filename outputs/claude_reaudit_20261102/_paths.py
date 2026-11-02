"""
Shared, portable paths for the Claude re-audit package.

Resolution order for the repository root:
  1. env var MACRO_REPO_ROOT (if set)
  2. two directories above this file (outputs/claude_reaudit_20261102/ -> repo root)

Raw price data (data/raw, data/raw_open, data/raw_tiingo, data/raw_wiki, ...) is .gitignored in
research/sector_stock_momentum/ and therefore NOT on GitHub. See README.md + INPUT_MANIFEST.csv
(SHA-256 of every input file) for how to supply and verify it.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("MACRO_REPO_ROOT") or os.path.dirname(os.path.dirname(HERE))
SSM = os.path.join(REPO, "research", "sector_stock_momentum")
DATA = os.path.join(SSM, "data")
GEMINI = os.path.join(REPO, "outputs", "gemini_full_data_audit_20261031", "v2_standalone")
WORK = os.path.join(HERE, "_work")          # regenerated intermediates (gitignored)
RESULTS = os.path.join(HERE, "results")     # small committed outputs
os.makedirs(WORK, exist_ok=True)
os.makedirs(RESULTS, exist_ok=True)


def gemini_ledger(name: str) -> str:
    """Path of a Gemini ledger CSV (used ONLY as the comparison target, never as an input)."""
    return os.path.join(GEMINI, name)


def raw_rf_monthly():
    """Monthly T-bill carry from raw FRED DGS3MO (tracked in git), same convention as the audited code:
    rf[holding month m] = (1 + DGS3MO_last(<= m-1 month-end)/100)^(1/12) - 1."""
    import json
    import pandas as pd
    p = os.path.join(DATA, "fred_DGS3MO.json")
    if not os.path.exists(p):
        p = os.path.join(REPO, "data", "fred", "DGS3MO.json")
    vals = json.load(open(p))["values"]
    y = pd.Series({pd.Timestamp(a): float(b) for a, b in vals if b is not None}).sort_index()
    y = y.resample("ME").last()
    hold = pd.date_range("2008-01-31", "2027-12-31", freq="ME")
    y_form = y.reindex(hold - pd.offsets.MonthEnd(1)).ffill().values / 100.0
    return pd.Series((1.0 + y_form) ** (1.0 / 12.0) - 1.0, index=hold)
