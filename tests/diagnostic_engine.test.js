const assert = require('assert');
const { evaluateDiagnostics } = require('../lib/diagnostic_engine');

function testNonCompensation() {
    // Assert that Pressure Red + Damage Green does NOT output a Yellow average.
    const result = evaluateDiagnostics('Red', 'Yellow', 'Green');
    
    assert.strictEqual(result.pressure.riskSeverity, 3, 'Pressure should be 3 (Red)');
    assert.strictEqual(result.damage.riskSeverity, 1, 'Damage should be 1 (Green)');
    assert.strictEqual(result.isCompensated, false, 'Result should explicitly not be compensated');
    assert.strictEqual(result.averageSeverity, undefined, 'Average riskSeverity should not exist');
    assert.strictEqual(result.maxRiskSeverity, 3, 'Max riskSeverity should be 3');
    
    console.log('diagnostic_engine.test.js passed!');
}

testNonCompensation();
