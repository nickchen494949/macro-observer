// One-off data repair (run with the server STOPPED):
//  1) drop today's unfinished bars (same rule as dropUnfinishedBar in server.js)
//  2) VIX: overwrite with official CBOE closes (scratch/VIX_History.csv)
//  3) 24h instruments (futures/FX): re-fetch 1y daily closes via fetch_yahoo.py and overwrite overlapping dates
//     (bars captured mid-session by earlier daily runs were never revised)
const fs = require('fs'), path = require('path');
const { execFileSync } = require('child_process');
const safe = id => id.replace(/[^a-zA-Z0-9._=-]/g, '_');
const fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
const p = fmt.formatToParts(new Date()), g = t => p.find(x => x.type === t).value;
const et = { date: `${g('year')}-${g('month')}-${g('day')}`, min: +g('hour') * 60 + +g('minute') };
const CUT = { '^N225': 180, '000001.SS': 240, '^STOXX': 720 };
const load = sym => { const f = path.join('data/yahoo', safe(sym) + '.json'); return fs.existsSync(f) ? [f, JSON.parse(fs.readFileSync(f, 'utf8'))] : [f, null]; };
const save = (f, sym, j) => {
  j.updated = new Date().toISOString();
  fs.writeFileSync(f, JSON.stringify(j));
  fs.writeFileSync(path.join('csv/yahoo', safe(sym) + '.csv'), 'Date,Value\n' + j.values.map(v => `${v[0]},${Array.isArray(v) ? v[1] : v.close}`).join('\n') + '\n');
};

// 1) unfinished bars
for (const fn of fs.readdirSync('data/yahoo').filter(f => f.endsWith('.json'))) {
  const f = path.join('data/yahoo', fn), j = JSON.parse(fs.readFileSync(f, 'utf8'));
  const sym = j.id || j.symbol; if (!sym || !Array.isArray(j.values)) continue;
  const cut = CUT[sym] ?? 18 * 60, before = j.values.length;
  j.values = j.values.filter(v => { const d = Array.isArray(v) ? v[0] : v.date; return d < et.date || (d === et.date && et.min >= cut); });
  if (j.values.length !== before) { save(f, sym, j); console.log('dropped unfinished', sym, before - j.values.length); }
}

// 2) VIX from CBOE
{
  const cb = {};
  for (const line of fs.readFileSync('scratch/VIX_History.csv', 'utf8').trim().split(/\r?\n/).slice(1)) {
    const [d, , , , c] = line.split(','); const [m, dd, y] = d.split('/');
    cb[`${y}-${m.padStart(2, '0')}-${dd.padStart(2, '0')}`] = +(+c).toFixed(2);
  }
  const [f, j] = load('^VIX'); let n = 0;
  for (const v of j.values) if (cb[v[0]] != null && Math.abs(v[1] - cb[v[0]]) > 0.005) { console.log('VIX fix', v[0], v[1], '->', cb[v[0]]); v[1] = cb[v[0]]; n++; }
  if (n) save(f, '^VIX', j);
}

// 3) futures / FX
const sleep = ms => Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
const syms = ['CL=F', 'NG=F', 'GC=F', 'HG=F', 'ZW=F', 'ZS=F', 'DX-Y.NYB', 'JPY=X'];
for (let k = 0; k < syms.length; k++) {
  const sym = syms[k];
  try {
    const out = JSON.parse(execFileSync('python3', ['fetch_yahoo.py', sym, '1y'], { timeout: 30000 }).toString());
    if (!out.ok) { console.log(sym, 'fetch failed', out.error); if (String(out.error).includes('429')) break; continue; }
    const fresh = new Map(out.data.filter(v => v[0] < et.date).map(v => [v[0], v[1]]));
    const [f, j] = load(sym); let n = 0, maxd = 0, worst = null;
    for (const v of j.values) {
      if (!fresh.has(v[0])) continue;
      const nv = fresh.get(v[0]);
      if (Math.abs(nv / v[1] - 1) > 0.0005) { const d = Math.abs(nv / v[1] - 1); if (d > maxd) { maxd = d; worst = [v[0], v[1], nv]; } v[1] = nv; n++; }
    }
    if (n) save(f, sym, j);
    console.log(sym, 'revised', n, 'bars; worst', worst, (maxd * 100).toFixed(2) + '%');
  } catch (e) { console.log(sym, 'error', e.message); }
  if (k < syms.length - 1) sleep(5000 + Math.random() * 5000);
}
console.log('done');
