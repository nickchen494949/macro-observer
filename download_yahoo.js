'use strict';
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DD = path.join(__dirname, 'data', 'yahoo');
const CD = path.join(__dirname, 'csv', 'yahoo');
[DD, CD].forEach(d => fs.mkdirSync(d, { recursive: true }));

// Canary symbols for Phase 0 tests (Option B: Challenger ETF proxies + research_only futures)
const SYMBOLS = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD', 'TLT', '^VIX', 'CL=F', 'GC=F', 'NG=F', '^GSPC', '^IXIC', 'SOXX', '^RUT', 'HG=F'];

const POLICY_MAP = {
  'SPY': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  'QQQ': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  'IWM': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  'IEF': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  'USO': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  'GLD': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  'TLT': { type: 'ETF', policy: 'yahoo_regular_end_plus_30m', buffer: 1800 },
  '^VIX': { type: 'INDEX', policy: 'symbol_specific', buffer: 3600 },
  'CL=F': { type: 'CONTINUOUS_FUTURE', policy: 'research_only', buffer: 0 },
  'GC=F': { type: 'CONTINUOUS_FUTURE', policy: 'research_only', buffer: 0 },
  'NG=F': { type: 'CONTINUOUS_FUTURE', policy: 'research_only', buffer: 0 }
};

const INTRA_DELAY = 1000;

function safeName(s) { return s.replace(/[^a-zA-Z0-9._=-]/g, '_'); }
const sleep = ms => new Promise(r => setTimeout(r, ms));

function get(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)' },
      timeout: 30000,
    }, res => {
      const c = []; res.on('data', d => c.push(d));
      res.on('end', () => resolve({ status: res.statusCode, body: Buffer.concat(c).toString() }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function parseAndValidate(body, sym) {
  const d = JSON.parse(body);
  const ch = d.chart?.result?.[0];
  if (!ch) return null;
  
  const ts = ch.timestamp || [];
  const quote = ch.indicators?.quote?.[0] || {};
  const adj = ch.indicators?.adjclose?.[0] || {};
  
  const opens = quote.open || [];
  const highs = quote.high || [];
  const lows = quote.low || [];
  const closes = quote.close || [];
  const vols = quote.volume || [];
  const adjcloses = adj.adjclose || closes;
  
  const divs = ch.events?.dividends || {};
  const splits = ch.events?.splits || {};
  
  const vals = [];
  let prevDate = null;
  let prevFactor = null;
  
  let caRowsChecked = 0;
  let matchedEvents = 0;
  let unexplainedChanges = 0;
  let toleranceExceptions = 0;
  let unexplained_adjustment_change = false;
  
  const meta = ch.meta || {};
  const currentEnd = meta.currentTradingPeriod?.regular?.end;
  const downloadedAtS = Math.floor(Date.now() / 1000);
  
  for (let i = 0; i < ts.length; i++) {
    const t = ts[i];
    const dateStr = new Date(t * 1000).toLocaleString('sv-SE', { timeZone: 'America/New_York' }).split(' ')[0];
    
    // Partial bar exclusion based on per-symbol completeness policy
    if (currentEnd && t >= currentEnd - 86400) {
      const currentEndDateStr = new Date(currentEnd * 1000).toLocaleString('sv-SE', { timeZone: 'America/New_York' }).split(' ')[0];
      const p = POLICY_MAP[sym] || { buffer: 1800 };
      if (dateStr === currentEndDateStr && downloadedAtS < currentEnd + p.buffer) {
        continue;
      }
    }
    
    // Check for duplicate dates
    if (prevDate === dateStr) {
      throw new Error("Duplicate date found: " + dateStr);
    }
    prevDate = dateStr;
    
    const o = opens[i];
    const h = highs[i];
    const l = lows[i];
    const c = closes[i];
    const ac = adjcloses[i];
    const v = vols[i] || 0;
    
    // Check if missing
    if (o == null || h == null || l == null || c == null || ac == null) {
      vals.push({
        date: dateStr,
        timestamp: t,
        status: "missing_source_observation"
      });
      continue;
    }
    const validation = {
      closeValid: true,
      openValid: true,
      highValid: true,
      lowValid: true,
      ohlcPathValid: true,
      issue: null
    };

    // Validate OHLC bounds (field-level invalidation)
    if (!isFinite(o) || !isFinite(h) || !isFinite(l) || !isFinite(c) || !isFinite(ac)) {
      validation.closeValid = isFinite(c);
      validation.openValid = isFinite(o);
      validation.highValid = isFinite(h);
      validation.lowValid = isFinite(l);
      validation.ohlcPathValid = false;
      validation.issue = "non_finite_values";
    } else if (h < o || h < c || l > o || l > c || v < 0) {
      validation.ohlcPathValid = false;
      if (h < o || h < c) { validation.highValid = false; validation.issue = "high_below_open_or_close"; }
      if (l > o || l > c) { validation.lowValid = false; validation.issue = (validation.issue ? validation.issue + "_and_low_issue" : "low_above_open_or_close"); }
      if (v < 0) { validation.issue = validation.issue || "negative_volume"; }
    }
    
    if (!validation.ohlcPathValid) {
      // Record this issue for global tracking
      validationFailures.push({ sym, date: dateStr, issue: validation.issue });
    }
    
    const factor = c === 0 ? 1.0 : ac / c;
    if (factor <= 0) {
      throw new Error("Invalid adjustment factor at " + dateStr);
    }
    
    let div = 0, split = 1;
    if (divs[t]) div = divs[t].amount;
    if (splits[t]) split = splits[t].numerator / splits[t].denominator;
    
    // Phase 0.5: Corporate action reconciliation
    if (prevFactor !== null) {
      const factorDiff = Math.abs(factor - prevFactor);
      if (factorDiff > 0.0001) {
        caRowsChecked++;
        if (div > 0 || split !== 1) {
          matchedEvents++;
          // Rough check if adjustment magnitude is somewhat bounded (tolerance exception detection could be refined here)
          const expectedFactorDrop = (c - div) / c;
          if (div > 0 && Math.abs(factor - (prevFactor * expectedFactorDrop)) > 0.1) {
            toleranceExceptions++;
          }
        } else {
          unexplainedChanges++;
          unexplained_adjustment_change = true;
        }
      }
    }
    prevFactor = factor;
    
    const adjO = o * factor;
    const adjH = h * factor;
    const adjL = l * factor;
    
    vals.push({
      date: dateStr,
      timestamp: t,
      open: +o.toFixed(6),
      high: +h.toFixed(6),
      low: +l.toFixed(6),
      close: +c.toFixed(6),
      adjClose: +ac.toFixed(6),
      volume: v,
      dividend: div,
      splitRatio: split,
      adjustmentFactor: +factor.toFixed(6),
      adjOpen: +adjO.toFixed(6),
      adjHigh: +adjH.toFixed(6),
      adjLow: +adjL.toFixed(6),
      validation
    });
  }
  
  return { vals, caStats: { caRowsChecked, matchedEvents, unexplainedChanges, toleranceExceptions }, unexplained_adjustment_change, currentEnd, exchangeTimezone: meta.exchangeTimezoneName, downloadedAtS };
}

let validationFailures = [];
let globalCaStats = { caRowsChecked: 0, matchedEvents: 0, unexplainedChanges: 0, toleranceExceptions: 0 };

async function main() {
  console.log(`\n📈 Downloading ${SYMBOLS.length} CANARY symbols...\n`);

  let ok = 0, fail = 0;
  for (const sym of SYMBOLS) {
    const url = 'https://query2.finance.yahoo.com/v8/finance/chart/' + encodeURIComponent(sym) + '?range=10y&interval=1d&events=div,splits';
    try {
      const r = await get(url);
      if (r.status !== 200) {
        throw new Error(`HTTP ${r.status}`);
      }
      
      const rawPayloadHash = crypto.createHash('sha256').update(r.body).digest('hex');
      const { vals, caStats, unexplained_adjustment_change, currentEnd, exchangeTimezone, downloadedAtS } = parseAndValidate(r.body, sym) || {};
      
      if (!vals || vals.length === 0) {
        console.log(`     ${sym}: ❌ no data`);
        fail++;
        continue;
      }
      
      if (caStats) {
        globalCaStats.caRowsChecked += caStats.caRowsChecked;
        globalCaStats.matchedEvents += caStats.matchedEvents;
        globalCaStats.unexplainedChanges += caStats.unexplainedChanges;
        globalCaStats.toleranceExceptions += caStats.toleranceExceptions;
      }
      
      const payload = {
        schemaVersion: 2,
        transformVersion: "yahoo-ohlc-v2",
        source: "Yahoo Chart API",
        symbol: sym,
        interval: "1d",
        downloadedAt: new Date().toISOString(),
        exchangeTimezone: exchangeTimezone || "America/New_York",
        officialSessionClose: currentEnd,
        barCompleteness: (currentEnd && downloadedAtS < currentEnd + (POLICY_MAP[sym]?.buffer || 1800)) ? "partial_excluded" : "complete",
        adjustmentMethod: "adjClose_divided_by_close",
        requestParameters: { range: "10y", interval: "1d" },
        rawPayloadHash,
        instrumentType: POLICY_MAP[sym]?.type || "unknown",
        completenessPolicy: POLICY_MAP[sym]?.policy || "unknown",
        returnValidationStatus: POLICY_MAP[sym]?.type === 'CONTINUOUS_FUTURE' ? "research_only" : "validation_candidate",
        flags: unexplained_adjustment_change ? ["unexplained_adjustment_change"] : [],
        caStats,
        values: vals
      };
      
      payload.normalizedDataHash = crypto.createHash('sha256').update(JSON.stringify(payload.values)).digest('hex');
      
      const n = safeName(sym);
      const tmpPath = path.join(DD, n + '.tmp.json');
      const finalPath = path.join(DD, n + '.json');
      
      fs.writeFileSync(tmpPath, JSON.stringify(payload));
      fs.renameSync(tmpPath, finalPath);
      
      let flagStr = unexplained_adjustment_change ? " [⚠️ unexplained factor jumps]" : "";
      
      // Fine-grained reporting
      const ohlcValid = vals.every(v => !v.validation || v.validation.ohlcPathValid !== false);
      const closeValid = vals.every(v => !v.validation || v.validation.closeValid !== false);
      
      let statusRep = "✅ Passed";
      if (!ohlcValid) {
        statusRep = closeValid ? "⚠️ Full-OHLC failed, Close-series passed" : "❌ Close-series failed";
      }
      
      console.log(`     ${sym}: ${statusRep} (${vals.length} pts)${flagStr}`);
      ok++;
    } catch (e) {
      console.log(`     ${sym}: ❌ ${e.message}`);
      fail++;
    }
    await sleep(INTRA_DELAY);
  }

  console.log(`\n==========================================`);
  console.log(`CORPORATE ACTION AUDIT REPORT`);
  console.log(`==========================================`);
  console.log(`Adjustment changes checked:     ${globalCaStats.caRowsChecked}`);
  console.log(`Matched dividend/split events:  ${globalCaStats.matchedEvents}`);
  console.log(`Unexplained material changes:   ${globalCaStats.unexplainedChanges}`);
  console.log(`Minor tolerance exceptions:     ${globalCaStats.toleranceExceptions}`);
  console.log(`==========================================`);
  
  if (validationFailures.length > 0) {
    console.log(`\n⚠️ Intraday/path-dependent OHLC validation failed for the following symbols:`);
    validationFailures.forEach(f => {
      console.log(`  - ${f.sym} on ${f.date}: ${f.issue}`);
    });
    console.log(`  Close-only CTA signal: Passed and usable (if closeValid).`);
    console.log(`  Full-OHLC path validation: Excluded.\n`);
  }

  if (globalCaStats.unexplainedChanges > 0) {
    console.error(`\n❌ CRITICAL ERROR: Found ${globalCaStats.unexplainedChanges} unexplained material changes in price histories.`);
    process.exit(1);
  }

  console.log(`✅ Phase 0.5 Data Check: Complete (${ok} succeeded, ${fail} failed)\n`);
}

main();
