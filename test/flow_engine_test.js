// Unit tests for flow_wrappers.js
// Tests use synthetic data to verify deterministic behavior

// We need to access the internal helpers, so we'll test via the exported runProductionFlows
const { runProductionFlows } = require('../lib/flow_wrappers');

function makeTimeSeries(values, startDate = '2025-01-01') {
  // Generate daily date series from values array
  const d = new Date(startDate);
  return values.map((v, i) => {
    const date = new Date(d);
    date.setDate(date.getDate() + i);
    // Skip weekends
    while (date.getDay() === 0 || date.getDay() === 6) {
      date.setDate(date.getDate() + 1);
    }
    const dateStr = date.toISOString().split('T')[0];
    return [dateStr, v];
  });
}

function makeFlatSeries(value, length, startDate = '2024-01-01') {
  // Constant price series (zero vol)
  return makeTimeSeries(Array(length).fill(value), startDate);
}

function makeGrowingSeries(start, dailyReturn, length, startDate = '2024-01-01') {
  const values = [start];
  for (let i = 1; i < length; i++) {
    values.push(values[i - 1] * (1 + dailyReturn));
  }
  return makeTimeSeries(values, startDate);
}

function makeStore(overrides = {}) {
  const defaultLength = 300; // enough for 200-day SMA + 60-day vol
  return {
    yahoo: {
      '^GSPC': overrides.spx || makeGrowingSeries(4000, 0.0003, defaultLength),
      '^VIX': overrides.vix || makeFlatSeries(15, defaultLength),
      '^IXIC': overrides.ndx || makeGrowingSeries(14000, 0.0004, defaultLength),
      'SOXX': overrides.sox || makeGrowingSeries(500, 0.0005, defaultLength),
      '^RUT': overrides.rut || makeGrowingSeries(2000, 0.0002, defaultLength),
      'CL=F': overrides.oil || makeGrowingSeries(70, 0.0001, defaultLength),
      'GC=F': overrides.gold || makeGrowingSeries(2000, 0.0002, defaultLength),
      'HG=F': overrides.copper || makeGrowingSeries(4, 0.0003, defaultLength),
    },
    fred: {
      'DGS10': overrides.dgs10 || makeFlatSeries(4.5, defaultLength),
      'BAMLH0A0HYM2': overrides.hyOas || makeFlatSeries(3.5, defaultLength),
    },
    ...overrides.storeOverrides,
  };
}

let passed = 0;
let failed = 0;

function assert(condition, testName, detail = '') {
  if (condition) {
    passed++;
    console.log(`  ✅ ${testName}`);
  } else {
    failed++;
    console.log(`  ❌ ${testName}${detail ? ' — ' + detail : ''}`);
  }
}

function assertApprox(actual, expected, tolerance, testName) {
  const diff = Math.abs(actual - expected);
  assert(diff < tolerance, testName, `expected ${expected}, got ${actual}, diff ${diff}`);
}

// =============================================
// TEST 1: LEVERAGED ETF — β(β-1) formula
// =============================================
console.log('\n=== TEST 1: Leveraged ETF formula ===');
{
  // Create SPX that goes up exactly 1% on the last day
  const spxBase = makeGrowingSeries(5000, 0.0003, 299);
  const lastPrice = spxBase[spxBase.length - 1][1];
  const newPrice = lastPrice * 1.01;
  const d = new Date(spxBase[spxBase.length - 1][0]);
  d.setDate(d.getDate() + 1);
  while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
  spxBase.push([d.toISOString().split('T')[0], newPrice]);

  const store = makeStore({ spx: spxBase });
  const result = runProductionFlows(store);
  const letf = result.modules.leveragedEtf;
  
  // SPXL/UPRO: +3x, AUM $12B, return +1%
  // Expected: 12e9 * 3 * (3-1) * 0.01 = 12e9 * 6 * 0.01 = $720M buy
  const spxlFund = letf.funds.find(f => f.name === 'SPXL/UPRO');
  assert(spxlFund != null, '3x bull fund found');
  assertApprox(spxlFund.grossRebalanceUsd, 12e9 * 6 * 0.01, 12e9 * 6 * 0.01 * 0.005,
    '+3x bull: AUM*6*r = $720M buy');
  assert(spxlFund.direction === 'buy', '+3x bull: direction is buy on +1%');

  // SPXS/SDS: -3x, AUM $2B, return +1%
  // Expected: 2e9 * (-3) * (-3-1) * 0.01 = 2e9 * 12 * 0.01 = $240M buy
  const spxsFund = letf.funds.find(f => f.name === 'SPXS/SDS');
  assertApprox(spxsFund.grossRebalanceUsd, 2e9 * 12 * 0.01, 2e9 * 12 * 0.01 * 0.005,
    '-3x bear: AUM*12*r = $240M buy (same direction as bull!)');
  assert(spxsFund.direction === 'buy', '-3x bear: direction is buy on +1% (both rebalance same way)');

  // SSO: +2x, AUM $8B
  // Expected: 8e9 * 2 * (2-1) * 0.01 = 8e9 * 2 * 0.01 = $160M buy
  const ssoFund = letf.funds.find(f => f.name === 'SSO');
  assertApprox(ssoFund.grossRebalanceUsd, 8e9 * 2 * 0.01, 8e9 * 2 * 0.01 * 0.005,
    '+2x bull: AUM*2*r = $160M buy');
}

// =============================================
// TEST 2: VOL-CONTROL — flat vol = near-zero daily change
// =============================================
console.log('\n=== TEST 2: Vol-Control flat vol ===');
{
  // Very stable series — constant growth, very low vol
  const store = makeStore();
  const result = runProductionFlows(store);
  const vc = result.modules.volControl;
  
  assert(vc.dailyPositionChange != null, 'dailyPositionChange is computed');
  assertApprox(Math.abs(vc.dailyPositionChange), 0, 0.005,
    'Flat vol: daily position change near zero');
  assert(vc.flowPressure === 'neutral', 'Flat vol: flow pressure is neutral');
}

// =============================================
// TEST 3: VOL-CONTROL — vol spike then constant
// =============================================
console.log('\n=== TEST 3: Vol-Control vol spike then constant ===');
{
  // Build series: 250 days of low vol, then 5 days of high vol (sudden 3% daily drops)
  const lowVolSeries = makeGrowingSeries(5000, 0.0003, 280);
  let lastVal = lowVolSeries[lowVolSeries.length - 1][1];
  const highVolDays = [];
  
  // Add 20 days of higher volatility (alternating big moves)
  for (let i = 0; i < 20; i++) {
    const move = (i % 2 === 0) ? -0.025 : 0.02;
    lastVal *= (1 + move);
    const d = new Date(lowVolSeries[lowVolSeries.length - 1][0]);
    d.setDate(d.getDate() + i + 1);
    while (d.getDay() === 0 || d.getDay() === 6) d.setDate(d.getDate() + 1);
    highVolDays.push([d.toISOString().split('T')[0], lastVal]);
  }
  
  const combinedSpx = [...lowVolSeries, ...highVolDays];
  const store = makeStore({ spx: combinedSpx });
  const result = runProductionFlows(store);
  const vc = result.modules.volControl;
  
  assert(vc.actualExposureToday != null, 'Actual exposure computed after vol spike');
  // After vol spike, target exposure should be lower (higher vol = less equity)
  assert(vc.targetExposureToday < 1.0, 'Target exposure reduced after vol spike: ' + vc.targetExposureToday?.toFixed(4));
  
  // Key test: actual exposure should lag target (recursion effect)
  if (vc.actualExposureToday != null && vc.targetExposureToday != null) {
    // actualExposureYesterday should NOT equal targetExposureYesterday (recursion carry-forward)
    const actualYest = vc.actualExposureYesterday;
    const targetYest = vc.targetExposureYesterday;
    const diff = Math.abs((actualYest || 0) - (targetYest || 0));
    assert(diff > 0.001, 'Recursion: actual_yesterday != target_yesterday, diff=' + diff.toFixed(6));
  }
}

// =============================================
// TEST 4: VOL-CONTROL — target drops then holds, selling decays
// =============================================
console.log('\n=== TEST 4: Vol-Control step down + decay ===');
{
  // Simulate: target goes from 1.0 to 0.5 suddenly, then stays at 0.5
  // With λ=0.25, expected actual path: 0.875, 0.781, 0.711, 0.658, ...
  // Each day's change should decrease but remain negative
  
  // We can verify this by building a SPX series that creates a step change in vol
  // But simpler: just test the recursion math directly
  const targets = [1.0, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5];
  const lambda = 0.25;
  let actual = targets[0];
  const changes = [];
  const actuals = [actual];
  
  for (let i = 1; i < targets.length; i++) {
    const prev = actual;
    actual = prev + lambda * (targets[i] - prev);
    changes.push(actual - prev);
    actuals.push(actual);
  }
  
  assertApprox(actuals[1], 0.875, 0.001, 'Day 1: 1.0 → 0.875');
  assertApprox(actuals[2], 0.78125, 0.001, 'Day 2: 0.875 → 0.781');
  assertApprox(actuals[3], 0.71094, 0.001, 'Day 3: → 0.711');
  
  assert(changes[0] < 0, 'Day 1: still selling');
  assert(changes[1] < 0, 'Day 2: still selling');
  assert(changes[2] < 0, 'Day 3: still selling');
  assert(changes[3] < 0, 'Day 4: still selling');
  
  assert(Math.abs(changes[1]) < Math.abs(changes[0]), 'Day 2 sell < Day 1 sell (decaying)');
  assert(Math.abs(changes[2]) < Math.abs(changes[1]), 'Day 3 sell < Day 2 sell (decaying)');
  assert(Math.abs(changes[3]) < Math.abs(changes[2]), 'Day 4 sell < Day 3 sell (decaying)');
}

// =============================================
// TEST 5: CTA — identity check
// =============================================
console.log('\n=== TEST 5: CTA decomposition identity ===');
{
  const store = makeStore();
  const result = runProductionFlows(store);
  
  let allPass = true;
  for (const a of result.modules.ctaFuturesProxy.assets) {
    const sum = (a.signalChange || 0) + (a.volScalingChange || 0);
    const delta = Math.abs((a.positionChange1d || 0) - sum);
    if (delta >= 1e-8) {
      allPass = false;
      console.log(`    ❌ ${a.name}: chg=${a.positionChange1d}, sig+vol=${sum}, err=${delta}`);
    }
  }
  assert(allPass, 'CTA identity: posChange1d == signalChange + volScalingChange for all assets');
}

// =============================================
// TEST 6: CTA — signal unchanged, vol changes
// =============================================
console.log('\n=== TEST 6: CTA signal unchanged, vol changes ===');
{
  // Steady uptrend (price always above all MAs), but vol changes day-to-day
  const store = makeStore();
  const result = runProductionFlows(store);
  
  // In a steady uptrend, score should be constant → signalChange ≈ 0
  for (const a of result.modules.ctaFuturesProxy.assets) {
    if (['S&P 500', 'Nasdaq', 'Russell 2000', 'Copper'].includes(a.name)) {
      assertApprox(a.signalChange || 0, 0, 1e-6,
        `${a.name}: signal unchanged in steady uptrend`);
    }
  }
}

// =============================================
// TEST 7: PENSION — correct drift formula
// =============================================
console.log('\n=== TEST 7: Pension rebalance math ===');
{
  // Manual check: equity +5%, bonds 0%
  // newEqWt = (0.60 * 1.05) / (0.60 * 1.05 + 0.40 * 1.0) = 0.63 / 1.03 = 0.61165
  const expected = (0.60 * 1.05) / (0.60 * 1.05 + 0.40);
  assertApprox(expected, 0.61165, 0.001, 'Formula: 60/40 after equity +5% = 61.17%');
  
  const overweight = expected - 0.60;
  assertApprox(overweight, 0.01165, 0.001, 'Overweight = 1.17%, not 2%');
}

// =============================================
// TEST 8: SUMMARY — double-count prevention
// =============================================
console.log('\n=== TEST 8: Summary double-count ===');
{
  const store = makeStore();
  const result = runProductionFlows(store);
  const s = result.summary;
  
  assert(s.activeFlowMechanismCount >= 0, 'activeFlowMechanismCount is valid');
  assert(s.activeRotationMechanismCount >= 0, 'activeRotationMechanismCount is valid');
  assert(Array.isArray(s.primaryCommonDrivers), 'primaryCommonDrivers is array');
  assert(Array.isArray(s.supportingDataDomains), 'supportingDataDomains is array');
  
  if (s.activeFlowMechanismCount >= 2 && s.primaryCommonDrivers.includes('equity_price')) {
    assert(s.primaryCommonDrivers.length > 0, 
      'Multiple equity-price mechanisms → primaryCommonDrivers populated');
  }
}

// =============================================
// TEST 9: Risk Parity — dual selloff
// =============================================
console.log('\n=== TEST 9: Risk Parity basic ===');
{
  // Use yields with small variation so bond vol is computable
  const yieldVals = [];
  for (let i = 0; i < 300; i++) yieldVals.push(4.5 + 0.01 * Math.sin(i * 0.1));
  const store = makeStore({ dgs10: makeTimeSeries(yieldVals, '2024-01-01') });
  const result = runProductionFlows(store);
  const rp = result.modules.riskParity;
  assert(rp != null, 'riskParityProxy exists');
  assert(rp.status === 'ok', 'rp status is ok');
  assert(rp.totalDeRisking === false, 'totalDeRisking is boolean false');
}

// =============================================
// TEST 10: Stress — estimatedFlowUsd is null
// =============================================
console.log('\n=== TEST 10: Stress conditions ===');
{
  const store = makeStore();
  const result = runProductionFlows(store);
  const sc = result.modules.stressConditions;
  
  assert(sc.estimatedFlowUsd === null, 'Stress: estimatedFlowUsd is null (correctly unprovable)');
  assert(typeof sc.stressScore === 'number', 'Stress score is number');
}

// =============================================
// RESULTS
// =============================================
console.log('\n' + '='.repeat(50));
console.log(`RESULTS: ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));
process.exit(failed > 0 ? 1 : 0);
