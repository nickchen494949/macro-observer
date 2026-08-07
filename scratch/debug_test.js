const fs = require('fs');
const { JSDOM } = require('jsdom');
const payload = JSON.parse(fs.readFileSync('test/fixtures/flow/real_mixed_snapshot.json', 'utf-8'));
const html = fs.readFileSync('flow.html', 'utf-8');
const dom = new JSDOM(html, { 
  runScripts: "dangerously",
  beforeParse(window) { window.fetch = async () => ({ ok: true, json: async () => payload }); }
});

setTimeout(() => {
  const document = dom.window.document;
  console.log("Loading occurrences:");
  console.log(document.body.innerHTML.match(/[^>]*Loading[^<]*/g));

  console.log("Vol-Control Card:", document.getElementById('vol-est-flow').textContent);
  console.log("Risk Parity Card:", document.getElementById('rp-alloc-change').textContent);
  console.log("LETF Card:", document.getElementById('letf-total').textContent);
  console.log("Timeline:\n", document.getElementById('flow-timeline').textContent);

}, 500);
