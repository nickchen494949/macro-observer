import os
import json
import yfinance as yf
from datetime import datetime

# Symbols to download
SYMBOLS = [
    'ZQ=F', 'CL=F', 'NG=F', 'GC=F', 'HG=F', 'ZW=F', 'ZS=F', 'BDRY',
    '^DJI', '^GSPC', '^IXIC', '^RUT',
    'XLK', 'SOXX', 'IGV', 'MAGS',
    'XLV', 'IBB', 'XLY', 'XRT', 'XLP', 'XLE', 'ICLN', 'XLB', 'GDX', 'XLRE',
    'TLT', '^VIX'
]

# Ensure we have a place to save them
DD = os.path.join(os.path.dirname(__file__), 'data', 'yahoo')
os.makedirs(DD, exist_ok=True)

def safe_name(sym):
    import re
    return re.sub(r'[^a-zA-Z0-9._=-]', '_', sym)

def main():
    print(f"Downloading {len(SYMBOLS)} symbols from Yahoo Finance using yfinance...")
    
    ok_count = 0
    fail_count = 0
    
    for sym in SYMBOLS:
        print(f"  Downloading {sym}...")
        try:
            # Setting auto_adjust=False ensures we get Raw OHLC + Adj Close
            ticker = yf.Ticker(sym)
            df = ticker.history(period="10y", auto_adjust=False)
            
            if df.empty:
                print(f"     {sym}: ❌ No data")
                fail_count += 1
                continue
                
            # Rename columns to match expected lowercase properties
            # yfinance returns Open, High, Low, Close, Adj Close, Volume, Dividends, Stock Splits
            values = []
            for date, row in df.iterrows():
                dt_str = date.strftime('%Y-%m-%d')
                
                raw_open = row['Open']
                raw_high = row['High']
                raw_low = row['Low']
                raw_close = row['Close']
                adj_close = row['Adj Close']
                volume = row['Volume']
                
                # Check for NaNs
                if any(x != x for x in [raw_open, raw_high, raw_low, raw_close, adj_close]):
                    continue
                
                # Calculate adjustment factors
                factor = adj_close / raw_close if raw_close != 0 else 1.0
                adj_open = raw_open * factor
                adj_high = raw_high * factor
                adj_low = raw_low * factor
                
                # Array structure for values:
                # [Date, Open, High, Low, Close, AdjClose, Volume, AdjOpen, AdjHigh, AdjLow]
                # Storing as array keeps JSON compact but we must remember the indices.
                # Actually, user requested JSON format with keys for clarity in Phase 0 description?
                # "suggested new cache structure: { date: '...', open: ..., adjOpen: ... }"
                
                record = {
                    "date": dt_str,
                    "open": float(raw_open),
                    "high": float(raw_high),
                    "low": float(raw_low),
                    "close": float(raw_close),
                    "adjClose": float(adj_close),
                    "adjustmentFactor": float(factor),
                    "adjOpen": float(adj_open),
                    "adjHigh": float(adj_high),
                    "adjLow": float(adj_low),
                    "volume": float(volume),
                    "dividend": float(row.get('Dividends', 0)),
                    "splitRatio": float(row.get('Stock Splits', 1))
                }
                values.append(record)
                
            if not values:
                print(f"     {sym}: ❌ No valid rows after filtering")
                fail_count += 1
                continue
                
            out_data = {
                "id": sym,
                "updated": datetime.utcnow().isoformat() + "Z",
                "source": "yfinance python",
                "adjustmentMethod": "adjCloseRatio",
                "values": values
            }
            
            n = safe_name(sym)
            out_path = os.path.join(DD, f"{n}.json")
            with open(out_path, 'w') as f:
                json.dump(out_data, f, separators=(',', ':'))
                
            print(f"     {sym}: ✅ {len(values)} pts")
            ok_count += 1
            
        except Exception as e:
            print(f"     {sym}: ❌ {str(e)}")
            fail_count += 1

    print(f"\n✅ Results: {ok_count} succeeded, {fail_count} failed\n")

if __name__ == '__main__':
    main()
