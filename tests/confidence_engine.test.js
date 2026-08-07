const assert = require('assert');
const { evaluateConfidence } = require('../lib/confidence_engine');

function testConfidence() {
    const indicatorData = { freshness: 'stale' };
    const diagnosticData = { missingCriticalVariables: true };
    
    const result = evaluateConfidence(indicatorData, diagnosticData);
    
    assert.strictEqual(result.indicatorConfidence, 'low');
    assert.strictEqual(result.diagnosticConfidence, 'low');
    
    const result2 = evaluateConfidence({ freshness: 'current' }, { macroConflict: true });
    assert.strictEqual(result2.indicatorConfidence, 'high');
    assert.strictEqual(result2.diagnosticConfidence, 'medium');

    console.log('confidence_engine.test.js passed!');
}

testConfidence();
