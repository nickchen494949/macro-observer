const fs = require('fs');
const { JSDOM } = require('jsdom');
const assert = require('assert');

const fixtures = [
  'real_mixed_snapshot.json',
  'real_buying_snapshot.json',
  'partial_unavailable_snapshot.json'
];

async function runTests() {
  const html = fs.readFileSync('flow.html', 'utf-8');
  let hasError = false;
  
  for (const fix of fixtures) {
    console.log(`\n--- Testing ${fix} ---`);
    const payload = JSON.parse(fs.readFileSync(`test/fixtures/flow/${fix}`, 'utf-8'));
    
    // Test LETF Math Invariant
    if (payload.modules.leveragedEtf.status === 'ok') {
      const sum = payload.modules.leveragedEtf.funds.reduce((a, b) => a + b.grossRebalanceUsd, 0);
      assert.ok(Math.abs(sum - payload.modules.leveragedEtf.totalGrossRebalanceUsd) < 1, "LETF sum invariant failed");
      console.log("✅ LETF Math Invariant Passed");
    }

    const dom = new JSDOM(html, { 
      runScripts: "dangerously",
      beforeParse(window) {
        window.fetch = async () => ({
          ok: true,
          json: async () => payload
        });
      }
    });

    await new Promise(resolve => setTimeout(resolve, 500));
    const document = dom.window.document;
    
    const errors = [];
    function check(condition, message) {
      if (!condition) {
        errors.push(message);
        console.error("❌ " + message);
      }
    }

    const bodyText = document.body.textContent;
    const forbidden = ['NaN', 'undefined', '[object Object]', 'Infinity', 'Loading'];
    forbidden.forEach(str => {
      check(!bodyText.includes(str), `Forbidden string found: ${str}`);
    });
    
    if (payload.modules.volControl.status === 'ok') {
      check(!bodyText.includes('~—'), "Placeholder '~—' found when status ok");
      
      const cardVolText = document.getElementById('vol-est-flow').textContent;
      const cardVol = cardVolText.split(' ')[0]; // extracts -$8.0B
      const timelineText = document.getElementById('flow-timeline').textContent;
      
      check(timelineText.includes(cardVol) || cardVol === '—', "Vol-control Card and Timeline values differ: " + cardVol);
    }
    
    if (payload.modules.riskParity.status === 'ok') {
      const cardRp = document.getElementById('rp-alloc-change').textContent;
      const timelineText = document.getElementById('flow-timeline').textContent;
      // extract magnitude
      const mag = Math.abs(parseFloat(cardRp));
      if (!isNaN(mag)) {
         check(timelineText.includes(mag.toString()) || timelineText.includes(mag.toFixed(2)), "Risk Parity Card and Timeline values differ: " + mag);
      }
    }
    
    if (payload.modules.leveragedEtf.status === 'ok' && payload.modules.leveragedEtf.totalGrossRebalanceUsd !== 0) {
      const cardLetf = document.getElementById('letf-total').textContent.split(' ')[0]; 
      const timelineText = document.getElementById('flow-timeline').textContent;
      check(timelineText.includes(cardLetf) || cardLetf === '—', "LETF Card and Timeline values differ: " + cardLetf);
    }

    if (errors.length > 0) {
      hasError = true;
    } else {
      console.log(`✅ All assertions passed for ${fix}`);
    }
  }

  if (hasError) process.exit(1);
  else process.exit(0);
}

runTests().catch(e => { console.error(e); process.exit(1); });
