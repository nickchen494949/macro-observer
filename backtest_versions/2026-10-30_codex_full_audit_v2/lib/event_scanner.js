'use strict';
const fs = require('fs');
const path = require('path');
const mc = require('./market_calendar');

/**
 * Event Scanner — reads indicator data around known event dates and measures market reactions.
 * 
 * CRITICAL RULES:
 * - READ-ONLY: never modifies store or diagnostics
 * - Event data (PAYEMS, UNRATE, etc.) is NOT scanned as market reaction
 * - After-hours earnings use next trading day close
 * - Rolling std is on CHANGES (returns/differences), not levels
 * - No causal language: "caused", "led to", "due to", "导致", "造成"
 */

class EventScanner {
  constructor({ store, indicatorRegistry }) {
    this.store = store;
    this.registry = indicatorRegistry || {};
    
    // Load configs
    const configDir = path.join(__dirname, '../config');
    this.calendar = this._loadJSON(path.join(configDir, 'event_calendar.json')) || [];
    this.results = this._loadJSON(path.join(configDir, 'event_results.json')) || {};
    this.windows = this._loadJSON(path.join(configDir, 'reaction_windows.json')) || {};
    this.marketMapping = this._loadJSON(path.join(configDir, 'event_market_mapping.json')) || {};
    
    // Ticker → file key mapping (Yahoo uses _ prefix for indices)
    this.tickerToKey = {
      '^GSPC': '^GSPC', '^IXIC': '^IXIC', '^DJI': '^DJI', '^RUT': '^RUT', '^VIX': '^VIX',
      'CL=F': 'CL=F', 'GC=F': 'GC=F', 'HG=F': 'HG=F', 'NG=F': 'NG=F',
      'XLK': 'XLK', 'SOXX': 'SOXX', 'XLF': 'XLF', 'XLY': 'XLY', 'XLB': 'XLB',
      'IGV': 'IGV', 'MAGS': 'MAGS', 'XLE': 'XLE', 'XRT': 'XRT', 'GDX': 'GDX',
      'KRE': 'KRE', 'KBE': 'KBE', 'XLRE': 'XLRE', 'XLV': 'XLV', 'XLP': 'XLP',
      'IBB': 'IBB', 'ICLN': 'ICLN'
    };
  }

  _loadJSON(filepath) {
    try {
      if (fs.existsSync(filepath)) return JSON.parse(fs.readFileSync(filepath, 'utf-8'));
    } catch (e) { /* silent */ }
    return null;
  }

  // ─── Data Access ───────────────────────────────
  
  _getValues(ticker) {
    // Try fred, yahoo, valuation in order
    const key = this.tickerToKey[ticker] || ticker;
    return this.store.fred[key] || this.store.yahoo[key] || this.store.valuation[key] || null;
  }

  // ─── Change Calculation ────────────────────────

  _calculateChange(beforeVal, afterVal, method) {
    if (beforeVal == null || afterVal == null) return null;
    if (method === 'difference_bp') {
      return { raw: (afterVal - beforeVal) * 100, formatted: this._fmtBp((afterVal - beforeVal) * 100) };
    } else if (method === 'percent_return') {
      if (beforeVal === 0) return null;
      const pct = ((afterVal / beforeVal) - 1) * 100;
      return { raw: pct, formatted: (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%' };
    }
    return { raw: afterVal - beforeVal, formatted: (afterVal - beforeVal).toFixed(2) };
  }

  _fmtBp(bp) {
    const sign = bp >= 0 ? '+' : '';
    return sign + bp.toFixed(0) + 'bp';
  }

  // ─── Volatility-Adjusted Materiality ───────────

  _calculateRollingStd(values, targetDate, window, method) {
    if (!values || values.length < window + 5) return null;
    
    // Find index of targetDate or closest before
    let idx = -1;
    for (let i = values.length - 1; i >= 0; i--) {
      if (values[i][0] <= targetDate) { idx = i; break; }
    }
    if (idx < window) return null;

    // Calculate changes over the window
    const changes = [];
    for (let i = idx - window; i < idx; i++) {
      if (values[i + 1] == null || values[i] == null) continue;
      if (method === 'difference_bp') {
        changes.push((values[i + 1][1] - values[i][1]) * 100);
      } else {
        if (values[i][1] === 0) continue;
        changes.push(((values[i + 1][1] / values[i][1]) - 1) * 100);
      }
    }
    if (changes.length < 10) return null;

    const mean = changes.reduce((a, b) => a + b, 0) / changes.length;
    const variance = changes.reduce((a, b) => a + (b - mean) ** 2, 0) / changes.length;
    return Math.sqrt(variance);
  }

  _isMaterial(changeRaw, absoluteThreshold, rollingStd, zThreshold) {
    const absChange = Math.abs(changeRaw);
    if (absChange >= absoluteThreshold) return true;
    if (rollingStd != null && rollingStd > 0 && (absChange / rollingStd) >= zThreshold) return true;
    return false;
  }

  // ─── Reaction Measurement ─────────────────────

  _measureReaction(ticker, eventDate, windowProfile, marketConfig) {
    const values = this._getValues(ticker);
    if (!values || values.length === 0) {
      return { status: 'insufficient_data', indicator: ticker };
    }

    const method = marketConfig.changeMethod || 'percent_return';
    const results = {};

    for (const windowName of ['immediate', 'followThrough']) {
      const windowDef = windowProfile[windowName];
      if (!windowDef) continue;

      const beforeDate = mc.resolveWindowDate(windowDef.before, eventDate);
      const afterDate = mc.resolveWindowDate(windowDef.after, eventDate);
      if (!beforeDate || !afterDate) {
        results[windowName] = { status: 'insufficient_data' };
        continue;
      }

      const beforePoint = mc.findClosestDataPoint(values, beforeDate, 'before', 5);
      const afterPoint = mc.findClosestDataPoint(values, afterDate, 'after', 5);
      
      // Also try exact match
      const beforeExact = values.find(v => v[0] === beforeDate);
      const afterExact = values.find(v => v[0] === afterDate);
      
      const bVal = beforeExact ? beforeExact[1] : (beforePoint ? beforePoint.value : null);
      const aVal = afterExact ? afterExact[1] : (afterPoint ? afterPoint.value : null);
      const bDate = beforeExact ? beforeDate : (beforePoint ? beforePoint.date : null);
      const aDate = afterExact ? afterDate : (afterPoint ? afterPoint.date : null);

      if (bVal == null || aVal == null) {
        results[windowName] = { status: 'insufficient_data' };
        continue;
      }

      const change = this._calculateChange(bVal, aVal, method);
      if (!change) {
        results[windowName] = { status: 'insufficient_data' };
        continue;
      }

      const rollingStd = this._calculateRollingStd(values, bDate, marketConfig.rollingWindow || 20, method);
      const volAdj = (rollingStd && rollingStd > 0) ? Math.abs(change.raw) / rollingStd : null;
      const material = this._isMaterial(
        change.raw, 
        marketConfig.absoluteThreshold || 999, 
        rollingStd, 
        marketConfig.zThreshold || 1.25
      );

      results[windowName] = {
        status: 'ok',
        before: { date: bDate, value: bVal },
        after: { date: aDate, value: aVal },
        change: change.raw,
        formattedChange: change.formatted,
        volAdjustedMove: volAdj != null ? +volAdj.toFixed(2) : null,
        material,
        magnitude: material ? (Math.abs(change.raw) >= (marketConfig.absoluteThreshold || 999) * 2 ? 'large' : 'material') : 'small'
      };
    }

    return { status: 'ok', indicator: ticker, windows: results };
  }

  // ─── Competing Events ─────────────────────────

  _findCompetingEvents(eventId, eventDate) {
    const competing = [];
    for (const evt of this.calendar) {
      if (evt.id === eventId) continue;
      const d = evt.scheduled.date;
      // Within ±1 trading day
      const prev = mc.previousTradingDay(eventDate);
      const next = mc.nextTradingDay(eventDate);
      if (d === eventDate || d === prev || d === next) {
        competing.push({ id: evt.id, date: d, type: evt.scheduled.type, label: evt.scheduled.label });
      }
    }
    return competing;
  }

  // ─── Confidence Scoring ───────────────────────

  _calculateConfidence(reactionSummary, competingEvents, eventResult, windowProfile) {
    let score = 0;

    // Time window matched (we have data for the reaction window)
    if (reactionSummary.some(r => r.status === 'ok')) score += 0.25;
    
    // Event result verified
    if (eventResult && (eventResult.status === 'verified' || eventResult.status === 'estimated')) score += 0.15;

    // At least one material reaction
    const materialReactions = reactionSummary.filter(r => 
      r.status === 'ok' && r.windows?.immediate?.material
    );
    if (materialReactions.length > 0) score += 0.20;

    // Multiple markets confirm (2+ material reactions)
    if (materialReactions.length >= 2) score += 0.15;

    // Channel consistency — check if direction is in expected direction
    // (simplified: we just check if reactions aren't contradicting each other)
    const dirs = materialReactions.map(r => Math.sign(r.windows?.immediate?.change || 0)).filter(d => d !== 0);
    const allSameDir = dirs.length > 0 && dirs.every(d => d === dirs[0]);
    if (!allSameDir && dirs.length >= 2) {
      // Mixed reaction directions — not necessarily wrong (dual-axis), just lower confidence
    } else if (allSameDir) {
      score += 0.15;
    }

    // Follow-through confirmed
    const followThrough = reactionSummary.filter(r =>
      r.status === 'ok' && r.windows?.followThrough?.material
    );
    if (followThrough.length > 0) score += 0.10;

    // Penalties
    if (competingEvents.length > 0) score -= 0.30;
    if (windowProfile === 'fomc_daily') score -= 0.05; // daily data can't isolate statement vs presser
    
    // Missing consensus
    if (eventResult && eventResult.consensus == null && eventResult.actual != null) score -= 0.10;

    score = Math.max(0, Math.min(1, score));

    // Classify
    let classification;
    if (score >= 0.80) classification = 'high_confidence';
    else if (score >= 0.60) classification = 'likely_related';
    else if (score >= 0.40) classification = 'mixed';
    else classification = 'low_confidence';

    return { score: +score.toFixed(2), classification };
  }

  // ─── Narrative Templates ──────────────────────

  _buildNarrative(event, result, materialReactions, confidence) {
    const type = event.scheduled.type;
    const label = event.scheduled.label;

    // Collect reaction summary for narrative
    const moves = materialReactions
      .filter(r => r.windows?.immediate?.material)
      .map(r => `${r.label || r.indicator}: ${r.windows.immediate.formattedChange}`)
      .join(', ');

    let en = '', zh = '';

    if (type === 'FOMC_DECISION' && result) {
      const decision = result.decision || 'hold';
      if (decision === 'hold') {
        en = `Fed held rates${result.vote ? ' (' + result.vote + ' vote)' : ''}. Market reaction: ${moves || 'no material moves'}.`;
        zh = `美联储维持利率${result.vote ? '（' + result.vote + '投票）' : ''}。市场反应：${moves || '无重大变动'}。`;
      } else if (decision.includes('cut')) {
        en = `Fed cut rates to ${result.targetLower}-${result.targetUpper}%. Market reaction: ${moves || 'no material moves'}.`;
        zh = `美联储降息至${result.targetLower}-${result.targetUpper}%。市场反应：${moves || '无重大变动'}。`;
      }
    } else if (type === 'NFP_RELEASE' && result) {
      const surprise = result.surprise != null ? (result.surprise > 0 ? `beat by ${result.surprise}k` : `missed by ${Math.abs(result.surprise)}k`) : '';
      en = `NFP: ${result.actual != null ? result.actual + 'k' : '?'} vs ${result.consensus != null ? result.consensus + 'k exp' : '?'}${surprise ? ' (' + surprise + ')' : ''}. ${moves ? 'Reaction: ' + moves + '.' : ''}`;
      zh = `非农：${result.actual != null ? result.actual + 'k' : '?'} vs 预期${result.consensus != null ? result.consensus + 'k' : '?'}${result.surprise != null ? '（' + (result.surprise > 0 ? '高于' : '低于') + '预期' + Math.abs(result.surprise) + 'k）' : ''}。${moves ? '反应：' + moves + '。' : ''}`;
    } else if (type === 'CPI_RELEASE' && result) {
      en = `CPI release${result.headline_yoy != null ? ': ' + result.headline_yoy + '% YoY' : ''}. ${moves ? 'Reaction: ' + moves + '.' : ''}`;
      zh = `CPI发布${result.headline_yoy != null ? '：' + result.headline_yoy + '% YoY' : ''}。${moves ? '反应：' + moves + '。' : ''}`;
    } else if (type === 'EARNINGS' && result) {
      en = `${label} earnings. ${moves ? 'Reaction (next trading day): ' + moves + '.' : 'No material reaction detected.'}`;
      zh = `${label}财报。${moves ? '反应（下一交易日）：' + moves + '。' : '未检测到重大反应。'}`;
    } else if (type === 'MARKET_EVENT') {
      en = `${label}. ${moves ? 'Market reaction: ' + moves + '.' : ''}`;
      zh = `${label}。${moves ? '市场反应：' + moves + '。' : ''}`;
    } else {
      en = `${label}. ${moves ? 'Moves: ' + moves + '.' : ''}`;
      zh = `${label}。${moves ? '变动：' + moves + '。' : ''}`;
    }

    // Add confidence caveat
    if (confidence.classification === 'mixed' || confidence.classification === 'low_confidence') {
      en += ' Attribution uncertain.';
      zh += ' 归因存在不确定性。';
    }

    return { en, zh };
  }

  // ─── Unmatched Move Detection ─────────────────

  _detectUnmatchedMoves(lookbackDate) {
    const thresholds = {
      '^GSPC': { method: 'percent_return', threshold: 1.5 },
      '^VIX': { method: 'percent_return', threshold: 15 },
      'DGS10': { method: 'difference_bp', threshold: 10 },
      'CL=F': { method: 'percent_return', threshold: 4 },
      'GC=F': { method: 'percent_return', threshold: 2 },
      'BAMLH0A0HYM2': { method: 'difference_bp', threshold: 10 }
    };

    const eventDates = new Set(this.calendar.map(e => e.scheduled.date));
    const clusters = {};

    for (const [ticker, config] of Object.entries(thresholds)) {
      const values = this._getValues(ticker);
      if (!values) continue;

      for (let i = 1; i < values.length; i++) {
        const date = values[i][0];
        if (date < lookbackDate) continue;
        
        let change;
        if (config.method === 'difference_bp') {
          change = (values[i][1] - values[i - 1][1]) * 100;
        } else {
          if (values[i - 1][1] === 0) continue;
          change = ((values[i][1] / values[i - 1][1]) - 1) * 100;
        }

        if (Math.abs(change) >= config.threshold) {
          // Check if any event is within ±1 day
          const prev = mc.previousTradingDay(date);
          const next = mc.nextTradingDay(date);
          const hasEvent = eventDates.has(date) || eventDates.has(prev) || eventDates.has(next);
          
          if (!hasEvent) {
            if (!clusters[date]) clusters[date] = { marketDate: date, reactions: [] };
            const label = ticker === '^GSPC' ? 'S&P 500' : ticker === '^VIX' ? 'VIX' : 
                          ticker === 'DGS10' ? '10Y' : ticker === 'CL=F' ? 'Oil' : 
                          ticker === 'GC=F' ? 'Gold' : ticker === 'BAMLH0A0HYM2' ? 'HY OAS' : ticker;
            clusters[date].reactions.push({
              indicator: ticker,
              label,
              change: change,
              formattedChange: config.method === 'difference_bp' 
                ? this._fmtBp(change) 
                : (change >= 0 ? '+' : '') + change.toFixed(1) + '%'
            });
          }
        }
      }
    }

    return Object.values(clusters).map(c => ({
      event: {
        date: c.marketDate,
        type: 'UNMATCHED_MOVE',
        label: 'No matched scheduled catalyst'
      },
      result: null,
      reactions: c.reactions,
      competingEvents: [],
      attribution: {
        classification: 'unmatched_move',
        score: 0,
        reactionStatus: 'material'
      },
      narrative: {
        en: `Large move detected without matching scheduled event. Review news and unscheduled developments.`,
        zh: `检测到显著波动，未匹配到已知计划事件。建议检查新闻和非计划性政策变化。`
      },
      dataWarnings: []
    }));
  }

  // ─── Main Scan ────────────────────────────────

  scan({ lookbackDays = 90 } = {}) {
    try {
      const now = new Date();
      const lookbackDate = new Date(now.getTime() - lookbackDays * 24 * 60 * 60 * 1000)
        .toISOString().slice(0, 10);

      const events = [];
      const dataWarnings = [];

      // Filter calendar to lookback window
      const relevantEvents = this.calendar.filter(e => e.scheduled.date >= lookbackDate);

      for (const calEvent of relevantEvents) {
        const eventDate = calEvent.scheduled.date;
        const eventId = calEvent.id;
        const eventResult = this.results[eventId] || null;
        const windowProfileName = calEvent.reactionWindow;
        const windowProfile = this.windows[windowProfileName];

        if (!windowProfile) {
          dataWarnings.push(`Missing window profile: ${windowProfileName} for ${eventId}`);
          continue;
        }

        // Resolve candidate market indicators from affectedMarkets
        const candidateIndicators = [];
        for (const market of (calEvent.affectedMarkets || [])) {
          const mapping = this.marketMapping[market];
          if (!mapping || !mapping.indicators) continue;
          for (const ticker of mapping.indicators) {
            if (!candidateIndicators.find(c => c.ticker === ticker)) {
              candidateIndicators.push({
                ticker,
                label: this._indicatorLabel(ticker),
                marketDomain: market,
                changeMethod: mapping.changeMethod,
                absoluteThreshold: mapping.absoluteThreshold,
                zThreshold: mapping.zThreshold,
                rollingWindow: mapping.rollingWindow,
                qualityWarning: mapping.qualityWarning || null
              });
            }
          }
        }

        // Measure reactions
        const reactionResults = [];
        for (const candidate of candidateIndicators) {
          const reaction = this._measureReaction(
            candidate.ticker, eventDate, windowProfile,
            {
              changeMethod: candidate.changeMethod,
              absoluteThreshold: candidate.absoluteThreshold,
              zThreshold: candidate.zThreshold,
              rollingWindow: candidate.rollingWindow
            }
          );
          reaction.label = candidate.label;
          reaction.marketDomain = candidate.marketDomain;
          if (candidate.qualityWarning) reaction.qualityWarning = candidate.qualityWarning;
          reactionResults.push(reaction);
        }

        // Find competing events
        const competingEvents = this._findCompetingEvents(eventId, eventDate);

        // Check if any material reaction
        const hasAnyMaterial = reactionResults.some(r => 
          r.status === 'ok' && r.windows?.immediate?.material
        );
        const allInsufficient = reactionResults.every(r => r.status === 'insufficient_data');

        let reactionStatus;
        if (allInsufficient) reactionStatus = 'insufficient_data';
        else if (!hasAnyMaterial) reactionStatus = 'no_material_reaction';
        else reactionStatus = 'material';

        // Calculate confidence
        const confidence = reactionStatus === 'material'
          ? this._calculateConfidence(reactionResults, competingEvents, eventResult, windowProfileName)
          : { score: null, classification: reactionStatus };

        // Build narrative
        const narrative = reactionStatus === 'material'
          ? this._buildNarrative(calEvent, eventResult, reactionResults, confidence)
          : {
              en: reactionStatus === 'insufficient_data' 
                ? 'Insufficient market data available for this event window.'
                : 'No material market reaction detected around this event.',
              zh: reactionStatus === 'insufficient_data'
                ? '此事件窗口内市场数据不足。'
                : '未检测到此事件附近的重大市场反应。'
            };

        // Build compact reaction summary for UI
        const reactionSummary = reactionResults
          .filter(r => r.status === 'ok' && r.windows?.immediate?.material)
          .map(r => ({
            indicator: r.indicator,
            label: r.label,
            change: r.windows.immediate.change,
            formattedChange: r.windows.immediate.formattedChange,
            volAdjustedMove: r.windows.immediate.volAdjustedMove,
            magnitude: r.windows.immediate.magnitude
          }));

        events.push({
          event: {
            date: eventDate,
            time: calEvent.scheduled.time,
            type: calEvent.scheduled.type,
            label: calEvent.scheduled.label,
            session: calEvent.scheduled.releaseSession
          },
          result: eventResult ? {
            ...eventResult,
            // Strip internal fields
            capturedAt: undefined,
            consensusSource: undefined
          } : null,
          reactions: reactionSummary,
          fullReactions: reactionResults,
          competingEvents,
          attribution: {
            classification: confidence.classification,
            score: confidence.score,
            reactionStatus
          },
          narrative,
          dataWarnings: reactionResults
            .filter(r => r.qualityWarning)
            .map(r => `${r.indicator}: ${r.qualityWarning}`)
        });
      }

      // Detect unmatched moves
      const unmatchedMoves = this._detectUnmatchedMoves(lookbackDate);

      // Merge and sort by date descending
      const allEvents = [...events, ...unmatchedMoves]
        .sort((a, b) => b.event.date.localeCompare(a.event.date));

      return {
        status: 'ok',
        generatedAt: now.toISOString(),
        lookbackDays,
        eventsScanned: relevantEvents.length,
        materialEvents: events.filter(e => e.attribution.reactionStatus === 'material').length,
        unmatchedMoveClusters: unmatchedMoves.length,
        dataWarnings,
        events: allEvents
      };

    } catch (error) {
      return {
        status: 'scanner_error',
        generatedAt: new Date().toISOString(),
        events: [],
        error: error.message
      };
    }
  }

  // ─── Helpers ──────────────────────────────────

  _indicatorLabel(ticker) {
    const labels = {
      'DGS2': '2Y', 'DGS5': '5Y', 'DGS10': '10Y', 'DGS30': '30Y', 'DGS20': '20Y',
      'DFII10': '10Y TIPS', 'T10Y3M': '3M-10Y Spread',
      '^GSPC': 'S&P 500', '^IXIC': 'Nasdaq', '^DJI': 'Dow Jones', '^RUT': 'Russell 2000',
      '^VIX': 'VIX',
      'CL=F': 'Oil (WTI)', 'GC=F': 'Gold', 'HG=F': 'Copper', 'NG=F': 'Natural Gas',
      'XLK': 'Tech (XLK)', 'SOXX': 'Semis (SOXX)', 'XLF': 'Financials (XLF)',
      'XLY': 'Consumer Disc (XLY)', 'XLB': 'Materials (XLB)', 'XLE': 'Energy (XLE)',
      'IGV': 'Software (IGV)', 'MAGS': 'Mag7 (MAGS)',
      'GDX': 'Gold Miners (GDX)', 'KRE': 'Regional Banks (KRE)', 'KBE': 'Banks (KBE)',
      'BAMLH0A0HYM2': 'HY OAS',
      'FED_PATH_HISTORY': 'Fed Path'
    };
    return labels[ticker] || ticker;
  }
}

module.exports = EventScanner;
