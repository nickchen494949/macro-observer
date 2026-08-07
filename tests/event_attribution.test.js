const EventAttributionEngine = require('../lib/event_attribution_engine');
const path = require('path');
const fs = require('fs');

describe('Event Attribution Engine', () => {
  let engine;

  beforeAll(() => {
    // Setup mock taxonomy
    const taxonomyPath = path.join(__dirname, '../config/event_taxonomy.json');
    if (!fs.existsSync(taxonomyPath)) {
        fs.writeFileSync(taxonomyPath, JSON.stringify({
            "MOCK_EVENT": {
                "requiredSignals": ["REQ1"],
                "supportingSignals": ["SUP1"],
                "contradictingSignals": ["CONTRA1"],
                "penaltyWeights": { "CONTRA1": 1 }
            }
        }));
    }
    engine = new EventAttributionEngine();
    // Inject mock taxonomy for testing
    engine.taxonomy = {
      MOCK_EVENT: {
        requiredSignals: ["REQ1"],
        supportingSignals: ["SUP1"],
        contradictingSignals: ["CONTRA1"],
        penaltyWeights: { "CONTRA1": 1 }
      }
    };
  });

  it('returns No identifiable driver for unknown event type', () => {
    const result = engine.attribute({ type: 'UNKNOWN' }, {});
    expect(result.tier).toBe('No identifiable driver');
  });

  it('returns Probable main driver when required and supporting are present intraday', () => {
    const result = engine.attribute({ type: 'MOCK_EVENT' }, { signals: ['REQ1', 'SUP1'] }, true);
    expect(result.tier).toBe('Probable main driver');
    expect(result.finalScore).toBe(7); // 5 (req) + 2 (sup)
  });

  it('applies daily data ceiling', () => {
    const result = engine.attribute({ type: 'MOCK_EVENT' }, { signals: ['REQ1', 'SUP1'] }, false);
    expect(result.tier).toBe('Contributing factor'); // Ceiled from Probable main driver
  });

  it('returns Rejected by data when contradicting signals overwhelm', () => {
    const result = engine.attribute({ type: 'MOCK_EVENT' }, { signals: ['CONTRA1'] }, true);
    expect(result.tier).toBe('Rejected by data');
    expect(result.finalScore).toBe(-5);
  });
});
