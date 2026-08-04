const monthCodes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'];

function getFedFundsTickers() {
  const d = new Date();
  let m = d.getUTCMonth(); // 0-11
  let y = d.getUTCFullYear() % 100; // e.g. 26
  const tickers = [];
  
  for (let i = 0; i < 18; i++) {
    tickers.push({
      symbol: `ZQ${monthCodes[m]}${y}.CBT`,
      label: `${d.getUTCFullYear()}-${String(m+1).padStart(2,'0')}`
    });
    m++;
    if (m > 11) {
      m = 0;
      y++;
      d.setUTCFullYear(d.getUTCFullYear() + 1);
    }
  }
  return tickers;
}
console.log(getFedFundsTickers());
