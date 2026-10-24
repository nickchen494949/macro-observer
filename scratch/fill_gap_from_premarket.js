// One-off: fill the missing previous-session bar in data/yahoo/*.json using data/premarket.json
// (prev close from the live snapshot). Same logic as fillPrevCloseGap() in server.js.
const fs = require('fs'), path = require('path');
const pm = JSON.parse(fs.readFileSync('data/premarket.json', 'utf8'));
const safe = id => id.replace(/[^a-zA-Z0-9._=-]/g, '_');
let n = 0;
for (const [sym, it] of Object.entries(pm.items || {})) {
  if (it.kind === 'fut' || it.kind === 'pre' || !it.prev || !it.ts) continue;
  const f = path.join('data/yahoo', safe(sym) + '.json');
  if (!fs.existsSync(f)) continue;
  const j = JSON.parse(fs.readFileSync(f, 'utf8'));
  const s = j.values;
  const today = new Date(it.ts * 1000).toISOString().slice(0, 10);
  let i = s.length - 1;
  while (i >= 0 && s[i][0] >= today) i--;
  if (i < 0) continue;
  const prev = s[i], pv = Array.isArray(prev) ? prev[1] : (prev.close ?? prev.adjClose);
  if (Math.abs(pv / it.prev - 1) < 0.0005) { console.log(sym, 'ok (no gap)'); continue; }
  const d = new Date(today + 'T00:00:00Z');
  do { d.setUTCDate(d.getUTCDate() - 1); } while (d.getUTCDay() === 0 || d.getUTCDay() === 6);
  const pd = d.toISOString().slice(0, 10);
  const prevDate = Array.isArray(prev) ? prev[0] : prev.date;
  if (pd <= prevDate) { console.log(sym, 'mismatch but no calendar gap — left alone', prevDate, pv, it.prev); continue; }
  s.splice(i + 1, 0, [pd, +(+it.prev).toFixed(4)]);
  j.updated = new Date().toISOString();
  fs.writeFileSync(f, JSON.stringify(j));
  const csv = path.join('csv/yahoo', safe(sym) + '.csv');
  fs.writeFileSync(csv, 'Date,Value\n' + s.map(v => `${v[0]},${v[1]}`).join('\n') + '\n');
  console.log(sym, 'filled', pd, it.prev, '(prior bar', prevDate, pv + ')');
  n++;
}
console.log('filled', n);
