const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({ viewport: { width: 1500, height: 2400 } });
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errs.push(m.type() + ': ' + m.text()); });
  await p.goto('http://localhost:8765', { waitUntil: 'domcontentloaded', timeout: 60000 });
  await p.waitForTimeout(25000);
  const out = await p.evaluate(() => {
    const rows = [...document.querySelectorAll('#stockBody tr')].slice(0, 8).map(r => r.innerText.replace(/\s+/g, ' '));
    const crow = [...document.querySelectorAll('#comBody tr')].slice(0, 3).map(r => r.innerText.replace(/\s+/g, ' '));
    return { status: document.getElementById('preStatus')?.innerText, pm: !!window._premarket, active: window._premarket?.active,
             n: Object.keys(window._premarket?.items || {}).length, rows, crow };
  });
  console.log(JSON.stringify(out, null, 1));
  console.log(errs.slice(0, 15).join('\n'));
  const el = await p.$('#stockBody');
  if (el) await el.screenshot({ path: 'scratch/stock_table.png' });
  await b.close();
})();
