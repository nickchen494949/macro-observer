const { chromium } = require('playwright');
(async () => {
  const target = process.argv[2] || 'stocks';
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 900, height: 700 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8765', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1200);

  const headingText = target === 'commodities' ? '大宗商品期货 Commodities' : '股票板块 Stock Sectors';
  const locator = page.getByText(headingText, { exact: false }).first();
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(250);
  const box = await locator.boundingBox();
  if (!box) throw new Error('heading not found');

  const y = Math.max(0, box.y - 10);
  const h = target === 'commodities' ? 180 : 210;
  const buf = await page.screenshot({ type: 'jpeg', quality: 8, clip: { x: 0, y, width: 520, height: h } });
  await browser.close();
  console.log(buf.toString('base64'));
})().catch(e => { console.error(e.stack || e.message); process.exit(1); });
