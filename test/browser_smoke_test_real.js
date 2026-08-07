const puppeteer = require('puppeteer');

async function run() {
  console.log("Launching Puppeteer against REAL server...");
  const browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  
  let hasError = false;
  
  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.error('PAGE ERROR:', msg.text());
      hasError = true;
    }
  });

  page.on('pageerror', error => {
    console.error('PAGE UNCAUGHT EXCEPTION:', error.message);
    hasError = true;
  });

  await page.goto('http://localhost:8765/flow.html', { waitUntil: 'networkidle0' });
  await new Promise(resolve => setTimeout(resolve, 2000)); // allow rendering

  const bodyText = await page.evaluate(() => document.body.textContent);
  const bodyHtml = await page.evaluate(() => document.body.innerHTML);
  
  const forbidden = ['NaN', 'undefined', '[object Object]', 'Infinity', 'Loading'];
  for (const str of forbidden) {
    if (bodyText.includes(str)) {
      console.error(`❌ Forbidden string found in DOM: ${str}`);
      hasError = true;
    }
  }
  
  if (!hasError) {
    console.log("✅ No forbidden strings or console errors found in live browser on port 8765.");
  } else {
      console.log("HTML:", bodyHtml.substring(0, 500));
  }

  await browser.close();

  if (hasError) process.exit(1);
  else process.exit(0);
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
