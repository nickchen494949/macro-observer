'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const mainDir = path.join(root, 'data', 'yahoo');
const validatedDir = path.join(root, 'data', 'yahoo_validated');
const CTA_ADJ = new Set(['SPY','QQQ','IWM','IEF','USO','GLD']);
fs.mkdirSync(validatedDir, { recursive: true });

function extract(symbol, row) {
  let date = null;
  let raw = null;
  let rich = false;
  if (Array.isArray(row)) {
    date = row[0];
    raw = row[1];
    rich = !!(raw && typeof raw === 'object');
  } else if (row && typeof row === 'object') {
    date = row.date;
    raw = row;
    rich = true;
  }
  let value = null;
  if (Number.isFinite(raw)) value = raw;
  else if (raw && typeof raw === 'object') {
    if (CTA_ADJ.has(symbol) && Number.isFinite(raw.adjClose)) value = raw.adjClose;
    else if (Number.isFinite(raw.close)) value = raw.close;
    else if (Number.isFinite(raw.adjClose)) value = raw.adjClose;
  }
  return { date, value, rich };
}

const report = [];
for (const file of fs.readdirSync(mainDir).filter(f => f.endsWith('.json'))) {
  const p = path.join(mainDir, file);
  let d;
  try { d = JSON.parse(fs.readFileSync(p, 'utf8')); } catch (_) { continue; }
  if (!Array.isArray(d.values)) continue;
  const symbol = d.id || d.symbol;
  if (!symbol) continue;
  let hadRich = false;
  const values = [];
  for (const row of d.values) {
    const x = extract(symbol, row);
    if (x.rich) hadRich = true;
    if (typeof x.date === 'string' && Number.isFinite(x.value)) values.push([x.date, x.value]);
  }
  if (!hadRich) continue;
  // Preserve the rich source exactly before restoring the main dashboard cache.
  fs.writeFileSync(path.join(validatedDir, file), JSON.stringify(d));
  fs.writeFileSync(p, JSON.stringify({
    id: symbol,
    updated: d.updated || d.downloadedAt || new Date().toISOString(),
    values
  }));
  report.push({ symbol, before:d.values.length, after:values.length, field:CTA_ADJ.has(symbol)?'adjClose':'close' });
}

console.log(JSON.stringify({ migrated:report.length, report }, null, 2));
if (!report.length) console.log('No rich/mixed Yahoo caches required migration.');

// Hard fail if representative files are not now numeric.
for (const symbol of ['^GSPC','^IXIC','^RUT','SOXX','CL=F','GC=F']) {
  const file = symbol.replace(/[^a-zA-Z0-9._=-]/g, '_') + '.json';
  const p = path.join(mainDir, file);
  const d = JSON.parse(fs.readFileSync(p,'utf8'));
  if (!Array.isArray(d.values) || d.values.length < 200 || d.values.some(v => !Array.isArray(v) || !Number.isFinite(v[1]))) {
    throw new Error('numeric cache verification failed for ' + symbol);
  }
}

try {
  execFileSync('launchctl', ['kickstart','-k',`gui/${process.getuid()}/com.macro-observer.dashboard`], { stdio:'inherit' });
} catch (e) {
  console.error('Dashboard restart failed:', e.message);
  process.exit(2);
}
console.log('PASS: main Yahoo cache restored to pure numeric series; rich source preserved separately; dashboard restarted.');
