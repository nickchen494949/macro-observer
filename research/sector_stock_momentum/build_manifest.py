#!/usr/bin/env python3
"""
build_manifest.py — MANIFEST.csv: one row per file in this folder (path, bytes, sha256, role, in_public_repo).

Lets an auditor verify that the files they hold are the ones the results were produced from.
Roles are assigned by path rules below (code / test / spec / audit doc / report / input data / raw data / derived data /
result / log). Raw vendor data is listed with its hash even where it is not committed to the public repo.
Excluded: .env (API keys), __pycache__, data/sec_tmp, data/_union_scratch, .DS_Store, MANIFEST.csv itself.
"""
import csv, fnmatch, hashlib, os

HERE = os.path.dirname(os.path.abspath(__file__))
SKIP_DIRS = {'__pycache__', '.git', 'sec_tmp', '_union_scratch', '_union_scratch_fund', '_smallcap_scratch'}
SKIP_FILES = {'.env', '.DS_Store', 'MANIFEST.csv'}

RULES = [   # first match wins
    ('test', ['pit_truncation_test.py', 'determinism_test.py', 'test_*.py', 'identity_check.py']),
    ('code: fetch (downloads external data)', ['fetch_*.py', 'resolve_successors.py']),
    ('code: build (derived data)', ['build_*.py', 'ndx_fundamentals.py', 'historical_sectors.py', 'ticker_aliases.py',
                                    'fundamentals_pit.py', 'ndx_universe.py']),
    ('code: shell chain', ['*.sh']),
    ('code: strategy / study', ['*.py']),
    ('spec (frozen before results)', ['FROZEN_SPEC.md', 'ML_SPEC.md']),
    ('audit doc', ['audit/*', 'AUDIT_INDEX.md']),
    ('report', ['README.md']),
    ('log', ['logs/*']),
    ('raw data (vendor download)', ['data/raw/*', 'data/raw_tiingo/*', 'data/raw_wiki/*', 'data/raw_wiki_check/*',
                                    'data/raw_archive/*', 'data/raw_ndx/*', 'data/raw_volume/*', 'data/sec_submissions/*',
                                    'data/fundamentals/sec_raw/*', 'data/nasdaq100_src/*', 'data/tiingo_supported_tickers.csv',
                                    'data/wiki_bulk/*', 'data/raw_smallcap/*']),
    ('hand-researched input (each row has a source)', ['data/identity_resolutions.csv', 'data/sector_overrides.csv',
                                                      'data/exit_resolutions.csv', 'data/membership_additions.csv',
                                                      'data/ndx_symbol_map.csv', 'data/ndx_cik_map.csv',
                                                      'data/ndx_sectors.csv']),
    ('derived data', ['data/fundamentals/*', 'data/fundamentals_ndx/*', 'data/ndx_*.csv', 'data/earnings_dates.csv']),
    ('input data (downloaded table)', ['data/*']),
    ('result', ['results/*']),
]
PUBLIC_EXCLUDED = ['data/raw/*', 'data/raw_tiingo/*', 'data/raw_wiki/*', 'data/raw_wiki_check/*', 'data/raw_archive/*',
                   'data/raw_ndx/*', 'data/raw_volume/*', 'data/sec_submissions/*', 'data/fundamentals/sec_raw/*',
                   'data/tiingo_supported_tickers.csv', 'data/wiki_bulk/*', 'data/raw_smallcap/*', 'data/smallcap/*.parquet']


def role(rel):
    for r, pats in RULES:
        if any(fnmatch.fnmatch(rel, p) for p in pats):
            return r
    return 'other'


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    rows = []
    for root, dirs, files in os.walk(HERE):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if f in SKIP_FILES:
                continue
            p = os.path.join(root, f)
            if os.path.islink(p):
                continue
            rel = os.path.relpath(p, HERE)
            rows.append({'path': rel, 'bytes': os.path.getsize(p), 'sha256': sha256(p), 'role': role(rel),
                         'in_public_repo': not any(fnmatch.fnmatch(rel, q) for q in PUBLIC_EXCLUDED)})
    with open(os.path.join(HERE, 'MANIFEST.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    c = Counter(r['role'] for r in rows)
    print(len(rows), 'files'); [print(f'  {v:6d}  {k}') for k, v in c.most_common()]


if __name__ == '__main__':
    main()
