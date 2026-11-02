#!/usr/bin/env python3
"""
09 — SHA-256 manifest of every input file read by the INDEPENDENT scripts (01-04, 07, 08), so a third
party who obtains the (gitignored) raw data can verify they hold byte-identical inputs.
The engine-dependent parts (05 Part A, 06 'gemini' engine) additionally read Gemini's library inputs
(SEC FSDS parquet, sectors.csv, etc.) — those are covered by Gemini's own baseline-integrity manifest.
Output: INPUT_MANIFEST.csv
"""
import glob, hashlib, os, subprocess
import pandas as pd
from _paths import REPO, DATA, GEMINI, HERE

files = [f"{DATA}/sp500_hist_components.csv", f"{DATA}/identity_resolutions.csv", f"{DATA}/fred_DGS3MO.json"]
for sub in ("raw", "raw_open", "raw_tiingo", "raw_wiki", "raw_archive"):
    files += sorted(glob.glob(f"{DATA}/{sub}/*.json"))
files += sorted(glob.glob(f"{GEMINI}/v2_06_ledger_*.csv"))
tracked = set(subprocess.run(["git", "-C", REPO, "ls-files"], capture_output=True, text=True).stdout.split("\n"))
rows = []
for p in files:
    rel = os.path.relpath(p, REPO)
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    rows.append(dict(path=rel, bytes=os.path.getsize(p), sha256=h, in_git=rel in tracked))
M = pd.DataFrame(rows)
M.to_csv(os.path.join(HERE, "INPUT_MANIFEST.csv"), index=False)
print(f"[09] {len(M)} input files | in git: {M.in_git.sum()} | NOT in git (must be supplied): {(~M.in_git).sum()} "
      f"| total {M.bytes.sum()/1e6:.1f} MB")
