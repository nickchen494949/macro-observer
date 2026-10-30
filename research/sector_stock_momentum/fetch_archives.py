#!/usr/bin/env python3
"""
fetch_archives.py — free ARCHIVAL price sources for old S&P members whose ticker was later re-used (so today's
APIs return the new owner). Sources (all public, found by the external audit 2026-10-28):
  * QSTK  — QuantSoftware Toolkit's frozen Yahoo snapshot on GitHub (Date,Open,High,Low,Close,Volume,Adj Close),
            taken around 2012, i.e. BEFORE most of these tickers were recycled.
  * OTT   — optiontradingtips.com historical S&P 500 text files (YYYYMMDD O H L C V, unadjusted).
  * BNSF  — BNSF Railway's own historical BNI share-price PDF (1995-09-22 .. 2010-02-12, closing prices).
Each file is stored as data/raw_archive/<FJA_TICKER>.json {symbol, source, archive_symbol, dates, close, adjclose,
adjusted}. 'adjusted' says whether adjclose includes dividends (QSTK: yes; OTT/BNSF: raw prices only).
Identity and quality are checked afterwards (identity_check.py, overlap comparison) before anything is used.
"""
import io, json, os, re, time, urllib.request

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'data', 'raw_archive')
os.makedirs(OUT, exist_ok=True)
QSTK = 'https://raw.githubusercontent.com/QuantSoftware/QuantSoftwareToolkit/master/QSTK/QSData/Yahoo/{}.csv'
OTT = 'https://www.optiontradingtips.com/resources/historical-data/sp500/{}.TXT'
BNSF = 'https://www.bnsf.com/about-bnsf/financial-information/pdf/bni_stock_1995_2010.pdf'

# fja ticker (index member)  →  (source, symbol in that archive, note)
WANT = {
    'ACS': ('qstk', 'ACS', 'Affiliated Computer Services'), 'BDK': ('qstk', 'BDK', 'Black & Decker'),
    'BMC': ('qstk', 'BMC', 'BMC Software'), 'CBE': ('qstk', 'CBE', 'Cooper Industries'),
    'GR': ('qstk', 'GR', 'Goodrich'), 'JAVA': ('qstk', 'JAVA', 'Sun Microsystems'),
    'NOVL': ('qstk', 'NOVL', 'Novell'), 'MOLX': ('qstk', 'MOLX', 'Molex'), 'NYX': ('qstk', 'NYX', 'NYSE Euronext'),
    'PGN': ('qstk', 'PGN', 'Progress Energy'), 'TLAB': ('qstk', 'TLAB', 'Tellabs'), 'MI': ('qstk', 'MI', 'Marshall & Ilsley'),
    'PTV': ('qstk', 'PTV', 'Pactiv'), 'LIFE': ('qstk', 'LIFE', 'Life Technologies'), 'BTUUQ': ('qstk', 'BTU', 'Peabody Energy (old)'),
    'EKDKQ': ('qstk', 'EK', 'Eastman Kodak (old)'), 'RSHCQ': ('qstk', 'RSH', 'RadioShack'), 'SII': ('qstk', 'SII', 'Smith International'),
    'WYE': ('qstk', 'WYE', 'Wyeth'), 'SGP': ('qstk', 'SGP', 'Schering-Plough'), 'DYN': ('qstk', 'DYN', 'Dynegy (old)'),
    'EQ': ('qstk', 'EQ', 'Embarq'), 'WFT': ('qstk', 'WFT', 'Weatherford'), 'NCC': ('qstk', 'NCC', 'National City'),
    'WB': ('qstk', 'WB', 'Wachovia'), 'UST': ('qstk', 'UST', 'UST Inc'), 'CTX': ('qstk', 'CTX', 'Centex'),
    'NSM': ('qstk', 'NSM', 'National Semiconductor'), 'Q': ('qstk', 'Q', 'Qwest'), 'GENZ': ('qstk', 'GENZ', 'Genzyme'),
    'KG': ('qstk', 'KG', 'King Pharmaceuticals'), 'CEG': ('qstk', 'CEG', 'Constellation Energy (old)'),
    'SUN': ('qstk', 'SUN', 'Sunoco Inc'), 'ATGE': ('qstk', 'DV', 'DeVry (later Adtalem)'),
    'ANRZQ': ('qstk', 'ANR', 'Alpha Natural Resources'), 'EP': ('qstk', 'EP', 'El Paso Corp'),
    'CITGQ': ('qstk', 'CIT', 'CIT Group (pre-2009 equity)'),
    'JCI-OLD': ('qstk', 'JCI', 'Johnson Controls Inc (before the 2016 Tyco merger)'),
    'AGN-OLD': ('qstk', 'AGN', 'Allergan Inc (before the 2015 Actavis merger)'),
    'CEPH': ('ott', 'CEPH', 'Cephalon'), 'MEE': ('ott', 'MEE', 'Massey Energy'),
    'BNI': ('bnsf', 'BNI', 'Burlington Northern Santa Fe'),
}


def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 macro-observer research'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def parse_qstk(b):
    df = pd.read_csv(io.BytesIO(b))
    df.columns = [c.strip() for c in df.columns]
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    return df.Date, df['Close'], df['Adj Close'], True


def parse_ott(b):
    rows = [l.split() for l in b.decode('latin-1').splitlines() if l.strip()]
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ['d', 'o', 'h', 'l', 'c', 'v']
    df['d'] = pd.to_datetime(df.d, format='%Y%m%d')
    df['c'] = df.c.astype(float)
    return df.d, df.c, df.c, False


def parse_bnsf(b):
    import fitz
    doc = fitz.open(stream=b, filetype='pdf')
    text = '\n'.join(p.get_text() for p in doc)
    pat = re.compile(r'(\d{1,2}/\d{1,2}/\d{2,4})\s+\$?\s*([0-9]+\.[0-9]+)')
    rows = [(pd.to_datetime(d), float(c)) for d, c in pat.findall(text)]
    df = pd.DataFrame(rows, columns=['d', 'c']).drop_duplicates('d').sort_values('d')
    return df.d, df.c, df.c, False


def main():
    log = {}
    for tk, (src, sym, note) in WANT.items():
        try:
            if src == 'qstk':
                d, c, a, adj = parse_qstk(get(QSTK.format(sym)))
            elif src == 'ott':
                d, c, a, adj = parse_ott(get(OTT.format(sym)))
            else:
                d, c, a, adj = parse_bnsf(get(BNSF))
            json.dump({'symbol': tk, 'source': src, 'archive_symbol': sym, 'note': note, 'adjusted': adj,
                       'dates': d.dt.strftime('%Y-%m-%d').tolist(), 'close': [round(float(x), 4) for x in c],
                       'adjclose': [round(float(x), 6) for x in a]}, open(os.path.join(OUT, f'{tk}.json'), 'w'))
            log[tk] = f'{src}:{sym} {d.iloc[0].date()}..{d.iloc[-1].date()} ({len(d)} rows)'
        except Exception as e:  # noqa
            log[tk] = f'{src}:{sym} FAIL {e}'
        print(tk, log[tk], flush=True)
        time.sleep(1)
    json.dump(log, open(os.path.join(OUT, '_log.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
