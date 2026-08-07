const fs = require('fs');
const path = require('path');
const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const { JSDOM } = require('jsdom');
const { runProductionFlows } = require('../lib/flow_wrappers');

// --- 1. Numeric Validation Test ---
console.log('=== Numeric Validation Test ===');
const makeTimeSeries = (base, startDate) => {
  const d = new Date(startDate);
  let val = base;
  return Array(150).fill(0).map(() => {
    const dStr = d.toISOString().split('T')[0];
    d.setDate(d.getDate() + 1);
    val = val * (1 + (Math.random() - 0.5) * 0.02);
    return [dStr, val];
  });
};

const storeFull = {
  yahoo: { 
    '^GSPC': makeTimeSeries(5000, '2024-01-01'), 
    '^VIX': makeTimeSeries(15, '2024-01-01'),
    'SOXX': makeTimeSeries(100, '2024-01-01'),
    'IBB': makeTimeSeries(100, '2024-01-01'),
    'XLE': makeTimeSeries(100, '2024-01-01')
  },
  fred: { 
    'DGS10': makeTimeSeries(4.0, '2024-01-01'),
    'BAMLH0A0HYM2': makeTimeSeries(3.0, '2024-01-01'),
    'DFII10': makeTimeSeries(1.5, '2024-01-01'),
    'DCOILWTICO': makeTimeSeries(80, '2024-01-01')
  }
};
const resFull = runProductionFlows(storeFull);
console.log('Numeric API fields remain numbers after formatting:', 
    typeof resFull.modules.volControl.targetExposureToday === 'number' && 
    typeof resFull.modules.stressConditions.vix === 'number' && 
    typeof resFull.modules.stressConditions.hyOas === 'number' && 
    typeof resFull.modules.riskParity.equityAllocationChange5d === 'number' ? 'PASS' : 'FAIL');

// --- 2. JSDOM Setup ---
const htmlStr = fs.readFileSync(path.join(__dirname, '../flow.html'), 'utf-8');

const dom = new JSDOM(htmlStr, { 
  runScripts: "dangerously",
  beforeParse(window) {
    window.ajv7 = function() {
      this.compile = () => { return () => true; };
    };
    window.ajvFormats = function() {};
  }
});
const window = dom.window;
const document = window.document;

setTimeout(() => {
  console.log('\n=== JSDOM Partial Cache Test ===');
  
  // Fake fetch function in the JSDOM to test race conditions and partial overrides
  // We will directly call window.renderAll(data) mimicking fetchFlows behavior 
  // Wait, fetchFlows handles the caching logic! So we will test fetchFlows logic!
  
  let fetchCall = 0;
  let mockResponses = [];
  window.fetch = async (url) => {
    const resData = mockResponses[fetchCall++];
    return {
      ok: true,
      json: async () => resData
    };
  };

  // Scenario 1: Complete cache survives subsequent partial response
  const completeSnapshot = {
     ...resFull,
     snapshotQuality: 'complete',
     snapshotGeneratedAt: '2026-08-01T12:00:00Z',
     summary: { ...resFull.summary, dominantRegime: 'complete_test' }
  };
  
  const partialSnapshot = {
     ...resFull,
     snapshotQuality: 'partial',
     snapshotGeneratedAt: '2026-08-01T13:00:00Z',
     summary: { ...resFull.summary, dominantRegime: 'partial_test' }
  };
  
  mockResponses = [completeSnapshot, partialSnapshot];
  
  window.fetchFlows().then(() => {
     // First fetch is complete
     const regime1 = document.getElementById('dominant-regime').textContent;
     return window.fetchFlows().then(() => {
         // Second fetch is partial
         const regime2 = document.getElementById('dominant-regime').textContent;
         const bannerText = document.getElementById('error-banner').textContent;
         
         const survives = regime1 === 'complete test' && regime2 === 'complete test';
         console.log('Complete cache survives subsequent partial response:', survives ? 'PASS' : 'FAIL');
         console.log('Banner text for partial:', bannerText.trim() !== '' ? 'PASS' : 'FAIL');
         
         // Scenario 2: Older asynchronous response cannot overwrite newer response
         console.log('\n=== Race Condition Test ===');
         
         const olderSnapshot = {
            ...resFull,
            snapshotQuality: 'complete',
            snapshotGeneratedAt: '2026-08-01T11:00:00Z', // older
            summary: { ...resFull.summary, dominantRegime: 'old_test' }
         };
         
         mockResponses = [olderSnapshot];
         // Reset fetchCall but keep the same window context so it remembers the 13:00:00Z partial timestamp
         fetchCall = 0;
         return window.fetchFlows().then(() => {
            const regime3 = document.getElementById('dominant-regime').textContent;
            // It should have rejected olderSnapshot and kept the current rendered UI (complete_test)
            console.log('Older asynchronous response cannot overwrite newer response:', regime3 === 'complete test' ? 'PASS' : 'FAIL');
            
            // Scenario 3: Fresh API + outdated market observations handled independently
            console.log('\n=== Expired vs Outdated Test ===');
            const outdatedMarketSnapshot = {
               ...resFull,
               snapshotQuality: 'complete',
               snapshotGeneratedAt: new Date().toISOString(), // Fresh API
               marketDataAsOf: '2020-01-01', // Outdated Market
               summary: { ...resFull.summary, dominantRegime: 'fresh_api_old_market' }
            };
            
            mockResponses = [outdatedMarketSnapshot];
            fetchCall = 0;
            return window.fetchFlows().then(() => {
               const headerText = document.getElementById('global-asof-status').textContent;
               console.log('Header text:', headerText);
               const isOutdated = headerText.includes('OUTDATED');
               const isExpired = headerText.includes('EXPIRED');
               
               console.log('Fresh API + outdated market observations handled independently:', (isOutdated && !isExpired) ? 'PASS' : 'FAIL');
            });
         });
     });
  });
  
}, 500);
