const fs = require('fs');
let html = fs.readFileSync('flow.html', 'utf8');

// 1. Fix updateFreshness to accept globalDate
html = html.replace(/function updateFreshness\(idPrefix, modData, viewState, globalDate\) \{[\s\S]*?function updateFreshness\(idPrefix, data, viewState\) \{[\s\S]*?\}\n    \}/, `function updateFreshness(idPrefix, data, viewState, globalDate) {\n      const date = data?.commonAsOfDate || globalDate || '--';\n      const el = document.getElementById(idPrefix + '-as-of');\n      if(el) {\n        el.textContent = 'As of ' + date;\n        if (viewState.marketFreshness === 'outdated') el.style.color = 'var(--text2)';\n      }\n    }`);

// 2. Fix the render calls in renderAll to pass globalAsOfDate
html = html.replace(/renderVolControl\(data\.volControl, viewState\);/, 'renderVolControl(data.volControl, viewState, globalAsOfDate);');
html = html.replace(/renderLetf\(data\.leveragedEtf, viewState\);/, 'renderLetf(data.leveragedEtf, viewState, globalAsOfDate);');
html = html.replace(/renderCta\(data\.ctaTrend, viewState\);/, 'renderCta(data.ctaTrend, viewState, globalAsOfDate);');
html = html.replace(/renderRiskParity\(data\.riskParity, viewState\);/, 'renderRiskParity(data.riskParity, viewState, globalAsOfDate);');
html = html.replace(/renderMonthEnd\(data\.pensionRebalance, viewState\);/, 'renderMonthEnd(data.pensionRebalance, viewState, globalAsOfDate);');
html = html.replace(/renderDeleveraging\(data\.stressConditions, viewState\);/, 'renderDeleveraging(data.stressConditions, viewState, globalAsOfDate);');

// 3. Fix the render* function signatures to accept globalDate
html = html.replace(/function renderVolControl\(data, viewState\)/, 'function renderVolControl(data, viewState, globalDate)');
html = html.replace(/updateFreshness\('vol', data, viewState\);/, "updateFreshness('vol', data, viewState, globalDate);");

html = html.replace(/function renderLetf\(data, viewState\)/, 'function renderLetf(data, viewState, globalDate)');
html = html.replace(/updateFreshness\('letf', data, viewState\);/, "updateFreshness('letf', data, viewState, globalDate);");

html = html.replace(/function renderCta\(data, viewState\)/, 'function renderCta(data, viewState, globalDate)');
html = html.replace(/updateFreshness\('cta', data, viewState\);/, "updateFreshness('cta', data, viewState, globalDate);");

html = html.replace(/function renderRiskParity\(data, viewState\)/, 'function renderRiskParity(data, viewState, globalDate)');
html = html.replace(/updateFreshness\('rp', data, viewState\);/, "updateFreshness('rp', data, viewState, globalDate);");

html = html.replace(/function renderMonthEnd\(data, viewState\)/, 'function renderMonthEnd(data, viewState, globalDate)');
html = html.replace(/updateFreshness\('pension', data, viewState\);/, "updateFreshness('pension', data, viewState, globalDate);");

html = html.replace(/function renderDeleveraging\(data, viewState\)/, 'function renderDeleveraging(data, viewState, globalDate)');
html = html.replace(/updateFreshness\('stress', data, viewState\);/, "updateFreshness('stress', data, viewState, globalDate);");

// 4. Fix summary pill mappings
html = html.replace(/document\.getElementById\('trend-amplifiers'\)\.innerHTML = '<span class="pill neutral">N\/A<\/span>';/, "fillPills('trend-amplifiers', Object.keys(summary?.trendAmplifiers || {}), 'buy'); // simplified logic later");
html = html.replace(/document\.getElementById\('cross-asset'\)\.innerHTML = '<span class="pill neutral">N\/A<\/span>';/, "fillPills('cross-asset', Object.keys(summary?.crossAssetDeRisking || {}), 'sell'); // simplified logic later");
html = html.replace(/document\.getElementById\('counter-cyclical'\)\.innerHTML = '<span class="pill neutral">N\/A<\/span>';/, "fillPills('counter-cyclical', Object.keys(summary?.counterCyclicalFlows || {}), 'neutral'); // simplified logic later");

// 5. Fix timeline conditional formatting for Stress
html = html.replace(/if \(mech === 'stressDeleveraging'\) \{\n\s*return \{\n\s*label: 'Stress-driven forced selling',/, `if (mech === 'stressDeleveraging') {
             return {
               label: d === 'neutral' ? 'Stress-triggered forced selling: not triggered' : 'Stress-triggered forced selling: active',`);

fs.writeFileSync('flow.html', html);
