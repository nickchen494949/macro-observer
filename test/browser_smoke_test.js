const puppeteer = require('puppeteer');
const { spawn } = require('child_process');
const fs = require('fs');

async function run() {
  // modify server.js port for testing
  let serverCode = fs.readFileSync('server.js', 'utf8');
  fs.writeFileSync('server_test.js', serverCode.replace(/const PORT = 8765;/, 'const PORT = 8766;'));

  const server = spawn('node', ['server_test.js'], { stdio: 'ignore' });

  // Wait for server to start
  await new Promise(resolve => setTimeout(resolve, 3000));

  console.log("Server started. Launching Puppeteer...");
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

  await page.goto('http://localhost:8766/flow.html', { waitUntil: 'networkidle0' });
  await new Promise(resolve => setTimeout(resolve, 2000)); // allow rendering

  const bodyText = await page.evaluate(() => document.body.textContent);
  
  const forbidden = ['NaN', 'undefined', '[object Object]', 'Infinity', 'Loading'];
  for (const str of forbidden) {
    if (bodyText.includes(str)) {
      console.error(`❌ Forbidden string found in DOM: ${str}`);
      hasError = true;
    }
  }
  
  if (!hasError) {
    console.log("✅ No forbidden strings or console errors found in live browser.");
  }

  await browser.close();
  server.kill();

  if (hasError) process.exit(1);
  else process.exit(0);
}

run().catch(err => {
  console.error(err);
  process.exit(1);
});
