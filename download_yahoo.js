'use strict';
// Yahoo downloader — batches of 5 with 30s cooldown between batches
// NO RETRIES — if 429 hit, just skip and let next run handle it
const https = require('https');
const fs = require('fs');
const path = require('path');

const DD = path.join(__dirname, 'data', 'yahoo');
const CD = path.join(__dirname, 'csv', 'yahoo');
[DD, CD].forEach(d => fs.mkdirSync(d, { recursive: true }));

const SYMBOLS = [
  'ZQ=F','CL=F','NG=F','GC=F','HG=F','ZW=F','ZS=F','BDRY',
  '^DJI','^GSPC','^IXIC','^RUT',
  'XLK','SOXX','IGV','MAGS',
  'XLV','IBB','XLY','XRT','XLP','XLE','ICLN','XLB','GDX','XLRE'
];

const BATCH_SIZE = 4;        // symbols per batch
const INTRA_DELAY = 3000;    // 3s between requests in a batch
const BATCH_DELAY = 45000;   // 45s cooldown between batches

function safeName(s) { return s.replace(/[^a-zA-Z0-9._=-]/g, '_'); }
const sleep = ms => new Promise(r => setTimeout(r, ms));

function get(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' },
      timeout: 30000,
    }, res => {
      const c = []; res.on('data', d => c.push(d));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(c).toString() }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function parse(body) {
  const d = JSON.parse(body);
  const ch = d.chart?.result?.[0];
  if (!ch) return null;
  const ts = ch.timestamp || [], cl = ch.indicators?.quote?.[0]?.close || [];
  const vals = [];
  for (let i = 0; i < ts.length; i++) {
    if (cl[i] != null && isFinite(cl[i]))
      vals.push([new Date(ts[i] * 1000).toISOString().split('T')[0], +cl[i].toFixed(4)]);
  }
  return vals.length > 0 ? vals : null;
}

function save(sym, vals) {
  const n = safeName(sym);
  fs.writeFileSync(path.join(DD, n + '.json'), JSON.stringify({ id: sym, updated: new Date().toISOString(), values: vals }));
  fs.writeFileSync(path.join(CD, n + '.csv'), 'Date,Value\n' + vals.map(v => v[0] + ',' + v[1]).join('\n') + '\n');
}

async function main() {
  // Filter to only symbols we don't have yet
  const needed = SYMBOLS.filter(sym => {
    const fp = path.join(DD, safeName(sym) + '.json');
    if (!fs.existsSync(fp)) return true;
    try { const d = JSON.parse(fs.readFileSync(fp)); return !d.values || d.values.length < 100; }
    catch { return true; }
  });

  if (needed.length === 0) {
    console.log('✅ All ' + SYMBOLS.length + ' symbols already cached!');
    return;
  }

  console.log(`\n📈 Need to download ${needed.length} symbols (${SYMBOLS.length - needed.length} cached)\n`);

  // Split into batches
  const batches = [];
  for (let i = 0; i < needed.length; i += BATCH_SIZE) {
    batches.push(needed.slice(i, i + BATCH_SIZE));
  }

  let ok = 0, fail = 0, rateLimit = false;

  for (let b = 0; b < batches.length; b++) {
    const batch = batches[b];
    console.log(`  📦 Batch ${b + 1}/${batches.length} (${batch.join(', ')})`);

    for (const sym of batch) {
      const url = 'https://query2.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(sym) + '?range=5y&interval=1d';
      try {
        const r = await get(url);
        if (r.status === 429) {
          console.log(`     ${sym}: 🔴 rate-limited — stopping batch`);
          fail++;
          rateLimit = true;
          break;
        }
        const vals = parse(r.body);
        if (vals) {
          save(sym, vals);
          console.log(`     ${sym}: ✅ ${vals.length} pts`);
          ok++;
        } else {
          console.log(`     ${sym}: ❌ no data`);
          fail++;
        }
      } catch (e) {
        console.log(`     ${sym}: ❌ ${e.message}`);
        fail++;
      }
      await sleep(INTRA_DELAY);
    }

    if (rateLimit) {
      console.log(`\n  ⚠️  Rate-limited. Got ${ok} symbols. Run again later for the rest.\n`);
      break;
    }

    // Cooldown between batches (skip after last batch)
    if (b < batches.length - 1) {
      console.log(`     ⏸️  Cooling down ${BATCH_DELAY / 1000}s...\n`);
      await sleep(BATCH_DELAY);
    }
  }

  const cached = SYMBOLS.length - needed.length;
  console.log(`\n✅ Results: ${ok + cached} total available (${ok} new + ${cached} cached), ${fail} failed\n`);
}

main();
