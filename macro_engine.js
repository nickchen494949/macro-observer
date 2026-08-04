const CLUSTER_REGISTRY = {};

// ============================================
// HELPER FUNCTIONS
// ============================================
const SIMPLE_CLUSTERS = [
  // Recession
  { id: 'layoffs', indicators: [{ id: 'initial_claims', bad: (v)=>v>250, good: (v)=>v<220, w:1 }, { id: 'continuing_claims', bad: (v)=>v>1900, good: (v)=>v<1700, w:1 }] },
  { id: 'hours', indicators: [{ id: 'agg_weekly_hours_yoy', bad: (v)=>v< -1.0, good: (v)=>v>0, w:1 }, { id: 'mfg_pns_avg_weekly_hrs', bad: (v)=>v<39.8, good: (v)=>v>40.2, w:1 }] },
  { id: 'income', indicators: [{ id: 'real_income_yoy', bad: (v)=>v<1.0, good: (v)=>v>2.5, w:1 }] },
  { id: 'demand', indicators: [{ id: 'real_pce_mom', bad: (v)=>v<0.1, good: (v)=>v>0.3, w:1 }, { id: 'retail_sales_control_mom', bad: (v)=>v<0.1, good: (v)=>v>0.4, w:1 }] },
  { id: 'production', indicators: [{ id: 'industrial_production_yoy', bad: (v)=>v< -1.0, good: (v)=>v>1.0, w:1 }] },
  { id: 'investment', indicators: [{ id: 'core_capex_orders_yoy_nsa', bad: (v)=>v<0, good: (v)=>v>3.0, w:1 }] },
  { id: 'sentiment', indicators: [{ id: 'consumer_sentiment', bad: (v)=>v<65, good: (v)=>v>75, w:1 }] },
  { id: 'output', indicators: [{ id: 'atlanta_fed_gdpnow', bad: (v)=>v<1.5, good: (v)=>v>2.5, w:1 }] },
  
  // Inflation
  { id: 'trend_inflation', indicators: [{ id: 'core_pce_yoy', bad: (v)=>v>2.8, good: (v)=>v<2.2, w:1 }] },
  { id: 'inflation_breadth', indicators: [{ id: 'median_cpi_yoy', bad: (v)=>v>3.5, good: (v)=>v<2.5, w:1 }, { id: 'trimmed_cpi_yoy', bad: (v)=>v>3.0, good: (v)=>v<2.2, w:1 }] },
  { id: 'wages', indicators: [{ id: 'avg_hourly_wage_yoy', bad: (v)=>v>4.5, good: (v)=>v<3.5, w:1 }] },
  { id: 'cost_push', indicators: [{ id: 'import_prices_yoy', bad: (v)=>v>3.0, good: (v)=>v<0, w:1 }, { id: 'ppi_final_demand_yoy', bad: (v)=>v>3.0, good: (v)=>v<1.5, w:1 }, { id: 'cpi_core_goods_yoy', bad: (v)=>v>2.5, good: (v)=>v<1.0, w:1 }] },
  { id: 'housing_inflation', indicators: [{ id: 'cpi_housing_yoy', bad: (v)=>v>5.0, good: (v)=>v<3.0, w:1 }] },
  { id: 'market_exp', indicators: [{ id: '10y_breakeven_inflation', bad: (v)=>v>2.5, good: (v)=>v<2.0, w:1 }, { id: '5y5y_inflation_forward', bad: (v)=>v>2.5, good: (v)=>v<2.0, w:1 }] },

  // Credit
  { id: 'lending_standards', indicators: [{ id: 'sloos_ci_standards', bad: (v)=>v>5, good: (v)=>v<=0, w:1, labelGood: 'Standards unchanged/easing' }, { id: 'sloos_small_biz_standards', bad: (v)=>v>5, good: (v)=>v<=0, w:1, labelGood: 'Small biz standards unchanged' }] },
  { id: 'lending_demand', indicators: [{ id: 'sloos_ci_demand', bad: (v)=>v< -15, good: (v)=>v> -5, w:1, labelGood: 'Demand strengthening/stable' }] },
  { id: 'credit_pricing', indicators: [{ id: '-_hy-ig', bad: (v)=>v>400, good: (v)=>v<250, w:1 }] },
  { id: 'bank_lending', indicators: [{ id: 'ci_loans_yoy', bad: (v)=>v<0, good: (v)=>v>3.0, w:1 }, { id: 'consumer_loans_yoy', bad: (v)=>v<0, good: (v)=>v>3.0, w:1 }] },
  { id: 'broad_fincon', indicators: [{ id: 'chicago_fed_nfci', bad: (v)=>v>0.5, good: (v)=>v<0, w:1 }] },
  { id: 'credit_damage', indicators: [
    { id: 'cc_delinquency_rate', bad: (v)=>v>4.0, good: (v)=>v<3.0, w:1, label: 'CC Delinquency' }, 
    { id: 'mortgage_delinquency_rate', bad: (v)=>v>4.0, good: (v)=>v<2.0, w:1, label: 'Mortgage Delinquency' },
    { id: 'charge_offs', bad: (v)=>v>1.0, good: (v)=>v<0.5, w:1, label: 'Charge-offs' },
    { id: 'bank_equity_stress', bad: (v)=>v>10, good: (v)=>v<5, w:1, label: 'Bank Equity Stress' }
  ] },

  // Long-End
  { id: 'supply_pressure', indicators: [{ id: 'treasury_net_issuance', bad: (v)=>v>500, good: (v)=>v<200, w:1, label: 'Treasury Net Issuance' }] },
  { id: 'term_premium', indicators: [{ id: '10y_acm_term_premium_model_est', bad: (v)=>v>0.6, good: (v)=>v<0.3, w:1 }] },
  { id: 'real_financing', indicators: [{ id: 'tip_yield_10y_tips', bad: (v)=>v>2.2, good: (v)=>v<1.5, w:1 }] },
  { id: 'fiscal_sustainability', indicators: [{ id: 'federal_interest_exp_gdp', bad: (v)=>v>3.5, good: (v)=>v<2.5, w:1 }, { id: 'federal_interest_exp_receipts', bad: (v)=>v>15, good: (v)=>v<10, w:1 }] },

  // Liquidity
  { id: 'funding_stress', indicators: [{ id: 'sofr-iorb', bad: (v)=>v>10, good: (v)=>v<=5, w:1 }] },
  { id: 'bank_liquidity', indicators: [{ id: 'bank_reserves', bad: (v)=>v<2800, good: (v)=>v>3200, w:1 }] },
  { id: 'liquidity_damage', indicators: [
    { id: 'repo_fails', bad: (v)=>v>1, good: (v)=>v<0, w:1, label: 'Repo Fails' },
    { id: 'srf_usage', bad: (v)=>v>1, good: (v)=>v<0, w:1, label: 'SRF Usage' }
  ] },

  
  // Valuation
  { id: 'valuation', indicators: [
    { id: 'SP500_PE', bad: (v)=>v>22, good: (v)=>v<18, w:1 },
    { id: 'SHILLER_CAPE', bad: (v)=>v>30, good: (v)=>v<25, w:1 },
    { id: 'SP500_EPS_GROWTH', bad: (v)=>v<5, good: (v)=>v>10, w:1 }
  ] },
  { id: 'asset_transmission', indicators: [{ id: 'tip_yield_10y_tips', bad: (v)=>v>2.0, good: (v)=>v<1.5, w:1 }, { id: '-_hy-ig', bad: (v)=>v>400, good: (v)=>v<250, w:1 }] }
];

function buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate = null) {
  if (maxScore === 0) return { status: 'unknown', score: 0, value: null, coverage: 0, confidence: 0, freshnessDays: null, obsDate: null, evidence: ev, counterEvidence: cev, missing: miss };
  const ratio = score / maxScore;
  let status = 'yellow';
  if (ratio >= 0.7) status = 'red';
  else if (ratio <= 0.3) status = 'green';

  let coverage = 100 - (miss.length * 15);
  if (coverage < 0) coverage = 0;
  
  let conflictPenalty = 0;
  if (ev.length > 0 && cev.length > 0) {
    conflictPenalty = 40; 
  }
  
  let conf = coverage - conflictPenalty;
  if (conf < 0) conf = 0;

  return { status, score: ratio, value: ratio, coverage, confidence: conf, freshnessDays: latestDay, obsDate, evidence: ev, counterEvidence: cev, missing: miss };
}

SIMPLE_CLUSTERS.forEach(sc => {
  CLUSTER_REGISTRY[sc.id] = {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;

      for (const ind of sc.indicators) {
        const d = dataMap.get(ind.id);
        if (d && d.current !== null) {
          maxScore += ind.w;
          latestDay = Math.min(latestDay || 999, d.daysSinceObs);
          if (!obsDate || d.lastObsDate > obsDate) obsDate = d.lastObsDate;
          
          if (ind.bad(d.current)) {
            score += ind.w;
            ev.push(`${d.label} bad (${d.current.toFixed?d.current.toFixed(1):d.current})`);
          } else if (ind.good(d.current)) {
            cev.push(ind.labelGood ? ind.labelGood : `${d.label} good (${d.current.toFixed?d.current.toFixed(1):d.current})`);
          } else {
            score += ind.w * 0.5;
          }
        } else {
          miss.push(ind.label || d?.label || ind.id);
        }
      }

      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  };
});

// ============================================
// CUSTOM CLUSTERS
// ============================================
Object.assign(CLUSTER_REGISTRY, {
  hiring: {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;

      const main = dataMap.get('private_payrolls_mom');
      if (main && main.current !== null) {
        maxScore += 4;
        latestDay = main.daysSinceObs;
        obsDate = main.lastObsDate;
        if (main.current < 100) { score += 4; ev.push(`Private Payrolls weak (+${Math.round(main.current)}k)`); }
        else if (main.current > 200) { cev.push(`Private Payrolls solid (+${Math.round(main.current)}k)`); }
        else { score += 2; }
      } else { miss.push('Private Payrolls'); }

      const ref = dataMap.get('nfp_mom');
      if (ref && ref.current !== null) {
        if (!obsDate || ref.lastObsDate > obsDate) obsDate = ref.lastObsDate;
        if (ref.current < 100) ev.push(`NFP confirms weak (+${Math.round(ref.current)}k)`);
        else if (ref.current > 200) cev.push(`NFP solid (+${Math.round(ref.current)}k)`);
      }

      const auxCheck = (id, badThresh, goodThresh, name) => {
        const d = dataMap.get(id);
        if (d && d.current !== null) {
          maxScore += 1;
          if (!obsDate || d.lastObsDate > obsDate) obsDate = d.lastObsDate;
          if (d.current <= badThresh) { score += 1; ev.push(`${name} weak`); }
          else if (d.current >= goodThresh) { cev.push(`${name} strong`); }
          else { score += 0.5; }
        } else {
          miss.push(id);
        }
      };

      auxCheck('temp_help_employment_yoy', -1.0, 1.0, 'Temp Help');
      auxCheck('jolts_openings', 7.5, 8.5, 'JOLTS'); 
      auxCheck('quits_rate', 2.0, 2.3, 'Quits');

      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  },

  unemployment: {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;

      const sahm = dataMap.get('sahm_rule');
      if (sahm && sahm.current !== null) {
        maxScore += 2;
        latestDay = sahm.daysSinceObs;
        obsDate = sahm.lastObsDate;
        if (sahm.current >= 0.5) { score += 2; ev.push(`Sahm Rule Triggered (${sahm.current}pp)`); }
        else if (sahm.current >= 0.3) { score += 1; ev.push(`Sahm Rule Elevated (${sahm.current}pp)`); }
        else { cev.push(`Sahm Rule safe (${sahm.current}pp)`); }
      } else { miss.push('Sahm Rule'); }

      const unrate = dataMap.get('unemployment');
      if (unrate && unrate.current !== null) {
        maxScore += 1;
        latestDay = Math.min(latestDay || 999, unrate.daysSinceObs);
        if (!obsDate || unrate.lastObsDate > obsDate) obsDate = unrate.lastObsDate;
        if (unrate.current >= 4.4) { score += 1; ev.push(`Unemployment High (${unrate.current}%)`); }
        else if (unrate.current <= 4.2) { cev.push(`Unemployment Low (${unrate.current}%)`); }
        else { score += 0.5; }
      } else { miss.push('Unemployment'); }

      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  },

  inflationMomentum: {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;

      const pce3m = dataMap.get('core_pce_3m_ann');
      if (pce3m && pce3m.current !== null) {
        maxScore += 3;
        latestDay = pce3m.daysSinceObs;
        obsDate = pce3m.lastObsDate;
        if (pce3m.current >= 3.5) { score += 3; ev.push(`PCE 3M Hot (${pce3m.current.toFixed(1)}%)`); }
        else if (pce3m.current <= 2.5) { cev.push(`PCE 3M Cool (${pce3m.current.toFixed(1)}%)`); }
        else { score += 1.5; }
      } else { miss.push('Core PCE 3M Ann'); }

      const pce6m = dataMap.get('core_pce_6m_ann');
      if (pce6m && pce6m.current !== null) {
        maxScore += 2;
        if (!obsDate || pce6m.lastObsDate > obsDate) obsDate = pce6m.lastObsDate;
        latestDay = Math.min(latestDay || 999, pce6m.daysSinceObs);
        if (pce6m.current > 3.0) { score += 2; ev.push(`PCE 6M Hot (${pce6m.current.toFixed(1)}%)`); }
        else if (pce6m.current < 2.2) { cev.push(`PCE 6M Cool (${pce6m.current.toFixed(1)}%)`); }
        else { score += 1; }
      } else { miss.push('Core PCE 6M Ann'); }

      const cMed = dataMap.get('median_cpi_1m_ann');
      if (cMed && cMed.current !== null) {
        maxScore += 1;
        if (!obsDate || cMed.lastObsDate > obsDate) obsDate = cMed.lastObsDate;
        if (cMed.current >= 4.0) { score += 1; ev.push(`Median CPI 1M Ann High`); }
        else if (cMed.current <= 2.5) { cev.push(`Median CPI 1M Ann Low`); }
        else { score += 0.5; }
      } else { miss.push('Median CPI 1M Ann'); }

      const cTrim = dataMap.get('trimmed_cpi_1m_ann');
      if (cTrim && cTrim.current !== null) {
        maxScore += 1;
        if (!obsDate || cTrim.lastObsDate > obsDate) obsDate = cTrim.lastObsDate;
        if (cTrim.current >= 3.5) { score += 1; ev.push(`16% Trimmed CPI 1M Ann High`); }
        else if (cTrim.current <= 2.2) { cev.push(`16% Trimmed CPI 1M Ann Low`); }
        else { score += 0.5; }
      } else { miss.push('Trimmed CPI 1M Ann'); }

      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  },

  reserve_supply_drivers: {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;

      const rrp = dataMap.get('rrp_overnight');
      if (rrp && rrp.current !== null) {
        maxScore += 1;
        latestDay = rrp.daysSinceObs;
        obsDate = rrp.lastObsDate;
        if (rrp.current < 200) { 
           score += 0.5; ev.push(`RRP Buffer limited (${Math.round(rrp.current)}B)`); 
        } else if (rrp.current > 500) {
          cev.push(`RRP absorbing shocks (${Math.round(rrp.current)}B)`); 
        } else {
          score += 0;
        }
      } else { miss.push('RRP Buffer'); }

      const tga = dataMap.get('tga_balance');
      if (tga && tga.current !== null) {
        maxScore += 1;
        latestDay = Math.min(latestDay || 999, tga.daysSinceObs);
        if (!obsDate || tga.lastObsDate > obsDate) obsDate = tga.lastObsDate;
        const tgaChg = tga.changes && tga.changes['1m'] ? tga.changes['1m'] : 0;
        if (tgaChg > 50) { score += 1; ev.push(`TGA Drain (+${Math.round(tgaChg)}B 1M)`); }
        else if (tgaChg < -50) { cev.push(`TGA Inject (${Math.round(tgaChg)}B 1M)`); }
        else { score += 0.5; }
      } else { miss.push('TGA Balance'); }

      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  },

  curve_steepness: {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;
      
      const rate10y = dataMap.get('10y');
      const spread = dataMap.get('03m-10y_spread');
      if (rate10y && rate10y.current !== null && spread && spread.current !== null) {
        maxScore += 2;
        latestDay = rate10y.daysSinceObs;
        obsDate = rate10y.lastObsDate;
        
        const chg10y = rate10y.changes?.['1M'] || 0;
        
        if (chg10y > 0.3) {
          score += 2;
          ev.push(`Bear Steepening: 10Y up ${Math.round(chg10y*100)}bp`);
        } else if (chg10y < -0.3) {
          cev.push(`10Y down ${Math.round(chg10y*100)}bp`);
        } else {
          score += 1;
        }
      } else {
        miss.push('10Y Yield'); miss.push('3M-10Y Spread');
      }
      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  },

  asset_damage: {
    aggregator: (dataMap) => {
      let score = 0, maxScore = 0;
      let ev = [], cev = [], miss = [];
      let latestDay = null;
      let obsDate = null;
      const vix = dataMap.get('^vix');
      if (vix && vix.current !== null) {
        maxScore += 1;
        latestDay = vix.daysSinceObs;
        obsDate = vix.lastObsDate;
        if (vix.current > 30) { score += 1; ev.push(`VIX High (${vix.current.toFixed(1)})`); }
        else if (vix.current < 15) { cev.push(`VIX Low (${vix.current.toFixed(1)})`); }
        else { score += 0.5; }
      } else {
        miss.push('VIX');
      }
      miss.push('Market Breadth');
      return buildOutput(score, maxScore, latestDay, ev, cev, miss, obsDate);
    }
  }

});

// ============================================
// AGGREGATOR ENGINE
// ============================================
function aggregateStages(clusterResults, overrideStatus = null) {
  const totalClusters = clusterResults.length;
  let validClusters = clusterResults.filter(c => c && c.status !== 'unknown');
  if (totalClusters === 0 || validClusters.length === 0) return { status: 'unknown', evidence: [], counterEvidence: [], missing: clusterResults.filter(c => c).flatMap(c => c.missing || []), coverage:0, confidence:0, obsDate: null };
  
  const avgScoreRaw = validClusters.reduce((sum, c) => sum + c.score, 0) / validClusters.length;
  
  let status = overrideStatus;
  if (!status) {
    status = 'yellow';
    if (avgScoreRaw >= 0.7) status = 'red';
    else if (avgScoreRaw <= 0.3) status = 'green';
  }

  const evidence = validClusters.flatMap(c => c.evidence);
  const counterEvidence = validClusters.flatMap(c => c.counterEvidence);
  
  const avgCovRaw = clusterResults.reduce((sum, c) => sum + (c && c.coverage ? c.coverage : 0), 0) / totalClusters;
  const avgConfRaw = validClusters.reduce((sum, c) => sum + (c.confidence || 0), 0) / totalClusters;
  
  const hasRed = validClusters.some(c => c.status === 'red');
  const hasGreen = validClusters.some(c => c.status === 'green');
  const stageConflictPenalty = (hasRed && hasGreen) ? 20 : 0;
  
  let finalConf = avgConfRaw - stageConflictPenalty;
  if (finalConf < 0) finalConf = 0;
  
  const obsDates = validClusters.map(c => c.obsDate).filter(d => d !== null);
  const maxObs = obsDates.length > 0 ? obsDates.reduce((a,b) => a > b ? a : b) : null;
  const allMissing = [...new Set(clusterResults.flatMap(c => c && c.missing ? c.missing : []))];

  return { status, score: avgScoreRaw, evidence, counterEvidence, missing: allMissing, coverage: Math.round(avgCovRaw), confidence: Math.round(finalConf), obsDate: maxObs };
}

function evaluateDiagnostics(allDataList) {
  const dataMap = new Map(allDataList.map(d => [d.id, d]));
  
  const clusters = {};
  for (const [key, clusterDef] of Object.entries(CLUSTER_REGISTRY)) {
    clusters[key] = clusterDef.aggregator(dataMap);
  }

  // 1. Demand Recession
  const recession = {
    question: "Demand-driven Recession (需求型衰退)",
    stages: [
      { name: "Pressure", ...aggregateStages([clusters.hours, clusters.hiring, clusters.layoffs, clusters.investment, clusters.sentiment]) },
      { name: "Transmission", ...aggregateStages([clusters.income]) },
      { name: "Damage", ...aggregateStages([clusters.demand, clusters.production, clusters.unemployment, clusters.output]) }
    ]
  };
  
  // Cap Recession confidence if signals are diverging (e.g., Pressure is yellow/red but Damage is green)
  if (recession.stages[0].score > 0.3 && recession.stages[2].score <= 0.3) {
    recession.stages.forEach(s => s.confidence = Math.min(s.confidence, 60)); // Medium
  }

  // 2. Inflation Dynamics
  const inflation = {
    question: "Inflation Dynamics (通胀动态)",
    stages: [
      { name: "Level (水平)", ...aggregateStages([clusters.trend_inflation, clusters.housing_inflation, clusters.inflation_breadth]) },
      { name: "Direction (方向)", ...aggregateStages([clusters.inflationMomentum, clusters.cost_push]) },
      { name: "Transmission (传导)", ...(() => {
        const res = aggregateStages([clusters.wages, clusters.market_exp]);
        if (res.evidence.length === 0 && res.counterEvidence.length === 0) {
          const w = allDataList.find(d => d.id === 'avg_hourly_wage_yoy')?.current;
          const u = allDataList.find(d => d.id === 'unit_labor_cost_yoy')?.current;
          const b = allDataList.find(d => d.id === '10y_breakeven_inflation')?.current;
          const f = allDataList.find(d => d.id === '5y5y_inflation_forward')?.current;
          res.counterEvidence = [`Transmission limited: wages moderate (${w ? w.toFixed(2) : '—'}%), ULC low (${u ? u.toFixed(2) : '—'}%), expectations anchored (BE ${b ? b.toFixed(2) : '—'}%, 5Y5Y ${f ? f.toFixed(2) : '—'}%)`];
        }
        return res;
      })() }
    ]
  };

  // 3. Credit Tightening
  const credit = {
    question: "Credit Tightening (信贷紧缩)",
    stages: [
      { name: "Pressure", ...aggregateStages([clusters.lending_standards, clusters.lending_demand]) },
      { name: "Transmission", ...aggregateStages([clusters.credit_pricing, clusters.broad_fincon, clusters.bank_lending]) },
      { name: "Damage", ...aggregateStages([clusters.credit_damage]) }
    ]
  };

  // Cap Credit confidence if missing critical damage indicators
  if (credit.stages[2].missing.includes('charge_offs') || credit.stages[2].missing.includes('bank_equity_stress')) {
    credit.stages.forEach(s => s.confidence = Math.min(s.confidence, 60)); // Medium
  }

  // 4. Long-End Financing Pressure
  const longEnd = {
    question: "Long-End Financing Pressure (长端融资压力)",
    stages: [
      { name: "Pressure", ...aggregateStages([clusters.supply_pressure, clusters.term_premium]) },
      { name: "Transmission", ...aggregateStages([clusters.real_financing, clusters.curve_steepness]) },
      { name: "Damage", ...aggregateStages([clusters.fiscal_sustainability]) }
    ]
  };
  
  // Cap Long-End confidence due to proxy/model-based data and missing issuance
  if (longEnd.stages[0].missing.includes('treasury_net_issuance')) {
    longEnd.stages.forEach(s => s.confidence = Math.min(s.confidence, 80)); // Medium-High
  }

  // 5. Liquidity Pressure
  const liquidity = {
    question: "Liquidity Pressure (流动性压力)",
    stages: [
      { name: "Pressure", ...aggregateStages([clusters.reserve_supply_drivers]) },
      { name: "Transmission", ...aggregateStages([clusters.bank_liquidity, clusters.funding_stress]) },
      { name: "Damage", ...(() => {
        const res = aggregateStages([clusters.liquidity_damage]);
        if (res.status === 'unknown') {
          res.evidence = ['Unknown — insufficient market-functioning data (Repo/SRF pending)'];
        }
        return res;
      })() }
    ]
  };

  // 6. Stagflation
  // Growth Direction down + Inflation Pressure/Direction up
  const stag_pressure_score = (recession.stages[0].score + inflation.stages[1].score) / 2;
  const stag_pressure_status = stag_pressure_score > 0.7 ? 'red' : stag_pressure_score < 0.4 ? 'green' : 'yellow';

  const stag_damage_score = (recession.stages[2].score + inflation.stages[0].score) / 2;
  const stag_damage_status = stag_damage_score > 0.7 ? 'red' : stag_damage_score < 0.4 ? 'green' : 'yellow';
  
  // Output mode custom
  let riskLevel = 'Low';
  if (stag_pressure_status === 'red' && stag_damage_status === 'red') riskLevel = 'Active';
  else if (stag_pressure_status === 'red' || stag_damage_status === 'red') riskLevel = 'Forming';

  let policyConstraint = 'Low';
  if (inflation.stages[0].score > 0.6 && recession.stages[2].score > 0.6) policyConstraint = 'Severe';
  else if (inflation.stages[0].score > 0.5 || inflation.stages[1].score > 0.6) policyConstraint = 'Moderate';

  const stagflation = {
    question: "Stagflation Risk (滞胀风险)",
    stages: [
      { 
        name: "Macro Divergence", 
        status: stag_pressure_status, 
        score: stag_pressure_score,
        evidence: [...recession.stages[0].evidence, ...inflation.stages[1].evidence],
        counterEvidence: [...recession.stages[0].counterEvidence, ...inflation.stages[1].counterEvidence],
        missing: [],
        coverage: Math.min(recession.stages[0].coverage, inflation.stages[1].coverage),
        confidence: Math.min(recession.stages[0].confidence, inflation.stages[1].confidence),
        obsDate: recession.stages[0].obsDate
      },
      { 
        name: "Policy Constraint (Inference)", 
        status: policyConstraint === 'Severe' ? 'red' : policyConstraint === 'Moderate' ? 'yellow' : 'green', 
        score: 0.5,
        evidence: [`Constraint: ${policyConstraint}`],
        counterEvidence: [],
        missing: [],
        coverage: 100,
        confidence: 100,
        obsDate: null
      },
      { 
        name: "Stagflation Status", 
        status: riskLevel === 'Active' ? 'red' : riskLevel === 'Forming' ? 'yellow' : 'green', 
        score: stag_damage_score,
        evidence: [`Risk: ${riskLevel}`],
        counterEvidence: [],
        missing: [],
        coverage: 100,
        confidence: 100,
        obsDate: null
      }
    ]
  };

  // 7. Asset Valuation Vulnerability
  const valuation = {
    question: "Asset Valuation Vulnerability (资产估值脆弱性)",
    stages: [
      { name: "Pressure", ...aggregateStages([clusters.valuation]) },
      { name: "Transmission", ...aggregateStages([clusters.asset_transmission]) },
      { name: "Damage", ...(() => {
        const res = aggregateStages([clusters.asset_damage]);
        if (res.status !== 'red' && res.status !== 'yellow') {
          res.counterEvidence = ['No repricing damage yet — S&P near highs'];
        }
        return res;
      })() }
    ]
  };
  
  // Cap confidence at 50 (Medium) due to missing data for valuation
  valuation.stages.forEach(st => { if (st.confidence > 50) st.confidence = 50; });

  return { recession, inflation, credit, longEnd, liquidity, stagflation, valuation, clusters };
}

module.exports = { evaluateDiagnostics };
