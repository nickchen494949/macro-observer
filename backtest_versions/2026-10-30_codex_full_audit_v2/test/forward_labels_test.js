const assert=require('assert'),fs=require('fs'),path=require('path'),os=require('os');
const {main,calculateDrawdownBounds}=require('../backtest/build_forward_labels');
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'codex-forward-labels-'));
try {
 const dates=[];for(let d=new Date('2023-01-03T00:00:00Z');dates.length<25;d.setUTCDate(d.getUTCDate()+1))
  if(d.getUTCDay()!==0&&d.getUTCDay()!==6)dates.push(d.toISOString().slice(0,10));
 const bars=dates.map((date,i)=>({date,open:100,high:120,low:100,close:105,adjOpen:100,adjHigh:120,adjLow:100,adjClose:105}));
 const snap={'2023-01-03':{modules:{volControl:{signalAvailableAt:'2023-01-03T22:00:00Z',firstTradableSession:'2023-01-04'}}}};
 const sp=path.join(tmp,'snap.json'),out=path.join(tmp,'labels.json'),yp=path.join(tmp,'_GSPC.json');
 fs.writeFileSync(sp,JSON.stringify(snap));
 const run=v=>{fs.writeFileSync(yp,JSON.stringify({values:v}));main([sp,out,tmp]);return JSON.parse(fs.readFileSync(out))['2023-01-03'].modules.volControl;};
 let x=run(bars);assert(Math.abs(x.return1dOpen-.05)<1e-12);assert.equal(x.lastLabelSession5d,dates[5]);
 assert(Math.abs(x.mdd1d-(100/120-1))<1e-12);assert(Math.abs(x.mddOptimistic1d+.125)<1e-12);
 assert.equal(x.drawdownMethod,'daily_ohlc_conservative_bound_not_intraday_path');
 assert.equal(run(bars.slice(0,4)).labelStatus,'insufficient_future_data');
 assert.throws(()=>run(bars.map(x=>[x.date,x.close])),/OHLC|format|date/i);
 const absent=JSON.parse(JSON.stringify(snap));absent['2023-01-03'].modules.volControl.firstTradableSession='1999-01-01';
 fs.writeFileSync(sp,JSON.stringify(absent));assert.equal(run(bars).labelStatus,'missing_entry_session');
 fs.writeFileSync(sp,JSON.stringify(snap));
 const bad=bars.map(x=>({...x}));bad[1].adjOpen=90;assert.equal(run(bad).labelStatus,'adjusted_ohlc_integrity_error');
 assert.throws(()=>calculateDrawdownBounds([{adjOpen:100,adjHigh:90,adjLow:80,adjClose:100}],100));
 console.log('PASS: isolated real-path labels, horizon alignment, OHLC bounds, short data and invalid adjustment.');
} finally {fs.rmSync(tmp,{recursive:true,force:true});}
