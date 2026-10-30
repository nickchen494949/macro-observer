'use strict';
const fs = require('fs');
const { execFileSync } = require('child_process');
const path = require('path');

const repo = path.resolve(__dirname, '..');
const serverPath = path.join(repo, 'server.js');
let src = fs.readFileSync(serverPath, 'utf8');

const helperAnchor = "function safeName(id) { return id.replace(/[^a-zA-Z0-9._=-]/g, '_'); }\n";
const helperBlock = `${helperAnchor}\n// Compatibility layer: validated Yahoo downloader may store rich OHLC objects,\n// while the main macro dashboard expects numeric [date, value] series.\n// Keep CTA ETF proxies on adjusted close; keep displayed indices/futures on regular close.\nconst CTA_ADJ_CLOSE_SYMBOLS = new Set(CTA_ETF_UPDATE_SYMBOLS);\nfunction yahooNumericValue(symbol, raw) {\n  if (Number.isFinite(raw)) return raw;\n  if (!raw || typeof raw !== 'object') return null;\n  if (CTA_ADJ_CLOSE_SYMBOLS.has(symbol) && Number.isFinite(raw.adjClose)) return raw.adjClose;\n  if (Number.isFinite(raw.close)) return raw.close;\n  if (Number.isFinite(raw.adjClose)) return raw.adjClose;\n  return null;\n}\nfunction normalizeYahooSeries(symbol, values) {\n  if (!Array.isArray(values)) return [];\n  const out = [];\n  for (const row of values) {\n    let date = null;\n    let raw = null;\n    if (Array.isArray(row)) {\n      date = row[0];\n      raw = row[1];\n    } else if (row && typeof row === 'object') {\n      date = row.date;\n      raw = row;\n    }\n    const value = yahooNumericValue(symbol, raw);\n    if (typeof date === 'string' && Number.isFinite(value)) out.push([date, value]);\n  }\n  return out;\n}\n`;

if (!src.includes('function normalizeYahooSeries(symbol, values)')) {
  if (!src.includes(helperAnchor)) throw new Error('helper anchor not found');
  src = src.replace(helperAnchor, helperBlock);
}

const oldLoader = `        const d = JSON.parse(fs.readFileSync(path.join(dir, f)));\n        let vals = d.values;\n        if (!vals) return;\n        \n        // Normalize array of objects to [date, value_object] like in the snapshot builder\n        if (vals.length > 0 && !Array.isArray(vals[0])) {\n          vals = vals.map(v => [v.date, v]);\n        }\n        \n        // Clip valuation data to post-1973\n        if (type === 'valuation') vals = vals.filter(v => v[0] >= VALUATION_CUTOFF);\n        if (process.env.TEST_DATE) vals = vals.filter(v => v[0] <= process.env.TEST_DATE);\n        store[type][d.id || d.symbol] = vals;\n`;
const newLoader = `        const d = JSON.parse(fs.readFileSync(path.join(dir, f)));\n        const key = d.id || d.symbol;\n        let vals = d.values;\n        if (!vals || !key) return;\n        \n        // Yahoo may be either legacy numeric rows or validated rich OHLC objects.\n        // Normalize to numbers before exposing the series to the macro dashboard.\n        if (type === 'yahoo') {\n          vals = normalizeYahooSeries(key, vals);\n        } else if (vals.length > 0 && !Array.isArray(vals[0])) {\n          vals = vals.map(v => [v.date, v]);\n        }\n        \n        // Clip valuation data to post-1973\n        if (type === 'valuation') vals = vals.filter(v => v[0] >= VALUATION_CUTOFF);\n        if (process.env.TEST_DATE) vals = vals.filter(v => v[0] <= process.env.TEST_DATE);\n        store[type][key] = vals;\n`;
if (src.includes(oldLoader)) {
  src = src.replace(oldLoader, newLoader);
} else if (!src.includes("vals = normalizeYahooSeries(key, vals);")) {
  throw new Error('loadAllFromDisk block not found');
}

const oldReload = `        const d = JSON.parse(fs.readFileSync(path.join(YAHOO_DIR, f)));\n        const key = d.id || d.symbol;\n        if (key && (!store.yahoo[key] || d.values.length > store.yahoo[key].length)) {\n          const arr = [];\n          for (const v of d.values) {\n            arr.push(Array.isArray(v) ? v : [v.date, v]);\n          }\n          store.yahoo[key] = arr;\n        }\n`;
const newReload = `        const d = JSON.parse(fs.readFileSync(path.join(YAHOO_DIR, f)));\n        const key = d.id || d.symbol;\n        if (key && Array.isArray(d.values) && (!store.yahoo[key] || d.values.length > store.yahoo[key].length)) {\n          store.yahoo[key] = normalizeYahooSeries(key, d.values);\n        }\n`;
if (src.includes(oldReload)) {
  src = src.replace(oldReload, newReload);
} else if (!src.includes("store.yahoo[key] = normalizeYahooSeries(key, d.values);")) {
  throw new Error('smartUpdate Yahoo reload block not found');
}

fs.writeFileSync(serverPath, src);
execFileSync('node', ['--check', 'server.js'], { cwd: repo, stdio: 'inherit' });

// Commit only the intended server compatibility change.
execFileSync('git', ['add', 'server.js'], { cwd: repo, stdio: 'inherit' });
const staged = execFileSync('git', ['diff', '--cached', '--name-only'], { cwd: repo, encoding: 'utf8' }).trim().split(/\n+/).filter(Boolean);
if (staged.length !== 1 || staged[0] !== 'server.js') throw new Error('unexpected staged files: ' + staged.join(', '));
try {
  execFileSync('git', ['commit', '-m', 'Restore numeric Yahoo compatibility for macro dashboard'], { cwd: repo, stdio: 'inherit' });
  execFileSync('git', ['push', 'origin', 'agent/phase4-composite-validation'], { cwd: repo, stdio: 'inherit' });
} catch (e) {
  const status = execFileSync('git', ['status', '--porcelain'], { cwd: repo, encoding: 'utf8' }).trim();
  if (status) throw e;
}

// Restart managed dashboard so disk data is reloaded through the compatibility layer.
try {
  execFileSync('launchctl', ['kickstart', '-k', `gui/${process.getuid()}/com.macro-observer.dashboard`], { stdio: 'ignore' });
} catch (_) {}

console.log('PASS: Yahoo rich-object compatibility applied; dashboard restart requested.');
