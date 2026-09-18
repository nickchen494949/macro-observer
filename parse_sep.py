#!/usr/bin/env python3
"""Supplement SEP_HISTORY with properly parsed 2012-2016 data.
The old PDFs have Table 2 with 7 values per row, each on its own line:
  participant_num, year, gdp, unemp, pce, core_pce, funds_rate
We extract fed funds rate (last in each group of 7) and compute medians."""
import fitz
import json
import os
import re
from statistics import median

SEP_DIR = '/Users/happygolucky/Desktop/QQQ_Risk_Strategy/fomc_sep'
OUTPUT = '/Users/happygolucky/projects/宏观观察器/data/valuation/SEP_HISTORY.json'

def is_float(s):
    try:
        float(s)
        return True
    except:
        return False

def parse_table2_page(text):
    """Parse Table 2 from a page where each cell is on its own line."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    rates_by_year = {}
    i = 0
    
    while i < len(lines):
        # Look for participant number (1-19)
        if not lines[i].isdigit():
            i += 1
            continue
        
        pnum = int(lines[i])
        if pnum < 1 or pnum > 19:
            i += 1
            continue
        
        # Next should be year or "Longer"
        if i + 1 >= len(lines):
            break
            
        year_line = lines[i + 1]
        
        if year_line.startswith('Longer'):
            # Longer run row - skip "run" if separate, then read values
            skip = 2
            if i + 2 < len(lines) and lines[i + 2].lower() == 'run':
                skip = 3
            # Read numeric values after
            nums = []
            j = i + skip
            while j < len(lines) and is_float(lines[j]) and len(nums) < 6:
                nums.append(float(lines[j]))
                j += 1
            if len(nums) >= 2:
                rates_by_year.setdefault('Longer Run', []).append(nums[-1])
            i = j
            continue
        
        try:
            year = int(year_line)
            if year < 2010 or year > 2035:
                i += 1
                continue
        except ValueError:
            i += 1
            continue
        
        # Read the data values: gdp, unemp, pce, core_pce, funds_rate  
        # That's 5 numbers (sometimes 4 if no core_pce in early PDFs)
        nums = []
        j = i + 2
        while j < len(lines) and is_float(lines[j]) and len(nums) < 6:
            nums.append(float(lines[j]))
            j += 1
        
        if len(nums) >= 5:
            # 5 values: gdp, unemp, pce, core_pce, funds_rate
            rate = nums[4]
            if rate < 20:  # sanity check - should be a reasonable rate
                rates_by_year.setdefault(str(year), []).append(rate)
        elif len(nums) == 4:
            # 4 values: gdp, unemp, pce, funds_rate (no core_pce, early format)
            rate = nums[3]
            if rate < 20:
                rates_by_year.setdefault(str(year), []).append(rate)
        
        i = j
    
    return rates_by_year

def process_old_pdf(filepath):
    """Process a 2012-2016 SEP PDF."""
    doc = fitz.open(filepath)
    basename = os.path.basename(filepath)
    m = re.search(r'(\d{4}-\d{2}-\d{2})', basename)
    if not m:
        return None
    date = m.group(1)
    
    all_rates = {}
    
    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        # Table 2 pages contain "Table 2" or individual projections with "funds rate"
        if 'Table 2' in text:
            rates = parse_table2_page(text)
            for year, vals in rates.items():
                all_rates.setdefault(year, []).extend(vals)
    
    if not all_rates or len(all_rates) < 2:
        return None
    
    # Compute median per year
    curve = []
    for year in sorted(all_rates.keys(), key=lambda x: x if x != 'Longer Run' else 'ZZZZ'):
        vals = all_rates[year]
        if vals:
            med = round(median(vals), 2)
            if med < 20:  # sanity
                curve.append({'year': year, 'rate': med})
    
    if len(curve) < 3:
        return None
    
    return [date, curve]

def main():
    # Load existing SEP_HISTORY
    with open(OUTPUT) as f:
        data = json.load(f)
    existing = {entry[0]: entry for entry in data['values']}
    
    # Parse old PDFs (2012-2016)
    pdfs = sorted([f for f in os.listdir(SEP_DIR) if f.endswith('.pdf')])
    updated = 0
    
    for pdf in pdfs:
        m = re.search(r'(\d{4})-', pdf)
        if not m:
            continue
        year = int(m.group(1))
        if year > 2016:
            continue  # strategy_engine handles these fine
        
        filepath = os.path.join(SEP_DIR, pdf)
        result = process_old_pdf(filepath)
        
        if result:
            date, curve = result
            pts = ', '.join(f"{p['year']}={p['rate']}" for p in curve)
            
            # Check if this improves on existing
            old = existing.get(date)
            old_len = len(old[1]) if old else 0
            
            if len(curve) > old_len:
                print(f"  ✅ {date}: {old_len} → {len(curve)} pts: {pts}")
                existing[date] = [date, curve]
                updated += 1
            else:
                print(f"  ⏭️  {date}: existing {old_len} pts ≥ new {len(curve)} pts, skip")
        else:
            print(f"  ❌ {pdf}: parse failed")
    
    # Rebuild sorted history
    history = sorted(existing.values(), key=lambda x: x[0])
    data['values'] = history
    data['updated'] = history[-1][0]
    
    with open(OUTPUT, 'w') as f:
        json.dump(data, f)
    
    print(f"\nUpdated {updated} entries. Total: {len(history)} meetings")
    print(f"Range: {history[0][0]} → {history[-1][0]}")

if __name__ == '__main__':
    main()
