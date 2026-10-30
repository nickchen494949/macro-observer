// Codex audited and modified: report observations, never invent a data-quality certificate.
const fs=require('fs'), path=require('path');
function inspect(root, requirePit=true) {
  const rows=[],errors=[];
  const required={fred:['DGS10'],yahoo:['_GSPC','SPY','QQQ','IWM','IEF','USO','GLD']};
  for(const kind of ['fred','yahoo']) {
    const dir=path.join(root,kind), seen=new Set();
    for(const f of fs.existsSync(dir)?fs.readdirSync(dir).filter(f=>f.endsWith('.json')).sort():[]) {
      const d=JSON.parse(fs.readFileSync(path.join(dir,f),'utf8'));
      const records=kind==='fred'&&Array.isArray(d.records);
      if(!records&&!Array.isArray(d.values)) continue;
      const id=f.slice(0,-5), v=records?d.records:d.values;seen.add(id);
      const observed=v.map(x=>records?x.observationDate:Array.isArray(x)?x[0]:x.date);
      const dates=records?[...new Set(observed)].sort():observed;
      const nonfinite=v.filter(x=>records?!Number.isFinite(x.value):Array.isArray(x)?!Number.isFinite(x[1]):!Number.isFinite(x.adjClose)).length;
      const keys=records?v.map(x=>`${x.observationDate}|${x.availableAt}`):dates;
      const duplicates=keys.length-new Set(keys).size;
      const invalidDates=observed.some(x=>!Number.isFinite(Date.parse(x))) ||
        (records&&v.some(x=>!Number.isFinite(Date.parse(x.availableAt))||Date.parse(x.availableAt)<Date.parse(x.observationDate)));
      const unsorted=dates.some((x,i)=>i&&x<=dates[i-1]);
      const gaps=dates.slice(1).map((x,i)=>(Date.parse(x)-Date.parse(dates[i]))/86400000).sort((a,b)=>a-b);
      const median=gaps.length?gaps[Math.floor(gaps.length/2)]:null;
      const pit=kind==='fred'?d.schemaVersion==='pit-observations-v1'&&Array.isArray(d.records)&&Boolean(d.source):null;
      let invalidOHLC=0;
      if(kind==='yahoo') invalidOHLC=v.filter(x=>![x.adjOpen,x.adjHigh,x.adjLow,x.adjClose].every(y=>Number.isFinite(y)&&y>0)
        ||x.adjLow>Math.min(x.adjOpen,x.adjClose)||x.adjHigh<Math.max(x.adjOpen,x.adjClose)).length;
      if(v.length<2||duplicates||unsorted||nonfinite||invalidOHLC||invalidDates) errors.push(`${kind}/${id}: insufficient/invalid observations`);
      if(kind==='yahoo'&&(d.schemaVersion!==2||d.adjustmentMethod!=='adjClose_divided_by_close')) errors.push(`${kind}/${id}: adjusted OHLC provenance unverified`);
      if(kind==='fred'&&requirePit&&!pit) errors.push(`${kind}/${id}: historical publication/vintage records unverified`);
      rows.push({kind,id,n:v.length,first:dates[0]||null,last:dates.at(-1)||null,
        missingValueShare:v.length?nonfinite/v.length:null,missingRequiredSessionShare:null,
        frequency:d.frequency||'UNVERIFIED',observedMedianGapDays:median,
        duplicateDates:duplicates,sorted:!unsorted,invalidOHLC,
        historicalAvailability:pit?'SOURCE_DECLARED_RECORDS':'UNVERIFIED',availabilityLag:'UNVERIFIED'});
    }
    for(const id of required[kind]) if(!seen.has(id))errors.push(`${kind}/${id}: required series missing`);
  }
  return {status:errors.length?'BLOCK':'STRUCTURAL_CHECKS_ONLY',pointInTimeCertified:false,
    note:'Observed gaps are not an authoritative calendar. Frequency and publication lag require source metadata. No claim of zero missing sessions.',rows,errors};
}
function main(args=process.argv.slice(2)) {
  const root=args.find(x=>!x.startsWith('--'))||path.join(__dirname,'../data');
  const report=inspect(root,!args.includes('--revised-history'));
  const out=path.join(__dirname,'../audit/data_coverage.json');fs.mkdirSync(path.dirname(out),{recursive:true});
  fs.writeFileSync(out,JSON.stringify(report,null,2));
  console.log(JSON.stringify({status:report.status,series:report.rows.length,errors:report.errors,output:out},null,2));
  if(report.errors.length)process.exitCode=2;
  return report;
}
module.exports={inspect,main};if(require.main===module)main();
