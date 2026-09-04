const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const outDir = path.join(__dirname, '../remote_results/captures');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8765', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2500);

  async function captureAroundText(text, filename, extraTop = 80, height = 760) {
    const locator = page.getByText(text, { exact: false }).first();
    await locator.scrollIntoViewIfNeeded();
    await page.waitForTimeout(600);
    const box = await locator.boundingBox();
    if (!box) throw new Error(`Could not find ${text}`);
    const y = Math.max(0, box.y - extraTop);
    const fullHeight = await page.evaluate(() => document.documentElement.scrollHeight);
    const clipHeight = Math.min(height, Math.max(200, fullHeight - y));
    const p = path.join(outDir, filename);
    await page.screenshot({ path: p, type: 'jpeg', quality: 58, clip: { x: 0, y, width: 1440, height: clipHeight } });
    return p;
  }

  const commodities = await captureAroundText('大宗商品期货 Commodities', 'commodities_recovered.jpg', 100, 700);
  const stocks = await captureAroundText('股票板块 Stock Sectors', 'stocks_recovered.jpg', 100, 900);

  await browser.close();

  const payload = {
    commodities: fs.readFileSync(commodities).toString('base64'),
    stocks: fs.readFileSync(stocks).toString('base64')
  };
  console.log(JSON.stringify(payload));
})().catch(err => {
  console.error(err.stack || err.message);
  process.exit(1);
});
