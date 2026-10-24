'use strict';
const http = require('http');

const targets = new Set([
  'S&P 500', 'Nasdaq', 'Russell 2000', 'SOXX 半导体',
  'CL Oil 原油', 'NG Gas 天然气', 'GC Gold 黄金'
]);

function getJson(path) {
  return new Promise((resolve, reject) => {
    http.get({ hostname:'127.0.0.1', port:8765, path, timeout:15000 }, res => {
      let body='';
      res.on('data', c => body += c);
      res.on('end', () => {
        try { resolve({ status:res.statusCode, data:JSON.parse(body) }); }
        catch(e) { reject(new Error('parse failed: ' + e.message + ' body=' + body.slice(0,300))); }
      });
    }).on('error', reject).on('timeout', function(){ this.destroy(); reject(new Error('timeout')); });
  });
}

function walk(x, found) {
  if (!x) return;
  if (Array.isArray(x)) { for (const v of x) walk(v, found); return; }
  if (typeof x !== 'object') return;
  if (typeof x.label === 'string' && targets.has(x.label)) {
    found[x.label] = {
      current: x.current ?? null,
      zscore: x.zscore ?? null,
      zscoreAll: x.zscoreAll ?? null,
      changes: x.changes ?? null
    };
  }
  for (const v of Object.values(x)) walk(v, found);
}

(async () => {
  const r = await getJson('/api/data');
  const found = {};
  walk(r.data, found);
  console.log(JSON.stringify({ http:r.status, found }, null, 2));
  if (r.status !== 200) process.exit(2);
  const missing = [...targets].filter(t => !found[t]);
  if (missing.length) {
    console.error('Missing target rows: ' + missing.join(', '));
    process.exit(3);
  }
  const broken = Object.entries(found).filter(([_, v]) => {
    const ch = v.changes || {};
    return v.current == null || (ch['1d'] == null && ch['1w'] == null && ch['1m'] == null);
  });
  if (broken.length) {
    console.error('Still broken: ' + broken.map(([k]) => k).join(', '));
    process.exit(4);
  }
  console.log('PASS: representative Yahoo dashboard rows have numeric history/change metrics again.');
})().catch(e => { console.error(e.stack || e.message); process.exit(1); });
