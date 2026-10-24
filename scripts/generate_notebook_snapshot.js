const fs = require('fs');
const http = require('http');
const path = require('path');

http.get('http://localhost:8765/api/data', (res) => {
  let body = '';
  res.on('data', d => body += d);
  res.on('end', () => {
    const data = JSON.parse(body);
    let md = `# Macro Observer Snapshot\nGenerated: ${new Date().toISOString()}\n\n`;
    
    md += `## 1. Macro Diagnostics\n`;
    if (data.diagnostics) {
      for (const [key, val] of Object.entries(data.diagnostics)) {
        md += `### ${key}\n`;
        md += `- Status: ${val.status || 'N/A'}\n`;
        md += `- Message: ${val.message || 'N/A'}\n`;
      }
    }

    md += `\n## 2. Market & Macro Data\n`;
    const groups = {};
    for (const row of (data.data || [])) {
      if (!groups[row.group]) groups[row.group] = [];
      groups[row.group].push(row);
    }
    
    for (const [groupName, rows] of Object.entries(groups)) {
      md += `\n### ${groupName}\n`;
      for (const r of rows) {
        md += `- **${r.label}**: Current: ${r.current}, Z-Score(4Y): ${r.zScore_4y}, 1M Change: ${r.delta_1m}\n`;
      }
    }
    
    const driveDir = `${process.env.HOME}/Library/CloudStorage/GoogleDrive-chenminein2020@gmail.com/My Drive/NotebookLM_Data`;
    let outPath = '';
    
    try {
      if (!fs.existsSync(driveDir)) {
        fs.mkdirSync(driveDir, { recursive: true });
      }
      outPath = path.join(driveDir, 'Macro_Snapshot.md');
      fs.writeFileSync(outPath, md);
      console.log(`Saved successfully to Google Drive: ${outPath}`);
    } catch(e) {
      console.log(`Google Drive not fully ready yet (${e.message}). Falling back to Desktop.`);
      outPath = `${process.env.HOME}/Desktop/Macro_Snapshot_For_NotebookLM.md`;
      fs.writeFileSync(outPath, md);
      console.log(`Saved to ${outPath}`);
    }
  });
}).on('error', console.error);
