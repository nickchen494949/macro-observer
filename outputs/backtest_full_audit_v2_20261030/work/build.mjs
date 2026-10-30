import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const work=path.dirname(fileURLToPath(import.meta.url)),out=path.dirname(work);
const d=JSON.parse(await fs.readFile(path.join(work,'data.json'),'utf8'));
const wb=Workbook.create(), navy='#233D59', teal='#257F83';let serial=0;
const col=n=>String.fromCharCode(65+n);
function sheet(name,title,sub,headers,rows,widths,pct=[]){
 const s=wb.worksheets.add(name);s.showGridLines=false;s.tabColor=navy;
 const end=rows.length+5,last=col(headers.length-1);
 s.getRange(`A1:${last}${end}`).format={font:{name:'Arial',size:10,color:'#22364B'},rowHeight:25,verticalAlignment:'center',wrapText:false};
 s.mergeCells(`A1:${last}2`);s.getRange('A1').values=[[title]];s.getRange('A1').format={fill:navy,font:{name:'Arial',size:18,bold:true,color:'#FFFFFF'},rowHeight:26};
 s.mergeCells(`A3:${last}4`);s.getRange('A3').values=[[sub]];s.getRange('A3').format={wrapText:true,font:{name:'Arial',size:11,color:'#52677D'},rowHeight:24};
 s.getRange(`A5:${last}${end}`).values=[headers,...rows];
 s.tables.add(`A5:${last}${end}`,true,`AuditTable${++serial}`).showFilterButton=true;
 s.getRange(`A5:${last}5`).format={fill:teal,font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},rowHeight:40,wrapText:true,horizontalAlignment:'center'};
 widths.forEach((w,i)=>s.getRange(`${col(i)}1:${col(i)}${end}`).format.columnWidth=w);
 for(const i of pct)s.getRange(`${col(i)}6:${col(i)}${end}`).setNumberFormat('0.0%;[Red]-0.0%;0.0%');
 if(rows.length){s.freezePanes.freezeRows(5);s.freezePanes.freezeColumns(Math.min(2,headers.length-1));}
 return s;
}
const summary=sheet('先看结论','全部回测审计与同期比较 · Codex v2',
 '2023-01—2026-09，共45个月。旧目录340条已逐项处置；修复并重跑可验证分支。最高收益不等于最可靠。',
 ['策略','45个月年化','月末最大回撤','2023—2025年化','2026前9月累计','成交口径','该怎么读'],d.headline,[40,17,18,20,22,30,67],[1,2,3,4]);
const noteRows=[
 '原目录340条：201条重跑并核算、34条重跑但股票池/价格有缺口、90条阻塞、11条条件统计、4条旧结果退役。',
 '不是全部每月换仓：多数股票组合按月检查；T1每月开新批次持有6个月；SEP按事件交易；ETF基准买入持有。',
 '同收盘科技三因子Top1为本次历史最高；尚未证明最可靠。SPY是最简单、最容易独立核验的基准。',
 'ML2同样开盘口径下：纯动量Top1胜过模型冠军。模型长期冠军约92.6%的净利润贡献来自SNDK。',
 '股票主表回撤只观察月末，可能明显小于月中损失；毛收益基准未扣买卖成本。所有历史均已反复查看。',
 '冻结输入 → 全入口审核/修复 → 实际重跑与账本核算 → 同期比较完成 → 数据不足项明确保留。'
];
for(let i=0;i<noteRows.length;i++){const r=16+i*2;summary.mergeCells(`A${r}:G${r+1}`);summary.getRange(`A${r}`).values=[[noteRows[i]]];summary.getRange(`A${r}`).format={wrapText:true,fill:i===0?'#E4F1F0':'#F1F4F7',font:{name:'Arial',size:11,color:'#28465C'},rowHeight:24};}
const perfHeaders=['编号','策略组','策略原名','同期年化','月末最大回撤','累计收益','月数','比较组','调仓频率','交易费用','成交时点','审计结论','账本路径','截至2025年化','2026前9月累计'];
sheet('同期45个月','全部可比股票组合 · 同期45个月','2023-01—2026-09。保留原策略/股票池/费用。按成交口径分组；数据缺口组只作诊断；本金早已归零的组合不能从2023重新起算。',perfHeaders,d.same,[10,26,65,17,18,18,10,37,39,55,85,52,100,20,23],[3,4,5,13,14]);
sheet('长期141个月','较长历史比较 · 141个月','2015-01—2026-09。只纳入完整月历且允许在该时点比较的策略；固定因子选择期与独立现金起步的ML留出段不拼接。',perfHeaders,d.long,[10,26,65,17,18,18,10,37,39,55,85,52,100,20,23],[3,4,5,13,14]);
sheet('旧目录340条','原来的340条 · 一条都不遗漏','空白表示该口径不可得，绝不拿旧成绩补成修正后表现。同期数据见45个月表；本表另保留各自原始可用期间。',
 ['旧编号','策略组','中文名称','原名称','最终处置','调仓频率','同期45月年化','同期45月回撤','原可用起点','原可用终点','原可用期间年化','原可用期间回撤','新编号','当前账本','限制与原因'],d.inventory,[10,28,57,67,52,39,20,20,18,18,23,24,10,100,125],[6,7,10,11]);
const nativeHeaders=['编号','策略组','策略名称','最终处置','调仓频率','起点','终点','观察数','期间年化','最大回撤','回撤频率','成本','成交方式','账本路径','限制'];
sheet('补充发现120条','补充发现与明确拆分的项目','包括因子研究、现行RF/Ridge与共同期切片、SEP原有参数、漏列诊断。不是120个新发明的策略。',nativeHeaders,d.extra,[10,29,68,50,40,18,18,13,18,18,23,65,90,110,140],[8,9]);
sheet('行业共同40期','行业模型 · 完全一致的40个持有区间','2023-04-04—2026-08-04，T+2收盘；所有行均为未扣交易成本毛收益。date原列是形成月，不能误当自然持有月。',
 ['策略','年化毛收益','期末最大回撤','期数','实际开始','实际结束','说明'],d.rotation.map(r=>[r[2],r[8],r[9],r[7],'2023-04-04','2026-08-04','历史估值资料未获逐期版本认证；不是自然月末成交']),[58,21,24,12,20,20,92],[1,2]);
sheet('SEP事件交易','纯SEP · 原有20组参数及买入持有','2015-09-18—2026-08-13；事件触发、次交易日收盘、日度回撤。20组参数不是20份独立验证，也不是按月换仓。',
 ['策略／既有参数','期间年化','日度最大回撤','开始','结束','成本','限制'],d.sep.map(r=>[r[2],r[8],r[9],r[5],r[6],r[11],r[14]]),[57,19,21,20,20,70,125],[1,2]);
sheet('96组原参数','主策略原有96组参数','固定旧搜索空间重跑。参数搜索不能当96次独立成功；选择窗口与后段成绩分别保存。',
 ['回看月数','行业数','每行业股票数','行业评分','不同收益序列ID','2023起同期年化','同期月末回撤','选择期年化','后段年化','后段月末回撤','账本路径'],d.grid,[16,14,21,18,25,23,22,20,20,22,110],[5,6,7,8,9]);
sheet('91项信号研究','预测信号研究 · 不是组合收益','宏观、资金流、鹰派路径、47个单因子。保留原有统计单位和证据结论，不把相关性或命中次数写成盈利。',
 ['研究组','信号','结论','指标单位','指标值','样本数','p值','解释','来源'],d.signals,[30,60,45,25,20,16,20,100,105]);
sheet('ML2收益集中度','ML2原规范的集中度诊断','2015-01—2026-09。去最大贡献股：原目标冻结、该份额留同利率现金、重算费用；剔除最好年：非连续样本诊断，不是可投资CAGR。',
 ['模型／对照','原年化','最大贡献股','该股占净利润贡献','去该股留现金后年化','最好年份','剔除该年的样本年化','原月末最大回撤'],d.concentration,[64,18,19,27,30,18,31,25],[1,3,4,6,7]);
sheet('股票池','股票够不够、对不对','数量足够研究某个股票范围，不代表历史成员、退市和身份已经完全正确。实际可选数按原规则统计。',
 ['股票范围','最少可选','最多可选','中位可选','结论','缺口'],d.pools,[29,17,17,17,46,130]);
sheet('修正记录','主要修正 · 保留审计证据','旧版和失败尝试保留。只在独立v2副本修改回测；dashboard未改；当前数字全部以本轮索引为准。',
 ['问题','修正／处理','证据文件'],d.fixes,[25,125,105]);
sheet('来源与指纹','来源与SHA-256','相对路径基于 backtest_versions/2026-10-30_codex_full_audit_v2。可用账本经逐月核算；哈希证明版本一致，不能替代原始数据真实性认证。',
 ['文件路径','SHA-256'],d.sources.map(r=>[r.path,r.sha256]),[135,83]);
sheet('口径说明','比较口径与剩余限制','Codex audited and modified — full audit v2 · 2026-10-30。按本轮实际证据给出结论，不是整个历史数据的无条件认证。',
 ['事项','说明'],d.notes,[28,155]);
wb.recalculate();
await fs.writeFile(path.join(work,'inspect.json'),JSON.stringify(await wb.inspect({kind:'region',sheetId:'先看结论',range:'A5:G13',maxChars:6500,tableMaxRows:9,tableMaxCols:7}),null,2));
await fs.writeFile(path.join(work,'errors.json'),JSON.stringify(await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:1500}),null,2));
for(const [name,range,id] of [['先看结论','A1:G27',1],['行业共同40期','A1:G13',2],['旧目录340条','A1:H13',3]]){
 const png=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(path.join(work,`preview_${id}.png`),new Uint8Array(await png.arrayBuffer()));
}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(out,'全部回测审核与同期比较_Codex_v2.xlsx'));
console.log(JSON.stringify({workbook:'全部回测审核与同期比较_Codex_v2.xlsx',sheets:serial,counts:d.counts}));
