'use strict';

const fs = require('fs');
const path = require('path');
const { buildProductionEngineInputs } = require('../lib/flow_wrappers');

const ROOT = path.resolve(__dirname, '..');
const safeName = s => s.replace(/[^a-zA-Z0-9._=-]/g, '_');

function loadSeries(type, id) {
  const file = path.join(ROOT, 'data', type, safeName(id) + '.json');
  if (!fs.existsSync(file)) return { id, exists: false, values: [] };
  try {
    const parsed = JSON.parse(fs.readFileSync(file, 'utf8'));
    const values = Array.isArray(parsed) ? parsed : (Array.isArray(parsed.values) ? parsed.values : []);
    return { id, exists: true, values, updated: parsed.updated || null };
  } catch (err) {
    return { id, exists: true, values: [], parseError: err.message };
  }
}

const yahooIds = ['^GSPC','^IXIC','^RUT','CL=F','GC=F','NG=F','SPY','QQQ','IWM','IEF','USO','GLD'];
const fredIds = ['DGS10'];

const yahoo = {};
for (const id of yahooIds) yahoo[id] = loadSeries('yahoo', id).values;
const fred = {};
for (const id of fredIds) fred[id] = loadSeries('fred', id).values;

const store = { yahoo, fred, valuation: {} };
const prod = buildProductionEngineInputs(store, new Date());
const marketDate = prod.marketDataAsOf;

function summarize(type, id) {
  const loaded = loadSeries(type, id);
  const vals = loaded.values;
  const eligible = vals.filter(pt => Array.isArray(pt) && typeof pt[0] === 'string' && pt[0] <= marketDate && pt[1] != null);
  const dates = eligible.map(pt => pt[0]).sort();
  return {
    id,
    type,
    exists: loaded.exists,
    count: eligible.length,
    firstDate: dates[0] || null,
    lastDate: dates[dates.length - 1] || null,
    updated: loaded.updated || null,
    has201: eligible.length >= 201,
  };
}

const futures = ['^GSPC','^IXIC','^RUT','DGS10','CL=F','GC=F','NG=F'];
const etfs = ['SPY','QQQ','IWM','IEF','USO','GLD'];

const summaries = {};
for (const id of futures) summaries[id] = summarize(id === 'DGS10' ? 'fred' : 'yahoo', id);
for (const id of etfs) summaries[id] = summarize('yahoo', id);

console.log(JSON.stringify({
  status: 'OK',
  decisionDate: prod.decisionDate,
  marketDataAsOf: marketDate,
  futures: futures.map(id => summaries[id]),
  etfs: etfs.map(id => summaries[id]),
  obviousInsufficient: Object.values(summaries).filter(x => !x.exists || !x.has201 || x.lastDate !== marketDate),
}, null, 2));
