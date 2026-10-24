'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const SERVER = path.join(ROOT, 'server.js');
const BRANCH = process.env.MACRO_BRANCH || 'agent/phase4-composite-validation';

function run(exe, args) {
  const r = spawnSync(exe, args, { cwd: ROOT, encoding: 'utf8', timeout: 60000 });
  if (r.status !== 0) {
    throw new Error(`${exe} ${args.join(' ')} failed\n${r.stdout || ''}\n${r.stderr || ''}`);
  }
  return (r.stdout || '').trim();
}

let src = fs.readFileSync(SERVER, 'utf8');
if (src.includes("const CTA_ETF_UPDATE_SYMBOLS = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD'];")) {
  console.log('CTA ETF hourly update symbols already present; no patch needed.');
  process.exit(0);
}

const needle = `function allYahooSymbols() {
  const s = new Set();
  for (const r of RATE_ROWS) { if (r.yahoo) s.add(r.yahoo); }
  for (const r of COMMODITY_ROWS) { if (r.yahoo) s.add(r.yahoo); }
  for (const g of STOCK_GROUPS) { for (const i of g.items) { if (i.yahoo) s.add(i.yahoo); } }
  return [...s];
}`;

const replacement = `const CTA_ETF_UPDATE_SYMBOLS = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD'];

function allYahooSymbols() {
  const s = new Set();
  for (const r of RATE_ROWS) { if (r.yahoo) s.add(r.yahoo); }
  for (const r of COMMODITY_ROWS) { if (r.yahoo) s.add(r.yahoo); }
  for (const g of STOCK_GROUPS) { for (const i of g.items) { if (i.yahoo) s.add(i.yahoo); } }
  // Flow-engine CTA ETF proxies are model inputs even when they are not rendered
  // as standalone dashboard rows. Keep them in the same hourly Yahoo refresh.
  for (const sym of CTA_ETF_UPDATE_SYMBOLS) s.add(sym);
  return [...s];
}`;

if (!src.includes(needle)) {
  throw new Error('Expected allYahooSymbols() block not found exactly; refusing to patch server.js');
}

src = src.replace(needle, replacement);
fs.writeFileSync(SERVER, src);
run(process.execPath, ['--check', SERVER]);
run('git', ['add', '--', 'server.js']);
run('git', ['commit', '-m', 'Keep CTA ETF inputs in Yahoo hourly updates', '--', 'server.js']);
run('git', ['push', 'origin', `HEAD:${BRANCH}`]);

// server.js is managed by launchd; restart so the new symbol list is active now.
const uid = process.getuid ? process.getuid() : Number(process.env.UID);
spawnSync('launchctl', ['kickstart', '-k', `gui/${uid}/com.macro-observer.dashboard`], { cwd: ROOT, encoding: 'utf8', timeout: 30000 });

console.log('PASS: server.js patched, syntax-checked, committed, pushed, and dashboard restart requested.');
