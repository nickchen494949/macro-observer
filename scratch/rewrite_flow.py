import re
import os

with open("flow.html", "r") as f:
    html = f.read()

# I will write a custom replacement for the `<script>` block.
# First, let's inject the AJV cdn scripts into the `<head>`
head_target = "</head>"
head_replacement = """  <script src="https://cdnjs.cloudflare.com/ajax/libs/ajv/8.12.0/ajv.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/ajv-formats/2.1.1/ajv-formats.min.js"></script>
</head>"""
html = html.replace(head_target, head_replacement)

# Now I'll replace the ENTIRE script block, starting from `<script>` to `</script>`
script_start = html.find("<script>")
script_end = html.find("</script>") + len("</script>")

new_script = """<script>
    const ajv = new window.ajv7({ allErrors: true });
    window.ajvFormats(ajv);
    let validateFlowSnapshot = null;

    // Formatting utilities
    function formatFiniteNumber(num, decimals=2) {
      if (num == null || !Number.isFinite(num)) return '—';
      return Number(num).toFixed(decimals);
    }
    function formatText(str) {
      if (str == null || str === '') return '—';
      return str;
    }
    
    function formatUsd(value) {
      if (value == null || !Number.isFinite(value)) return '—';
      const abs = Math.abs(value);
      const sign = value < 0 ? '-' : '+';
      if (abs >= 1e9) return sign + '$' + (abs / 1e9).toFixed(1) + 'B';
      if (abs >= 1e6) return sign + '$' + (abs / 1e6).toFixed(0) + 'M';
      return sign + '$' + abs.toFixed(0);
    }
    function formatUsdAbs(value) {
      if (value == null || !Number.isFinite(value)) return '—';
      const abs = Math.abs(value);
      if (abs >= 1e12) return '$' + (abs / 1e12).toFixed(1) + 'T';
      if (abs >= 1e9) return '$' + (abs / 1e9).toFixed(0) + 'B';
      if (abs >= 1e6) return '$' + (abs / 1e6).toFixed(0) + 'M';
      return '$' + abs.toFixed(0);
    }
    
    function colorize(val, isInverse = false) {
      if (val == null) return 'text-muted';
      let num = parseFloat(val);
      if (!Number.isFinite(num)) return '';
      if (num > 0) return isInverse ? 'text-red' : 'text-green';
      if (num < 0) return isInverse ? 'text-green' : 'text-red';
      return 'text-muted';
    }

    function removeSkeletons() {
      document.querySelectorAll('.skeleton').forEach(el => el.classList.remove('skeleton'));
    }

    // View State & Quality Management
    let lastValidSnapshot = null;
    let currentAbortController = null;
    let globalAsOfDate = '--';

    // Helper: Calculate trading days between two dates
    function getTradingDaysBetween(startStr, endStr) {
      let start = new Date(startStr);
      let end = new Date(endStr);
      let count = 0;
      let curr = new Date(start);
      while (curr < end) {
        curr.setDate(curr.getDate() + 1);
        if (curr.getDay() !== 0 && curr.getDay() !== 6) count++;
      }
      return count;
    }

    function determineViewState(snapshot) {
      if (!snapshot) return { status: 'unavailable', quality: null };
      
      const asOfStr = snapshot.marketDataAsOf;
      const genAtStr = snapshot.snapshotGeneratedAt;
      const todayStr = new Date().toISOString().split('T')[0];
      
      let viewState = 'current';
      if (asOfStr) {
        const lag = getTradingDaysBetween(asOfStr, todayStr);
        if (lag > 2) viewState = 'outdated';
      }
      
      if (genAtStr) {
        const genTime = new Date(genAtStr).getTime();
        const now = Date.now();
        const hoursOld = (now - genTime) / (1000 * 60 * 60);
        if (hoursOld > 2) {
          viewState = viewState === 'outdated' ? 'expired' : 'stale';
        }
      }
      return { status: viewState, quality: snapshot.snapshotQuality };
    }

    function updateFreshness(idPrefix, data, viewState) {
      if (data?.commonAsOfDate) {
        document.getElementById(idPrefix + '-asof').textContent = data.commonAsOfDate;
        if(globalAsOfDate === '--' || data.commonAsOfDate > globalAsOfDate) {
          globalAsOfDate = data.commonAsOfDate;
          document.getElementById('global-asof').textContent = globalAsOfDate;
        }
      }
      
      const staleBadge = document.getElementById(idPrefix + '-stale');
      if (staleBadge) {
        if (viewState.status === 'outdated' || viewState.status === 'expired' || viewState.status === 'stale') {
          staleBadge.style.display = 'block';
          staleBadge.textContent = viewState.status.toUpperCase();
        } else if (viewState.quality === 'partial') {
           staleBadge.style.display = 'block';
           staleBadge.textContent = 'PARTIAL';
           staleBadge.style.background = 'var(--amber)';
        } else {
          staleBadge.style.display = 'none';
        }
      }
    }

    function getPillClass(val) {
      if (!val) return 'neutral';
      const s = String(val).toLowerCase();
      if (s.includes('buy')) return 'buy';
      if (s.includes('sell')) return 'sell';
      if (s.includes('stabilizer')) return 'stabilizer';
      return 'neutral';
    }

    function renderSummary(data, viewState) {
      if(!data) return;
      document.getElementById('dominant-regime').textContent = formatText(data?.dominantRegime?.replace(/_/g, ' '));
      
      const mech = data?.mechanismCount ?? 0;
      const driver = data?.driverCount ?? 0;
      const dup = data?.duplicatedDriverCount ?? 0;
      
      const mechText = mech === 1 ? '1 mechanism' : `${mech} mechanisms`;
      const driverText = driver === 1 ? '1 driver' : `${driver} drivers`;
      
      let confidence = 'Low';
      if (driver >= 3 && mech >= 3) confidence = 'High';
      else if (driver >= 2 && mech >= 2) confidence = 'Medium';
      else if (mech >= 2 && dup > 0) confidence = 'Medium-Low';
      
      document.getElementById('evidence-count').textContent = `${mechText}, ${driverText} (${dup} dup) · Confidence: ${confidence}`;
      
      const pressureColor = (p) => {
        const ps = String(p).toLowerCase();
        if (ps.includes('sell') || ps.includes('deleverage')) return 'var(--red)';
        if (ps.includes('buy') || ps === 'bonds_to_equity') return 'var(--green)';
        if (ps.includes('equity_to_bonds')) return 'var(--amber)';
        return 'var(--text2)';
      };
      
      const immEl = document.getElementById('immediate-pressure');
      const immVal = data?.dominantImmediatePressure || 'none';
      if (viewState.status === 'expired' || viewState.status === 'outdated') {
        immEl.textContent = 'Disabled (Data Outdated)';
        immEl.style.color = 'var(--text2)';
      } else {
        immEl.textContent = immVal === 'sell' ? 'Sell (retrospective estimate)' : immVal;
        immEl.style.color = pressureColor(immVal);
      }

      const medEl = document.getElementById('medium-pressure');
      if (viewState.status === 'expired' || viewState.status === 'outdated') {
        medEl.textContent = 'Disabled (Data Outdated)';
        medEl.style.color = 'var(--text2)';
      } else {
        medEl.textContent = formatText(data?.dominantMediumHorizonPressure);
        medEl.style.color = pressureColor(data?.dominantMediumHorizonPressure);
      }

      const tl = data?.flowTimeline;
      const timelineEl = document.getElementById('flow-timeline');
      if (tl) {
        const dirIcon = (d) => {
          const ds = String(d).toLowerCase();
          if (ds.includes('sell') || ds.includes('deleverage')) return '🔴';
          if (ds.includes('buy') || ds === 'bonds_to_equity') return '🟢';
          if (ds.includes('equity_to_bonds')) return '🟠';
          return '⚪';
        };
        const tiers = [
          { title: '📋 Retrospective Same-Day Estimate', subtitle: 'Estimated closing rebalance demand', items: tl.estimatedCompleted, emptyText: 'No completed flow estimated' },
          { title: '⏳ Ongoing Model Adjustment', subtitle: 'Active position changes, conditional on market', items: tl.ongoingAdjustment, emptyText: 'No active adjustment' },
          { title: '🔄 Recent Medium-Horizon Rotation', subtitle: 'Observed model configuration shifts', items: tl.recentRotation, emptyText: 'No recent structural rotation detected' },
          { title: '🔔 Conditional Future Pressure', subtitle: 'Requires conditions to materialize', items: tl.conditionalFuture, emptyText: 'No conditional pressure' }
        ];
        let html = '';
        for (const tier of tiers) {
          html += `<div style="margin-bottom: 10px; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 6px;">`;
          html += `<div style="font-weight: 600; font-size: 12px; color: var(--text); margin-bottom: 2px;">${tier.title}</div>`;
          html += `<div style="font-size: 10px; color: var(--text2); margin-bottom: 4px;">${tier.subtitle}</div>`;
          if (tier.items && tier.items.length > 0) {
            for (const item of tier.items) {
              const flowStr = item.estimatedFlow != null ? ' ' + formatUsd(item.estimatedFlow) : '';
              html += `<div style="margin-left: 8px;">${dirIcon(item.direction)} ${formatText(item.label)}${flowStr}</div>`;
              if (item.detail) {
                html += `<div style="margin-left: 24px; font-size: 11px; color: var(--text2);">${formatText(item.detail)}</div>`;
              }
              if (item.conditional) {
                html += `<div style="margin-left: 24px; font-size: 10px; color: var(--text2); font-style: italic;">${formatText(item.conditional)}</div>`;
              }
            }
          } else {
            html += `<div style="margin-left: 8px; color: var(--text2);">⚪ ${tier.emptyText}</div>`;
          }
          html += '</div>';
        }
        timelineEl.innerHTML = html;
      }
      
      document.getElementById('narrative-text').textContent = formatText(data?.narrative?.en);
      document.getElementById('narrative-zh').textContent = formatText(data?.narrative?.zh);
    }

    function renderVolControl(data, viewState) {
      if(!data) return;
      updateFreshness('vol', data, viewState);
      
      const change = data?.dailyPositionChange;
      const changeEl = document.getElementById('vol-change-prominent');
      changeEl.textContent = change != null ? ((change>0?'+':'') + formatFiniteNumber(change * 100, 2) + '%') : '—';
      changeEl.className = 'big-value ' + colorize(change);

      let flowStr = '—';
      if(data?.estimatedDailyFlowUsd != null) {
        flowStr = formatUsd(data.estimatedDailyFlowUsd);
        if(data?.estimatedFlowRange?.low != null && data?.estimatedFlowRange?.high != null) {
          const lo = Math.min(data.estimatedFlowRange.low, data.estimatedFlowRange.high);
          const hi = Math.max(data.estimatedFlowRange.low, data.estimatedFlowRange.high);
          flowStr += ` (${formatUsd(lo)} to ${formatUsd(hi)})`;
        }
      }
      const flowEl = document.getElementById('vol-est-flow');
      flowEl.textContent = flowStr;
      flowEl.className = 'data-value ' + colorize(data?.estimatedDailyFlowUsd);
      
      document.getElementById('vol-forecast').textContent = '—'; // Removed from schema
      
      const tgt = data?.targetExposureToday;
      document.getElementById('vol-exposure').textContent = tgt != null ? formatFiniteNumber(tgt * 100, 1) + '%' : '—';
      
      const act = data?.actualExposureToday;
      document.getElementById('vol-actual').textContent = act != null ? formatFiniteNumber(act * 100, 1) + '%' : '—';
      
      const p = data?.flowPressure || '—';
      document.getElementById('vol-pressure').textContent = formatText(p);

      document.getElementById('vol-speed').textContent = '—'; // Removed from schema
    }

    function renderLetf(data, viewState) {
      if(!data) return;
      updateFreshness('letf', data, viewState);

      const tbody = document.getElementById('letf-tbody');
      if(!data?.funds || !data.funds.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;">No data</td></tr>';
      } else {
        tbody.innerHTML = data.funds.map(f => {
          return `
            <tr>
              <td style="text-align:left;">${formatText(f?.name)}</td>
              <td>${f?.leverage != null ? f.leverage + 'x' : '—'}</td>
              <td class="${colorize(f?.underlyingReturn)}">${f?.underlyingReturn != null ? (f.underlyingReturn>0?'+':'') + formatFiniteNumber(f.underlyingReturn * 100, 2) + '%' : '—'}</td>
              <td class="${colorize(f?.grossRebalance)}">${f?.grossRebalance != null ? formatUsd(f.grossRebalance) : '—'}</td>
            </tr>
          `;
        }).join('');
      }
      let totStr = '—';
      const tot = data?.totalGrossRebalance;
      if (tot != null) {
         totStr = formatUsd(tot);
         if(data?.estimateRange?.low != null && data?.estimateRange?.high != null) {
           const lo = Math.min(data.estimateRange.low, data.estimateRange.high);
           const hi = Math.max(data.estimateRange.low, data.estimateRange.high);
           totStr += ` (${formatUsd(lo)} to ${formatUsd(hi)})`;
         }
      }
      const totEl = document.getElementById('letf-total');
      totEl.textContent = totStr;
      totEl.className = 'big-value ' + colorize(tot);
      
      document.getElementById('letf-window').textContent = formatText(data?.timing?.executionWindow);
    }

    function renderCta(data, viewState) {
      if(!data) return;
      updateFreshness('cta', data, viewState);
      
      const aggChange = data?.aggregatePositionChange;
      const aggEl = document.getElementById('cta-agg-change');
      aggEl.textContent = aggChange != null ? (aggChange > 0 ? '+' : '') + formatFiniteNumber(aggChange, 4) : '—';
      aggEl.className = 'big-value ' + colorize(aggChange);

      const regimeMap = { 'strong_buy': 'Strong Long', 'buy': 'Long', 'neutral': 'Neutral', 'sell': 'Short', 'strong_sell': 'Strong Short' };
      const regimeLabel = regimeMap[data?.positionRegime] || formatText(data?.positionRegime);
      document.getElementById('cta-pressure').textContent = `${regimeLabel} / ${formatText(data?.flowPressure)}`;
      
      const list = document.getElementById('cta-list');
      if(data?.assets && data.assets.length) {
        list.innerHTML = data.assets.map(a => {
          let nameHtml = formatText(a?.name);
          if (nameHtml === '10Y Yield Trend Signal') {
            nameHtml = `10Y Yield Trend <span style="font-size: 10px; color: var(--text2); margin-left: 4px;">(short-duration bias)</span>`;
          }
          return `
            <tr>
              <td style="text-align:left;">${nameHtml}</td>
              <td class="${colorize(a?.positionChange1d)}">${a?.positionChange1d != null ? (a.positionChange1d>0?'+':'') + formatFiniteNumber(a.positionChange1d, 4) : '—'}</td>
              <td class="${colorize(a?.distanceToSma50Pct)}">${a?.distanceToSma50Pct != null ? (a.distanceToSma50Pct>0?'+':'') + formatFiniteNumber(a.distanceToSma50Pct, 1) + '%' : '—'}</td>
            </tr>
          `;
        }).join('');
      } else {
        list.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center;">No data</td></tr>';
      }
    }

    function renderRiskParity(data, viewState) {
      if(!data) return;
      updateFreshness('rp', data, viewState);

      const allocChange = data?.equityAllocationChange5d;
      const allocEl = document.getElementById('rp-alloc-change');
      allocEl.textContent = allocChange != null ? (allocChange > 0 ? '+' : '') + formatFiniteNumber(allocChange * 100, 2) + ' pp' : '—';
      allocEl.className = 'big-value ' + colorize(allocChange);

      const dirMap = { 'equity_to_bonds': 'Equity → Bonds', 'bonds_to_equity': 'Bonds → Equity', 'stable': 'Stable' };
      const dirLabel = dirMap[data?.allocationDirection] || '—';
      if (allocEl.parentElement) {
        let dirSpan = document.getElementById('rp-alloc-dir');
        if (!dirSpan) {
          dirSpan = document.createElement('div');
          dirSpan.id = 'rp-alloc-dir';
          dirSpan.style.cssText = 'font-size: 12px; color: var(--text2); margin-top: 2px;';
          allocEl.parentElement.appendChild(dirSpan);
        }
        dirSpan.textContent = dirLabel;
        if (data?.allocationDirection === 'equity_to_bonds') dirSpan.style.color = 'var(--amber)';
        else if (data?.allocationDirection === 'bonds_to_equity') dirSpan.style.color = 'var(--green)';
        else dirSpan.style.color = 'var(--text2)';
      }

      const delEl = document.getElementById('rp-deleverage');
      const dp = data?.deleveragingPressure || 'none';
      delEl.textContent = dp === 'none' ? 'None detected' : formatText(dp);
      delEl.style.color = (dp === 'broad_deleveraging') ? 'var(--red)' : (dp === 'moderate_deleveraging' ? 'var(--amber)' : 'var(--text2)');
    }

    function renderMonthEnd(data, viewState) {
      if(!data) return;
      updateFreshness('me', data, viewState);
      
      document.getElementById('me-days').textContent = data?.daysToMonthEnd != null ? data.daysToMonthEnd : '—';
      if(data?.isRebalanceWindow) {
        document.getElementById('me-window-badge').style.display = 'block';
      } else {
        document.getElementById('me-window-badge').style.display = 'none';
      }

      const cw = data?.currentEquityWeight;
      const tw = data?.targetEquityWeight || 0.60;
      document.getElementById('me-weights').textContent = `${cw != null ? formatFiniteNumber(cw * 100, 1)+'%' : '—'} / ${tw != null ? formatFiniteNumber(tw * 100, 1)+'%' : '—'}`;

      const ovr = data?.equityOverweightPct;
      const dEl = document.getElementById('me-overweight');
      dEl.textContent = ovr != null ? ((ovr>0?'+':'') + formatFiniteNumber(ovr, 2) + '%') : '—';
      dEl.className = 'data-value ' + colorize(ovr);
      
      const biasEl = document.getElementById('me-bias');
      if (ovr != null && Math.abs(ovr) > 0.1) {
        const biasText = ovr > 0 ? 'Potential equity selling' : 'Potential equity buying';
        biasEl.textContent = biasText;
        biasEl.style.color = ovr > 0 ? 'var(--red)' : 'var(--green)';
      } else {
        biasEl.textContent = 'Near target';
        biasEl.style.color = 'var(--text2)';
      }

      const execEl = document.getElementById('me-exec-status');
      execEl.textContent = data?.isRebalanceWindow ? 'In rebalance window' : `Outside window (${data?.daysToMonthEnd ?? '—'} days to month end)`;

      const flow = document.getElementById('me-flow');
      if (data?.isRebalanceWindow && ovr != null && Math.abs(ovr) > 0.2) {
        flow.textContent = ovr > 0 ? 'Selling equity' : 'Buying equity';
        flow.style.color = ovr > 0 ? 'var(--red)' : 'var(--green)';
      } else {
        flow.textContent = 'None';
        flow.style.color = 'var(--text2)';
      }
    }

    function renderDeleveraging(data, viewState) {
      if(!data) return;
      updateFreshness('del', data, viewState);
      
      const score = data?.stressScore;
      document.getElementById('del-score').textContent = score != null ? formatFiniteNumber(score, 0) : '—';
      
      if(score != null && Number.isFinite(score)) {
        const bar = document.getElementById('del-bar');
        bar.style.width = Math.min(score, 100) + '%';
        bar.style.background = score > 80 ? 'var(--red)' : (score > 50 ? 'var(--amber)' : 'var(--green)');
      }
      
      document.getElementById('del-status').textContent = formatText(data?.status);
      
      const f = data?.estimatedFlowUsd;
      document.getElementById('stress-flow').textContent = f != null ? formatUsd(f) : 'Not estimable from available data';
      
      document.getElementById('del-vix').textContent = data?.vix != null ? formatFiniteNumber(data.vix, 2) : '—';
      document.getElementById('del-hy').textContent = data?.hyOas != null ? formatFiniteNumber(data.hyOas,0)+'bp' : '—';
      
      if (data?.status === 'insufficient_data') {
         document.getElementById('del-flashing').innerHTML = '⚠️ Unavailable — insufficient data<br>Missing inputs: ' + (data?.missingInputs || []).join(', ');
      } else if (data?.status === 'series_too_stale') {
         document.getElementById('del-flashing').innerHTML = '⚠️ Data is too stale to assess stress';
      } else {
         document.getElementById('del-flashing').innerHTML = '';
      }
    }

    function renderAll(data) {
      removeSkeletons();
      const viewState = determineViewState(data);
      globalAsOfDate = '--';
      
      // Update header info
      const headerStatus = document.getElementById('global-asof');
      if (viewState.status === 'outdated' || viewState.status === 'expired' || viewState.status === 'stale') {
         headerStatus.innerHTML = `<span style="color:var(--amber);">Data Status: ${viewState.status.toUpperCase()}</span>`;
         document.getElementById('stale-summary-banner').style.display = 'block';
         if (data?.snapshotGeneratedAt) {
           document.getElementById('error-banner').style.display = 'block';
           document.getElementById('error-banner').innerHTML = `⚠️ Data is ${viewState.status}. Showing snapshot generated at ${new Date(data.snapshotGeneratedAt).toLocaleString()}`;
         }
      } else {
         document.getElementById('stale-summary-banner').style.display = 'none';
         document.getElementById('error-banner').style.display = 'none';
      }

      renderSummary(data.summary, viewState);
      renderVolControl(data.volControl, viewState);
      renderLetf(data.leveragedEtf, viewState);
      renderCta(data.ctaTrend, viewState);
      renderRiskParity(data.riskParityProxy, viewState);
      renderMonthEnd(data.pensionRebalance, viewState);
      renderDeleveraging(data.stressConditions, viewState);
    }

    async function initializeSchema() {
      try {
        const res = await fetch('/api/schema/flow_v1');
        const schema = await res.json();
        validateFlowSnapshot = ajv.compile(schema);
      } catch (e) {
        console.error("Failed to load schema", e);
      }
    }

    async function fetchFlows() {
      if (currentAbortController) {
        currentAbortController.abort();
      }
      currentAbortController = new AbortController();

      try {
        const res = await fetch('/api/flows', { signal: currentAbortController.signal });
        if(!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        
        if (validateFlowSnapshot) {
          const isValid = validateFlowSnapshot(data);
          if (!isValid) {
            console.error("Frontend schema validation failed:", validateFlowSnapshot.errors);
            throw new Error("Invalid schema received from server");
          }
        }
        
        lastValidSnapshot = data;
        renderAll(data);
      } catch(e) {
        if (e.name === 'AbortError') return;
        console.error("Failed to fetch flows data:", e);
        
        const banner = document.getElementById('error-banner');
        banner.style.display = 'block';
        if (lastValidSnapshot) {
          const dt = new Date(lastValidSnapshot.snapshotGeneratedAt || Date.now()).toLocaleString();
          banner.innerHTML = `⚠️ Connection lost. Showing last successful snapshot from ${dt}.`;
          document.getElementById('stale-summary-banner').style.display = 'block';
          
          // Re-render the last valid snapshot with 'expired' state implicitly since we couldn't fetch
          renderAll(lastValidSnapshot);
        } else {
          banner.innerHTML = `⚠️ Flow data unavailable. No valid snapshot has been loaded.`;
          removeSkeletons();
        }
      }
    }

    // Initialize
    (async function() {
      await initializeSchema();
      await fetchFlows();
      setInterval(fetchFlows, 60000);
    })();

  </script>"""

new_html = html[:script_start] + new_script + html[script_end:]

with open("flow.html", "w") as f:
    f.write(new_html)
