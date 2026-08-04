const https = require('https');
const FRED_KEY = '5e8696731dbd4002c9043ea10e8fbc5f';

function check(series) {
  const url = `https://api.stlouisfed.org/fred/series?series_id=${series}&api_key=${FRED_KEY}&file_type=json`;
  https.get(url, (res) => {
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
      try {
        const parsed = JSON.parse(data);
        if (parsed.seriess && parsed.seriess[0]) {
          console.log(`${series}: OK - ${parsed.seriess[0].frequency}`);
        } else {
          console.log(`${series}: Failed - ${data}`);
        }
      } catch(e) {
        console.log(`${series}: Error parsing JSON - ${e.message}`);
      }
    });
  }).on('error', e => console.log(`${series}: Error - ${e.message}`));
}

check('NEWORDER');
check('A091RC1Q027SBEA');
check('W006RC1Q027SBEA');
check('GDP');
