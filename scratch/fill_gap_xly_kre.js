// One-off: fill XLY / KRE 2026-10-21 (skipped by the first pass because their 10-20 close ≈ 10-21 close).
const fs = require('fs');
for (const [sym, v] of [['XLY', 115.53], ['KRE', 70.62]]) {
  const f = `data/yahoo/${sym}.json`, j = JSON.parse(fs.readFileSync(f, 'utf8')), s = j.values;
  if (s.some(r => r[0] === '2026-10-21')) { console.log(sym, 'already has 10-21'); continue; }
  const i = s.findIndex(r => r[0] === '2026-10-22');
  s.splice(i, 0, ['2026-10-21', v]);
  j.updated = new Date().toISOString();
  fs.writeFileSync(f, JSON.stringify(j));
  fs.writeFileSync(`csv/yahoo/${sym}.csv`, 'Date,Value\n' + s.map(r => `${r[0]},${r[1]}`).join('\n') + '\n');
  console.log(sym, 'filled 2026-10-21', v);
}
