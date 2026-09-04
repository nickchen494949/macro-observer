'use strict';
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const syms = ['^GSPC','^IXIC','^RUT'];
const safe = s => s.replace(/[^a-zA-Z0-9._=-]/g, '_');
const out = {};
for (const sym of syms) {
  const p = path.join(root,'data','yahoo',safe(sym)+'.json');
  if (!fs.existsSync(p)) { out[sym]={exists:false,path:p}; continue; }
  const d = JSON.parse(fs.readFileSync(p,'utf8'));
  const vals = d.values || [];
  const sample = row => {
    if (Array.isArray(row)) return {kind:'array', date:row[0], valueType:typeof row[1], value:row[1]};
    if (row && typeof row==='object') return {kind:'object', date:row.date, close:row.close, adjClose:row.adjClose, status:row.status, validation:row.validation};
    return {kind:typeof row, value:row};
  };
  out[sym] = {exists:true, id:d.id, symbol:d.symbol, schemaVersion:d.schemaVersion, count:vals.length, first:sample(vals[0]), last:sample(vals[vals.length-1]), prev:sample(vals[vals.length-2])};
}
console.log(JSON.stringify(out,null,2));
