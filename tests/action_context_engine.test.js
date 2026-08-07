const test = require('node:test');
const assert = require('node:assert');
const { generateActionContext } = require('../lib/action_context_engine.js');

test('Action Context Engine - Systemic Stress', (t) => {
  const diagnosis = { maxRiskSeverity: 3, hasDamage: true, hasContradiction: false };
  const res = generateActionContext(diagnosis);
  assert.strictEqual(res.environment, 'systemic stress');
});

test('Action Context Engine - Adverse', (t) => {
  const diagnosis = { maxRiskSeverity: 2, hasDamage: false, hasContradiction: true };
  const res = generateActionContext(diagnosis);
  assert.strictEqual(res.environment, 'adverse');
});

test('Action Context Engine - Supportive', (t) => {
  const diagnosis = { maxRiskSeverity: 0, hasDamage: false, hasContradiction: false };
  const res = generateActionContext(diagnosis);
  assert.strictEqual(res.environment, 'supportive');
});

test('Action Context Engine - Neutral', (t) => {
  const diagnosis = { maxRiskSeverity: 1, hasDamage: false, hasContradiction: false };
  const res = generateActionContext(diagnosis);
  assert.strictEqual(res.environment, 'neutral');
});
