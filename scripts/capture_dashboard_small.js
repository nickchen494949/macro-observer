const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const target = process.argv[2] || 'stocks';
  const map = {
    stocks: { text: '股票板块 Stock Sectors', top: 70, height: 520 },
    commodities: { text: '大宗商品期货 Commodities', top: 70, height: 440 }
  };
  const cfg = map[target];
  if (!cfg) throw new Error('unknown target');
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1000, height: 700 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8765', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1800);
  const locator = page.getByText(cfg.text, { exact: false }).first();
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(400);
  const box = await locator.boundingBox();
  if (!box) throw new Error('heading not found');
  const y = Math.max(0, box.y - cfg.top);
  const buf = await page.screenshot({ type: 'jpeg', quality: 34, clip: { x: 0, y, width: 1000, height: cfg.height } });
  await browser.close();
  console.log(buf.toString('base64'));
})().catch(e => { console.error(e.stack || e.message); process.exit(1); });
