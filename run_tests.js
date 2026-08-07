const EventDeduplicator = require('./lib/event_deduplicator');
const EventTimelineEngine = require('./lib/event_timeline_engine');
const SurpriseEngine = require('./lib/surprise_engine');
const EventAttributionEngine = require('./lib/event_attribution_engine');
const assert = require('assert');

function runTests() {
  console.log("Running Tests...");
  
  // Deduplicator Test
  try {
    const deduplicator = new EventDeduplicator(3600000);
    const events = [
      { id: '1', type: 'CPI_RELEASE', timestamp: 1000000, source: 'Reuters' },
      { id: '2', type: 'CPI_RELEASE', timestamp: 1001000, source: 'Bloomberg' },
      { id: '3', type: 'NFP_RELEASE', timestamp: 1000000, source: 'WSJ' },
      { id: '4', type: 'CPI_RELEASE', timestamp: 5000000, source: 'CNBC' }
    ];
    const result = deduplicator.deduplicate(events);
    assert.strictEqual(result.length, 3, "Deduplicator failed: expected 3 clusters");
    const cpiPrimary = result.find(e => e.id === '1');
    assert.strictEqual(cpiPrimary.echoCount, 2, "Deduplicator failed: expected 2 echoes for CPI");
    console.log("✅ Event Deduplicator Tests passed");
  } catch (e) {
    console.error("❌ Event Deduplicator Tests failed", e);
  }

  // Timeline Engine Test
  try {
    const engine = new EventTimelineEngine(86400000);
    assert.strictEqual(engine.validatePrecedence({ timestamp: 10000 }, { timestamp: 20000 }), true, "Timeline failed: should be valid");
    assert.strictEqual(engine.validatePrecedence({ timestamp: 10000 }, { timestamp: 5000 }), false, "Timeline failed: should be too early");
    assert.strictEqual(engine.validatePrecedence({ timestamp: 10000 }, { timestamp: 10000 + 86400000 + 1000 }), false, "Timeline failed: should be too late");
    console.log("✅ Event Timeline Engine Tests passed");
  } catch (e) {
    console.error("❌ Event Timeline Engine Tests failed", e);
  }

  // Surprise Engine Test
  try {
    const engine = new SurpriseEngine();
    let res = engine.calculateSurprise({ actual: 5.5, consensus: 5.0 });
    assert.strictEqual(Math.round(res.surpriseValue * 10) / 10, 0.5, "Surprise failed: positive surprise value");
    assert.strictEqual(res.surpriseDirection, 'positive', "Surprise failed: positive surprise direction");

    res = engine.calculateSurprise({ actual: 4.8, consensus: 5.0 });
    assert.strictEqual(Math.round(res.surpriseValue * 10) / 10, -0.2, "Surprise failed: negative surprise value");
    assert.strictEqual(res.surpriseDirection, 'negative', "Surprise failed: negative surprise direction");

    res = engine.calculateSurprise({ actual: 5.0, consensus: 5.0 });
    assert.strictEqual(res.surpriseValue, 0, "Surprise failed: inline surprise value");
    assert.strictEqual(res.surpriseDirection, 'inline', "Surprise failed: inline surprise direction");
    console.log("✅ Surprise Engine Tests passed");
  } catch (e) {
    console.error("❌ Surprise Engine Tests failed", e);
  }

  // Attribution Engine Test
  try {
    const engine = new EventAttributionEngine();
    // inject taxonomy
    engine.taxonomy = {
      MOCK_EVENT: {
        requiredSignals: ["REQ1"],
        supportingSignals: ["SUP1"],
        contradictingSignals: ["CONTRA1"],
        penaltyWeights: { "CONTRA1": 1 }
      }
    };

    let res = engine.attribute({ type: 'UNKNOWN' }, {});
    assert.strictEqual(res.tier, 'No identifiable driver', "Attribution failed: unknown event type");

    res = engine.attribute({ type: 'MOCK_EVENT' }, { signals: ['REQ1', 'SUP1'] }, true);
    assert.strictEqual(res.tier, 'Probable main driver', "Attribution failed: intraday probable main driver");
    assert.strictEqual(res.finalScore, 7, "Attribution failed: score calculation");

    res = engine.attribute({ type: 'MOCK_EVENT' }, { signals: ['REQ1', 'SUP1'] }, false);
    assert.strictEqual(res.tier, 'Contributing factor', "Attribution failed: daily data ceiling");

    res = engine.attribute({ type: 'MOCK_EVENT' }, { signals: ['CONTRA1'] }, true);
    assert.strictEqual(res.tier, 'Rejected by data', "Attribution failed: contradicting signals");
    console.log("✅ Event Attribution Engine Tests passed");
  } catch (e) {
    console.error("❌ Event Attribution Engine Tests failed", e);
  }
}

runTests();
