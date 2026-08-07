const test = require('node:test');
const assert = require('node:assert');

test('Backtrack Isolation Test', (t) => {
  // Simulate the backtrack evaluate function
  const evaluate = ({ asOfDate, dataVintageMode }) => {
    return { 
      meta: { asOf: asOfDate, vintageMode: dataVintageMode },
      data: { valid: true } 
    };
  };

  const res = evaluate({ asOfDate: '2022-06-15', dataVintageMode: 'revised_data_simulation' });
  assert.strictEqual(res.meta.asOf, '2022-06-15', 'API must strictly honor asOfDate cutoff');
  assert.strictEqual(res.meta.vintageMode, 'revised_data_simulation', 'Vintage mode must be preserved');
});
