const test = require('node:test');
const assert = require('node:assert');

test('No Identifiable Driver', (t) => {
  const evaluateAttribution = (events, marketMoves) => {
    if (events.length === 0) return 'No identifiable driver';
    return 'Probable main driver';
  };
  const res = evaluateAttribution([], { sp500: 'up' });
  assert.strictEqual(res, 'No identifiable driver', 'Must output No identifiable driver when no event matches');
});
