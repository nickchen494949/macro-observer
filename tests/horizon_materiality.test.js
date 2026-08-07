const test = require('node:test');
const assert = require('node:assert');
const { calculateTrend, _setRules } = require('../lib/horizon_engine');

const mockRules = {
  frequencies: {
    daily: { shortTerm: 1, mediumTerm: 5, longTerm: 20 }
  },
  materialityFilters: {
    equities: { unit: 'pct', thresholds: { shortTerm: 0.5, mediumTerm: 2.0, longTerm: 5.0 } },
    rates: { unit: 'bp', thresholds: { shortTerm: 5, mediumTerm: 15, longTerm: 30 } }
  }
};

_setRules(mockRules);

test('Equities noise band (neutral)', () => {
  const data = [];
  for(let i=0; i<21; i++) data.push(['2023', 0]);
  data[20-20] = ['2023', 96.0];
  data[20-5] = ['2023', 98.5];
  data[20-1] = ['2023', 99.6];
  data[20] = ['2023', 100];

  const result = calculateTrend(data, 'equities', 'daily');
  assert.strictEqual(result.shortTerm, 'neutral');
  assert.strictEqual(result.mediumTerm, 'neutral');
  assert.strictEqual(result.longTerm, 'neutral');
  assert.strictEqual(result.coherence, 'mixed');
});

test('Rates noise band (neutral)', () => {
  const data = [];
  for(let i=0; i<21; i++) data.push(['2023', 0]);
  data[20-20] = ['2023', 71];
  data[20-5] = ['2023', 114];
  data[20-1] = ['2023', 96];
  data[20] = ['2023', 100];

  const result = calculateTrend(data, 'rates', 'daily');
  assert.strictEqual(result.shortTerm, 'neutral');
  assert.strictEqual(result.mediumTerm, 'neutral');
  assert.strictEqual(result.longTerm, 'neutral');
});
