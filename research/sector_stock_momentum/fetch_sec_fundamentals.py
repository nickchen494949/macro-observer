#!/usr/bin/env python3
"""
fetch_sec_fundamentals.py — GAAP fundamentals, point-in-time, from SEC
"Financial Statement Data Sets" (https://www.sec.gov/dera/data/financial-statement-data-sets).

Why this source:
  * Each quarterly zip contains ONLY the filings submitted in that quarter, with the filing
    date (`filed`) and acceptance timestamp → values are naturally point-in-time
    (as-first-reported; restatements show up later under their own filing date).
  * One bulk file per quarter (≈60–130 MB), not one request per company.

Process (disk-friendly — only one zip on disk at any time):
  for each quarter 2009q1 … latest:
    download zip → keep 10-K/10-Q(/A) submissions and a curated list of us-gaap/dei tags
    (consolidated values only: no co-registrant, no segment axis) → write parquet → delete zip

Output (all companies, so the universe can be widened later):
  data/fundamentals/sec_raw/sub_<q>.parquet   submissions (adsh, cik, name, sic, form, period, fy, fp, filed, accepted)
  data/fundamentals/sec_raw/num_<q>.parquet   values      (adsh, tag, ddate, qtrs, uom, value)

SEC fair-access policy: declared User-Agent, ≤ 1 request / 3 s here (limit is 10/s).
"""
import io, os, random, sys, time, urllib.error, urllib.request, zipfile
from datetime import date

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'fundamentals', 'sec_raw')
TMP = os.path.join(HERE, 'data', 'sec_tmp')
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)

def _default_ua():
    """SEC requires a contact in the User-Agent — use the repo's git identity."""
    import subprocess
    try:
        email = subprocess.run(['git', 'config', 'user.email'], capture_output=True, text=True, cwd=HERE).stdout.strip()
    except Exception:  # noqa
        email = ''
    return f'macro-observer research {email or "contact-unset"}'


UA = os.environ.get('SEC_USER_AGENT') or _default_ua()
BASE = 'https://www.sec.gov/files/dera/data/financial-statement-data-sets/{q}.zip'
FORMS = {'10-K', '10-Q', '10-K/A', '10-Q/A', '10-KT', '10-KT/A'}

TAGS = {
    # EPS (GAAP)
    'EarningsPerShareBasic', 'EarningsPerShareDiluted', 'EarningsPerShareBasicAndDiluted',
    'IncomeLossFromContinuingOperationsPerBasicShare', 'IncomeLossFromContinuingOperationsPerDilutedShare',
    # income statement
    'NetIncomeLoss', 'NetIncomeLossAvailableToCommonStockholdersBasic', 'NetIncomeLossAvailableToCommonStockholdersDiluted',
    'ProfitLoss', 'IncomeLossFromContinuingOperations', 'OperatingIncomeLoss',
    'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
    'IncomeTaxExpenseBenefit', 'GrossProfit',
    'Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax', 'RevenueFromContractWithCustomerIncludingAssessedTax',
    'SalesRevenueNet', 'SalesRevenueGoodsNet', 'SalesRevenueServicesNet', 'InterestAndDividendIncomeOperating',
    'CostOfRevenue', 'CostOfGoodsAndServicesSold', 'ResearchAndDevelopmentExpense',
    'SellingGeneralAndAdministrativeExpense', 'DepreciationDepletionAndAmortization', 'InterestExpense',
    # shares
    'WeightedAverageNumberOfSharesOutstandingBasic', 'WeightedAverageNumberOfDilutedSharesOutstanding',
    'CommonStockSharesOutstanding', 'EntityCommonStockSharesOutstanding',
    # cash flow
    'NetCashProvidedByUsedInOperatingActivities', 'NetCashProvidedByUsedInOperatingActivitiesContinuingOperations',
    'PaymentsToAcquirePropertyPlantAndEquipment', 'PaymentsForRepurchaseOfCommonStock',
    'PaymentsOfDividends', 'PaymentsOfDividendsCommonStock', 'ShareBasedCompensation',
    # balance sheet
    'Assets', 'Liabilities', 'LiabilitiesAndStockholdersEquity', 'StockholdersEquity',
    'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest', 'AssetsCurrent', 'LiabilitiesCurrent',
    'CashAndCashEquivalentsAtCarryingValue', 'LongTermDebt', 'LongTermDebtNoncurrent', 'LongTermDebtCurrent',
    'DebtCurrent', 'Goodwill', 'IntangibleAssetsNetExcludingGoodwill', 'RetainedEarningsAccumulatedDeficit', 'InventoryNet',
    # dividends per share
    'CommonStockDividendsPerShareDeclared', 'CommonStockDividendsPerShareCashPaid',
}


def quarters():
    today = date.today()
    out = []
    for y in range(2009, today.year + 1):
        for q in range(1, 5):
            if (y, q) < (today.year, (today.month - 1) // 3 + 1):
                out.append(f'{y}q{q}')
    return out


def download(q, path):
    req = urllib.request.Request(BASE.format(q=q), headers={'User-Agent': UA, 'Accept-Encoding': 'identity'})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, 'wb') as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)


def process(q, path):
    with zipfile.ZipFile(path) as z:
        with z.open('sub.txt') as f:
            sub = pd.read_csv(f, sep='\t', dtype=str, encoding='utf-8', encoding_errors='replace',
                              usecols=lambda c: c in {'adsh', 'cik', 'name', 'sic', 'form', 'period', 'fy', 'fp',
                                                      'filed', 'accepted', 'prevrpt', 'afs', 'fye'})
        sub = sub[sub.form.isin(FORMS)].copy()
        keep = set(sub.adsh)
        parts = []
        with z.open('num.txt') as f:
            for ch in pd.read_csv(f, sep='\t', dtype=str, encoding='utf-8', encoding_errors='replace',
                                  chunksize=1_000_000, quoting=3):
                ch = ch[ch.adsh.isin(keep) & ch.tag.isin(TAGS)]
                if 'coreg' in ch:
                    ch = ch[ch.coreg.isna() | (ch.coreg == '')]
                if 'segments' in ch:
                    ch = ch[ch.segments.isna() | (ch.segments == '')]
                ch = ch[ch.version.str.startswith(('us-gaap', 'dei'), na=False)]
                parts.append(ch[['adsh', 'tag', 'ddate', 'qtrs', 'uom', 'value']])
    num = pd.concat(parts) if parts else pd.DataFrame(columns=['adsh', 'tag', 'ddate', 'qtrs', 'uom', 'value'])
    num['value'] = pd.to_numeric(num.value, errors='coerce')
    num['qtrs'] = pd.to_numeric(num.qtrs, errors='coerce').astype('Int16')
    num = num.dropna(subset=['value']).drop_duplicates()
    sub['cik'] = pd.to_numeric(sub.cik, errors='coerce').astype('Int64')
    sub.to_parquet(os.path.join(OUT, f'sub_{q}.parquet'), index=False)
    num.to_parquet(os.path.join(OUT, f'num_{q}.parquet'), index=False)
    return len(sub), len(num)


def main():
    qs = quarters()
    todo = [q for q in qs if not os.path.exists(os.path.join(OUT, f'num_{q}.parquet'))]
    print(f'{len(qs)} quarters, {len(todo)} to fetch', flush=True)
    for q in todo:
        path = os.path.join(TMP, f'{q}.zip')
        for attempt in range(3):
            try:
                download(q, path)
                break
            except urllib.error.HTTPError as e:
                print(f'{q} HTTP {e.code}', flush=True)
                if e.code == 404:
                    break
                if e.code in (403, 429):
                    time.sleep(600)
            except Exception as e:  # noqa
                print(f'{q} download error {e}', flush=True)
                time.sleep(30)
        if not os.path.exists(path):
            continue
        try:
            ns, nn = process(q, path)
            print(f'{q} ok: {ns} filings, {nn} values', flush=True)
        except Exception as e:  # noqa
            print(f'{q} PROCESS FAIL {e}', flush=True)
        finally:
            os.remove(path)
        time.sleep(random.uniform(3, 6))
    print('done', flush=True)


if __name__ == '__main__':
    main()
