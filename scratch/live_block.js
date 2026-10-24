// ============================================
// LIVE PRICES — fully automatic (see README "Live column")
// Yahoo via Python only. Request budget per NYSE trading day ≈ 200:
//   pre-market 04:00–09:30 ET : index futures via 1 spark request every 15 min
//                               + ETF pre-market quotes (1 request each, 5–10s apart) once per hour
//   regular   09:30–16:05 ET  : all ETFs + indices via spark (2 requests) every 10 min
//   after close 16:05–20:00   : one final spark run (closing move)
// Shares the isUpdating lock with the daily batch; an HTTP 429 pauses everything for 12h.
// This NEVER writes today's bar into the daily store — "1D Δ" stays the last completed session.
// ============================================
const PREMARKET_FILE = path.join(DATA_DIR, 'premarket.json');
const LIVE_BLOCK_MS = 12 * 60 * 60 * 1000; // after an HTTP 429
// Indices have no pre-market quote on Yahoo → approximate with the matching futures.
const PREMARKET_FUTURES = { '^DJI': 'YM=F', '^GSPC': 'ES=F', '^IXIC': 'NQ=F', '^RUT': 'RTY=F' };
const premarket = { session: null, fetchedAt: 0, updating: false, items: {}, blockedUntil: 0, error: null,
                    lastFut: 0, lastPreEtf: 0, lastSpark: 0, closeDoneFor: null };
try {
  const saved = JSON.parse(fs.readFileSync(PREMARKET_FILE, 'utf8'));
  if (saved && saved.session) Object.assign(premarket, saved, { updating: false });
} catch (e) { /* no snapshot yet */ }

function premarketSymbols() {
  const etfs = [], indices = [];
  for (const g of STOCK_GROUPS) for (const i of g.items) {
    if (!i.yahoo) continue;
    (i.yahoo.startsWith('^') ? indices : etfs).push(i.yahoo);
  }
  return { etfs, indices, futures: Object.values(PREMARKET_FUTURES) };
}

// ---- New York clock + NYSE calendar (data/nyse_calendar.json; falls back to weekdays if not covered)
const _etFmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23',
  year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
function etNow() {
  const p = _etFmt.formatToParts(new Date());
  const g = t => p.find(x => x.type === t).value;
  return { date: `${g('year')}-${g('month')}-${g('day')}`, min: +g('hour') * 60 + +g('minute') };
}
let _nyseDays = null;
function nyseDays() {
  if (!_nyseDays) {
    try { _nyseDays = JSON.parse(fs.readFileSync(path.join(DATA_DIR, 'nyse_calendar.json'), 'utf8')); } catch (e) { _nyseDays = []; }
  }
  return _nyseDays;
}
function calendarCovers(d) { const c = nyseDays(); return c.length && d >= c[0] && d <= c[c.length - 1]; }
function isNyseDay(d) {
  if (calendarCovers(d)) return nyseDays().includes(d);
  const wd = new Date(d + 'T00:00:00Z').getUTCDay();
  return wd !== 0 && wd !== 6;
}
function prevNyseDay(today) {
  const d = new Date(today + 'T00:00:00Z');
  for (let k = 0; k < 10; k++) {
    d.setUTCDate(d.getUTCDate() - 1);
    const s = d.toISOString().slice(0, 10);
    if (isNyseDay(s)) return s;
  }
  return null;
}
// Session whose move the live column shows: today from 04:00 ET on a trading day, else the last trading day.
function currentSessionDate() {
  const et = etNow();
  if (isNyseDay(et.date) && et.min >= 240) return et.date;
  return prevNyseDay(et.date);
}

// Yahoo's daily chart sometimes drops a bar (e.g. 2026-10-21 missing for US equities while today's bar exists).
// Then "1D Δ" is computed vs two sessions ago. The live quote carries the true previous close, so use it to
// fill exactly one missing bar: the NYSE trading day before the live session. Never overwrites.
function fillPrevCloseGap(sym, prevClose, sessionDate) {
  const s = store.yahoo[sym];
  if (!Array.isArray(s) || s.length < 2 || !prevClose || !sessionDate) return false;
  const pd = prevNyseDay(sessionDate);
  if (!pd) return false;
  let i = s.length - 1;
  while (i >= 0 && s[i][0] >= sessionDate) i--;
  if (i < 0 || s[i][0] >= pd) return false; // bar for the previous session already stored
  s.splice(i + 1, 0, [pd, +(+prevClose).toFixed(4)]);
  saveFile('yahoo', sym, s);
  console.log(`  🩹 ${sym}: filled missing ${pd} close ${prevClose} from live quote`);
  return true;
}

function runPy(script, arg, timeout) {
  return new Promise((resolve, reject) => {
    execFile('python3', [path.join(__dirname, script), arg], { timeout }, (err, stdout, stderr) => {
      if (err) return reject(new Error(err.message || stderr));
      try {
        const r = JSON.parse(stdout.trim());
        if (!r.ok) return reject(new Error(r.error && r.error.includes('429') ? 'RATE_LIMITED' : (r.error || 'unknown')));
        resolve(r);
      } catch (e) { reject(new Error('parse: ' + e.message)); }
    });
  });
}
const fetchYahooLive = sym => runPy('fetch_yahoo_live.py', sym, 25000);
async function fetchYahooSpark(syms) {
  const out = {};
  for (let k = 0; k < syms.length; k += 20) {
    const r = await runPy('fetch_yahoo_spark.py', syms.slice(k, k + 20).join(','), 30000);
    Object.assign(out, r.data || {});
    if (k + 20 < syms.length) await sleep(5000 + Math.random() * 5000);
  }
  return out;
}

function premarketStatus() {
  const active = !!premarket.session && premarket.session === currentSessionDate();
  return {
    updating: premarket.updating, error: premarket.error, fetchedAt: premarket.fetchedAt,
    session: premarket.session, active, blockedUntil: premarket.blockedUntil,
    items: active ? premarket.items : {},
  };
}

function saveLive() {
  const { updating, ...rest } = premarket;
  fs.writeFileSync(PREMARKET_FILE, JSON.stringify(rest));
}

const pct = (p, prev) => +((p / prev - 1) * 100).toFixed(2);

async function liveTick() {
  if (isUpdating || premarket.updating) return;
  if (Date.now() < premarket.blockedUntil) return;
  const et = etNow();
  if (!isNyseDay(et.date)) return;
  const m = et.min, now = Date.now();
  const PRE = m >= 240 && m < 570, REG = m >= 570 && m < 965, AFTER = m >= 965 && m < 1200;
  const dueFut = PRE && now - premarket.lastFut >= 15 * 60000 - 30000;
  const duePreEtf = PRE && m >= 245 && now - premarket.lastPreEtf >= 60 * 60000 - 30000;
  const dueSpark = REG && now - premarket.lastSpark >= 10 * 60000 - 30000;
  const dueClose = AFTER && premarket.closeDoneFor !== et.date;
  if (!dueFut && !duePreEtf && !dueSpark && !dueClose) return;

  isUpdating = true; premarket.updating = true;
  const { etfs, indices, futures } = premarketSymbols();
  if (premarket.session !== et.date) { premarket.session = et.date; premarket.items = {}; premarket.closeDoneFor = null; }
  const items = premarket.items;
  try {
    if (dueSpark || dueClose) {
      const kind = dueClose ? 'close' : 'regular';
      const data = await fetchYahooSpark([...etfs, ...indices]);
      for (const [sym, r] of Object.entries(data)) {
        items[sym] = { price: r.price, prev: r.prev, pct: pct(r.price, r.prev), ts: r.ts, kind };
        try { fillPrevCloseGap(sym, r.prev, et.date); } catch (e) { console.log(`  ⚠️  gap-fill ${sym}: ${e.message}`); }
      }
      premarket.lastSpark = now;
      if (dueClose) premarket.closeDoneFor = et.date;
    }
    if (dueFut) {
      const data = await fetchYahooSpark(futures);
      for (const [idx, fut] of Object.entries(PREMARKET_FUTURES)) {
        const r = data[fut];
        if (r) items[idx] = { price: r.price, prev: r.prev, pct: pct(r.price, r.prev), ts: r.ts, kind: 'fut', proxy: fut };
      }
      premarket.lastFut = now;
    }
    if (duePreEtf) {
      let fails = 0;
      for (const sym of etfs) {
        try {
          const r = await fetchYahooLive(sym);
          fails = 0;
          if (r.session === 'pre' && r.prev_close && r.price) {
            items[sym] = { price: r.price, prev: r.prev_close, pct: pct(r.price, r.prev_close), ts: r.price_ts, kind: 'pre' };
          }
        } catch (e) {
          if (e.message === 'RATE_LIMITED') throw e;
          if (++fails >= 3) { premarket.error = '盘前连续 3 次失败: ' + e.message; break; }
        }
        await sleep(5000 + Math.random() * 5000);
      }
      premarket.lastPreEtf = now;
    }
    premarket.error = null;
    premarket.fetchedAt = Date.now();
    console.log(`  📡 Live ${dueClose ? 'close' : dueSpark ? 'regular' : 'pre-market'} snapshot: ${Object.keys(items).length} symbols`);
  } catch (e) {
    if (e.message === 'RATE_LIMITED') {
      premarket.blockedUntil = Date.now() + LIVE_BLOCK_MS;
      premarket.error = 'Yahoo 429 — 实时价暂停 12 小时';
    } else {
      premarket.error = e.message;
    }
    console.log(`  ⚠️  Live snapshot: ${premarket.error}`);
  } finally {
    premarket.updating = false; isUpdating = false;
    try { saveLive(); } catch (e) {}
  }
}
