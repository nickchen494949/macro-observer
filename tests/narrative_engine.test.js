const assert = require('assert');
const { generateNarrative } = require('../lib/narrative_engine');

function testNarrative() {
    const context = { growth: 'strong', inflation: 'low' };
    const result = generateNarrative(context);
    
    assert.strictEqual(result, 'Economic growth remains robust. Inflation is cooling.');
    
    console.log('narrative_engine.test.js passed!');
}

testNarrative();
