const fs = require('fs');
let html = fs.readFileSync('flow.html', 'utf8');

// fix renderAll call
html = html.replace(/renderSummary\(data\.summary, viewState\);/, 'renderSummary(data, viewState);');

// fix renderSummary body
html = html.replace(/function renderSummary\(data, viewState\) \{/g, `function renderSummary(data, viewState) {\n      if(!data) return;\n      const summary = data.summary || {};`);

// replace all data?. to summary?. in renderSummary top logic
html = html.replace(/data\?\.dominantRegime/g, 'summary?.dominantRegime');
html = html.replace(/data\?\.mechanismCount/g, 'summary?.mechanismCount');
html = html.replace(/data\?\.driverCount/g, 'summary?.driverCount');
html = html.replace(/data\?\.duplicatedDriverCount/g, 'summary?.duplicatedDriverCount');
html = html.replace(/data\?\.dominantImmediatePressure/g, 'summary?.dominantImmediatePressure');
html = html.replace(/data\?\.dominantMediumHorizonPressure/g, 'summary?.dominantMediumHorizonPressure');
html = html.replace(/data\?\.timelinePressures/g, 'summary?.timelinePressures');
html = html.replace(/data\?\.independentDataDomains/g, 'summary?.independentDataDomains');
html = html.replace(/data\?\.narrative/g, 'summary?.narrative');

fs.writeFileSync('flow.html', html);
