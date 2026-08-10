const fs = require('fs');
const path = require('path');
const http = require('http');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const envPath = path.join(ROOT, '.env');
const yahooDir = path.join(ROOT, 'data', 'yahoo');
const fredDir = path.join(ROOT, 'data', 'fred');

function parseEnv() {
  const out = {};
  if (!fs.existsSync(envPath)) return out;
  for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
    if (!line || line.trim().startsWith('#')) continue;
    const i = line.indexOf('=');
    if (i > 0) out[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return out;
}

function readSeries(dir, sym) {
  const safe = sym.replace(/[^a-zA-Z0-9._=-]/g, '_');
  const p = path.join(dir, safe + '.json');
  if (!fs.existsSync(p)) return { exists:false };
  try {
    const d = JSON.parse(fs.readFileSync(p, 'utf8'));
    const vals = Array.isArray(d.values) ? d.values : [];
    const dateOf = v => Array.isArray(v) ? v[0] : v && v.date;
    return {
      exists:true,
      count:vals.length,
      first: vals.length ? dateOf(vals[0]) : null,
      last: vals.length ? dateOf(vals[vals.length - 1]) : null,
      updated: d.updated || null,
      mtime: fs.statSync(p).mtime.toISOString(),
    };
  } catch (e) {
    return { exists:true, error:e.message };
  }
}

function getJson(url) {
  return new Promise(resolve => {
    const req = http.get(url, { timeout:5000 }, res => {
      let s='';
      res.on('data', c => s += c);
      res.on('end', () => {
        try { resolve({status:res.statusCode, body:JSON.parse(s)}); }
        catch { resolve({status:res.statusCode, raw:s.slice(0,500)}); }
      });
    });
    req.on('error', e => resolve({error:e.message}));
    req.on('timeout', () => { req.destroy(); resolve({error:'timeout'}); });
  });
}

(async () => {
  const env = parseEnv();
  let proc = '';
  try { proc = execFileSync('pgrep', ['-fl', 'download_all_history.js'], {encoding:'utf8'}).trim(); }
  catch { proc = ''; }

  const symbols = ['^GSPC','^IXIC','^RUT','^VIX','SOXX','XLK','IGV','MAGS','XLV','IBB','XLY','XRT','XLP','XLE','ICLN','XLB','GDX','XLRE','XLF','KRE','KBE','CL=F','NG=F','GC=F','HG=F','ZW=F','ZS=F'];
  const yahoo = Object.fromEntries(symbols.map(s => [s, readSeries(yahooDir, s)]));
  const shortYahoo = Object.entries(yahoo).filter(([,v]) => !v.exists || v.error || (v.count || 0) < 500).map(([s,v]) => ({symbol:s, ...v}));
  const fullYahooCount = Object.values(yahoo).filter(v => v.exists && !v.error && (v.count || 0) >= 500).length;

  const fred = {
    DGS10: readSeries(fredDir, 'DGS10'),
    PCEPILFE: readSeries(fredDir, 'PCEPILFE'),
    PAYEMS: readSeries(fredDir, 'PAYEMS'),
  };

  const health = await getJson('http://127.0.0.1:8765/health');
  const data = await getJson('http://127.0.0.1:8765/api/data');

  const result = {
    checkedAt: new Date().toISOString(),
    env: {
      envExists: fs.existsSync(envPath),
      fredKeyConfigured: typeof env.FRED_API_KEY === 'string' && env.FRED_API_KEY.length > 10,
      fredKeyLength: env.FRED_API_KEY ? env.FRED_API_KEY.length : 0,
      adminTokenConfigured: typeof env.LOCAL_ADMIN_TOKEN === 'string' && env.LOCAL_ADMIN_TOKEN.length > 0,
      envMtime: fs.existsSync(envPath) ? fs.statSync(envPath).mtime.toISOString() : null,
    },
    downloadAllHistoryRunning: !!proc,
    downloadProcess: proc ? proc.replace(/\s+/g,' ').slice(0,250) : null,
    health,
    yahooSummary: {
      checked: symbols.length,
      fullHistoryCount: fullYahooCount,
      shortOrMissingCount: shortYahoo.length,
      shortOrMissing: shortYahoo,
      representative: Object.fromEntries(['XLK','IGV','MAGS','XLF','KRE','^GSPC','SOXX','CL=F','GC=F'].map(s => [s,yahoo[s]])),
    },
    fred,
    apiDataHttp: data.status || null,
  };
  console.log(JSON.stringify(result, null, 2));
})();
