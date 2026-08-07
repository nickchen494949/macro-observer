const fs = require('fs');
const path = require('path');

let rules = null;
try {
  const rulesPath = path.join(__dirname, '../config/horizon_rules.json');
  rules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
} catch (e) {
  // Fallback or mock for tests if needed
}

/**
 * Calculate multi-horizon trend for an indicator.
 * 
 * Two modes:
 * 1. RAW SERIES mode (for level/price indicators like rates, stocks):
 *    Computes changes directly from the time series.
 *    
 * 2. PRE-COMPUTED mode (for transformed indicators like YoY, MoM):
 *    Uses the pre-computed changes map from calcMetrics() because
 *    raw FRED data is index levels, not the derived transform.
 *
 * @param {Object} options
 * @param {Array} options.series - Raw time series [[date, value], ...]
 * @param {string} options.type - Materiality filter type: 'rates', 'equities', 'commodities', 'flows', 'nowcast'
 * @param {string} options.frequency - Frequency bucket: 'daily_markets', 'weekly', 'monthly_macro', 'quarterly_macro'
 * @param {string} options.transformation - How raw data is transformed: 'level', 'yoy', 'mom_abs', 'mom_pct'
 * @param {number} [options.horizonScale=1] - Multiplier to convert raw diff to threshold units (e.g. 100 for % → bp)
 * @param {Object} [options.changes] - Pre-computed changes from calcMetrics: { '1d': x, '1w': x, '1m': x, '1q': x, '6m': x, '1y': x }
 * @param {number} [options.current] - Current display value (after transformation)
 */
function calculateTrend(options) {
  if (!rules) throw new Error('Rules not loaded');
  
  // Support old call signature: calculateTrend(series, type, frequency)
  let series, type, frequency, transformation, horizonScale, changes, current;
  if (Array.isArray(options)) {
    // Legacy call: calculateTrend(series, type, frequency)
    series = options;
    type = arguments[1];
    frequency = arguments[2];
    transformation = 'level';
    horizonScale = 1;
    changes = null;
    current = null;
  } else {
    series = options.series;
    type = options.type;
    frequency = options.frequency;
    transformation = options.transformation || 'level';
    horizonScale = options.horizonScale || 1;
    changes = options.changes || null;
    current = options.current;
  }

  const freqRules = rules.frequencies[frequency];
  const matRules = rules.materialityFilters[type];
  
  if (!freqRules || !matRules) {
    return {
      shortTerm: 'insufficient',
      mediumTerm: 'insufficient',
      longTerm: 'insufficient',
      coherence: 'insufficient_data',
      _debug: { error: `Invalid frequency '${frequency}' or type '${type}'` }
    };
  }

  const result = {
    shortTerm: 'insufficient',
    mediumTerm: 'insufficient',
    longTerm: 'insufficient',
    coherence: 'insufficient_data',
    _debug: {}
  };

  // ==========================================================
  // MODE 1: Use pre-computed changes (for YoY, MoM transforms)
  // ==========================================================
  if (transformation !== 'level' && changes) {
    // Map frequency buckets to pre-computed change keys
    const bucketMap = {
      daily_markets: { short: '1w', medium: '1m', long: '6m' },
      weekly:        { short: '1m', medium: '1q', long: '1y' },
      monthly_macro: { short: '1m', medium: '1q', long: '1y' },
      quarterly_macro: { short: '1q', medium: '6m', long: '1y' }
    };
    
    const mapping = bucketMap[frequency];
    if (!mapping) return result;
    
    const evaluateFromChanges = (changeKey, threshold) => {
      const val = changes[changeKey];
      if (val == null) return 'insufficient';
      
      // changes are already in display units — apply horizonScale for unit conversion
      const scaled = val * horizonScale;
      
      result._debug[changeKey] = { raw: val, scaled, threshold };
      
      if (scaled > threshold) return 'rising';
      if (scaled < -threshold) return 'falling';
      return 'neutral';
    };
    
    result.shortTerm = evaluateFromChanges(mapping.short, matRules.thresholds.shortTerm);
    result.mediumTerm = evaluateFromChanges(mapping.medium, matRules.thresholds.mediumTerm);
    result.longTerm = evaluateFromChanges(mapping.long, matRules.thresholds.longTerm);
    
  } else {
    // ==========================================================
    // MODE 2: Compute from raw series (for level indicators)
    // ==========================================================
    const getVal = (s, offset) => {
      if (s.length <= offset) return null;
      return s[s.length - 1 - offset][1];
    };

    const currentVal = getVal(series, 0);
    if (currentVal === null) return result;

    const evaluate = (offset, threshold, calcType) => {
      const past = getVal(series, offset);
      if (past === null) return 'insufficient';
      
      let diff = 0;
      if (calcType === 'pct') {
        diff = ((currentVal - past) / Math.abs(past)) * 100;
      } else if (calcType === 'bp') {
        // Data in % → threshold in bp → multiply by 100
        diff = (currentVal - past) * 100;
      } else if (calcType === 'abs' || calcType === 'pct_point') {
        diff = (currentVal - past) * horizonScale;
      }

      result._debug[`offset_${offset}`] = { current: currentVal, past, diff, threshold };

      if (diff > threshold) return 'rising';
      if (diff < -threshold) return 'falling';
      return 'neutral';
    };

    const calcType = matRules.unit;
    result.shortTerm = evaluate(freqRules.shortTerm, matRules.thresholds.shortTerm, calcType);
    result.mediumTerm = evaluate(freqRules.mediumTerm, matRules.thresholds.mediumTerm, calcType);
    result.longTerm = evaluate(freqRules.longTerm, matRules.thresholds.longTerm, calcType);
  }

  // ==========================================================
  // Coherence classification
  // ==========================================================
  const trends = [result.shortTerm, result.mediumTerm, result.longTerm];
  const risingCount = trends.filter(t => t === 'rising').length;
  const fallingCount = trends.filter(t => t === 'falling').length;
  const neutralCount = trends.filter(t => t === 'neutral').length;
  const insufficientCount = trends.filter(t => t === 'insufficient').length;

  if (insufficientCount > 0) {
    result.coherence = 'insufficient_data';
  } else if (neutralCount === 3) {
    result.coherence = 'stable';
  } else if (risingCount === 3) {
    result.coherence = 'confirmed_uptrend';
  } else if (fallingCount === 3) {
    result.coherence = 'confirmed_downtrend';
  } else if (risingCount > 0 && fallingCount === 0) {
    // 2 rising + 1 neutral, or 1 rising + 2 neutral
    result.coherence = risingCount >= 2 ? 'upward_bias' : 'stable';
  } else if (fallingCount > 0 && risingCount === 0) {
    // 2 falling + 1 neutral, or 1 falling + 2 neutral
    result.coherence = fallingCount >= 2 ? 'downward_bias' : 'stable';
  } else if (risingCount > 0 && fallingCount > 0) {
    result.coherence = 'horizon_divergence';
  } else {
    result.coherence = 'mixed';
  }

  return result;
}

module.exports = { calculateTrend, _setRules: r => rules = r };
