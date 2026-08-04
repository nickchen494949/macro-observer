const fs = require('fs');

let code = fs.readFileSync('server.js', 'utf8');

function slugify(label) {
  let s = label.replace(/[^\w\s-]/g, '').trim().toLowerCase().replace(/\s+/g, '_');
  if (!s) s = 'id_' + Math.random().toString(36).substr(2, 5);
  return s;
}

// Add ids to RATE_ROWS, COMMODITY_ROWS, ECONOMY_ROWS, MACRO_TRANSMISSION_ROWS
['RATE_ROWS', 'COMMODITY_ROWS', 'ECONOMY_ROWS', 'MACRO_TRANSMISSION_ROWS'].forEach(arrName => {
  const regex = new RegExp(`const ${arrName} = \\[([\\s\\S]*?)\\];`);
  code = code.replace(regex, (match, inner) => {
    const lines = inner.split('\n');
    const newLines = lines.map(line => {
      if (!line.trim() || line.trim().startsWith('//')) return line;
      const labelMatch = line.match(/label:\s*['"]([^'"]+)['"]/);
      if (labelMatch) {
        let label = labelMatch[1];
        let id = '';
        if (label.includes('Core PCE 1M')) id = 'core_pce_1m_ann';
        else if (label.includes('Core PCE 3M')) id = 'core_pce_3m_ann';
        else if (label.includes('Core PCE 6M')) id = 'core_pce_6m_ann';
        else if (label.includes('Core PCE 通胀 (YoY)')) id = 'core_pce_yoy';
        else if (label.includes('PCE Price 通胀')) id = 'pce_yoy';
        else if (label.includes('Trimmed Mean PCE 12M')) id = 'trimmed_pce_yoy';
        else if (label.includes('Median CPI 1M')) id = 'median_cpi_1m_ann';
        else if (label.includes('Median CPI YoY')) id = 'median_cpi_yoy';
        else if (label.includes('16% Trimmed CPI 1M')) id = 'trimmed_cpi_1m_ann';
        else if (label.includes('16% Trimmed CPI YoY')) id = 'trimmed_cpi_yoy';
        else if (label.includes('Fed Fund Futures (12M Path)')) id = 'fed_path_12m';
        else if (label.includes('Fed Fund Rate')) id = 'fed_fund_rate';
        else if (label.includes('Sahm Rule')) id = 'sahm_rule';
        else if (label.includes('Agg Weekly Payrolls')) id = 'real_income_yoy';
        else if (label.includes('Nonfarm Payrolls')) id = 'nfp_mom';
        else if (label.includes('Private Payrolls')) id = 'private_payrolls_mom';
        else id = slugify(label);
        
        return line.replace(/\{/, `{ id:'${id}',`);
      }
      return line;
    });
    return `const ${arrName} = [${newLines.join('\n')}];`;
  });
});

// Update the map functions to include 'id: r.id'
code = code.replace(/label: r\.label,/g, 'id: r.id, label: r.label,');

fs.writeFileSync('server.js', code);
console.log('Added ids to server.js');
