'use strict';

const assert = require('assert');
const {
  buildProductionEngineInputs,
  getNewYorkClock,
  getLatestCompletedUsSessionDate,
} = require('../lib/flow_wrappers');

function storeWithSpx(points) {
  return {
    yahoo: { '^GSPC': points },
    fred: {},
    valuation: {}
  };
}

// Monday 2026-08-10 01:21 New York: market has not opened.
// Even if a provider exposes an Aug-10 intraday/daily placeholder, production
// must remain anchored to the last completed session, Friday Aug-07.
const preOpen = new Date('2026-08-10T05:21:00.000Z');
const withIntradayPlaceholder = storeWithSpx([
  ['2026-08-07', 6500],
  ['2026-08-10', 6510],
]);
assert.strictEqual(getNewYorkClock(preOpen).date, '2026-08-10');
assert.strictEqual(getLatestCompletedUsSessionDate(withIntradayPlaceholder, preOpen), '2026-08-07');
let inputs = buildProductionEngineInputs(withIntradayPlaceholder, preOpen);
assert.strictEqual(inputs.decisionDate, '2026-08-10');
assert.strictEqual(inputs.marketDataAsOf, '2026-08-07');

// After the regular 16:00 New York close, today's session can be used — but
// only when today's SPX observation actually exists.
const afterClose = new Date('2026-08-10T20:30:00.000Z');
assert.strictEqual(getLatestCompletedUsSessionDate(withIntradayPlaceholder, afterClose), '2026-08-10');
inputs = buildProductionEngineInputs(withIntradayPlaceholder, afterClose);
assert.strictEqual(inputs.marketDataAsOf, '2026-08-10');

// If the downloader is still one session behind after the close, do not invent
// today's market state.
const laggedStore = storeWithSpx([
  ['2026-08-06', 6480],
  ['2026-08-07', 6500],
]);
assert.strictEqual(getLatestCompletedUsSessionDate(laggedStore, afterClose), '2026-08-07');

// Timezone boundary: UTC may already be Aug-10 while New York is still Aug-09.
// decisionDate must follow New York, not UTC or Malaysia time.
const nySundayNight = new Date('2026-08-10T00:30:00.000Z');
inputs = buildProductionEngineInputs(laggedStore, nySundayNight);
assert.strictEqual(inputs.decisionDate, '2026-08-09');
assert.strictEqual(inputs.marketDataAsOf, '2026-08-07');

console.log(JSON.stringify({
  status: 'PASS',
  preOpenMarketDataAsOf: buildProductionEngineInputs(withIntradayPlaceholder, preOpen).marketDataAsOf,
  afterCloseMarketDataAsOf: buildProductionEngineInputs(withIntradayPlaceholder, afterClose).marketDataAsOf,
  laggedAfterCloseMarketDataAsOf: buildProductionEngineInputs(laggedStore, afterClose).marketDataAsOf,
  timezoneBoundaryDecisionDate: buildProductionEngineInputs(laggedStore, nySundayNight).decisionDate,
}, null, 2));
