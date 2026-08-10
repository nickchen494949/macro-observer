'use strict';
const http = require('http');
const targets = new Set(['S&P 500','Nasdaq','Russell 2000']);
function getJson(path){return new Promise((resolve,reject)=>{http.get({hostname:'127.0.0.1',port:8765,path,timeout:15000},res=>{let b='';res.on('data',c=>b+=c);res.on('end',()=>{try{resolve(JSON.parse(b));}catch(e){reject(e);}})}).on('error',reject);});}
function walk(x,path,out){
  if (Array.isArray(x)){x.forEach((v,i)=>walk(v,`${path}[${i}]`,out));return;}
  if (!x || typeof x!=='object') return;
  if (targets.has(x.label)) out.push({path,label:x.label,current:x.current??null,zscore:x.zscore??null,zscoreAll:x.zscoreAll??null,changes:x.changes??null,id:x.id??null,chartKey:x.chartKey??null});
  for (const [k,v] of Object.entries(x)) walk(v,path?`${path}.${k}`:k,out);
}
(async()=>{const data=await getJson('/api/data');const out=[];walk(data,'root',out);console.log(JSON.stringify(out,null,2));})();
