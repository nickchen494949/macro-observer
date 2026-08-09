// /Users/happygolucky/Desktop/宏观观察器/lib/rp_mechanical.js
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

module.exports = {
  computeRpSnapshot,
  computeRpMechanicalPressure,
  buildAlignedReturns,
  DEFAULT_CONFIG,
  // Export internals for testing
  _stddev: stddev,
  _covarianceMatrix: covarianceMatrix,
};
