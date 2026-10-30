'use strict';

const fs = require('fs');
const path = require('path');
const assert = require('assert');
const {
  computeRpForwardPressure,
  computeRpSnapshot,
  buildAlignedReturns,
} = require('../lib/rp_mechanical');

const ROOT = path.resolve(__dirname, '..');

function loadJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function extractSeries(obj) {
  if (Array.isArray(obj)) return obj;
  if (obj && Array.isArray(obj.values)) return obj.values;
  if (obj && Array.isArray(obj.data)) return obj.data;
  throw new Error('Unsupported series JSON shape');
}

function findSeries(dir, needle) {
  const files = fs.readdirSync(dir);
  const f = files.find(name => name.toUpperCase().includes(needle.toUpperCase()) && name.endsWith('.json'));
  if (!f) throw new Error(`Could not find ${needle} JSON under ${dir}`);
  return extractSeries(loadJson(path.join(dir, f)));
}

function numberValue(v) {
  if (v == null) return null;
  if (typeof v === 'object') return v.adjClose ?? v.close ?? null;
  return v;
}

function makeMap(series) {
  const m = new Map();
  for (const [d, raw] of series) {
    const v = numberValue(raw);
    if (v != null && Number.isFinite(Number(v))) m.set(d, Number(v));
  }
  return m;
}

function round4(v) {
  return v == null ? null : Number(v.toFixed(4));
}

function assertClose(actual, expected, tol = 0.00011, label = 'value') {
  assert(Number.isFinite(actual), `${label}: actual is not finite`);
  assert(Number.isFinite(expected), `${label}: expected is not finite`);
  assert(Math.abs(actual - expected) <= tol, `${label}: ${actual} != ${expected}`);
}

function futureDatesAfter(calendar, modelDate) {
  return calendar.filter(d => d > modelDate).slice(0, 5);
}

function extendSequential(rawSpx, rawDgs10, dates, modelDate) {
  const spxMap = makeMap(rawSpx);
  const dgsMap = makeMap(rawDgs10);
  let carrySpx = spxMap.get(modelDate);
  let carryDgs = dgsMap.get(modelDate);
  assert(Number.isFinite(carrySpx), 'Missing SPX on modelDate');
  assert(Number.isFinite(carryDgs), 'Missing DGS10 on modelDate');

  const sx = [...rawSpx];
  const dg = [...rawDgs10];
  for (const d of dates) {
    if (spxMap.has(d)) carrySpx = spxMap.get(d);
    else sx.push([d, carrySpx]);

    if (dgsMap.has(d)) carryDgs = dgsMap.get(d);
    else dg.push([d, carryDgs]);
  }
  return { sx, dg };
}

const rawSpx = findSeries(path.join(ROOT, 'data', 'yahoo'), 'GSPC');
const rawDgs10 = findSeries(path.join(ROOT, 'data', 'fred'), 'DGS10');
const calendar = loadJson(path.join(ROOT, 'data', 'nyse_calendar.json'));

const out = computeRpForwardPressure(rawSpx, rawDgs10, calendar);
assert.strictEqual(out.status, 'ok', 'live RP forward output must be ok');
assert.deepStrictEqual(out.horizons.map(h => h.horizon), [1, 2, 3, 5], 'display horizons');
assert(out.horizons.every(h => h.certaintyLevel !== 'LOCKED'), 'RP forward must never be LOCKED');

const dates = futureDatesAfter(calendar, out.modelDate);
assert.strictEqual(dates.length, 5, 'need five future trading dates');
for (const h of out.horizons) {
  assert.strictEqual(h.targetDate, dates[h.horizon - 1], `T+${h.horizon} targetDate`);
  assertClose(
    round4(h.dailyEqExposureDelta + h.dailyBondExposureDelta),
    h.dailyLeverageDelta,
    0.00021,
    `T+${h.horizon} daily exposure identity`
  );
  assertClose(
    round4(h.eqExposureDeltaFromCurrent + h.bondExposureDeltaFromCurrent),
    h.leverageDeltaFromCurrent,
    0.00021,
    `T+${h.horizon} cumulative exposure identity`
  );
  if (h.allocRollOff && h.allocRollOff.primaryEq) {
    assert(h.allocRollOff.primaryBond, `T+${h.horizon} 20D bond roll-off missing`);
  }
  if (h.riskRollOff && h.riskRollOff.primaryEq) {
    assert(h.riskRollOff.primaryBond, `T+${h.horizon} 60D bond roll-off missing`);
  }
}

// Prove hidden T+4 is actually used for T+5 daily delta.
const baseAligned = buildAlignedReturns(rawSpx, rawDgs10, 8);
const baseLen = baseAligned.eqReturns.length;
const ext = extendSequential(rawSpx, rawDgs10, dates, out.modelDate);
const fullAligned = buildAlignedReturns(ext.sx, ext.dg, 8);
const snap4 = computeRpSnapshot(fullAligned.eqReturns.slice(0, baseLen + 4), fullAligned.bondReturns.slice(0, baseLen + 4));
const snap5 = computeRpSnapshot(fullAligned.eqReturns.slice(0, baseLen + 5), fullAligned.bondReturns.slice(0, baseLen + 5));
assert(snap4 && snap5, 'T+4/T+5 snapshots required');
const h5 = out.horizons.find(h => h.horizon === 5);
assert.strictEqual(h5.dailyLeverageDelta, round4(snap5.targetLeverage - snap4.targetLeverage), 'T+5 daily delta must be T+5 minus hidden T+4');

// Chronology / no-lookahead regression test.
// Baseline has no observations after modelDate. Variant adds a large future DGS10
// observation only at hidden T+4. T+1..T+3 MUST remain identical; the T+4 shock
// may only affect T+4 onward.
const truncSpx = rawSpx.filter(([d]) => d <= out.modelDate);
const truncDgs = rawDgs10.filter(([d]) => d <= out.modelDate);
const baseline = computeRpForwardPressure(truncSpx, truncDgs, calendar);
assert.strictEqual(baseline.status, 'ok', 'truncated baseline must be ok');

const dgsMap = makeMap(truncDgs);
const modelYield = dgsMap.get(out.modelDate);
assert(Number.isFinite(modelYield), 'model DGS10 yield required');
const futureBondVariant = [...truncDgs, [dates[3], modelYield + 1.00]];
const variant = computeRpForwardPressure(truncSpx, futureBondVariant, calendar);
assert.strictEqual(variant.status, 'ok', 'future-observation variant must be ok');
for (const hNo of [1, 2, 3]) {
  const a = baseline.horizons.find(h => h.horizon === hNo);
  const b = variant.horizons.find(h => h.horizon === hNo);
  assert.strictEqual(b.targetLeverage, a.targetLeverage, `future T+4 DGS10 must not leak into T+${hNo}`);
  assert.strictEqual(b.portfolioVol, a.portfolioVol, `future T+4 DGS10 vol must not leak into T+${hNo}`);
}

// Symmetric partial scenario: bond observed, equity missing.
const bondAtT1 = [...truncDgs, [dates[0], modelYield + 0.10]];
const bondOnlyPartial = computeRpForwardPressure(truncSpx, bondAtT1, calendar);
const p1 = bondOnlyPartial.horizons.find(h => h.horizon === 1);
assert.strictEqual(p1.certaintyLevel, 'PARTIAL_SCENARIO');
assert.strictEqual(p1.certaintySemantic, 'bond_observed_equity_assumed');

console.log(JSON.stringify({
  status: 'PASS',
  modelDate: out.modelDate,
  spxLastDate: out.spxLastDate,
  dgs10LastDate: out.dgs10LastDate,
  displayHorizons: out.horizons.map(h => ({
    horizon: h.horizon,
    targetDate: h.targetDate,
    certainty: h.certaintySemantic,
    targetLeverage: h.targetLeverage,
    dailyLeverageDelta: h.dailyLeverageDelta,
  })),
  hiddenT4Verified: true,
  noLookaheadVerified: true,
  symmetricPartialVerified: true,
}, null, 2));
