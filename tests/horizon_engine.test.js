const test = require('node:test');
const assert = require('node:assert');
const { calculateTrend, _setRules } = require('../lib/horizon_engine');

const mockRules = {
  frequencies: {
    daily_markets: { shortTerm: 1, mediumTerm: 5, longTerm: 20 },
    monthly_macro: { shortTerm: 1, mediumTerm: 3, longTerm: 12 }
  },
  materialityFilters: {
    equities: { unit: 'pct', thresholds: { shortTerm: 0.4, mediumTerm: 2.0, longTerm: 5.0 } },
    rates: { unit: 'bp', thresholds: { shortTerm: 3, mediumTerm: 10, longTerm: 25 } },
    flows: { unit: 'abs', thresholds: { shortTerm: 10, mediumTerm: 30, longTerm: 50 } },
    nowcast: { unit: 'pct_point', thresholds: { shortTerm: 0.1, mediumTerm: 0.3, longTerm: 0.5 } }
  }
};

_setRules(mockRules);

test('Horizon Engine - Equities (pct) - confirmed_uptrend', () => {
  const data = Array.from({length: 25}, (_, i) => ['2023', 90 + i]); 
  const result = calculateTrend(data, 'equities', 'daily_markets');
  assert.strictEqual(result.shortTerm, 'rising');
  assert.strictEqual(result.mediumTerm, 'rising');
  assert.strictEqual(result.longTerm, 'rising');
  assert.strictEqual(result.coherence, 'confirmed_uptrend');
});

test('Horizon Engine - Rates (bp) - falling', () => {
  const data = Array.from({length: 25}, (_, i) => ['2023', 100 - i * 2]);
  const result = calculateTrend(data, 'rates', 'daily_markets');
  assert.strictEqual(result.shortTerm, 'neutral');
  assert.strictEqual(result.mediumTerm, 'neutral');
});

test('Horizon Engine - Rates (bp) - confirmed_downtrend', () => {
  const data = Array.from({length: 25}, (_, i) => ['2023', 100 - i * 5]);
  const result = calculateTrend(data, 'rates', 'daily_markets');
  assert.strictEqual(result.shortTerm, 'falling');
  assert.strictEqual(result.mediumTerm, 'falling');
  assert.strictEqual(result.longTerm, 'falling');
  assert.strictEqual(result.coherence, 'confirmed_downtrend');
});

test('Horizon Engine - Flows (flow_momentum) - neutral/insufficient', () => {
  const data = Array.from({length: 5}, (_, i) => ['2023', 200 + i]);
  const result = calculateTrend(data, 'flows', 'monthly_macro');
  assert.strictEqual(result.coherence, 'insufficient_data');
});

test('Horizon Engine - Flows (flow_momentum) - valid', () => {
  const data = Array.from({length: 25}, (_, i) => ['2023', i < 12 ? 100 : 200]);
  const result = calculateTrend(data, 'flows', 'monthly_macro');
  assert.strictEqual(result.shortTerm, 'neutral');
});

test('Horizon Engine - Nowcast (pct_point) - rising', () => {
  const data = Array.from({length: 25}, (_, i) => ['2023', i * 0.2]);
  const result = calculateTrend(data, 'nowcast', 'daily_markets');
  assert.strictEqual(result.shortTerm, 'rising');
  assert.strictEqual(result.mediumTerm, 'rising');
  assert.strictEqual(result.longTerm, 'rising');
});
