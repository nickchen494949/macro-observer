import re

with open('flow.html', 'r') as f:
    text = f.read()

# I will write a custom replacement for the View State & Quality Management up to fetchFlows

replacement = """    // View State & Quality Management
    var lastCompleteSnapshot = null;
    var lastValidSnapshot = null; // keeps the latest valid snapshot (partial or complete)
    var lastRenderedSnapshotTimestamp = 0;
    var currentAbortController = null;
    var globalAsOfDate = '--';

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

    function determineViewState(snapshot, apiConnectionFailed = false) {
      if (!snapshot) return { apiStatus: 'unavailable', marketFreshness: 'unavailable', quality: null };
      
      const asOfStr = snapshot.marketDataAsOf;
      const genAtStr = snapshot.snapshotGeneratedAt;
      const todayStr = new Date().toISOString().split('T')[0];
      
      let marketFreshness = 'current';
      if (asOfStr) {
        const lag = getTradingDaysBetween(asOfStr, todayStr);
        if (lag > 2) marketFreshness = 'outdated';
      }
      
      let apiStatus = 'current';
      if (apiConnectionFailed) {
         apiStatus = 'expired'; // we treat failed fetch as expired/stale depending on time, but fallback always shows banner
      }
      if (genAtStr) {
        const genTime = new Date(genAtStr).getTime();
        const now = Date.now();
        const hoursOld = (now - genTime) / (1000 * 60 * 60);
        if (hoursOld > 2) {
          apiStatus = 'stale';
        }
      }
      return { apiStatus, marketFreshness, quality: snapshot.snapshotQuality };
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
        let badges = [];
        if (viewState.apiStatus === 'expired' || viewState.apiStatus === 'stale') {
           badges.push(viewState.apiStatus.toUpperCase());
        }
        if (viewState.marketFreshness === 'outdated') {
           badges.push('OUTDATED');
        }
        if (viewState.quality === 'partial') {
           badges.push('PARTIAL');
        }
        if (badges.length > 0) {
           staleBadge.style.display = 'block';
           staleBadge.textContent = badges.join(' / ');
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
      
      const isForwardDisabled = viewState.apiStatus === 'expired' || viewState.marketFreshness === 'outdated';
      
      const immEl = document.getElementById('immediate-pressure');
      const immVal = data?.dominantImmediatePressure || 'none';
      if (isForwardDisabled) {
        immEl.textContent = 'Disabled (Data Outdated)';
        immEl.style.color = 'var(--text2)';
      } else {
        immEl.textContent = immVal === 'sell' ? 'Sell (retrospective estimate)' : immVal;
        immEl.style.color = pressureColor(immVal);
      }

      const medEl = document.getElementById('medium-pressure');
      if (isForwardDisabled) {
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
          html += `<div style=\"margin-bottom: 10px; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 6px;\">`;
          html += `<div style=\"font-weight: 600; font-size: 12px; color: var(--text); margin-bottom: 2px;\">${tier.title}</div>`;
          html += `<div style=\"font-size: 10px; color: var(--text2); margin-bottom: 4px;\">${tier.subtitle}</div>`;
          if (tier.items && tier.items.length > 0) {
            for (const item of tier.items) {
              const flowStr = item.estimatedFlow != null ? ' ' + formatUsd(item.estimatedFlow) : '';
              html += `<div style=\"margin-left: 8px;\">${dirIcon(item.direction)} ${formatText(item.label)}${flowStr}</div>`;
              if (item.detail) {
                html += `<div style=\"margin-left: 24px; font-size: 11px; color: var(--text2);\">${formatText(item.detail)}</div>`;
              }
              if (item.conditional) {
                html += `<div style=\"margin-left: 24px; font-size: 10px; color: var(--text2); font-style: italic;\">${formatText(item.conditional)}</div>`;
              }
            }
          } else {
            html += `<div style=\"margin-left: 8px; color: var(--text2);\">⚪ ${tier.emptyText}</div>`;
          }
          html += '</div>';
        }
        timelineEl.innerHTML = html;
      }
      
      document.getElementById('narrative-text').textContent = formatText(data?.narrative?.en);
      document.getElementById('narrative-zh').textContent = formatText(data?.narrative?.zh);
    }

    function renderVolControl(data, viewState) {
"""

# Now the renderAll and fetchFlows parts:

replacement_end = """    function renderAll(data, apiConnectionFailed = false, isPartialOverlay = false) {
      removeSkeletons();
      const viewState = determineViewState(data, apiConnectionFailed);
      globalAsOfDate = '--';
      
      const headerStatus = document.getElementById('global-asof');
      if (viewState.apiStatus === 'stale' || viewState.apiStatus === 'expired' || viewState.marketFreshness === 'outdated' || viewState.quality === 'partial' || isPartialOverlay) {
         let statuses = [];
         if (viewState.apiStatus !== 'current') statuses.push(`API ${viewState.apiStatus.toUpperCase()}`);
         if (viewState.marketFreshness !== 'current') statuses.push(`Market ${viewState.marketFreshness.toUpperCase()}`);
         if (viewState.quality === 'partial') statuses.push(`PARTIAL`);
         if (isPartialOverlay) statuses.push(`PARTIAL API OVERLAY`);
         
         headerStatus.innerHTML = `<span style=\"color:var(--amber);\">Data Status: ${statuses.join(', ')}</span>`;
         document.getElementById('stale-summary-banner').style.display = 'block';
         
         if (apiConnectionFailed && data?.snapshotGeneratedAt) {
           document.getElementById('error-banner').style.display = 'block';
           document.getElementById('error-banner').innerHTML = `⚠️ Connection lost.<br><span style="font-size:12px; font-weight:normal;">Showing last successful snapshot from ${new Date(data.snapshotGeneratedAt).toLocaleString()}. No values have been refreshed since then.</span>`;
         } else if (isPartialOverlay) {
           document.getElementById('error-banner').style.display = 'block';
           document.getElementById('error-banner').innerHTML = `⚠️ Warning: Latest API update was partial. Showing previous complete snapshot from ${new Date(data.snapshotGeneratedAt).toLocaleString()}.`;
         } else {
           document.getElementById('error-banner').style.display = 'none';
         }
      } else {
         document.getElementById('stale-summary-banner').style.display = 'none';
         document.getElementById('error-banner').style.display = 'none';
         headerStatus.innerHTML = `Current Validated Snapshot`;
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
        console.error(\"Failed to load schema\", e);
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
            console.error(\"Frontend schema validation failed:\", validateFlowSnapshot.errors);
            throw new Error(\"Invalid schema received from server\");
          }
        }
        
        const incomingTime = new Date(data.snapshotGeneratedAt || Date.now()).getTime();
        if (incomingTime < lastRenderedSnapshotTimestamp) {
           console.warn("Rejecting older response received out of order", data.snapshotGeneratedAt);
           return;
        }
        lastRenderedSnapshotTimestamp = incomingTime;
        lastValidSnapshot = data;
        
        if (data.snapshotQuality === 'complete') {
           lastCompleteSnapshot = data;
           renderAll(data);
        } else {
           if (lastCompleteSnapshot) {
               // Render old complete snapshot but warn that latest fetch was partial
               renderAll(lastCompleteSnapshot, false, true);
           } else {
               // Render partial
               renderAll(data);
           }
        }
      } catch(e) {
        if (e.name === 'AbortError') return;
        console.error(\"Failed to fetch flows data:\", e);
        
        const banner = document.getElementById('error-banner');
        banner.style.display = 'block';
        if (lastCompleteSnapshot || lastValidSnapshot) {
          const snapToRender = lastCompleteSnapshot || lastValidSnapshot;
          renderAll(snapToRender, true);
        } else {
          banner.innerHTML = `⚠️ Flow data unavailable. No valid snapshot has been loaded.`;
          removeSkeletons();
        }
      }
    }
"""

start1 = text.find("    // View State & Quality Management")
end1 = text.find("    function renderVolControl(data, viewState) {")

start2 = text.find("    function renderAll(data) {")
end2 = text.find("    // Initialize")

new_html = text[:start1] + replacement + text[end1:start2] + replacement_end + text[end2:]

with open('flow.html', 'w') as f:
    f.write(new_html)
