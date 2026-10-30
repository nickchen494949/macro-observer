// /Users/happygolucky/Projects/宏观观察器/lib/rp_mechanical.js
//
// Canonical Reduced Risk Parity Mechanical Model
//
// This is the SINGLE source of truth for all RP mechanical pressure calculations.
// Both production (flow_engine.js) and diagnostics (rp_v2_diagnostic.js) call this.
//
// METHODOLOGY:
//   Layer 1 (Allocation):   Inverse-vol weights using allocLookback-day asset volatilities
//   Layer 2 (Portfolio Risk): Full covariance matrix from riskLookback-day window (coherent)
//   Layer 3 (Leverage):      targetVol / portfolioVol, clamped to [leverageFloor, leverageCap]
//   Layer 4 (Pressure):      Delta analysis of leverage and gross exposures
//
// KEY DESIGN DECISION:
//   Allocation and portfolio-risk use DIFFERENT lookback windows.
//   - allocLookback (20d): reactive to recent vol changes for weight adjustment
//   - riskLookback (60d):  stable, coherent covariance matrix for portfolio-level risk
//   Both windows are documented explicitly and never mixed.
//   The covariance matrix for portfolio vol is computed entirely from the riskLookback window.
//   We do NOT mix 20d vol with 60d correlation — that would be an incoherent matrix.

const DEFAULT_CONFIG = {
  allocLookback: 20,        // days for inverse-vol weights
  riskLookback: 60,         // days for full covariance matrix (portfolio vol)
  bondDuration: 8,          // modified duration for 10Y Treasury
  targetPortfolioVol: 0.10, // 10% annualized — ASSUMPTION
  leverageCap: 3.0,         // max leverage — ASSUMPTION
  leverageFloor: 0.2,       // min leverage
  annFactor: Math.sqrt(252),
};

/**
 * Compute a single RP mechanical snapshot from pre-aligned daily return arrays.
 *
 * @param {number[]} eqReturns  - Daily log returns for equity, ordered chronologically
 * @param {number[]} bondReturns - Daily bond returns (-D * ΔY/100), same length, aligned
 * @param {object}   [config]   - Override defaults (allocLookback, riskLookback, etc.)
 * @returns {object|null}       - RP snapshot or null if insufficient data
 */
function computeRpSnapshot(eqReturns, bondReturns, config) {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  if (!eqReturns || !bondReturns) return null;
  if (eqReturns.length !== bondReturns.length) return null;
  const n = eqReturns.length;
  if (n < Math.max(cfg.allocLookback, cfg.riskLookback)) return null;

  // --- Layer 1: Allocation weights (allocLookback-day vol) ---
  const eqAllocSlice = eqReturns.slice(n - cfg.allocLookback);
  const bondAllocSlice = bondReturns.slice(n - cfg.allocLookback);
  const eqAllocVol = stddev(eqAllocSlice) * cfg.annFactor;
  const bondAllocVol = stddev(bondAllocSlice) * cfg.annFactor;

  if (eqAllocVol <= 0 || bondAllocVol <= 0) return null;

  const wEq = (1 / eqAllocVol) / (1 / eqAllocVol + 1 / bondAllocVol);
  const wBond = 1 - wEq;

  // --- Layer 2: Portfolio risk (riskLookback-day coherent covariance) ---
  const eqRiskSlice = eqReturns.slice(n - cfg.riskLookback);
  const bondRiskSlice = bondReturns.slice(n - cfg.riskLookback);

  const riskStats = covarianceMatrix(eqRiskSlice, bondRiskSlice);
  // Annualize: daily var/cov * 252
  const annEqVar = riskStats.eqVar * 252;
  const annBondVar = riskStats.bondVar * 252;
  const annCov = riskStats.cov * 252;

  // σ_p² = w_eq²·σ²_eq + w_bond²·σ²_bond + 2·w_eq·w_bond·Cov(eq,bond)
  const portVar = wEq ** 2 * annEqVar
                + wBond ** 2 * annBondVar
                + 2 * wEq * wBond * annCov;
  const portfolioVol = Math.sqrt(Math.max(portVar, 0));

  // --- Layer 3: Target-vol leverage ---
  let targetLeverage = portfolioVol > 0 ? cfg.targetPortfolioVol / portfolioVol : 1;
  targetLeverage = Math.min(targetLeverage, cfg.leverageCap);
  targetLeverage = Math.max(targetLeverage, cfg.leverageFloor);

  // Gross exposures
  const eqGrossExposure = wEq * targetLeverage;
  const bondGrossExposure = wBond * targetLeverage;

  return {
    equityWeight: wEq,
    bondWeight: wBond,
    equityAllocVol: eqAllocVol,
    bondAllocVol: bondAllocVol,
    stockBondCorrelation: riskStats.corr,
    portfolioVol,
    targetLeverage,
    eqGrossExposure,
    bondGrossExposure,
  };
}

/**
 * Compute full RP mechanical pressure with delta analysis.
 *
 * Calls computeRpSnapshot at three points in time: now, 1d ago, 5d ago.
 * Reports deltas, pressure direction, and broad deleveraging flags.
 *
 * @param {number[]} eqReturns   - Full aligned equity return history
 * @param {number[]} bondReturns - Full aligned bond return history
 * @param {object}   [config]    - Override defaults
 * @returns {object}             - Full RP mechanical pressure output
 */
function computeRpMechanicalPressure(eqReturns, bondReturns, config) {
  const cfg = { ...DEFAULT_CONFIG, ...config };

  const now = computeRpSnapshot(eqReturns, bondReturns, cfg);
  if (!now) {
    return {
      status: 'insufficient_data',
      equityWeight: null, bondWeight: null, portfolioVol: null,
      stockBondCorrelation: null, targetLeverage: null,
      leverageChange1d: null, leverageChange5d: null,
      equityGrossExposure: null, bondGrossExposure: null,
      equityExposureChange1d: null, equityExposureChange5d: null,
      bondExposureChange1d: null, bondExposureChange5d: null,
      pressureDirection1d: null, pressureDirection5d: null,
      broadDeleveraging1d: null, broadDeleveraging5d: null,
      leverageReduction1d: null, leverageReduction5d: null,
      assumptions: cfg,
      disclaimer: 'Reduced 2-asset RP proxy. Does not represent actual RP fund positions or AUM.',
    };
  }

  // 1d ago
  const ago1d = eqReturns.length > 1
    ? computeRpSnapshot(eqReturns.slice(0, -1), bondReturns.slice(0, -1), cfg)
    : null;

  // 5d ago
  const ago5d = eqReturns.length > 5
    ? computeRpSnapshot(eqReturns.slice(0, -5), bondReturns.slice(0, -5), cfg)
    : null;

  // Delta computations
  const leverageChange1d = ago1d ? now.targetLeverage - ago1d.targetLeverage : null;
  const leverageChange5d = ago5d ? now.targetLeverage - ago5d.targetLeverage : null;

  const eqExpChange1d = ago1d ? now.eqGrossExposure - ago1d.eqGrossExposure : null;
  const eqExpChange5d = ago5d ? now.eqGrossExposure - ago5d.eqGrossExposure : null;
  const bondExpChange1d = ago1d ? now.bondGrossExposure - ago1d.bondGrossExposure : null;
  const bondExpChange5d = ago5d ? now.bondGrossExposure - ago5d.bondGrossExposure : null;

  // Pressure direction: based on leverage change, NOT exposure change
  const pressureDir = (delta) => {
    if (delta == null) return null;
    if (delta < -0.01) return 'deleveraging';
    if (delta > 0.01) return 'leveraging';
    return 'neutral';
  };

  // leverageReduction: leverage fell > threshold (mechanical fact)
  const isLevReduction = (delta) => delta != null && delta < -0.01;

  // broadDeleveraging: BOTH equity AND bond gross exposures decreased (stricter test)
  const isBroadDelev = (eqDelta, bondDelta) => {
    if (eqDelta == null || bondDelta == null) return null;
    return eqDelta < -0.005 && bondDelta < -0.005;
  };

  return {
    status: 'ok',
    equityWeight: round4(now.equityWeight),
    bondWeight: round4(now.bondWeight),
    portfolioVol: round4(now.portfolioVol),
    stockBondCorrelation: round4(now.stockBondCorrelation),
    targetLeverage: round4(now.targetLeverage),
    leverageChange1d: round4(leverageChange1d),
    leverageChange5d: round4(leverageChange5d),
    equityGrossExposure: round4(now.eqGrossExposure),
    bondGrossExposure: round4(now.bondGrossExposure),
    equityExposureChange1d: round4(eqExpChange1d),
    equityExposureChange5d: round4(eqExpChange5d),
    bondExposureChange1d: round4(bondExpChange1d),
    bondExposureChange5d: round4(bondExpChange5d),
    pressureDirection1d: pressureDir(leverageChange1d),
    pressureDirection5d: pressureDir(leverageChange5d),
    leverageReduction1d: isLevReduction(leverageChange1d),
    leverageReduction5d: isLevReduction(leverageChange5d),
    broadDeleveraging1d: isBroadDelev(eqExpChange1d, bondExpChange1d),
    broadDeleveraging5d: isBroadDelev(eqExpChange5d, bondExpChange5d),
    assumptions: {
      targetPortfolioVol: cfg.targetPortfolioVol,
      leverageCap: cfg.leverageCap,
      leverageFloor: cfg.leverageFloor,
      allocLookback: cfg.allocLookback,
      riskLookback: cfg.riskLookback,
      bondDuration: cfg.bondDuration,
      label: 'ASSUMPTION',
    },
    disclaimer: 'Reduced 2-asset RP proxy. Does not represent actual RP fund positions or AUM.',
  };
}

// --- Pure math helpers (no side effects, no I/O) ---

function stddev(arr) {
  if (!arr || arr.length < 2) return 0;
  const n = arr.length;
  const mean = arr.reduce((a, b) => a + b, 0) / n;
  const variance = arr.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1);
  return Math.sqrt(variance);
}

function covarianceMatrix(eqArr, bondArr) {
  const n = eqArr.length;
  const eqMean = eqArr.reduce((a, b) => a + b, 0) / n;
  const bondMean = bondArr.reduce((a, b) => a + b, 0) / n;
  let cov = 0, eqVar = 0, bondVar = 0;
  for (let i = 0; i < n; i++) {
    const de = eqArr[i] - eqMean;
    const db = bondArr[i] - bondMean;
    cov += de * db;
    eqVar += de * de;
    bondVar += db * db;
  }
  // Sample covariance (n-1 denominator)
  cov /= (n - 1);
  eqVar /= (n - 1);
  bondVar /= (n - 1);
  const corr = (eqVar > 0 && bondVar > 0) ? cov / (Math.sqrt(eqVar) * Math.sqrt(bondVar)) : 0;
  return { cov, eqVar, bondVar, corr };
}

function round4(v) {
  if (v == null) return null;
  return Number(v.toFixed(4));
}

/**
 * Build aligned daily return arrays from raw price/yield series.
 *
 * @param {Array} eqSeries   - [[date, price], ...] equity series
 * @param {Array} bondSeries - [[date, yield], ...] bond yield series (e.g. DGS10)
 * @param {number} duration  - Bond modified duration (default 8)
 * @returns {object}         - { dates, eqReturns, bondReturns }
 */
function buildAlignedReturns(eqSeries, bondSeries, duration) {
  const dur = duration || DEFAULT_CONFIG.bondDuration;

  // Build date-indexed maps, handling mixed Yahoo format (object vs number)
  const eqMap = new Map();
  for (const pt of eqSeries) {
    const val = pt[1];
    if (val == null) continue;
    const price = typeof val === 'object' ? (val.adjClose || val.close) : val;
    if (price != null && !isNaN(price)) eqMap.set(pt[0], price);
  }

  const bondMap = new Map();
  for (const pt of bondSeries) {
    if (pt[1] != null && !isNaN(pt[1])) bondMap.set(pt[0], pt[1]);
  }

  // Common dates (sorted)
  const allEqDates = [...eqMap.keys()].sort();
  const commonDates = allEqDates.filter(d => bondMap.has(d));
  if (commonDates.length < 2) return { dates: [], eqReturns: [], bondReturns: [] };

  const eqPrices = commonDates.map(d => eqMap.get(d));
  const bondYields = commonDates.map(d => bondMap.get(d));

  const dates = [];
  const eqReturns = [];
  const bondReturns = [];
  for (let i = 1; i < commonDates.length; i++) {
    if (eqPrices[i] == null || eqPrices[i - 1] == null || eqPrices[i] <= 0 || eqPrices[i - 1] <= 0) continue;
    if (bondYields[i] == null || bondYields[i - 1] == null) continue;
    dates.push(commonDates[i]);
    eqReturns.push(Math.log(eqPrices[i] / eqPrices[i - 1]));
    bondReturns.push(-dur * (bondYields[i] - bondYields[i - 1]) / 100);
  }

  return { dates, eqReturns, bondReturns };
}

/**
 * Compute RP Forward Mechanical Pressure — Zero-Shock Decay Path.
 *
 * For each T+h, extends raw SPX and DGS10 with simulated data, then re-runs
 * the canonical buildAlignedReturns → computeRpSnapshot pipeline.
 *
 * Uses each observed leg where available; a missing leg is carried forward only
 * from information available on or before that target date. Never backfills a
 * missing earlier horizon with a later observation. Never uses LOCKED — RP has
 * no structural lag.
 *
 * @param {Array}  rawSpx    - Raw SPX price series [[date, priceOrObj], ...]
 * @param {Array}  rawDgs10  - Raw DGS10 yield series [[date, yield], ...]
 * @param {Array}  calendar  - Sorted array of trading dates (strings)
 * @param {object} [config]  - Override defaults
 * @returns {object}         - Forward pressure output with horizons array
 */
function computeRpForwardPressure(rawSpx, rawDgs10, calendar, config) {
  const cfg = { ...DEFAULT_CONFIG, ...config };
  const duration = cfg.bondDuration;

  if (!rawSpx || !rawDgs10 || !calendar || calendar.length === 0) {
    return { status: 'insufficient_data' };
  }

  // Build maps from raw data to determine last dates and real data coverage
  const spxMap = new Map();
  let spxLastDate = null;
  for (const pt of rawSpx) {
    const val = pt[1];
    if (val == null) continue;
    const price = typeof val === 'object' ? (val.adjClose || val.close) : val;
    if (price != null && !isNaN(price)) {
      spxMap.set(pt[0], price);
      if (!spxLastDate || pt[0] > spxLastDate) spxLastDate = pt[0];
    }
  }

  const dgs10Map = new Map();
  let dgs10LastDate = null;
  for (const pt of rawDgs10) {
    if (pt[1] != null && !isNaN(pt[1])) {
      dgs10Map.set(pt[0], pt[1]);
      if (!dgs10LastDate || pt[0] > dgs10LastDate) dgs10LastDate = pt[0];
    }
  }

  if (spxMap.size === 0 || dgs10Map.size === 0) return { status: 'insufficient_data' };

  // Current state (T+0) — canonical pipeline on real data
  const currentAligned = buildAlignedReturns(rawSpx, rawDgs10, duration);
  const baseLen = currentAligned.eqReturns.length;
  if (baseLen < Math.max(cfg.allocLookback, cfg.riskLookback)) {
    return { status: 'insufficient_data' };
  }
  const currentSnapshot = computeRpSnapshot(currentAligned.eqReturns, currentAligned.bondReturns, cfg);
  if (!currentSnapshot) return { status: 'insufficient_data' };

  const modelDate = currentAligned.dates[baseLen - 1];
  const modelSpxPrice = spxMap.get(modelDate);
  const modelDgs10Yield = dgs10Map.get(modelDate);
  if (!Number.isFinite(modelSpxPrice) || !Number.isFinite(modelDgs10Yield)) {
    return { status: 'insufficient_data' };
  }

  // Find 5 future trading dates after modelDate
  let calStartIdx = -1;
  for (let i = 0; i < calendar.length; i++) {
    if (calendar[i] > modelDate) { calStartIdx = i; break; }
  }
  if (calStartIdx < 0) return { status: 'insufficient_data' };

  const futureDates = [];
  for (let i = calStartIdx; i < calendar.length && futureDates.length < 5; i++) {
    futureDates.push(calendar[i]);
  }
  if (futureDates.length < 5) return { status: 'insufficient_data' };

  // Build FULL extended raw data through T+5 (all 5 future dates).
  // Missing observations are filled sequentially from the last value known as of
  // that date. This prevents a later observation from leaking backward into an
  // earlier PARTIAL_SCENARIO horizon.
  const fullExtSpx = [...rawSpx];
  const fullExtDgs10 = [...rawDgs10];
  let carrySpxPrice = modelSpxPrice;
  let carryDgs10Yield = modelDgs10Yield;

  for (let d = 0; d < 5; d++) {
    const date = futureDates[d];

    if (spxMap.has(date)) {
      carrySpxPrice = spxMap.get(date);
    } else {
      fullExtSpx.push([date, carrySpxPrice]);
    }

    if (dgs10Map.has(date)) {
      carryDgs10Yield = dgs10Map.get(date);
    } else {
      fullExtDgs10.push([date, carryDgs10Yield]);
    }
  }

  // Run canonical pipeline ONCE on fully extended data
  const fullAligned = buildAlignedReturns(fullExtSpx, fullExtDgs10, duration);
  const fullLen = fullAligned.eqReturns.length;

  // Verify extension produced enough data
  if (fullLen < baseLen + 5) {
    // Some future dates might not have aligned; compute what we can
  }

  // Compute snapshots for each horizon by slicing the full aligned arrays
  const computeHorizons = [1, 2, 3, 4, 5];
  const displayHorizonsSet = new Set([1, 2, 3, 5]);
  const horizonResults = [];

  let prevSnapshot = currentSnapshot;
  let prevLen = baseLen;

  for (const h of computeHorizons) {
    const hLen = baseLen + h;
    if (hLen > fullLen) {
      horizonResults.push({ horizon: h, status: 'insufficient_data' });
      continue;
    }

    const snapshot = computeRpSnapshot(
      fullAligned.eqReturns.slice(0, hLen),
      fullAligned.bondReturns.slice(0, hLen),
      cfg
    );

    if (!snapshot) {
      horizonResults.push({ horizon: h, status: 'insufficient_data' });
      continue;
    }

    // Certainty: based on whether the T+h date has real data
    const targetDate = futureDates[h - 1];
    const spxKnown = spxMap.has(targetDate);
    const bondKnown = dgs10Map.has(targetDate);
    let certaintyLevel, certaintySemantic;
    if (spxKnown && bondKnown) {
      certaintyLevel = 'OBSERVED';
      certaintySemantic = 'both_legs_observed';
    } else if (spxKnown) {
      certaintyLevel = 'PARTIAL_SCENARIO';
      certaintySemantic = 'equity_observed_bond_assumed';
    } else if (bondKnown) {
      certaintyLevel = 'PARTIAL_SCENARIO';
      certaintySemantic = 'bond_observed_equity_assumed';
    } else {
      certaintyLevel = 'SCENARIO';
      certaintySemantic = 'both_assumed';
    }

    // Cumulative deltas vs model state (T+0)
    const leverageDeltaFromCurrent = snapshot.targetLeverage - currentSnapshot.targetLeverage;
    const eqExpDeltaFromCurrent = snapshot.eqGrossExposure - currentSnapshot.eqGrossExposure;
    const bondExpDeltaFromCurrent = snapshot.bondGrossExposure - currentSnapshot.bondGrossExposure;

    // Daily deltas vs previous horizon (T+h vs T+h-1)
    const dailyLeverageDelta = prevSnapshot ? snapshot.targetLeverage - prevSnapshot.targetLeverage : null;
    const dailyEqExpDelta = prevSnapshot ? snapshot.eqGrossExposure - prevSnapshot.eqGrossExposure : null;
    const dailyBondExpDelta = prevSnapshot ? snapshot.bondGrossExposure - prevSnapshot.bondGrossExposure : null;

    let dailyPressureDirection = 'neutral';
    if (dailyLeverageDelta != null) {
      if (dailyLeverageDelta > 0.01) dailyPressureDirection = 'leveraging';
      else if (dailyLeverageDelta < -0.01) dailyPressureDirection = 'deleveraging';
    }

    // Portfolio risk decomposition vs previous
    let portfolioVolDirection = 'stable';
    let correlationDirection = 'stable';
    let diversificationStatus = 'stable';
    if (prevSnapshot) {
      const volDelta = snapshot.portfolioVol - prevSnapshot.portfolioVol;
      if (volDelta < -0.001) portfolioVolDirection = 'falling';
      else if (volDelta > 0.001) portfolioVolDirection = 'rising';

      const corrDelta = snapshot.stockBondCorrelation - prevSnapshot.stockBondCorrelation;
      if (corrDelta < -0.01) { correlationDirection = 'decreasing'; diversificationStatus = 'improving'; }
      else if (corrDelta > 0.01) { correlationDirection = 'increasing'; diversificationStatus = 'deteriorating'; }
    }

    // Roll-off analysis: 20D allocation window
    const allocRollOff = analyzeRpWindowRollOff(fullAligned, prevLen, hLen, cfg.allocLookback);
    // Roll-off analysis: 60D risk/covariance window
    const riskRollOff = analyzeRpWindowRollOff(fullAligned, prevLen, hLen, cfg.riskLookback);

    // Explanation
    let explanation = null;
    if (dailyLeverageDelta != null && Math.abs(dailyLeverageDelta) > 0.005) {
      const volLabel = portfolioVolDirection === 'falling' ? 'portfolio vol falling' :
                       portfolioVolDirection === 'rising' ? 'portfolio vol rising' : 'portfolio vol stable';
      const levLabel = dailyLeverageDelta > 0 ? 'target leverage rising' : 'target leverage falling';
      const parts = [volLabel + ' → ' + levLabel];
      if (correlationDirection !== 'stable') {
        parts.push('stock-bond correlation ' + correlationDirection);
      }
      explanation = parts.join(' | ');
    }

    horizonResults.push({
      horizon: h,
      label: `T+${h}`,
      targetDate,
      certaintyLevel,
      certaintySemantic,

      targetLeverage: round4(snapshot.targetLeverage),
      equityWeight: round4(snapshot.equityWeight),
      bondWeight: round4(snapshot.bondWeight),
      equityExposure: round4(snapshot.eqGrossExposure),
      bondExposure: round4(snapshot.bondGrossExposure),
      portfolioVol: round4(snapshot.portfolioVol),
      prevPortfolioVol: prevSnapshot ? round4(prevSnapshot.portfolioVol) : null,
      equityAllocVol: round4(snapshot.equityAllocVol),
      bondAllocVol: round4(snapshot.bondAllocVol),
      stockBondCorrelation: round4(snapshot.stockBondCorrelation),
      prevCorrelation: prevSnapshot ? round4(prevSnapshot.stockBondCorrelation) : null,

      // Cumulative vs model state (T+0)
      leverageDeltaFromCurrent: round4(leverageDeltaFromCurrent),
      eqExposureDeltaFromCurrent: round4(eqExpDeltaFromCurrent),
      bondExposureDeltaFromCurrent: round4(bondExpDeltaFromCurrent),

      // Daily mechanical flow (T+h vs T+h-1)
      dailyLeverageDelta: round4(dailyLeverageDelta),
      dailyEqExposureDelta: round4(dailyEqExpDelta),
      dailyBondExposureDelta: round4(dailyBondExpDelta),
      dailyPressureDirection,

      // Risk decomposition
      portfolioVolDirection,
      correlationDirection,
      diversificationStatus,

      // Two-layer roll-off
      allocRollOff,
      riskRollOff,

      explanation
    });

    // Update previous for next iteration
    prevSnapshot = snapshot;
    prevLen = hLen;
  }

  // Dominant signal — uses all 5 computed horizons (including hidden T+4)
  let dominantSignal = 'neutral_under_zero_return_path';
  const validHorizons = horizonResults.filter(h => h.dailyLeverageDelta != null);
  if (validHorizons.length > 0) {
    const avgDailyLev = validHorizons.reduce((s, h) => s + h.dailyLeverageDelta, 0) / validHorizons.length;
    if (avgDailyLev > 0.005) dominantSignal = 'mechanical_leveraging_under_zero_return_path';
    else if (avgDailyLev < -0.005) dominantSignal = 'mechanical_deleveraging_under_zero_return_path';
  }

  // Filter to display horizons (T+4 computed but hidden)
  const displayResults = horizonResults.filter(h => displayHorizonsSet.has(h.horizon));

  return {
    status: 'ok',
    currentTargetLeverage: round4(currentSnapshot.targetLeverage),
    currentPortfolioVol: round4(currentSnapshot.portfolioVol),
    currentCorrelation: round4(currentSnapshot.stockBondCorrelation),
    currentEqExposure: round4(currentSnapshot.eqGrossExposure),
    currentBondExposure: round4(currentSnapshot.bondGrossExposure),
    modelDate,
    spxLastDate,
    dgs10LastDate,
    horizons: displayResults,
    dominantForwardSignal: dominantSignal,
    methodology: 'Zero-shock decay path with chronological carry-forward only: observed legs are used when available; missing legs assume zero shock from the latest value known as of that date. Re-runs canonical buildAlignedReturns → computeRpSnapshot per horizon.',
    disclaimer: 'Reduced 2-asset RP proxy. PARTIAL_SCENARIO uses the observed leg plus a flat assumed missing leg. SCENARIO assumes both legs flat. NOT a market forecast.'
  };
}

/**
 * Analyze which returns drop off a rolling window when stepping from prevLen to currLen.
 *
 * For a window of size W:
 *   Previous window: aligned[prevLen - W .. prevLen - 1]
 *   Current window:  aligned[currLen - W .. currLen - 1]
 *   Dropped indices: [prevLen - W .. currLen - W - 1]
 *
 * @param {object} fullAligned - Full aligned data (dates, eqReturns, bondReturns)
 * @param {number} prevLen     - Return array length at previous horizon
 * @param {number} currLen     - Return array length at current horizon
 * @param {number} windowSize  - Rolling window size (20 for alloc, 60 for risk)
 * @returns {object}           - { primaryEq, primaryBond, droppedCount }
 */
function analyzeRpWindowRollOff(fullAligned, prevLen, currLen, windowSize) {
  if (prevLen < windowSize || currLen < windowSize) {
    return { primaryEq: null, primaryBond: null, droppedCount: 0 };
  }

  const dropStart = prevLen - windowSize;
  const dropEnd = currLen - windowSize - 1; // last index that drops off

  const droppedEq = [];
  const droppedBond = [];

  for (let i = dropStart; i <= dropEnd; i++) {
    if (i >= 0 && i < fullAligned.eqReturns.length) {
      droppedEq.push({
        date: fullAligned.dates[i],
        returnPct: Number((fullAligned.eqReturns[i] * 100).toFixed(3))
      });
      droppedBond.push({
        date: fullAligned.dates[i],
        returnPct: Number((fullAligned.bondReturns[i] * 100).toFixed(3))
      });
    }
  }

  const primaryEq = droppedEq.length > 0
    ? droppedEq.reduce((best, cur) => Math.abs(cur.returnPct) > Math.abs(best.returnPct) ? cur : best)
    : null;
  const primaryBond = droppedBond.length > 0
    ? droppedBond.reduce((best, cur) => Math.abs(cur.returnPct) > Math.abs(best.returnPct) ? cur : best)
    : null;

  return { primaryEq, primaryBond, droppedCount: droppedEq.length };
}

module.exports = {
  computeRpSnapshot,
  computeRpMechanicalPressure,
  computeRpForwardPressure,
  buildAlignedReturns,
  DEFAULT_CONFIG,
  // Export internals for testing
  _stddev: stddev,
  _covarianceMatrix: covarianceMatrix,
};
