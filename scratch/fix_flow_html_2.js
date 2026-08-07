const fs = require('fs');
let html = fs.readFileSync('flow.html', 'utf8');

// fix LETF variables in renderLetf
html = html.replace(/f\?\.grossRebalance/g, 'f?.grossRebalanceUsd');
html = html.replace(/f\.grossRebalance/g, 'f.grossRebalanceUsd');
html = html.replace(/data\?\.totalGrossRebalance;/g, 'data?.totalGrossRebalanceUsd;'); // since my prev replace failed if it missed this

// fix loading skeletons if status is not ok
html = html.replace(/const tbody = document.getElementById\('letf-tbody'\);/, `const tbody = document.getElementById('letf-tbody');\n      if(data.status !== 'ok') { tbody.innerHTML = '<tr><td colspan="4" class="text-muted" style="text-align:center;">Unavailable</td></tr>'; } else `);
html = html.replace(/const tbody = document.getElementById\('cta-list'\);/, `const tbody = document.getElementById('cta-list');\n      if(data.status !== 'ok') { tbody.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center;">Unavailable</td></tr>'; } else `);

fs.writeFileSync('flow.html', html);
