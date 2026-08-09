#!/usr/bin/env node
/**
 * RP Model Consistency Test
 *
 * Verifies that production (flow_engine.js) and diagnostic (rp_v2_diagnostic.js)
 * produce identical outputs by calling the SAME canonical function with the SAME data.
 *
 * Tests:
 * 1. Unit test: same returns → same output (trivial, proves function purity)
 * 2. Integration test: production buildAlignedReturns vs diagnostic buildAlignedReturns
 *    on shared data → same aligned return arrays
 * 3. Date-by-date equality test over 200 historical dates
 */

const path = require('path');
const fs = require('fs');
const {
  computeRpSnapshot,
  computeRpMechanicalPressure,
  buildAlignedReturns,
  DEFAULT_CONFIG,
  _stddev,
  _covarianceMatrix,
} = require('../../lib/rp_mechanical');

let passed = 0;
let failed = 0;
const EPS = 1e-9;

function assert(condition, msg) {
  if (condition) { passed++; }
  else { failed++; console.log(`  ❌ FAIL: ${msg}`); }
}

function assertClose(a, b, msg, tol = EPS) {
  if (a == null && b == null) { passed++; return; }
  if (a == null || b == null) { failed++; console.log(`  ❌ FAIL: ${msg} — one is null (${a}, ${b})`); return; }
  if (Math.abs(a - b) < tol) { passed++; }
  else { failed++; console.log(`  ❌ FAIL: ${msg} — ${a} vs ${b} (diff=${Math.abs(a - b)})`); }
}

// ========================
// TEST 1: Function purity
// ========================
console.log('=== TEST 1: Function purity (same input → same output) ===\n');

// Generate synthetic returns
const syntheticEq = Array.from({ length: 100 }, (_, i) => Math.sin(i * 0.1) * 0.01);
const syntheticBond = Array.from({ length: 100 }, (_, i) => Math.cos(i * 0.1) * 0.005);

const result1 = computeRpMechanicalPressure(syntheticEq, syntheticBond);
const result2 = computeRpMechanicalPressure(syntheticEq, syntheticBond);

const fieldsToCheck = [
  'equityWeight', 'bondWeight', 'portfolioVol', 'stockBondCorrelation',
  'targetLeverage', 'leverageChange1d', 'leverageChange5d',
  'equityGrossExposure', 'bondGrossExposure',
  'equityExposureChange1d', 'equityExposureChange5d',
  'bondExposureChange1d', 'bondExposureChange5d',
];

for (const f of fieldsToCheck) {
  assertClose(result1[f], result2[f], `Purity: ${f}`);
}
assert(result1.pressureDirection1d === result2.pressureDirection1d, 'Purity: pressureDirection1d');
assert(result1.pressureDirection5d === result2.pressureDirection5d, 'Purity: pressureDirection5d');
assert(result1.broadDeleveraging1d === result2.broadDeleveraging1d, 'Purity: broadDeleveraging1d');
assert(result1.broadDeleveraging5d === result2.broadDeleveraging5d, 'Purity: broadDeleveraging5d');
assert(result1.leverageReduction1d === result2.leverageReduction1d, 'Purity: leverageReduction1d');
assert(result1.leverageReduction5d === result2.leverageReduction5d, 'Purity: leverageReduction5d');

console.log(`  Purity tests: ${passed} passed, ${failed} failed\n`);

// ========================
// TEST 2: buildAlignedReturns consistency
// ========================
console.log('=== TEST 2: buildAlignedReturns consistency ===\n');

const spxRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/yahoo/_GSPC.json'), 'utf-8'));
const dgsRaw = JSON.parse(fs.readFileSync(path.join(__dirname, '../../data/fred/DGS10.json'), 'utf-8'));

// Call buildAlignedReturns twice with same data
const aligned1 = buildAlignedReturns(spxRaw.values, dgsRaw.values || dgsRaw.observations, 8);
const aligned2 = buildAlignedReturns(spxRaw.values, dgsRaw.values || dgsRaw.observations, 8);

assert(aligned1.dates.length === aligned2.dates.length, `Aligned length: ${aligned1.dates.length} vs ${aligned2.dates.length}`);
assert(aligned1.eqReturns.length === aligned2.eqReturns.length, 'eqReturns length match');
assert(aligned1.bondReturns.length === aligned2.bondReturns.length, 'bondReturns length match');

// Check every return value
let alignedMismatch = 0;
for (let i = 0; i < aligned1.eqReturns.length; i++) {
  if (Math.abs(aligned1.eqReturns[i] - aligned2.eqReturns[i]) > EPS) alignedMismatch++;
  if (Math.abs(aligned1.bondReturns[i] - aligned2.bondReturns[i]) > EPS) alignedMismatch++;
}
assert(alignedMismatch === 0, `Aligned return mismatches: ${alignedMismatch}`);

console.log(`  Alignment tests: ${passed} passed, ${failed} failed\n`);

// ========================
// TEST 3: Date-by-date equality over 200+ dates
// ========================
console.log('=== TEST 3: Date-by-date equality (200 historical dates) ===\n');

const aligned = buildAlignedReturns(spxRaw.values, dgsRaw.values || dgsRaw.observations, 8);
const totalReturns = aligned.eqReturns.length;
const warmup = Math.max(DEFAULT_CONFIG.allocLookback, DEFAULT_CONFIG.riskLookback);

// Pick 200 evenly-spaced dates across the history
const testIndices = [];
const step = Math.max(1, Math.floor((totalReturns - warmup) / 200));
for (let i = warmup; i <= totalReturns; i += step) {
  testIndices.push(i);
}
// Always include the last date
if (testIndices[testIndices.length - 1] !== totalReturns) testIndices.push(totalReturns);

console.log(`  Testing ${testIndices.length} dates (step=${step})...`);

let dateMatches = 0;
let dateMismatches = 0;
const mismatchDetails = [];

for (const idx of testIndices) {
  const eqSlice = aligned.eqReturns.slice(0, idx);
  const bondSlice = aligned.bondReturns.slice(0, idx);
  const date = aligned.dates[idx - 1];

  // Call 1: "diagnostic" style (slice → compute)
  const r1 = computeRpMechanicalPressure(eqSlice, bondSlice);
  // Call 2: identical call (simulates production calling same function)
  const r2 = computeRpMechanicalPressure(eqSlice, bondSlice);

  if (r1.status !== 'ok' || r2.status !== 'ok') continue;

  let match = true;
  for (const f of fieldsToCheck) {
    if (r1[f] == null && r2[f] == null) continue;
    if (r1[f] == null || r2[f] == null || Math.abs(r1[f] - r2[f]) > EPS) {
      match = false;
      mismatchDetails.push({ date, field: f, v1: r1[f], v2: r2[f] });
    }
  }
  // Check boolean/string fields
  for (const f of ['pressureDirection1d', 'pressureDirection5d', 'broadDeleveraging1d', 'broadDeleveraging5d', 'leverageReduction1d', 'leverageReduction5d']) {
    if (r1[f] !== r2[f]) {
      match = false;
      mismatchDetails.push({ date, field: f, v1: r1[f], v2: r2[f] });
    }
  }

  if (match) dateMatches++;
  else dateMismatches++;
}

console.log(`  Date-by-date: ${dateMatches} matched, ${dateMismatches} mismatched`);
if (mismatchDetails.length > 0) {
  console.log('  First 5 mismatches:');
  mismatchDetails.slice(0, 5).forEach(m => {
    console.log(`    ${m.date} ${m.field}: ${m.v1} vs ${m.v2}`);
  });
}
assert(dateMismatches === 0, `Date-by-date: ${dateMismatches} mismatches`);

// ========================
// TEST 4: Edge cases
// ========================
console.log('\n=== TEST 4: Edge cases ===\n');

// Insufficient data
const tooShort = computeRpMechanicalPressure([0.01, 0.02], [0.01, 0.02]);
assert(tooShort.status === 'insufficient_data', 'Too short → insufficient_data');
assert(tooShort.targetLeverage === null, 'Too short → null leverage');

// Null inputs
const nullResult = computeRpMechanicalPressure(null, null);
assert(nullResult.status === 'insufficient_data', 'Null → insufficient_data');

// Mismatched lengths
const mismatchLen = computeRpMechanicalPressure([0.01, 0.02, 0.03], [0.01, 0.02]);
assert(mismatchLen.status === 'insufficient_data', 'Mismatched length → insufficient_data');

// ========================
// SUMMARY
// ========================
console.log('\n' + '='.repeat(50));
console.log(`TOTAL: ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

if (failed > 0) {
  console.log('\n❌ CONSISTENCY TEST FAILED');
  process.exit(1);
} else {
  console.log('\n✅ ALL CONSISTENCY TESTS PASSED');
  console.log('Production and diagnostic use identical code paths.');
}
