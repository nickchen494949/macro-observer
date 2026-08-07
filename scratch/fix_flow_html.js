const fs = require('fs');
let html = fs.readFileSync('flow.html', 'utf8');

// 1. In fetch block, check schemaVersion and extract modules
html = html.replace(/const data = await res\.json\(\);/, `const data = await res.json();
        if (data.schemaVersion !== 2) throw new Error('Unsupported flow API schema');
        const { volControl, leveragedEtf, ctaTrend, riskParity, pensionRebalance, stressConditions } = data.modules || {};
        // attach back to data for legacy functions
        data.volControl = volControl;
        data.leveragedEtf = leveragedEtf;
        data.ctaTrend = ctaTrend;
        data.riskParity = riskParity;
        data.pensionRebalance = pensionRebalance;
        data.stressConditions = stressConditions;
`);

// 2. Immediate Pressure & Medium Horizon
html = html.replace(/const immVal = data\?\.dominantImmediatePressure \|\| 'none';/, `const immVal = data?.summary?.timelinePressures?.retrospectiveSameDay?.direction || 'none';`);
html = html.replace(/medEl.textContent = formatText\(data\?\.dominantMediumHorizonPressure\);/, `medEl.textContent = formatText(data?.summary?.timelinePressures?.ongoing1To5Days?.direction);`);
html = html.replace(/medEl.style.color = pressureColor\(data\?\.dominantMediumHorizonPressure\);/, `medEl.style.color = pressureColor(data?.summary?.timelinePressures?.ongoing1To5Days?.direction);`);

// 3. Rewrite renderSummary timeline part completely
const timelineReplacement = `
      const tl = data?.summary?.timelinePressures;
      const timelineEl = document.getElementById('flow-timeline');
      if (tl) {
        const dirIcon = (d) => {
          const ds = String(d).toLowerCase();
          if (ds.includes('sell') || ds.includes('deleverage')) return '🔴';
          if (ds.includes('buy') || ds === 'bonds_to_equity') return '🟢';
          if (ds.includes('equity_to_bonds')) return '🟠';
          return '⚪';
        };
        const formatTimelineItem = (mech, d, status) => {
           if (status !== 'ok') return { label: mech + ' unavailable', detail: '', conditional: '' };
           if (mech === 'leveragedEtf') {
             return {
               label: \`Leveraged ETF gross rebalance (\${globalAsOfDate} close)\`,
               detail: data.leveragedEtf.totalGrossRebalanceUsd != null ? ' ' + formatUsd(data.leveragedEtf.totalGrossRebalanceUsd) : ''
             };
           }
           if (mech === 'volControl') {
             const gap = data.volControl.remainingExposureGap;
             const gapDir = gap != null ? (gap > 0 ? 'addition' : 'reduction') : '';
             const gapAbs = data.volControl.remainingExposureGap != null ? Math.abs(data.volControl.remainingExposureGap * 400e9) : null;
             return {
               label: d === 'selling' ? 'Vol-control reducing exposure' : 'Vol-control increasing exposure',
               detail: \`Latest daily adjustment: \${data.volControl.estimatedDailyFlowUsd != null ? (data.volControl.estimatedDailyFlowUsd > 0 ? '+' : '') + formatUsd(data.volControl.estimatedDailyFlowUsd) : '—'}. Remaining model exposure gap: ~\${gapAbs != null ? formatUsd(gapAbs) : '—'} of potential \${gapDir} if target remains unchanged.\`,
               conditional: \`Execution path: decaying, conditional on realized volatility\`
             };
           }
           if (mech === 'ctaTrend') {
             return { label: 'CTA trend-following adjustment', detail: '', conditional: 'Manager-dependent timing' };
           }
           if (mech === 'riskParity') {
             const shift = data.riskParity.equityAllocationChange5d;
             return {
               label: \`Risk parity model: \${d === 'equity_to_bonds' ? 'equity → bonds' : 'bonds → equity'}\`,
               detail: \`\${shift != null ? formatFiniteNumber(Math.abs(shift)*100, 2) + 'pp' : '—'} over past 5D\`
             };
           }
           if (mech === 'pensionRebalance') {
             return { label: 'Balanced-fund rebalance', detail: '' };
           }
           if (mech === 'stressConditions') {
             return { label: 'Stress-driven forced selling', detail: '' };
           }
           return { label: mech, detail: '' };
        };

        const tiers = [
          { title: '📋 Retrospective Same-Day Estimate', subtitle: 'Estimated closing rebalance demand', item: tl.retrospectiveSameDay, emptyText: 'No completed flow estimated' },
          { title: '⏳ Ongoing Model Adjustment', subtitle: 'Active position changes, conditional on market', item: tl.ongoing1To5Days, emptyText: 'No active adjustment' },
          { title: '🔄 Recent Medium-Horizon Rotation', subtitle: 'Observed model configuration shifts', item: tl.recent5To20Days, emptyText: 'No recent structural rotation detected' },
          { title: '🔔 Conditional Future Pressure', subtitle: 'Requires conditions to materialize', item: tl.conditionalFuture, emptyText: 'No conditional pressure' }
        ];
        let html = '';
        for (const tier of tiers) {
          html += \`<div style="margin-bottom: 10px; padding: 8px; background: rgba(255,255,255,0.03); border-radius: 6px;">\`;
          html += \`<div style="font-weight: 600; font-size: 12px; color: var(--text); margin-bottom: 2px;">\${tier.title}</div>\`;
          html += \`<div style="font-size: 10px; color: var(--text2); margin-bottom: 4px;">\${tier.subtitle}</div>\`;
          if (tier.item && (tier.item.mechanisms.length > 0 || tier.item.status !== 'ok')) {
            const mechs = tier.item.mechanisms.length > 0 ? tier.item.mechanisms : ['data'];
            for (const mech of mechs) {
              const formatted = formatTimelineItem(mech, tier.item.direction, tier.item.status);
              html += \`<div style="margin-left: 8px;">\${tier.item.status === 'ok' ? dirIcon(tier.item.direction) : '⚪'} \${formatText(formatted.label)}\${formatted.detail && mech==='leveragedEtf' ? formatted.detail : ''}</div>\`;
              if (formatted.detail && mech !== 'leveragedEtf') {
                html += \`<div style="margin-left: 24px; font-size: 11px; color: var(--text2);">\${formatText(formatted.detail)}</div>\`;
              }
              if (formatted.conditional) {
                html += \`<div style="margin-left: 24px; font-size: 10px; color: var(--text2); font-style: italic;">\${formatText(formatted.conditional)}</div>\`;
              }
            }
          } else {
            html += \`<div style="margin-left: 8px; color: var(--text2);">⚪ \${tier.emptyText}</div>\`;
          }
          html += '</div>';
        }
        timelineEl.innerHTML = html;
      }
`;

html = html.replace(/const tl = data\?\.flowTimeline;[\s\S]*?timelineEl\.innerHTML = html;\s*\}/, timelineReplacement);

// 4. Trend Amplifiers and Independent Domains (clear loading)
html = html.replace(/<div id="trend-amplifiers" class="pill-list"><span class="pill buy skeleton">Loading<\/span><\/div>/, `<div id="trend-amplifiers" class="pill-list"></div>`);
html = html.replace(/<div id="cross-asset" class="pill-list"><span class="pill sell skeleton">Loading<\/span><\/div>/, `<div id="cross-asset" class="pill-list"></div>`);
html = html.replace(/<div id="counter-cyclical" class="pill-list"><span class="pill stabilizer skeleton">Loading<\/span><\/div>/, `<div id="counter-cyclical" class="pill-list"></div>`);
html = html.replace(/<div id="data-domains" class="pill-list"><span class="pill neutral skeleton">Loading<\/span><\/div>/, `<div id="data-domains" class="pill-list"></div>`);

const pillFilling = `
      const fillPills = (id, arr, type) => {
         const el = document.getElementById(id);
         if (!arr || arr.length === 0) { el.innerHTML = '<span class="pill neutral">None</span>'; return; }
         el.innerHTML = arr.map(a => \`<span class="pill \${type}">\${a.replace(/_/g, ' ')}</span>\`).join('');
      };
      fillPills('data-domains', data?.summary?.independentDataDomains, 'neutral');
      document.getElementById('trend-amplifiers').innerHTML = '<span class="pill neutral">N/A</span>';
      document.getElementById('cross-asset').innerHTML = '<span class="pill neutral">N/A</span>';
      document.getElementById('counter-cyclical').innerHTML = '<span class="pill neutral">N/A</span>';
`;
html = html.replace(/document\.getElementById\('narrative-text'\)\.textContent/, pillFilling + "\n      document.getElementById('narrative-text').textContent");

// 5. Update LETF bindings
html = html.replace(/data\?\.totalEstimatedFlow/g, `data?.totalGrossRebalanceUsd`);
html = html.replace(/fund\.grossRebalance/g, `fund.grossRebalanceUsd`);

// 6. Update Stress bindings
html = html.replace(/VIX Level\/Change\(5D\)/g, `VIX Level`);
html = html.replace(/HY OAS Level\/Change\(5D\)/g, `HY OAS Level`);
html = html.replace(/const vixChange = data\?\.vixChange5d;[\s\S]*?vixEl\.textContent = \`\$\{vix\} \/ \$\{vcStr\}\`;/, `vixEl.textContent = vix != null ? formatFiniteNumber(vix, 2) : '—';`);
html = html.replace(/const hyChange = data\?\.hyOasChange5d;[\s\S]*?hyEl\.textContent = \`\$\{hy\} \/ \$\{hycStr\}\`;/, `hyEl.textContent = hy != null ? formatFiniteNumber(hy, 2) : '—';`);

fs.writeFileSync('flow.html', html);
