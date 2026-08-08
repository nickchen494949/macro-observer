const { chromium } = require('playwright');
const symbol = process.argv[2];
const range = process.argv[3] || '5d';

if (!symbol) {
  console.log(JSON.stringify({ ok: false, error: 'usage: node fetch_yahoo.js SYMBOL [RANGE]' }));
  process.exit(1);
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });
    const page = await context.newPage();

    // Go to Yahoo Finance main page to set cookies/crumb
    await page.goto(`https://finance.yahoo.com/quote/${symbol}`, { waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});

    // Now fetch the JSON API
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=1d&includePrePost=false`;
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
    
    if (!response || !response.ok()) {
      console.log(JSON.stringify({ ok: false, error: `HTTP ${response ? response.status() : 'Unknown'}` }));
      process.exit(0);
    }
    
    const text = await response.text();
    const raw = JSON.parse(text);
    
    const result = raw.chart.result[0];
    const timestamps = result.timestamp;
    const closes = result.indicators.quote[0].close;
    
    const data = [];
    if (timestamps && closes) {
      for (let i = 0; i < timestamps.length; i++) {
        const ts = timestamps[i];
        const cl = closes[i];
        if (cl != null && !Number.isNaN(cl)) {
          const dateStr = new Date(ts * 1000).toISOString().split('T')[0];
          data.push([dateStr, Number(cl.toFixed(4))]);
        }
      }
    }
    
    console.log(JSON.stringify({ ok: true, symbol, data }));
  } catch (err) {
    console.log(JSON.stringify({ ok: false, error: err.message }));
  } finally {
    if (browser) await browser.close();
  }
})();
