const assert=require('assert'),fs=require('fs'),path=require('path'),os=require('os'),vm=require('vm');
const m=require('../backtest_v3'), coverage=require('../backtest/audit_data_coverage');
const store={ICSA:[['2020-01-04',250000]],CCSA:[['2020-01-04',1900000]],MARTSMPCSM44X72USS:[['2020-01-01',1],['2020-02-01',.3]]};
const ind=m.buildIndicatorsAsOf('2020-02-29',store);
assert.equal(ind.find(x=>x.id==='initial_claims').current,250);
assert.equal(ind.find(x=>x.id==='continuing_claims').current,1900);
assert.equal(ind.find(x=>x.id==='retail_sales_control_mom').current,.3);
assert.equal(m.computeYoY([['2020-01-01',100],['2020-02-01',110]],'2020-02-29').value,null);
assert(Math.abs(m.computeYoY([['2019-02-01',100],['2020-02-01',110]],'2020-02-29').value-10)<1e-10);
const rec=[{observationDate:'2020-03-01',value:100,availableAt:'2020-04-30T12:30:00Z'},
 {observationDate:'2020-03-01',value:110,availableAt:'2020-05-29T12:30:00Z'}];
assert.equal(m.getLatestValue(rec,'2020-03-30').value,null);assert.equal(m.getLatestValue(rec,'2020-05-01').value,100);
assert.equal(m.getLatestValue(rec,'2020-06-01').value,110);
const dates=['2020-01-31','2020-02-29','2020-03-31','2020-04-30','2020-05-31'];
const ev=[{name:'test',start:'2020-03-01',end:'2020-05-31'}];
const early=m.scoreAlerts(m.extractAlerts(dates,i=>i>=1),ev,dates);assert.equal(early.hits[0].leadMonths,1);
const late=m.scoreAlerts(m.extractAlerts(dates,i=>i>=3),ev,dates);assert.equal(late.hits[0].leadMonths,-1);
const unknown=m.scoreAlerts(m.extractAlerts(dates,m.baselineSpreadSignal({},dates,'A','B',400,'above')),ev,dates);
assert.equal(unknown.unavailableEvents.length,1);assert.equal(unknown.misses.length,0);
const always=m.scoreAlerts(m.extractAlerts(dates,()=>true),ev,dates);assert.equal(always.coverage.alertTimeShare,1);
const repeated=m.scoreAlerts(m.extractAlerts(dates,i=>i===2||i===4),ev,dates);assert.equal(repeated.falseAlarms.length,0);
assert.throws(()=>m.main([]),/BLOCK/);
const src=fs.readFileSync(path.join(__dirname,'../backtest_v3.js'),'utf8');
const context={require:n=>n==='./macro_engine'?{evaluateDiagnostics(){throw new Error('INJECTED_ENGINE_FAILURE')}}:require(n),
 module:{exports:{}},__dirname:path.join(__dirname,'..'),process,console};
vm.runInNewContext(src,context);assert.throws(()=>context.module.exports.main(['--revised-history']),/INJECTED_ENGINE_FAILURE/);
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'codex-coverage-'));
try {fs.mkdirSync(path.join(temp,'fred'));fs.mkdirSync(path.join(temp,'yahoo'));
 fs.writeFileSync(path.join(temp,'fred','GDP.json'),JSON.stringify({id:'GDP',values:[['2020-01-01',100]]}));
 const a=coverage.inspect(temp);assert.equal(a.status,'BLOCK');assert.equal(a.rows[0].frequency,'UNVERIFIED');
 assert.equal(a.rows[0].historicalAvailability,'UNVERIFIED');assert(a.errors.some(x=>x.includes('required series missing')));
} finally {fs.rmSync(temp,{recursive:true,force:true});}
console.log('PASS: units, retail, warmup, publication/revision boundaries, lead sign, unknown coverage, repeated alerts, fail-closed execution and coverage audit.');
