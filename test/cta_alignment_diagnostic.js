'use strict';

const fs = require('fs');
const path = require('path');
const { getFieldForPurpose } = require('../lib/data_validation');
const { buildProductionEngineInputs } = require('../lib/flow_wrappers');

const ROOT = path.resolve(__dirname, '..');
const safeName = s => s.replace(/[^a-zA-Z0-9._=-]/g, '_');

function loadJson(type, id) {
  const file = path.join(ROOT, 'data', type, safeName(id) + '.json');
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function yahooSeries(id) {
  const d = loadJson('yahoo', id);
  if (!d || !Array.isArray(d.values)) return [];
  return d.values.map(v => Array.isArray(v) ? v : [v.date, v]);
}

function fredSeries(id) {
  const d = loadJson('fred', id);
  if (!d || !Array.isArray(d.values)) return [];
  return d.values.map(v => Array.isArray(v) ? v : [v.date, v.value]);
}

const idsYahoo = ['^GSPC','^IXIC','^RUT','CL=F','GC=F','NG=F','SPY','QQQ','IWM','IEF','USO','GLD'];
const yahoo = Object.fromEntries(idsYahoo.map(id => [id, yahooSeries(id)]));
const fred = { DGS10: fredSeries('DGS10') };
const prod = buildProductionEngineInputs({ yahoo, fred, valuation: {} }, new Date());
const marketDate = prod.marketDataAsOf;
const nyseCalendar = JSON.parse(fs.readFileSync(path.join(ROOT, 'data/nyse_calendar.json'), 'utf8'))
  .filter(d => d <= marketDate);

function toValueMap(id, series, purpose) {
  const m = new Map();
  for (const pt of series) {
    if (!Array.isArray(pt) || typeof pt[0] !== 'string') continue;
    let val = pt[1];
    if (purpose && val && typeof val === 'object') val = getFieldForPurpose(id, val, purpose);
    if (val != null && Number.isFinite(Number(val))) m.set(pt[0], Number(val));
  }
  return m;
}

function auditOnCalendar(id, series, calendar, purpose) {
  const map = toValueMap(id, series, purpose);
  const last201 = calendar.slice(-201);
  const missing = last201.filter(d => !map.has(d));
  const observedDates = [...map.keys()].filter(d => d <= marketDate).sort();
  return {
    id,
    observations: observedDates.length,
    firstObserved: observedDates[0] || null,
    lastObserved: observedDates[observedDates.length - 1] || null,
    calendarSessionsChecked: last201.length,
    missingCountLast201: missing.length,
    recentMissingDates: missing.slice(-15),
    sufficientForCurrentRule: last201.length >= 201 && missing.length === 0,
  };
}

const clMap = toValueMap('CL=F', yahoo['CL=F'], 'cta_close');
const futuresCalendar = [...clMap.keys()].filter(d => d <= marketDate).sort();

const futuresAudits = [
  auditOnCalendar('^GSPC', yahoo['^GSPC'], futuresCalendar, 'cta_close'),
  auditOnCalendar('^IXIC', yahoo['^IXIC'], futuresCalendar, 'cta_close'),
  auditOnCalendar('^RUT', yahoo['^RUT'], futuresCalendar, 'cta_close'),
  auditOnCalendar('DGS10', fred.DGS10, futuresCalendar, null),
  auditOnCalendar('CL=F', yahoo['CL=F'], futuresCalendar, 'cta_close'),
  auditOnCalendar('GC=F', yahoo['GC=F'], futuresCalendar, 'cta_close'),
  auditOnCalendar('NG=F', yahoo['NG=F'], futuresCalendar, 'cta_close'),
];

const etfAudits = ['SPY','QQQ','IWM','IEF','USO','GLD'].map(id =>
  auditOnCalendar(id, yahoo[id], nyseCalendar, 'cta_close')
);

console.log(JSON.stringify({
  status: 'OK',
  decisionDate: prod.decisionDate,
  marketDataAsOf: marketDate,
  futuresAudits,
  etfAudits,
  futuresBlockers: futuresAudits.filter(x => !x.sufficientForCurrentRule),
  etfBlockers: etfAudits.filter(x => !x.sufficientForCurrentRule),
}, null, 2));
