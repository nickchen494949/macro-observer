const assert = require('assert');
const { identifyContradictions } = require('../lib/contradiction_engine');

function testContradictions() {
    const data = {
        output: 'strong',
        labor: 'weak',
        financialConditions: 'easy',
        longRates: 'tight'
    };
    
    const result = identifyContradictions(data);
    
    assert.strictEqual(result.length, 2);
    assert.strictEqual(result[0].name, 'Output-Labor Divergence');
    assert.strictEqual(result[1].name, 'Broad Ease-Long Rate Tightness');
    
    console.log('contradiction_engine.test.js passed!');
}

testContradictions();
