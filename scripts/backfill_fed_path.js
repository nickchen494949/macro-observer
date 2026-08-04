const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');

const FETCH_YAHOO_PY = path.join(__dirname, '../fetch_yahoo.py');
const VALUATION_DIR = path.join(__dirname, '../data/valuation');

function fetchYahoo(symbol, range = '1y') {
  return new Promise((resolve, reject) => {
    execFile('python3', [FETCH_YAHOO_PY, symbol, range], { timeout: 30000 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(err.message || stderr));
      try {
        const result = JSON.parse(stdout.trim());
        if (!result.ok) return reject(new Error(result.error || 'unknown'));
        resolve(result.data);
      } catch(e) {
        reject(new Error('parse: ' + e.message));
      }
    });
  });
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const monthCodes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'];
  
  // We need to fetch enough tickers to reconstruct 18-month curves for the past 12 months.
  // Today is ~July 2026. 12 months ago was July 2025. 
  // From July 2025, an 18 month curve goes out to Dec 2026.
  // From July 2026, an 18 month curve goes out to Dec 2027.
  // So we need to fetch all contracts from July 2025 through Dec 2027.
  
  const tickers = [];
  let d = new Date('2025-07-01T00:00:00Z');
  const end = new Date('2027-12-01T00:00:00Z');
  
  while (d <= end) {
    const m = d.getUTCMonth();
    const y = d.getUTCFullYear() % 100;
    const sym = `ZQ${monthCodes[m]}${y}.CBT`;
    const label = `${d.getUTCFullYear()}-${String(m+1).padStart(2,'0')}`;
    tickers.push({ sym, label, dateObj: new Date(d) });
    d.setUTCMonth(d.getUTCMonth() + 1);
  }
  
  console.log(`Need to fetch ${tickers.length} tickers...`);
  
  const allData = {}; // symbol -> Map of { date -> price }
  
  for (const t of tickers) {
    try {
      const data = await fetchYahoo(t.sym, '1y');
      const map = new Map();
      if (data) {
        for (const [dateStr, price] of data) {
          map.set(dateStr, price);
        }
      }
      allData[t.sym] = map;
      console.log(`Fetched ${t.sym} - ${map.size} data points`);
    } catch(e) {
      console.log(`Failed ${t.sym}: ${e.message}`);
    }
    await sleep(2000);
  }
  
  // Find all unique trading days across all fetched data
  const allDatesSet = new Set();
  for (const t of tickers) {
    if (!allData[t.sym]) continue;
    for (const k of allData[t.sym].keys()) {
      allDatesSet.add(k);
    }
  }
  const allDates = [...allDatesSet].sort();
  
  console.log(`Found ${allDates.length} unique trading days in the last year.`);
  
  const history = []; // [ ["2026-07-01", [{month, rate}, ...]], ... ]
  
  for (const date of allDates) {
    const dObj = new Date(date + 'T00:00:00Z');
    
    // Build the 18 month curve for this date
    const curve = [];
    let curD = new Date(dObj);
    for (let i = 0; i < 18; i++) {
      const m = curD.getUTCMonth();
      const yStr = curD.getUTCFullYear() % 100;
      const sym = `ZQ${monthCodes[m]}${yStr}.CBT`;
      const label = `${curD.getUTCFullYear()}-${String(m+1).padStart(2,'0')}`;
      
      const priceMap = allData[sym];
      if (priceMap && priceMap.has(date)) {
        const price = priceMap.get(date);
        curve.push({ month: label, rate: 100 - price, price });
      }
      
      curD.setUTCMonth(curD.getUTCMonth() + 1);
    }
    if (curve.length > 0) {
      history.push([date, curve]);
    }
  }
  
  // Sort history chronologically just in case
  history.sort((a,b) => a[0].localeCompare(b[0]));
  
  if (!fs.existsSync(VALUATION_DIR)) fs.mkdirSync(VALUATION_DIR, {recursive:true});
  fs.writeFileSync(path.join(VALUATION_DIR, 'FED_PATH_HISTORY.json'), JSON.stringify({
    id: 'FED_PATH_HISTORY',
    updated: new Date().toISOString(),
    values: history
  }));
  
  console.log(`Successfully generated FED_PATH_HISTORY.json with ${history.length} days of curves!`);
}

main().catch(console.error);
