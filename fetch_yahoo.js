const { chromium } = require('playwright');
const symbol = process.argv[2];
const range = process.argv[3] || '5d';

if (!symbol) {
  console.log(JSON.stringify({ ok: false, error: 'usage: node fetch_yahoo.js SYMBOL [RANGE]' }));
  process.exit(1);
}

// CTA ETF proxies must use adjusted closes so dividends/splits do not create
// artificial trend breaks. Existing index/futures/dashboard symbols keep the
// historical raw-close behavior of this helper.
const ADJUSTED_CLOSE_SYMBOLS = new Set(['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD', 'TLT', 'SOXX']);

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

    // Now fetch the JSON API. Include corporate actions / adjusted close so ETF
    // trend proxies can remain on a total-return-consistent price history.
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=1d&includePrePost=false&events=div%2Csplits&includeAdjustedClose=true`;
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
    const adjCloses = result.indicators?.adjclose?.[0]?.adjclose || closes;
    const useAdjusted = ADJUSTED_CLOSE_SYMBOLS.has(symbol);
    
    const data = [];
    if (timestamps && closes) {
      for (let i = 0; i < timestamps.length; i++) {
        const ts = timestamps[i];
        const rawClose = closes[i];
        const adjustedClose = adjCloses ? adjCloses[i] : null;
        const selected = useAdjusted && adjustedClose != null ? adjustedClose : rawClose;
        if (selected != null && !Number.isNaN(selected)) {
          const dateStr = new Date(ts * 1000).toISOString().split('T')[0];
          data.push([dateStr, Number(selected.toFixed(4))]);
        }
      }
    }
    
    console.log(JSON.stringify({ ok: true, symbol, priceField: useAdjusted ? 'adjClose' : 'close', data }));
  } catch (err) {
    console.log(JSON.stringify({ ok: false, error: err.message }));
  } finally {
    if (browser) await browser.close();
  }
})();
