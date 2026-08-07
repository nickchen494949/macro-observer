const test = require('node:test');
const assert = require('node:assert');

test('Daily Attribution Ceiling', (t) => {
  const getAttributionCeiling = (dataFrequency) => {
    if (dataFrequency === 'intraday') return 'Probable main driver';
    return 'Contributing factor';
  };
  const ceiling = getAttributionCeiling('daily');
  assert.strictEqual(ceiling, 'Contributing factor', 'Daily data must be capped at Contributing factor');
});
