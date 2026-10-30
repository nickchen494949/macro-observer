const { alignToCalendar } = require('../../lib/data_validation');
const fs = require('fs');

const nyse = JSON.parse(fs.readFileSync('data/nyse_calendar.json'));

const assets = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD'];

for (const a of assets) {
    const raw = JSON.parse(fs.readFileSync('data/yahoo/' + a + '.json')).values;
    const aligned = alignToCalendar(a, raw, 'cta_close', nyse);
    console.log(a, "Raw len:", raw.length, "Aligned len:", aligned ? aligned.length : null);
}
