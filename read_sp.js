const { chromium } = require('playwright');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
  });
  const page = await context.newPage();
  
  console.log("Navigating...");
  try {
    const response = await page.goto('https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-risk-control-indices.pdf', { waitUntil: 'networkidle' });
    const buffer = await response.body();
    fs.writeFileSync('output.pdf', buffer);
    console.log("Written output.pdf, size:", buffer.length);
  } catch(e) {
    console.error(e);
  }
  
  await browser.close();
})();
