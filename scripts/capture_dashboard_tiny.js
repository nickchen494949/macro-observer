const { chromium } = require('playwright');
(async () => {
  const target = process.argv[2] || 'stocks';
  const cfg = target === 'commodities'
    ? { text: '大宗商品期货 Commodities', top: 55, h: 290 }
    : { text: '股票板块 Stock Sectors', top: 55, h: 330 };
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 760, height: 520 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8765', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1200);
  const locator = page.getByText(cfg.text, { exact: false }).first();
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  const box = await locator.boundingBox();
  if (!box) throw new Error('heading not found');
  const y = Math.max(0, box.y - cfg.top);
  const buf = await page.screenshot({ type: 'jpeg', quality: 18, clip: { x: 0, y, width: 760, height: cfg.h } });
  await browser.close();
  console.log(buf.toString('base64'));
})().catch(e => { console.error(e.stack || e.message); process.exit(1); });
