const fs = require('fs');
const crypto = require('crypto');
const { execSync } = require('child_process');

console.log('Running builder twice...');
execSync('node backtest/build_historical_snapshots.js 2026-08-01 2026-08-05 out1.json');
execSync('node backtest/build_historical_snapshots.js 2026-08-01 2026-08-05 out2.json');

const o1 = JSON.parse(fs.readFileSync('out1.json', 'utf8'));
const o2 = JSON.parse(fs.readFileSync('out2.json', 'utf8'));

let diffs = 0;
for (const k in o1) {
  if (o1[k].meta) { delete o1[k].meta.timeToRunMs; delete o1[k].snapshotGeneratedAt; }
  if (o2[k].meta) { delete o2[k].meta.timeToRunMs; delete o2[k].snapshotGeneratedAt; }
  const h1 = crypto.createHash('sha256').update(JSON.stringify(o1[k])).digest('hex');
  const h2 = crypto.createHash('sha256').update(JSON.stringify(o2[k])).digest('hex');
  if (h1 !== h2) diffs++;
}
assert(diffs === 0, 'Determinism failed!');
console.log('Determinism OK');
