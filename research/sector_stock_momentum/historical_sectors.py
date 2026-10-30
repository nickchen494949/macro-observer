"""
historical_sectors.py — rebuild the GICS sector a stock had AT A GIVEN DATE.

Free data only gives today's classification (Wikipedia GICS sector + sub-industry for current
members, Yahoo sector + industry for former members). This module undoes the three big GICS
reshuffles that happened inside the 2008–2026 sample, using the sub-industry / industry:

  1. 2016-09-01  Real Estate split out of Financials          (S&P effective after close 2016-08-31)
  2. 2018-09-24  Telecommunication Services → Communication Services, media/internet moved in
                 (S&P effective after close 2018-09-21)
  3. 2023-03-20  Payments: IT → Financials; HR/data-processing: IT → Industrials;
                 general-merchandise retail (DG, DLTR, TGT): Consumer Discretionary → Staples
                 (S&P effective after close 2023-03-17)

Anything else (individual company re-classifications, smaller GICS tweaks) is NOT reconstructed.
Rows where the rebuild relies on a guess are flagged via `sector_asof(..., return_flag=True)`.
"""
import pandas as pd

D_RE = pd.Timestamp('2016-09-01')
D_CS = pd.Timestamp('2018-09-24')
D_23 = pd.Timestamp('2023-03-20')

# --- 2018 Communication Services: where each sub-industry lived before ---
CS_PRE2018_GICS = {
    'Integrated Telecommunication Services': 'Telecommunication Services',
    'Wireless Telecommunication Services': 'Telecommunication Services',
    'Alternative Carriers': 'Telecommunication Services',
    'Interactive Media & Services': 'Information Technology',      # GOOGL, META (Internet Software & Services)
    'Interactive Home Entertainment': 'Information Technology',    # EA, ATVI, TTWO (Home Entertainment Software)
    'Movies & Entertainment': 'Consumer Discretionary',            # DIS, NFLX (NFLX was Internet Retail, still Cons. Disc.)
    'Broadcasting': 'Consumer Discretionary',
    'Cable & Satellite': 'Consumer Discretionary',
    'Publishing': 'Consumer Discretionary',
    'Advertising': 'Consumer Discretionary',
}
CS_PRE2018_YAHOO = {
    'Telecom Services': 'Telecommunication Services',
    'Internet Content & Information': 'Information Technology',
    'Electronic Gaming & Multimedia': 'Information Technology',
    'Entertainment': 'Consumer Discretionary',
    'Broadcasting': 'Consumer Discretionary',
    'Publishing': 'Consumer Discretionary',
    'Advertising Agencies': 'Consumer Discretionary',
}
# eBay moved IT → Consumer Discretionary in the same 2018 change
MOVED_2018_TO_CD_FROM_IT = {'EBAY'}

# --- 2023 changes ---
PAYMENTS_SUB = {'Transaction & Payment Processing Services'}            # → Financials (was IT)
MOVED_2023_IT_TO_IND = {'ADP', 'PAYX', 'PAYC', 'DAY', 'CDAY', 'BR'}     # HR / data processing (was IT)
MOVED_2023_CD_TO_CS = {'DG', 'DLTR', 'TGT'}                            # general merchandise (was Cons. Disc.)


def sector_asof(ticker, date, sector, source, industry, return_flag=False):
    d = pd.Timestamp(date)
    sec, flag = sector, 'as_today'
    ind = industry if isinstance(industry, str) else ''

    # undo 2023 first (latest change), then 2018, then 2016
    if d < D_23:
        if sec == 'Financials' and (ind in PAYMENTS_SUB or (source == 'yahoo' and ind == 'Credit Services'
                                                             and ticker in {'V', 'MA'})):
            sec, flag = 'Information Technology', 'rebuilt_2023'
        elif sec == 'Industrials' and ticker in MOVED_2023_IT_TO_IND:
            sec, flag = 'Information Technology', 'rebuilt_2023'
        elif sec == 'Consumer Staples' and ticker in MOVED_2023_CD_TO_CS:
            sec, flag = 'Consumer Discretionary', 'rebuilt_2023'
    if d < D_CS:
        if sec == 'Communication Services':
            gics = 'wikipedia_gics' in str(source) or str(source).startswith('manual')
            m = CS_PRE2018_GICS.get(ind) if gics else CS_PRE2018_YAHOO.get(ind)
            if m is None and ind.startswith('SIC '):
                code = ind[4:].split('.')[0]
                m = ('Telecommunication Services' if code.startswith('48') and code not in ('4833', '4841')
                     else 'Information Technology' if code.startswith('737') else 'Consumer Discretionary')
            if m:
                sec, flag = m, 'rebuilt_2018'
            else:
                sec, flag = 'Consumer Discretionary', 'guess_2018'   # unknown sub-industry → media default
        elif ticker in MOVED_2018_TO_CD_FROM_IT and sec == 'Consumer Discretionary':
            sec, flag = 'Information Technology', 'rebuilt_2018'
    if d < D_RE and sec == 'Real Estate':
        sec, flag = 'Financials', 'rebuilt_2016'
    return (sec, flag) if return_flag else sec


def build_panel(sector_df, month_ends):
    """DataFrame [month_end × ticker] of point-in-time sectors (+ flags).
    Rows with valid_from / valid_to (dated manual overrides) are taken AS IS for their dates (they already state
    the classification at that time); all other rows go through the 2016/2018/2023 rebuild."""
    sec, flg = {}, {}
    has_dates = 'valid_from' in sector_df.columns
    for tk, g in sector_df.groupby('ticker', sort=True):
        g = g[g.sector.apply(lambda x: isinstance(x, str) and x != 'UNKNOWN')]
        if g.empty:
            continue
        col_s, col_f = [None] * len(month_ends), [None] * len(month_ends)
        undated = g[g.valid_from.isna() & g.valid_to.isna()] if has_dates else g
        dated = g[~g.index.isin(undated.index)]
        if len(undated):
            r = undated.iloc[0]
            for i, t in enumerate(month_ends):
                col_s[i], col_f[i] = sector_asof(tk, t, r.sector, r.source, r.get('industry'), True)
        for _, r in dated.iterrows():
            a = pd.Timestamp(r.valid_from) if pd.notna(r.valid_from) else pd.Timestamp('1900-01-01')
            b = pd.Timestamp(r.valid_to) if pd.notna(r.valid_to) else pd.Timestamp('2100-01-01')
            for i, t in enumerate(month_ends):
                if a <= t < b:
                    col_s[i], col_f[i] = r.sector, 'manual_dated'
        sec[tk], flg[tk] = col_s, col_f
    return pd.DataFrame(sec, index=month_ends), pd.DataFrame(flg, index=month_ends)
