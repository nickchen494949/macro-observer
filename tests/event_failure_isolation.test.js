const test = require('node:test');
const assert = require('node:assert');

test('Event Failure Isolation', (t) => {
  const eventEngine = {
    ingest: () => { throw new Error('Network failure'); },
    safeIngest: function() {
      try { this.ingest(); } catch(e) { return { status: 'unavailable', reason: '暂无足够事件数据，不强行归因' }; }
    }
  };
  const res = eventEngine.safeIngest();
  assert.strictEqual(res.status, 'unavailable');
  assert.strictEqual(res.reason, '暂无足够事件数据，不强行归因');
});
