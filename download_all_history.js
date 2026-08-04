'use strict';
const https = require('https');
const fs = require('fs');
const path = require('path');

const FRED_KEY = '5e8696731dbd4002c9043ea10e8fbc5f';
const DATA_DIR = path.join(__dirname, 'data');
const FRED_DIR = path.join(DATA_DIR, 'fred');
const YAHOO_DIR = path.join(DATA_DIR, 'yahoo');
const CSV_DIR = path.join(__dirname, 'csv');
const CSV_FRED = path.join(CSV_DIR, 'fred');
const CSV_YAHOO = path.join(CSV_DIR, 'yahoo');

[FRED_DIR, YAHOO_DIR, CSV_FRED, CSV_YAHOO].forEach(d => fs.mkdirSync(d, { recursive: true }));

// ============================================
// ALL INDICATORS
// ============================================
const FRED_SERIES = [
  'DFII10','BAMLH0A0HYM2','BAMLC0A0CM','SOFR','IORB',
  'DFF','DGS3MO','DGS1','DGS2','DGS3','DGS5','DGS7','DGS10','DGS20','DGS30','T10Y3M',
  'DCOILWTICO','DHHNGSP',
  'SP500','DJIA','NASDAQCOM',
];

const YAHOO_SYMBOLS = [
  'ZQ=F','CL=F','NG=F','GC=F','HG=F','ZW=F','ZS=F','BDRY',
  '^DJI','^GSPC','^IXIC','^RUT',
  'XLK','SOXX','IGV','MAGS','XLV','IBB',
  'XLY','XRT','XLP','XLE','ICLN','XLB','GDX','XLRE',
];

const safeName = s => s.replace(/[^a-zA-Z0-9._=-]/g, '_');

// ============================================
// HTTP HELPER
// ============================================
function httpsGet(url, headers = {}) {
  return new Promise((resolve, reject) => {
    https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36', ...headers },
      timeout: 30000,
    }, res => {
      const chunks = [];
      res.on('data', d => chunks.push(d));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString() }));
    }).on('error', reject).on('timeout', function () { this.destroy(); reject(new Error('timeout')); });
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function saveData(type, id, values) {
  const dir = type === 'fred' ? FRED_DIR : YAHOO_DIR;
  const csvDir = type === 'fred' ? CSV_FRED : CSV_YAHOO;
  const name = safeName(id);
  
  fs.writeFileSync(path.join(dir, name + '.json'), JSON.stringify({
    id, updated: new Date().toISOString(), values,
  }));
  
  fs.writeFileSync(path.join(csvDir, name + '.csv'),
    'Date,Value\n' + values.map(v => v[0] + ',' + v[1]).join('\n') + '\n');
}

// ============================================
// FRED: FULL HISTORY (from 1900-01-01)
// ============================================
async function downloadFred(seriesId) {
  // FRED API allows observation_start=1776-07-04 if you want, but 1900 covers everything
  const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&observation_start=1900-01-01&sort_order=asc`;
  const r = await httpsGet(url);
  if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
  const d = JSON.parse(r.body);
  if (d.error_message) throw new Error(d.error_message);
  return (d.observations || []).filter(o => o.value !== '.').map(o => [o.date, parseFloat(o.value)]);
}

// ============================================
// YAHOO: MAX DAILY HISTORY (using epoch timestamps)
// ============================================
async function downloadYahoo(symbol) {
  const now = Math.floor(Date.now() / 1000);
  // period1=0 means Jan 1, 1970; Yahoo returns all available daily data
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?period1=0&period2=${now}&interval=1d`;
  const r = await httpsGet(url);
  if (r.status === 429) throw new Error('RATE_LIMITED');
  if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
  
  const ch = JSON.parse(r.body).chart?.result?.[0];
  if (!ch) throw new Error('No chart data');
  
  const ts = ch.timestamp || [];
  const cl = ch.indicators?.quote?.[0]?.close || [];
  const values = [];
  for (let i = 0; i < ts.length; i++) {
    if (cl[i] != null && isFinite(cl[i])) {
      values.push([new Date(ts[i] * 1000).toISOString().split('T')[0], +cl[i].toFixed(4)]);
    }
  }
  return values;
}

// ============================================
// MAIN
// ============================================
async function main() {
  console.log('');
  console.log('  ╔═══════════════════════════════════════════════╗');
  console.log('  ║  📥 Download ALL Historical Data              ║');
  console.log('  ║  FRED: full history from inception            ║');
  console.log('  ║  Yahoo: max available range                   ║');
  console.log('  ╚═══════════════════════════════════════════════╝');
  console.log('');

  // --- FRED ---
  console.log(`  📊 FRED: ${FRED_SERIES.length} series (full history)...`);
  let fredOk = 0, fredFail = 0;
  for (const id of FRED_SERIES) {
    try {
      const vals = await downloadFred(id);
      saveData('fred', id, vals);
      const first = vals[0]?.[0] || '?';
      const last = vals[vals.length - 1]?.[0] || '?';
      console.log(`  ✅ ${id}: ${vals.length} obs (${first} → ${last})`);
      fredOk++;
    } catch (e) {
      console.log(`  ❌ ${id}: ${e.message}`);
      fredFail++;
    }
    await sleep(300); // FRED rate limit: 120 req/min, so 300ms is safe
  }

  console.log('');
  console.log(`  📊 FRED done: ${fredOk} ok, ${fredFail} failed`);
  console.log('');

  // --- YAHOO ---
  console.log(`  📈 Yahoo: ${YAHOO_SYMBOLS.length} symbols (max range)...`);
  let yahooOk = 0, yahooFail = 0;
  for (const sym of YAHOO_SYMBOLS) {
    try {
      const vals = await downloadYahoo(sym);
      if (vals.length === 0) throw new Error('empty');
      saveData('yahoo', sym, vals);
      const first = vals[0]?.[0] || '?';
      const last = vals[vals.length - 1]?.[0] || '?';
      console.log(`  ✅ ${sym}: ${vals.length} pts (${first} → ${last})`);
      yahooOk++;
    } catch (e) {
      if (e.message === 'RATE_LIMITED') {
        console.log(`  🔴 ${sym}: rate limited — stopping Yahoo downloads`);
        yahooFail++;
        break;
      }
      console.log(`  ❌ ${sym}: ${e.message}`);
      yahooFail++;
    }
    await sleep(4000); // 4s between Yahoo requests to avoid 429
  }

  console.log('');
  console.log(`  📈 Yahoo done: ${yahooOk} ok, ${yahooFail} failed`);
  console.log('');

  // --- Summary ---
  console.log('  ═══════════════════════════════════════');
  console.log(`  Total CSV files: ${fredOk + yahooOk}`);
  console.log(`  FRED: ${fredOk}/${FRED_SERIES.length}  |  Yahoo: ${yahooOk}/${YAHOO_SYMBOLS.length}`);
  console.log(`  Saved to: csv/fred/ and csv/yahoo/`);
  console.log('  ═══════════════════════════════════════');
  console.log('');
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
