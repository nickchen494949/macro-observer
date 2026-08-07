const fs = require('fs');
const { JSDOM } = require('jsdom');

const data = require('./real_flows.json');

console.log("=== API Fields ===");
console.log("data.marketDataAsOf:", data.marketDataAsOf);
console.log("data.modules.volControl.asOf:", data.modules?.volControl?.asOf);
console.log("data.modules.volControl.remainingExposureGap:", data.modules?.volControl?.remainingExposureGap);
console.log("data.modules.volControl.estimatedDailyFlowUsd:", data.modules?.volControl?.estimatedDailyFlowUsd);
console.log("data.modules.leveragedEtf.asOf:", data.modules?.leveragedEtf?.asOf);
console.log("data.modules.leveragedEtf.executionTiming:", data.modules?.leveragedEtf?.executionTiming);
console.log("data.summary.trendAmplifiers:", JSON.stringify(data.summary?.trendAmplifiers));
console.log("data.summary.crossAssetDeRisking:", JSON.stringify(data.summary?.crossAssetDeRisking));
console.log("data.summary.timelinePressures:", JSON.stringify(data.summary?.timelinePressures));
console.log("==================\n");

const html = fs.readFileSync('flow.html', 'utf-8');
const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  beforeParse(window) {
    window.fetch = async () => ({ ok: true, json: async () => data });
  }
});

setTimeout(() => {
  const document = dom.window.document;
  const timelineText = document.getElementById('flow-timeline').textContent;
  
  const target = data.modules?.volControl?.targetExposureToday;
  const actual = data.modules?.volControl?.actualExposureToday;
  if (target < actual) {
    console.assert(timelineText.includes('reducing exposure'), "Timeline must include 'reducing exposure'");
  }

  const gap = data.modules?.volControl?.remainingExposureGap;
  if (gap < 0) {
    console.assert(!timelineText.includes('addition'), "Timeline must not include 'addition'");
  }
  
  if (data.modules?.volControl?.status === 'ok') {
    const vcDate = document.getElementById('vol-asof')?.textContent;
    console.assert(vcDate !== '--', "VolControl rendered date should not be '--'");
  }

  if (data.modules?.leveragedEtf?.executionTiming != null) {
    const letfTiming = document.getElementById('letf-window')?.textContent;
    console.assert(!letfTiming.includes('—'), "LETF card should not contain '• —'");
  }
  
  const pills = document.getElementById('trend-amplifiers')?.textContent;
  if (Object.keys(data.summary?.trendAmplifiers || {}).length > 0) {
    console.assert(!pills.includes('None'), "Rendered pills must not be 'None'");
  }
  
  if (data.modules?.stressConditions?.status === 'calm') {
    console.assert(timelineText.includes('not triggered'), "Timeline must contain 'not triggered'");
  }
  
  console.log("Timeline text:", timelineText.trim());
  console.log("LETF timing:", document.getElementById('letf-window')?.textContent);
  console.log("Pills text:", pills);
  console.log("Vol-Control As Of:", document.getElementById('vol-asof')?.textContent);
  console.log("DONE");
}, 500);
