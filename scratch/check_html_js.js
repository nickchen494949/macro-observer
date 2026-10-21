const fs = require('fs');
const html = fs.readFileSync('index.html', 'utf8');
const blocks = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
let bad = 0;
blocks.forEach((b, i) => { try { new Function(b); } catch (e) { bad++; console.log('block', i, 'ERROR', e.message); } });
console.log('script blocks:', blocks.length, 'errors:', bad);
