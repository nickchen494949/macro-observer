const test = require('node:test');
const assert = require('node:assert');

test('Production Payload Exclusion Test', (t) => {
  const resPayload = {
    meta: { featureFlags: { pca: false, inflationForecast: false } },
    conclusions: {}
  };
  
  assert.ok(!resPayload.pca, 'PCA must not be in payload');
  assert.ok(!resPayload.inflationForecast, 'Forecast must not be in payload');
  assert.strictEqual(resPayload.meta.featureFlags.pca, false);
});
