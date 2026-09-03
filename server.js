'use strict';
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const { execFile } = require('child_process');
const { evaluateDiagnostics } = require('./macro_engine');
const { fetchAllNews, loadNewsFromDisk } = require('./lib/fetch_news');

const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const ajv = new Ajv({ allErrors: true });
addFormats(ajv);

if (!process.env.FRED_API_KEY) {
  throw new Error('FRED_API_KEY is required in .env');
}
if (!process.env.LOCAL_ADMIN_TOKEN) {
  throw new Error('LOCAL_ADMIN_TOKEN is required in .env');
}

const flowApiSchemaStr = fs.readFileSync(path.join(__dirname, 'config/schemas/flow_api_v2.schema.json'), 'utf-8');
const validateFlowSnapshot = ajv.compile(JSON.parse(flowApiSchemaStr));

const flowApiSchemaV3Str = fs.readFileSync(path.join(__dirname, 'config/schemas/flow_api_v3.schema.json'), 'utf-8');
const validateFlowSnapshotV3 = ajv.compile(JSON.parse(flowApiSchemaV3Str));

const PORT = 8765;
const FRED_KEY = process.env.FRED_API_KEY || '';
const DATA_DIR = path.join(__dirname, 'data');
const FRED_DIR = path.join(DATA_DIR, 'fred');
const YAHOO_DIR = path.join(DATA_DIR, 'yahoo');
const VALUATION_DIR = path.join(DATA_DIR, 'valuation');
const CSV_DIR = path.join(__dirname, 'csv');
const CSV_FRED = path.join(CSV_DIR, 'fred');
const CSV_YAHOO = path.join(CSV_DIR, 'yahoo');
// Feature flags
const USE_RULE_ENGINE_V2 = true;
const ENABLE_PCA = false;
const ENABLE_INFLATION_FORECAST = false;

// ============================================
// ALL INDICATORS
// ============================================
const FRED_SERIES_IDS = [
  // Interest rates
  'DFII10','BAMLH0A0HYM2','BAMLC0A0CM','SOFR','IORB',
  'DFF','DGS3MO','DGS1','DGS2','DGS3','DGS5','DGS7','DGS10','DGS20','DGS30','T10Y3M',
  // Commodities (daily)
  'DCOILWTICO',   // WTI Crude Oil
  'DHHNGSP',      // Henry Hub Natural Gas
  // Indices (daily)
  'SP500',        // S&P 500
  'DJIA',         // Dow Jones
  'NASDAQCOM',    // Nasdaq Composite
  // Economy / Macro — inflation & monetary
  'PCEPILFE',     // Core PCE Price Index
  'PCE',          // Personal Consumption Expenditures (nominal)
  'CES0500000003',// Average Hourly Earnings
  'WM2NS',        // M2 Money Stock
  'PCEPI',            // PCE Price Index (headline inflation)
  'PCETRIM12M159SFRBDAL', // Dallas Fed Trimmed Mean PCE (12M)
  'MEDCPIM158SFRBCLE',    // Cleveland Fed Median CPI (1M Ann)
  'MEDCPIM159SFRBCLE',    // Cleveland Fed Median CPI (12M YoY)
  'TRMMEANCPIM158SFRBCLE', // Cleveland 16% Trimmed Mean CPI (1M Ann)
  'TRMMEANCPIM159SFRBCLE', // Cleveland 16% Trimmed Mean CPI (12M YoY)
  'IR',               // Import Price Index
  // Economy / Macro — activity
  'DPCERAM1M225NBEA', // Real PCE MoM %
  'MARTSMPCSM44X72USS', // Retail Sales Control Group
  'INDPRO',       // Industrial Production Index
  'NEWORDER',     // Core Capital Goods Orders (nondefense, ex-aircraft)
  'GDPNOW',       // Atlanta Fed GDPNow
  // Economy / Macro — labour
  'PAYEMS',       // Nonfarm Payrolls (level, compute MoM Δ)
  'UNRATE',       // Unemployment Rate
  'ICSA',         // Initial Jobless Claims (weekly)
  'CCSA',         // Continuing Claims (weekly)
  'AWHMAN',       // Average Weekly Hours (manufacturing)
  'TEMPHELPS',    // Temporary Help Services Employment
  'USPRIV',           // Private Payrolls
  'CES0500000017',    // Aggregate Weekly Payrolls Index (Private)
  'SAHMREALTIME',     // Sahm Rule Recession Indicator
  'AWHAE',            // Aggregate Weekly Hours Index (All, Total Private)
  // Economy / Macro — JOLTS
  'JTSJOL',       // JOLTS Job Openings
  'JTSQUR',       // Quits Rate
  // Economy / Macro — fiscal & financial conditions
  'GFDEBTN',      // Federal Debt: Total Public Debt
  'WALCL',        // Fed Total Assets
  'UMCSENT',      // U of Michigan Consumer Sentiment
  'MMMFFAQ027S',  // Money Market Funds Total Assets
  'BUSLOANS',         // C&I Loans
  'CONSUMER',         // Consumer Loans
  'DRCCLACBS',        // CC Delinquency Rate (Q)
  'DRSFRMACBS',       // Mortgage Delinquency Rate (Q)
  'NFCI',             // Chicago Fed NFCI (W)
  'FYFSGDA188S',      // Fiscal Deficit % GDP (A)
  'FGEXPND',          // Federal Expenditures (Q)
  'FYOINT',           // Federal Interest Expense (A)
  'A091RC1Q027SBEA',  // Government current expenditures: Interest payments (Q)
  'W006RC1Q027SBEA',  // Federal government current receipts (Q)
  'GDP',              // Gross Domestic Product (Q)
  'WTREGEN',          // TGA Balance (W)
  'RRPONTSYD',        // RRP Overnight (D)
  'WRESBAL',          // Bank Reserves (W)
  'CUSR0000SACL1E',   // CPI Core Goods (M)
  'CUSR0000SAH1',     // CPI Housing (M)
  'ULCNFB',           // Unit Labor Cost (Q)
  'OPHNFB',           // Productivity (Q)
  'PPIFIS',             // PPI Final Demand – BLS headline (M)
  'T10YIE',           // 10Y Breakeven Inflation Rate (D)
  'THREEFYTP10',      // Term Premium 10Y Zero Coupon (D, NY Fed ACM)
  'DRTSCILM',         // SLOOS C&I Lending Standards (Large/Mid)
  'DRSDCILM',         // SLOOS C&I Loan Demand (Large/Mid)
  'DRTSCIS',          // SLOOS C&I Lending Standards (Small)
  'T5YIFR',           // 5Y5Y Inflation Forward
  'CORCCACBS'         // Charge-Off Rate on Credit Card Loans
];

const RATE_ROWS = [
  // unit:'%'   + bpChanges:true  → current shown as %, changes shown in bp (×100)
  // unit:'bp'  + bpValue:true    → current shown as bp (raw×100), changes in bp
  // unit:'bp'                    → current already in bp (spread_pct gives bp directly)
  { id:'tip_yield_10y_tips', label:'TIP Yield (10Y TIPS)',   series:'DFII10',                          unit:'%',  bpChanges:true },
  { id:'-_hy-ig', label:'(垃圾-优质) 利差 HY-IG',  computed:'spread', a:'BAMLH0A0HYM2', b:'BAMLC0A0CM', unit:'bp', bpValue:true },
  { id:'sofr-iorb', label:'(SOFR-IORB) 利差',       computed:'spread_pct', a:'SOFR', b:'IORB',            unit:'bp' },
  { id:'fed_fund_rate', label:'Fed Fund Rate',          series:'DFF',                             unit:'%',  bpChanges:true },
  { id:'fed_path_12m', label:'Fed Fund Futures (12M Path)', computed:'fed_path_12m', unit:'bp' },
  { id:'03m', label:'03M',                    series:'DGS3MO',                          unit:'%',  bpChanges:true },
  { id:'1y', label:'1Y',                     series:'DGS1',                            unit:'%',  bpChanges:true },
  { id:'2y', label:'2Y',                     series:'DGS2',                            unit:'%',  bpChanges:true },
  { id:'3y', label:'3Y',                     series:'DGS3',                            unit:'%',  bpChanges:true },
  { id:'5y', label:'5Y',                     series:'DGS5',                            unit:'%',  bpChanges:true },
  { id:'7y', label:'7Y',                     series:'DGS7',                            unit:'%',  bpChanges:true },
  { id:'10y', label:'10Y',                    series:'DGS10',                           unit:'%',  bpChanges:true },
  { id:'20y', label:'20Y',                    series:'DGS20',                           unit:'%',  bpChanges:true },
  { id:'30y', label:'30Y',                    series:'DGS30',                           unit:'%',  bpChanges:true },
  { id:'03m-10y_spread', label:'03M-10Y Spread',         series:'T10Y3M',                          unit:'bp', bpValue:true },
  { id:'10y_breakeven_inflation', label:'10Y Breakeven Inflation', series:'T10YIE',                          unit:'%',  bpChanges:true },
  { id:'5y5y_inflation_forward', label:'5Y5Y Inflation Forward',   series:'T5YIFR',                          unit:'%',  bpChanges:true },
  { id:'10y_acm_term_premium_model_est', label:'10Y ACM Term Premium (Model Est.)', series:'THREEFYTP10',           unit:'%',  bpChanges:true },
];

const COMMODITY_ROWS = [
  { id:'cl_oil', label:'CL Oil 原油',          series:'DCOILWTICO', yahoo:'CL=F', unit:'$' },
  { id:'ng_gas', label:'NG Gas 天然气',        series:'DHHNGSP',    yahoo:'NG=F', unit:'$' },
  { id:'gc_gold', label:'GC Gold 黄金',                              yahoo:'GC=F', unit:'$' },
  { id:'hg_copper', label:'HG Copper 铜',                              yahoo:'HG=F', unit:'$' },
  { id:'zw_wheat', label:'ZW Wheat 小麦',                             yahoo:'ZW=F', unit:'$' },
  { id:'zs_soybean', label:'ZS Soybean 大豆',                           yahoo:'ZS=F', unit:'$' },
  { id:'baltic_dry_index', label:'Baltic Dry Index',   valuation:'BDI',                    unit:'pt' },
];

const ECONOMY_ROWS = [
  // ── Inflation / Monetary ──────────────────────────────
  { id:'core_pce_yoy', label:'Core PCE 通胀 (YoY)',     series:'PCEPILFE',            unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'pce_yoy', label:'PCE Price 通胀 (YoY)',     series:'PCEPI',                unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'core_pce_1m_ann', label:'Core PCE 1M Ann 月化',     series:'PCEPILFE',             unit:'%',   transform:'ann_1m',  absoluteChanges:true },
  { id:'core_pce_3m_ann', label:'Core PCE 3M Ann 季化',     series:'PCEPILFE',             unit:'%',   transform:'ann_3m',  absoluteChanges:true },
  { id:'core_pce_6m_ann', label:'Core PCE 6M Ann 半年化',   series:'PCEPILFE',             unit:'%',   transform:'ann_6m',  absoluteChanges:true },
  { id:'trimmed_pce_yoy', label:'Trimmed Mean PCE 12M',     series:'PCETRIM12M159SFRBDAL', unit:'%',   absoluteChanges:true },
  { id:'median_cpi_1m_ann', label:'Median CPI 1M Ann',        series:'MEDCPIM158SFRBCLE',    unit:'%',   absoluteChanges:true },
  { id:'median_cpi_yoy', label:'Median CPI YoY 中位CPI',   series:'MEDCPIM159SFRBCLE',    unit:'%',   absoluteChanges:true },
  { id:'trimmed_cpi_1m_ann', label:'16% Trimmed CPI 1M Ann',   series:'TRMMEANCPIM158SFRBCLE',unit:'%',   absoluteChanges:true },
  { id:'trimmed_cpi_yoy', label:'16% Trimmed CPI YoY',      series:'TRMMEANCPIM159SFRBCLE',unit:'%',   absoluteChanges:true },
  { id:'import_prices_yoy', label:'Import Prices 进口价格 (YoY)', series:'IR',               unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'nominal_pce_yoy', label:'Nominal PCE 名义消费支出 (YoY)',          series:'PCE',                 unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'avg_hourly_wage_yoy', label:'Avg Hourly Wage (YoY)',   series:'CES0500000003',       unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'m2_yoy', label:'M2 增速 (YoY)',           series:'WM2NS',               unit:'%',   transform:'yoy',     absoluteChanges:true },
  // ── Activity ──────────────────────────────────────────
  { id:'real_pce_mom', label:'Real PCE (MoM)',          series:'DPCERAM1M225NBEA',    unit:'%',   absoluteChanges:true },
  { id:'retail_sales_control_mom', label:'Retail Sales Control (MoM)', series:'MARTSMPCSM44X72USS', unit:'%', absoluteChanges:true },
  { id:'industrial_production_yoy', label:'Industrial Production (YoY)', series:'INDPRO',          unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'core_capex_orders_yoy_nsa', label:'Core Capex Orders (YoY, NSA)', series:'NEWORDER',          unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'atlanta_fed_gdpnow', label:'Atlanta Fed GDPNow 亚特兰大联储',                  series:'GDPNOW',              unit:'%',   absoluteChanges:true },
  // ── Labour ────────────────────────────────────────────
  { id:'nfp_mom', label:'Nonfarm Payrolls (MoM Δ)', series:'PAYEMS',             unit:'k',   transform:'mom_abs', absoluteChanges:true },
  { id:'private_payrolls_mom', label:'Private Payrolls 私人部门 (MoM Δ)', series:'USPRIV',      unit:'k',   transform:'mom_abs', absoluteChanges:true },
  { id:'real_income_yoy', label:'Agg Weekly Payrolls 实际总周薪 (YoY)', computed:'real_yoy', a:'CES0500000017', b:'PCEPI', unit:'%', absoluteChanges:true },
  { id:'agg_weekly_hours_yoy', label:'Agg Weekly Hours 总工时 (YoY)', series:'AWHAE',            unit:'%',  transform:'yoy',     absoluteChanges:true },
  { id:'sahm_rule', label:'Sahm Rule 衰退指标',         series:'SAHMREALTIME',        unit:'pp',  absoluteChanges:true },
  { id:'unemployment', label:'Unemployment 失业率',     series:'UNRATE',              unit:'%',   absoluteChanges:true },
  { id:'initial_claims', label:'Initial Claims',          series:'ICSA',                unit:'k',   transform:'÷1000',   absoluteChanges:true },
  { id:'continuing_claims', label:'Continuing Claims',       series:'CCSA',                unit:'k',   transform:'÷1000',   absoluteChanges:true },
  { id:'mfg_pns_avg_weekly_hrs', label:'Mfg P&NS Avg Weekly Hrs', series:'AWHMAN',              unit:'hrs', absoluteChanges:true },
  { id:'temp_help_employment_yoy', label:'Temp Help Employment (YoY)', series:'TEMPHELPS',        unit:'%',   transform:'yoy',     absoluteChanges:true },
  // ── JOLTS ─────────────────────────────────────────────
  { id:'jolts_openings', label:'JOLTS Openings',          series:'JTSJOL',              unit:'M',   transform:'÷1000',   absoluteChanges:true },
  { id:'quits_rate', label:'Quits Rate',              series:'JTSQUR',              unit:'%',   absoluteChanges:true },
  // ── Fiscal / Financial Conditions ─────────────────────
  { id:'gov_debt_yoy', label:'Gov Debt 增速 (YoY)',     series:'GFDEBTN',             unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'fed', label:'Fed 资产负债表',          series:'WALCL',               unit:'T$',  transform:'M→T', absoluteChanges:true },
  { id:'money_market_funds', label:'Money Market Funds 现金', series:'MMMFFAQ027S',         unit:'T$',  transform:'M→T', absoluteChanges:true },
  { id:'consumer_sentiment', label:'Consumer Sentiment',      series:'UMCSENT',             unit:'' },
];

const MACRO_TRANSMISSION_ROWS = [
  // ── Credit Conditions ──────────────────────────────────
  { id:'ci_loans_yoy', label:'C&I Loans (YoY)',           series:'BUSLOANS',        unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'consumer_loans_yoy', label:'Consumer Loans (YoY)',      series:'CONSUMER',        unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'cc_delinquency_rate', label:'CC Delinquency Rate',       series:'DRCCLACBS',       unit:'%',   absoluteChanges:true },
  { id:'mortgage_delinquency_rate', label:'Mortgage Delinquency Rate', series:'DRSFRMACBS',      unit:'%',   absoluteChanges:true },
  { id:'chicago_fed_nfci', label:'Chicago Fed NFCI',          series:'NFCI',            unit:'',    absoluteChanges:true },
  { id:'sloos_ci_standards', label:'SLOOS C&I Standards', series:'DRTSCILM', unit:'%', absoluteChanges:true, directionGood:'lower', neutralBand:[-5,5], sloosType:'standards' },
  { id:'sloos_ci_demand', label:'SLOOS C&I Demand',    series:'DRSDCILM', unit:'%', absoluteChanges:true, directionGood:'higher', neutralBand:[-5,5], sloosType:'demand' },
  { id:'sloos_small_biz_standards', label:'SLOOS Small Biz Standards', series:'DRTSCIS',  unit:'%', absoluteChanges:true, directionGood:'lower', neutralBand:[-5,5], sloosType:'standards' },
  { id:'charge_offs', label:'Charge-Off Rate', series:'CORCCACBS', unit:'%', absoluteChanges:true },
  // ── Fiscal ─────────────────────────────────────────────
  { id:'fiscal_deficit_gdp', label:'Fiscal Deficit % GDP',      series:'FYFSGDA188S',     unit:'%',   absoluteChanges:true },
  { id:'federal_expenditures_yoy', label:'Federal Expenditures (YoY)',series:'FGEXPND',         unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'federal_interest_exp_gdp', label:'Federal Interest Exp / GDP', computed:'ratio', a:'A091RC1Q027SBEA', b:'GDP', unit:'%', absoluteChanges:true },
  { id:'federal_interest_exp_receipts', label:'Federal Interest Exp / Receipts', computed:'ratio', a:'A091RC1Q027SBEA', b:'W006RC1Q027SBEA', unit:'%', absoluteChanges:true },
  { id:'treasury_net_issuance', label:'Treasury Net Issuance',     valuation:'TREASURY_NET_ISSUANCE', unit:'$B', absoluteChanges:true },
  // ── Liquidity ───────────────────────────────────────────
  { id:'tga_balance', label:'TGA Balance',               series:'WTREGEN',         unit:'$B',  transform:'÷1000',   absoluteChanges:true },
  { id:'rrp_overnight', label:'RRP Overnight',             series:'RRPONTSYD',       unit:'$B',  absoluteChanges:true },
  { id:'bank_reserves', label:'Bank Reserves',             series:'WRESBAL',         unit:'$B',  transform:'÷1000',   absoluteChanges:true },
  // ── Inflation Breakdown ─────────────────────────────────
  { id:'ppi_final_demand_yoy', label:'PPI Final Demand (YoY)',    series:'PPIFIS',          unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'cpi_core_goods_yoy', label:'CPI Core Goods (YoY)',      series:'CUSR0000SACL1E',  unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'cpi_housing_yoy', label:'CPI Housing (YoY)',         series:'CUSR0000SAH1',    unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'unit_labor_cost_yoy', label:'Unit Labor Cost (YoY)',     series:'ULCNFB',          unit:'%',   transform:'yoy',     absoluteChanges:true },
  { id:'productivity_yoy', label:'Productivity (YoY)',        series:'OPHNFB',          unit:'%',   transform:'yoy',     absoluteChanges:true },
];

const STOCK_GROUPS = [
  { name:'主要指数 Major Indices', items:[
    { id: 'dow_jones', label:'Dow Jones', series:'DJIA', yahoo:'^DJI' },
    { id: 'sp500', label:'S&P 500', series:'SP500', yahoo:'^GSPC' },
    { id: 'VIX', label:'VIX', yahoo:'^VIX' },
    { id: 'nasdaq', label:'Nasdaq', series:'NASDAQCOM', yahoo:'^IXIC' },
    { id: 'russell2000', label:'Russell 2000', yahoo:'^RUT' },
  ]},
  { name:'💻 信息技术 Info Tech', items:[
    { label:'XLK 科技股', yahoo:'XLK' },
    { label:'SOXX 半导体', yahoo:'SOXX' },
    { label:'IGV 软件股', yahoo:'IGV' },
    { label:'MAGS 7巨头', yahoo:'MAGS' },
  ]},
  { name:'🏥 医疗健康 Health Care', items:[
    { label:'XLV 医疗保健', yahoo:'XLV' },
    { label:'IBB 生物科技', yahoo:'IBB' },
  ]},
  { name:'🛒 消费 Consumer', items:[
    { label:'XLY 非必需消费', yahoo:'XLY' },
    { label:'XRT 零售', yahoo:'XRT' },
    { label:'XLP 必需消费', yahoo:'XLP' },
  ]},
  { name:'⚡ 能源 Energy', items:[
    { label:'XLE 石油天然气', yahoo:'XLE' },
    { label:'ICLN 清洁能源', yahoo:'ICLN' },
  ]},
  { name:'🏗️ 原材料 & 房产 Materials & REITs', items:[
    { label:'XLB 原材料', yahoo:'XLB' },
    { label:'GDX 黄金矿业', yahoo:'GDX' },
    { label:'XLRE 房产信托', yahoo:'XLRE' },
  ]},
  { name:'🏦 金融银行 Financials & Banks', items:[
    { label:'XLF 金融股', yahoo:'XLF' },
    { label:'KRE 区域银行', yahoo:'KRE' },
    { label:'KBE 银行业', yahoo:'KBE' },
  ]},
];

const CTA_ETF_UPDATE_SYMBOLS = ['SPY', 'QQQ', 'IWM', 'IEF', 'USO', 'GLD'];

// World overview tickers (global indices, USD, JPY)
const WORLD_YAHOO_SYMBOLS = [
  '^STOXX',     // Euro Stoxx 600
  '^N225',      // Nikkei 225
  '000001.SS',  // Shanghai Composite
  'DX-Y.NYB',   // US Dollar Index (DXY)
  'JPY=X',      // USD/JPY
];

function allYahooSymbols() {
  const s = new Set();
  for (const r of RATE_ROWS) { if (r.yahoo) s.add(r.yahoo); }
  for (const r of COMMODITY_ROWS) { if (r.yahoo) s.add(r.yahoo); }
  for (const g of STOCK_GROUPS) { for (const i of g.items) { if (i.yahoo) s.add(i.yahoo); } }
  for (const sym of CTA_ETF_UPDATE_SYMBOLS) s.add(sym);
  for (const sym of WORLD_YAHOO_SYMBOLS) s.add(sym);
  return [...s];
}

// ============================================
// STATE
// ============================================
const store = { fred: {}, yahoo: {}, valuation: {} };
let dlStatus = { state:'idle', progress:0, total:0, msg:'' };

// ============================================
// HELPERS
// ============================================
const sleep = ms => new Promise(r => setTimeout(r, ms));
function ensureDir(d) { fs.mkdirSync(d, { recursive: true }); }

function httpsGet(reqUrl, hdrs = {}, timeout = 15000) {
  return new Promise((resolve, reject) => {
    const req = https.get(reqUrl, {
      headers: {
        'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept':'application/json,text/plain,*/*',
        ...hdrs,
      },
      timeout,
    }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks) }));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

// ============================================
// YAHOO AUTH
// ============================================
let yCookies = '', yCrumb = '';

async function getYahooAuth() {
  try {
    const r1 = await httpsGet('https://fc.yahoo.com', {}, 5000).catch(() => ({ headers: {} }));
    const cookies = (r1.headers?.['set-cookie'] || []).map(c => c.split(';')[0]).join('; ');
    if (cookies) yCookies = cookies;
    if (!yCookies) return;
    const r2 = await httpsGet('https://query2.finance.yahoo.com/v1/test/getcrumb', { Cookie: yCookies }, 5000);
    const txt = r2.body.toString();
    if (r2.status === 200 && txt && !txt.includes('Too Many') && !txt.includes('<!')) {
      yCrumb = txt.trim();
      console.log('  🍪 Yahoo auth OK');
    }
  } catch(e) { console.log('  ⚠️  Yahoo auth failed:', e.message); }
}

// ============================================
// FRED FETCH
// ============================================
async function fetchFred(seriesId, startDate) {
  const url = `https://api.stlouisfed.org/fred/series/observations?series_id=${seriesId}&api_key=${FRED_KEY}&file_type=json&observation_start=${startDate}&sort_order=asc`;
  const r = await httpsGet(url);
  if (r.status !== 200) throw new Error(`HTTP ${r.status}`);
  const d = JSON.parse(r.body.toString());
  if (d.error_message) throw new Error(d.error_message);
  return (d.observations || []).filter(o => o.value !== '.').map(o => [o.date, parseFloat(o.value)]);
}

// ============================================
// YAHOO FETCH (via Python subprocess — bypasses Node.js TLS block)
// ============================================
const FETCH_YAHOO_JS = path.join(__dirname, 'fetch_yahoo.js');

function fetchYahoo(symbol, range = '5d') {
  return new Promise((resolve, reject) => {
    execFile('node', [FETCH_YAHOO_JS, symbol, range], { timeout: 20000 }, (err, stdout, stderr) => {
      if (err) return reject(new Error(err.message || stderr));
      try {
        const result = JSON.parse(stdout.trim());
        if (!result.ok) {
          if (result.error && result.error.includes('429')) return reject(new Error('RATE_LIMITED'));
          return reject(new Error(result.error || 'unknown'));
        }
        resolve(result.data);
      } catch(e) {
        reject(new Error('parse: ' + e.message));
      }
    });
  });
}

// ============================================
// DISK I/O
// ============================================
function safeName(id) { return id.replace(/[^a-zA-Z0-9._=-]/g, '_'); }

// Compatibility layer: validated Yahoo downloader may store rich OHLC objects,
// while the main macro dashboard expects numeric [date, value] series.
// Keep CTA ETF proxies on adjusted close; keep displayed indices/futures on regular close.
const CTA_ADJ_CLOSE_SYMBOLS = new Set(CTA_ETF_UPDATE_SYMBOLS);
function yahooNumericValue(symbol, raw) {
  if (Number.isFinite(raw)) return raw;
  if (!raw || typeof raw !== 'object') return null;
  if (CTA_ADJ_CLOSE_SYMBOLS.has(symbol) && Number.isFinite(raw.adjClose)) return raw.adjClose;
  if (Number.isFinite(raw.close)) return raw.close;
  if (Number.isFinite(raw.adjClose)) return raw.adjClose;
  return null;
}
function normalizeYahooSeries(symbol, values) {
  if (!Array.isArray(values)) return [];
  const out = [];
  for (const row of values) {
    let date = null;
    let raw = null;
    if (Array.isArray(row)) {
      date = row[0];
      raw = row[1];
    } else if (row && typeof row === 'object') {
      date = row.date;
      raw = row;
    }
    const value = yahooNumericValue(symbol, raw);
    if (typeof date === 'string' && Number.isFinite(value)) out.push([date, value]);
  }
  return out;
}

function saveFile(type, id, values) {
  // Save JSON cache
  const dir = type === 'fred' ? FRED_DIR : YAHOO_DIR;
  ensureDir(dir);
  fs.writeFileSync(path.join(dir, safeName(id) + '.json'), JSON.stringify({ id, updated: new Date().toISOString(), values }));
  // Save CSV
  saveCsv(type, id, values);
}

function saveCsv(type, id, values) {
  const dir = type === 'fred' ? CSV_FRED : CSV_YAHOO;
  ensureDir(dir);
  const header = 'Date,Value';
  const rows = values.map(v => `${v[0]},${v[1]}`);
  fs.writeFileSync(path.join(dir, safeName(id) + '.csv'), header + '\n' + rows.join('\n') + '\n');
}

const VALUATION_CUTOFF = '1973-01-01'; // Only use modern post-Bretton Woods era data

function loadAllFromDisk() {
  let count = 0;
  [['fred', FRED_DIR], ['yahoo', YAHOO_DIR], ['valuation', VALUATION_DIR]].forEach(([type, dir]) => {
    if (!fs.existsSync(dir)) return;
    fs.readdirSync(dir).filter(f => f.endsWith('.json')).forEach(f => {
      try {
        const d = JSON.parse(fs.readFileSync(path.join(dir, f)));
        const key = d.id || d.symbol;
        let vals = d.values;
        if (!vals || !key) return;
        
        // Yahoo may be either legacy numeric rows or validated rich OHLC objects.
        // Normalize to numbers before exposing the series to the macro dashboard.
        if (type === 'yahoo') {
          vals = normalizeYahooSeries(key, vals);
        } else if (vals.length > 0 && !Array.isArray(vals[0])) {
          vals = vals.map(v => [v.date, v]);
        }
        
        // Clip valuation data to post-1973
        if (type === 'valuation') vals = vals.filter(v => v[0] >= VALUATION_CUTOFF);
        if (process.env.TEST_DATE) vals = vals.filter(v => v[0] <= process.env.TEST_DATE);
        store[type][key] = vals;
        count++;
      } catch(e) { /* skip bad files */ }
    });
  });
  return count;
}

// ============================================
// FULL DOWNLOAD
// ============================================
async function downloadAll() {
  const yahooSyms = allYahooSymbols();
  const total = FRED_SERIES_IDS.length + yahooSyms.length;
  dlStatus = { state:'downloading', progress:0, total, msg:'Starting...' };

  // Full history from inception
  const startStr = '1900-01-01';

  // FRED
  console.log('\n  📊 Downloading FRED data...');
  for (let i = 0; i < FRED_SERIES_IDS.length; i++) {
    const id = FRED_SERIES_IDS[i];
    dlStatus.progress = i; dlStatus.msg = `FRED: ${id}`;
    if (store.fred[id] && store.fred[id].length > 0) { console.log(`  ⏭️  FRED ${id}: cached (${store.fred[id].length} obs)`); continue; }
    try {
      const vals = await fetchFred(id, startStr);
      store.fred[id] = vals;
      saveFile('fred', id, vals);
      console.log(`  ✅ FRED ${id}: ${vals.length} obs`);
    } catch(e) { console.log(`  ❌ FRED ${id}: ${e.message}`); }
    await sleep(200);
  }

  // Yahoo: server does NOT fetch from Yahoo API.
  // Use 'node download_yahoo.js' separately, then restart server.
  // Server only loads Yahoo data from disk files in data/yahoo/
  const yLoaded = Object.keys(store.yahoo).length;
  if (yLoaded > 0) {
    console.log(`\n  📈 Yahoo: ${yLoaded}/${yahooSyms.length} loaded from disk cache`);
  } else {
    console.log('\n  📈 Yahoo: no data cached yet. Run: node download_yahoo.js');
  }

  dlStatus = { state:'ready', progress:total, total, msg:'Done' };
  console.log(`\n  ✅ Ready! (FRED: ${Object.keys(store.fred).length}, Yahoo: ${yLoaded}/${yahooSyms.length})\n`);
}

// ============================================
// INCREMENTAL UPDATE (only recent data)
// ============================================
// FED FUNDS FUTURES PATH
// ============================================
async function updateFedPath() {
  console.log('  📈 Updating Fed Funds Futures path...');
  const monthCodes = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z'];
  const d = new Date();
  let m = d.getUTCMonth(); 
  let y = d.getUTCFullYear() % 100;
  
  const pathData = [];
  for (let i = 0; i < 18; i++) {
    const symbol = `ZQ${monthCodes[m]}${y}.CBT`;
    const label = `${d.getUTCFullYear()}-${String(m+1).padStart(2,'0')}`;
    try {
      const data = await fetchYahoo(symbol, '1d');
      if (data && data.length > 0) {
        const price = data[data.length - 1][1];
        const rate = 100 - price;
        pathData.push({ month: label, rate: rate, price: price });
      }
    } catch(e) {
      console.log(`  ⚠️  Failed to fetch ${symbol}: ${e.message}`);
    }
    // Random delay 1-2 seconds between requests
    await sleep(1000 + Math.random() * 1000);
    
    m++;
    if (m > 11) {
      m = 0;
      y++;
      d.setUTCFullYear(d.getUTCFullYear() + 1);
    }
  }
  if (pathData.length > 0) {
    const today = new Date().toISOString().slice(0,10);
    const history = store.valuation['FED_PATH_HISTORY'] || [];
    // Replace if same date exists, else append
    const idx = history.findIndex(h => h[0] === today);
    if (idx >= 0) {
      history[idx][1] = pathData;
    } else {
      history.push([today, pathData]);
    }
    store.valuation['FED_PATH_HISTORY'] = history;
    
    ensureDir(VALUATION_DIR);
    fs.writeFileSync(path.join(VALUATION_DIR, 'FED_PATH_HISTORY.json'), JSON.stringify({ id: 'FED_PATH_HISTORY', updated: new Date().toISOString(), values: history }));
    console.log(`  ✅ Saved FED_PATH_HISTORY with ${pathData.length} months for ${today} (total ${history.length} days)`);
  }
}

// ============================================
// FOMC SUMMARY OF ECONOMIC PROJECTIONS (SEP)
// ============================================
async function updateSepPath() {
  console.log('  📈 Updating FOMC SEP Dot Plot...');
  return new Promise((resolve) => {
    const pyScript = `
import sys
import json
sys.path.insert(0, '/Users/happygolucky/Desktop/QQQ_Risk_Strategy/tools')
try:
    import strategy_engine as se
    raw = se.parse_sep_pdfs('/Users/happygolucky/Desktop/QQQ_Risk_Strategy/fomc_sep')
    # Filter for meetings that have rate_by_year (since ~2012)
    valid = [r for r in raw if r.get('rate_by_year')]
    # Sort chronologically
    valid.sort(key=lambda x: x['date'])
    history = []
    for r in valid:
        date = r['date']
        # Convert rate_by_year dict to array of {year, rate}
        rates_dict = r['rate_by_year']
        curve = []
        keys = sorted(rates_dict.keys())
        for i, y in enumerate(keys):
            # The 4th point in the dot plot is always the "Longer Run" projection
            label = "Longer Run" if i == len(keys) - 1 else str(y)
            curve.append({"year": label, "rate": float(rates_dict[y])})
        history.append([date, curve])
    print(json.dumps(history))
except Exception as e:
    print(json.dumps({"error": str(e)}))
`;
    const child = require('child_process').spawn('python3', ['-c', pyScript]);
    let out = '';
    child.stdout.on('data', d => out += d);
    child.on('close', code => {
      try {
        const res = JSON.parse(out);
        if (res.error) throw new Error(res.error);
        if (Array.isArray(res) && res.length > 0) {
          store.valuation['SEP_HISTORY'] = res;
          ensureDir(VALUATION_DIR);
          fs.writeFileSync(path.join(VALUATION_DIR, 'SEP_HISTORY.json'), JSON.stringify({ id: 'SEP_HISTORY', updated: new Date().toISOString(), values: res }));
          console.log(`  ✅ Saved SEP_HISTORY with ${res.length} meetings`);
        }
      } catch(e) {
        console.log(`  ⚠️  Failed to parse SEP data: ${e.message}`);
      }
      resolve();
    });
  });
}


// ============================================
let lastYahooUpdate = 0;
let isUpdating = false; // lock to prevent concurrent updates

async function smartUpdate(includeYahoo = false) {
  if (isUpdating) {
    console.log('  ⏭️  Update already running, skipping.');
    return;
  }
  isUpdating = true;
  try {
  console.log('\n  🔄 Incremental update...');
  dlStatus = { state:'updating', progress:0, total:0, msg:'Updating...' };

  // Always reload Yahoo from disk (picks up manual download_all_history.js runs)
  const yahooBefore = Object.keys(store.yahoo).length;
  if (fs.existsSync(YAHOO_DIR)) {
    fs.readdirSync(YAHOO_DIR).filter(f => f.endsWith('.json')).forEach(f => {
      try {
        const d = JSON.parse(fs.readFileSync(path.join(YAHOO_DIR, f)));
        const key = d.id || d.symbol;
        if (key && Array.isArray(d.values) && (!store.yahoo[key] || d.values.length > store.yahoo[key].length)) {
          store.yahoo[key] = normalizeYahooSeries(key, d.values);
        }
      } catch(e) {}
    });
  }
  const yahooAfter = Object.keys(store.yahoo).length;
  if (yahooAfter > yahooBefore) console.log(`  📂 Reloaded Yahoo from disk: ${yahooAfter} files`);

  // Also reload FRED from disk (picks up manual download_all_history.js runs)
  if (fs.existsSync(FRED_DIR)) {
    fs.readdirSync(FRED_DIR).filter(f => f.endsWith('.json')).forEach(f => {
      try {
        const d = JSON.parse(fs.readFileSync(path.join(FRED_DIR, f)));
        // Only replace if disk has more data (don't overwrite full history with partial)
        if (!store.fred[d.id] || d.values.length > store.fred[d.id].length) {
          store.fred[d.id] = d.values;
        }
      } catch(e) {}
    });
  }

  // FRED: always update (free, no rate limits)
  const tenDaysAgo = new Date();
  tenDaysAgo.setDate(tenDaysAgo.getDate() - 10);
  const startStr = tenDaysAgo.toISOString().split('T')[0];
  for (const id of FRED_SERIES_IDS) {
    try {
      const newVals = await fetchFred(id, startStr);
      if (newVals.length && store.fred[id]) {
        const existing = store.fred[id];
        const lastDate = existing.length ? existing[existing.length - 1][0] : '';
        const fresh = newVals.filter(v => v[0] > lastDate);
        if (fresh.length) {
          store.fred[id] = [...existing, ...fresh];
        } else if (newVals.length) {
          const latest = newVals[newVals.length - 1];
          if (existing.length && existing[existing.length-1][0] === latest[0]) {
            existing[existing.length-1][1] = latest[1];
          }
        }
        saveFile('fred', id, store.fred[id]);
      }
    } catch(e) {
      console.log(`  ⚠️  FRED ${id} failed: ${e.message}`);
    }
    await sleep(100);
  }

  // Yahoo: only if requested (hourly)
  if (includeYahoo) {
    console.log('  📈 Updating Yahoo...');

    // Shuffle symbol order so same symbol doesn't always hit rate limit first
    const yahooSyms = allYahooSymbols().sort(() => Math.random() - 0.5);
    let yOk = 0, yFail = 0, consecutiveFails = 0;
    for (const sym of yahooSyms) {
      // Back off after 3 consecutive failures
      if (consecutiveFails >= 3) {
        console.log(`  ⏸️  Yahoo: 3 consecutive fails, backing off remaining symbols`);
        break;
      }
      try {
        const newVals = await fetchYahoo(sym, '5d');
        if (!newVals.length) { yFail++; continue; }
        const existing = store.yahoo[sym] || [];
        if (existing.length > 0) {
          const lastDate = existing[existing.length - 1][0];
          const fresh = newVals.filter(v => v[0] > lastDate);
          if (fresh.length) {
            store.yahoo[sym] = [...existing, ...fresh];
          } else {
            const latest = newVals[newVals.length - 1];
            if (existing.length && existing[existing.length-1][0] === latest[0]) {
              existing[existing.length-1][1] = latest[1];
            }
            store.yahoo[sym] = existing;
          }
        } else {
          store.yahoo[sym] = newVals;
        }
        saveFile('yahoo', sym, store.yahoo[sym]);
        yOk++;
        consecutiveFails = 0; // reset on success
      } catch(e) {
        if (e.message === 'RATE_LIMITED') {
          console.log(`  🔴 Yahoo ${sym}: rate-limited`);
          consecutiveFails++;
          await sleep(10000); // extra cooldown on rate limit
        } else {
          console.log(`  ⚠️  Yahoo ${sym}: ${e.message}`);
          consecutiveFails++;
        }
        yFail++;
      }
      // Random delay 5-10 seconds between requests
      await sleep(5000 + Math.random() * 5000);
    }
    console.log(`  📈 Yahoo: ${yOk} ok, ${yFail} failed`);
    lastYahooUpdate = Date.now();
  }

  // Update Fed Path
  await updateFedPath();
  // Update SEP Path
  await updateSepPath();

  // Update macro news (GDELT + Fed RSS)
  try { await fetchAllNews(); } catch(e) { console.log(`  ⚠️  News update failed: ${e.message}`); }

  dlStatus = { state:'ready', progress:0, total:0, msg:'Updated' };
  console.log('  ✅ Update done\n');
  } finally {
    isUpdating = false;
  }
}

// ============================================
// METRICS CALCULATION
// ============================================
// absoluteChanges=true: changes are pp differences, not % of %. Use for series that are already rates/percentages.
function calcMetrics(values, absoluteChanges = false) {
  if (!values || values.length < 5) return null;
  const current = values[values.length - 1][1];
  if (current == null || !Number.isFinite(current)) return null;
  const currentDate = new Date(values[values.length - 1][0] + 'T00:00:00Z');

  // Z-score percentile (4 years ≈ 1008 trading days)
  const n4y = Math.min(values.length, 1008);
  const d4y = values.slice(-n4y).map(v => v[1]);
  let zscore = null;
  if (d4y.length >= 20) {
    const below = d4y.filter(v => v < current).length;
    const equal = d4y.filter(v => v === current).length;
    zscore = Math.round(((below + 0.5 * equal) / d4y.length) * 100);
  }

  // All-time Z-score percentile
  const allVals = values.map(v => v[1]);
  let zscoreAll = null;
  if (allVals.length >= 20) {
    const belowAll = allVals.filter(v => v < current).length;
    const equalAll = allVals.filter(v => v === current).length;
    zscoreAll = Math.round(((belowAll + 0.5 * equalAll) / allVals.length) * 100);
  }

  // Calendar-based lookbacks: use month offsets for 1m+ to handle monthly/quarterly data correctly
  // (91 days != 3 months for monthly data — May 1 - 91d = Jan 30 → finds Jan, not Feb)
  const lookbackDays = { '1d':1, '1w':7 };
  const lookbackMonths = { '1m':1, '1q':3, '6m':6, '1y':12 };
  const changes = {};

  // Build date->value map for quick lookup
  const dateMap = new Map(values.map(v => [v[0], v[1]]));
  const allDates = values.map(v => v[0]); // sorted ascending

  // Detect typical data frequency from last few gaps (in days)
  const recentDates = allDates.slice(-10);
  const gaps = [];
  for (let i = 1; i < recentDates.length; i++) {
    gaps.push((new Date(recentDates[i]) - new Date(recentDates[i-1])) / 86400000);
  }
  gaps.sort((a, b) => a - b);
  const medianGap = gaps[Math.floor(gaps.length / 2)] || 1;

  // Map median gap → minimum meaningful lookback (days)
  let minLookback;
  if      (medianGap < 2)   minLookback = 1;
  else if (medianGap < 10)  minLookback = 2;
  else if (medianGap < 50)  minLookback = 8;
  else if (medianGap < 120) minLookback = 31;
  else                      minLookback = 92;

  // Helper: find the closest observation on or before a target date string
  function findPast(targetStr) {
    for (let i = allDates.length - 1; i >= 0; i--) {
      if (allDates[i] <= targetStr) return allDates[i];
    }
    return null;
  }

  function computeChange(oldVal) {
    if (!isFinite(oldVal)) return null;
    if (absoluteChanges) return +(current - oldVal).toFixed(2);
    if (oldVal !== 0) return +((current - oldVal) / Math.abs(oldVal) * 100).toFixed(2);
    return null;
  }

  // Day-based lookbacks (1d, 1w)
  for (const [period, days] of Object.entries(lookbackDays)) {
    if (days < minLookback) { changes[period] = null; continue; }
    const targetDate = new Date(currentDate);
    targetDate.setUTCDate(targetDate.getUTCDate() - days);
    const targetStr = targetDate.toISOString().split('T')[0];
    const bestDate = findPast(targetStr);
    changes[period] = bestDate ? computeChange(dateMap.get(bestDate)) : null;
  }

  // Month-based lookbacks (1m, 1q, 6m, 1y)
  for (const [period, months] of Object.entries(lookbackMonths)) {
    // Convert months to approximate days for the minLookback filter
    const approxDays = months * 30;
    if (approxDays < minLookback) { changes[period] = null; continue; }
    const targetDate = new Date(currentDate);
    targetDate.setUTCMonth(targetDate.getUTCMonth() - months);
    const targetStr = targetDate.toISOString().split('T')[0];
    const bestDate = findPast(targetStr);
    changes[period] = bestDate ? computeChange(dateMap.get(bestDate)) : null;
  }


  return { current: +current.toFixed(4), zscore, zscoreAll, changes, absoluteChanges };
}

function computeSpread(a, b, mult = 1) {
  const da = store.fred[a], db = store.fred[b];
  if (!da || !db) return null;
  const mapB = new Map(db);
  return da.filter(([d]) => mapB.has(d)).map(([d, v]) => [d, (v - mapB.get(d)) * mult]);
}

function medianGapToFrequency(vals) {
  if (!vals || vals.length < 5) return 'unknown';
  const recent = vals.slice(-10);
  const gaps = [];
  for (let i = 1; i < recent.length; i++) {
    gaps.push((new Date(recent[i][0]) - new Date(recent[i-1][0])) / 86400000);
  }
  gaps.sort((a, b) => a - b);
  const mg = gaps[Math.floor(gaps.length / 2)] || 1;
  if (mg < 2) return 'daily';
  if (mg < 10) return 'weekly';
  if (mg < 50) return 'monthly';
  if (mg < 120) return 'quarterly';
  return 'annual';
}

function gradeFreshness(daysSince, frequency) {
  if (daysSince == null) return 'unknown';
  const t = {
    daily:     { fresh: 3,  due: 5,   stale: 10 },
    weekly:    { fresh: 10, due: 14,  stale: 21 },
    monthly:   { fresh: 40, due: 50,  stale: 65 },
      quarterly: { fresh: 100, due: 120, stale: 150 },
    annual:    { fresh: 380, due: 400, stale: 420 },
    unknown:   { fresh: 30, due: 60,  stale: 90 },
  };
  const th = t[frequency] || t.unknown;
  if (daysSince <= th.fresh) return 'fresh';
  if (daysSince <= th.due) return 'due';
  if (daysSince <= th.stale) return 'stale';
  return 'very_stale';
}

function getClosestPrior(data, targetDate) {
  for (let i = data.length - 1; i >= 0; i--) {
    if (data[i][0] <= targetDate) return data[i][1];
  }
  return null;
}

function getYearAgoValue(vals, currentIndex) {
  const [date] = vals[currentIndex];
  const yr = parseInt(date.slice(0,4)) - 1;
  const target = `${yr}${date.slice(4)}`;
  // Find index near target
  for (let i = currentIndex; i >= 0; i--) {
    if (vals[i][0] <= target) {
      if (Math.abs(new Date(vals[i][0]) - new Date(target)) < 20 * 86400000) return vals[i][1];
      break;
    }
  }
  return null;
}

// ============================================
// BUILD DASHBOARD RESPONSE
// ============================================
function buildDashboard() {
  // Helper: pick the source with the most recent data point
  function pickBest(fredKey, yahooKey) {
    const f = fredKey && store.fred[fredKey];
    const y = yahooKey && store.yahoo[yahooKey];
    if (!f && !y) return null;
    if (!f) return y;
    if (!y) return f;
    const fDate = f.length ? f[f.length - 1][0] : '';
    const yDate = y.length ? y[y.length - 1][0] : '';
    return yDate >= fDate ? y : f;
  }

  // Get current DFF for futures implied-rate diff
  const dffVals = store.fred['DFF'];
  const currentDFF = dffVals && dffVals.length ? dffVals[dffVals.length - 1][1] : null;

  // Align T10YIE to same last date as DGS10 so table shows the same breakeven change
  const _dgs10Last = (store.fred['DGS10']||[]).reduce((a,[d]) => d > a ? d : a, '');

  const rates = RATE_ROWS.map(r => {
    let vals = [];
    if (r.computed === 'spread' || r.computed === 'spread_pct' || r.computed === 'real_yoy' || r.computed === 'ratio') {
      const dataA = store.fred[r.a];
      const dataB = store.fred[r.b];
      if (dataA && dataB) {
        const mapB = new Map(dataB.map(([d, v]) => [d, v]));
        for (const [date, valA] of dataA) {
          const valB = mapB.get(date) || getClosestPrior(dataB, date);
          if (valB != null) {
            if (r.computed === 'spread') vals.push([date, valA - valB]);
            else if (r.computed === 'spread_pct') vals.push([date, (valA - valB) * 100]); 
            else if (r.computed === 'ratio') vals.push([date, (valA / valB) * 100]);
            else if (r.computed === 'real_yoy') {
              vals.push([date, valA / valB]);
            }
          }
        }
      }
    } else if (r.computed === 'fed_path_12m') {
      const pathHist = store.valuation['FED_PATH_HISTORY'] || [];
      for (const [dateStr, pathArray] of pathHist) {
        if (!pathArray || !pathArray.length) continue;
        const currentRate = pathArray[0].rate;
        const forwardRate = pathArray.length > 11 ? pathArray[11].rate : pathArray[pathArray.length-1].rate;
        vals.push([dateStr, (forwardRate - currentRate) * 100]);
      }
    } else {
      vals = pickBest(r.series, r.yahoo);
    }

    // Clip T10YIE to same last date as DGS10 for date-aligned breakeven calculation
    if (r.series === 'T10YIE' && vals && _dgs10Last) {
      vals = vals.filter(([d]) => d <= _dgs10Last);
    }

    // bpValue: multiply raw values ×100 (e.g. spread 1.93% → 193 bp)
    if (r.bpValue && vals) vals = vals.map(([d, v]) => [d, +(v * 100).toFixed(2)]);

    // Fed Fund Futures: convert price → implied rate (100 - price)
    if (r.unit === 'futures' && vals) {
      const impliedVals = vals.map(([d, v]) => [d, +(100 - v).toFixed(4)]);
      const m = calcMetrics(impliedVals, true); 
      const impliedRate = m ? m.current : null;
      const diffBP = (impliedRate != null && currentDFF != null)
        ? +((impliedRate - currentDFF) * 100).toFixed(1)
        : null;
      const bpChanges = {};
      if (m) for (const [p, v] of Object.entries(m.changes)) bpChanges[p] = v != null ? +(v * 100).toFixed(1) : null;
      return {
        id: r.id, label: r.label,
        unit: 'futures',
        chartKey: r.yahoo || '',
        current: impliedRate,
        diffBP,
        zscore: m?.zscore ?? null,
        zscoreAll: m?.zscoreAll ?? null,
        changes: bpChanges,
        absoluteChanges: true,
      };
    }

    const alreadyBp = (r.unit === 'bp' && !r.bpValue);
    const m = calcMetrics(vals, r.bpChanges || !!r.bpValue || alreadyBp);
    const chartKey = r.computed ? `spread:${r.a}:${r.b}` : (r.series || r.yahoo || '');
    let changes = m?.changes || {};
    if (r.bpChanges && m) {
      changes = {};
      for (const [p, v] of Object.entries(m.changes)) changes[p] = v != null ? +(v * 100).toFixed(1) : null;
    }
    return { id: r.id, label: r.label, unit: r.unit, chartKey, bpChanges: r.bpChanges || false,
      ...(m || { current:null, zscore:null, zscoreAll:null, changes:{} }), changes };
  });

  const commodities = COMMODITY_ROWS.map(r => {
    const vals = r.valuation ? store.valuation[r.valuation] : pickBest(r.series, r.yahoo);
    const m = calcMetrics(vals);
    const chartKey = r.valuation ? ('val:' + r.valuation) : (r.yahoo || r.series || '');
    const extra = (r.valuation && vals?.length) ? { lastDate: vals[vals.length - 1][0] } : {};
    return { id: r.id, label: r.label, unit: r.unit || '$', chartKey, ...extra, ...(m || { current:null, zscore:null, zscoreAll:null, changes:{} }) };
  });

  const economy = ECONOMY_ROWS.map(r => {
    let vals = [];
    if (r.computed === 'real_yoy' || r.computed === 'ratio') {
      const dataA = store.fred[r.a];
      const dataB = store.fred[r.b];
      if (dataA && dataB) {
        const mapB = new Map(dataB.map(([d, v]) => [d, v]));
        for (const [date, valA] of dataA) {
          const valB = mapB.get(date) || getClosestPrior(dataB, date);
          if (valB != null) {
            if (r.computed === 'ratio') vals.push([date, (valA / valB) * 100]);
            else if (r.computed === 'real_yoy') vals.push([date, valA / valB]);
          }
        }
      }
    } else {
      vals = store.fred[r.series];
    }
    if (!vals || vals.length === 0) return { id: r.id, label: r.label, unit: r.unit, chartKey: r.series, current:null, zscore:null, zscoreAll:null, changes:{} };

    if (r.transform === 'yoy' || r.computed === 'real_yoy') {
      const yoyVals = [];
      for (let i = 0; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prevVal = getYearAgoValue(vals, i);
        if (prevVal && prevVal !== 0) yoyVals.push([date, +((val / prevVal - 1) * 100).toFixed(4)]);
      }
      vals = yoyVals;
    } else if (r.transform === '÷1000') {
      vals = vals.map(([d, v]) => [d, +(v / 1000).toFixed(3)]);
    } else if (r.transform === 'mom_pct') {
      const momVals = [];
      for (let i = 1; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 1][1];
        if (prev && prev !== 0) momVals.push([date, +((val / prev - 1) * 100).toFixed(4)]);
      }
      vals = momVals;
    } else if (r.transform === 'mom_abs') {
      const momVals = [];
      for (let i = 1; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 1][1];
        if (prev != null) momVals.push([date, +(val - prev).toFixed(1)]);
      }
      vals = momVals;
    } else if (r.transform === 'ann_1m') {
      const annVals = [];
      for (let i = 1; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 1][1];
        if (prev && prev > 0 && val > 0) {
          annVals.push([date, +((Math.pow(val / prev, 12) - 1) * 100).toFixed(4)]);
        }
      }
      vals = annVals;
    } else if (r.transform === 'ann_3m') {
      const annVals = [];
      for (let i = 3; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 3][1];
        if (prev && prev > 0 && val > 0) {
          annVals.push([date, +((Math.pow(val / prev, 4) - 1) * 100).toFixed(4)]);
        }
      }
      vals = annVals;
    } else if (r.transform === 'ann_6m') {
      const annVals = [];
      for (let i = 6; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 6][1];
        if (prev && prev > 0 && val > 0) {
          annVals.push([date, +((Math.pow(val / prev, 2) - 1) * 100).toFixed(4)]);
        }
      }
      vals = annVals;
    } else if (r.transform === 'M→T') {
      vals = vals.map(([d, v]) => [d, +(v / 1_000_000).toFixed(4)]);
    } else if (r.transform === 'B→T') {
      vals = vals.map(([d, v]) => [d, +(v / 1000).toFixed(4)]);
    }
    if (r.postScale && vals) vals = vals.map(([d, v]) => [d, +(v * r.postScale).toFixed(2)]);

    const m = calcMetrics(vals, !!r.absoluteChanges);
    const lastObsDate = vals && vals.length ? vals[vals.length - 1][0] : null;
    const frequency = medianGapToFrequency(vals);
    const daysSinceObs = lastObsDate ? Math.floor((Date.now() - new Date(lastObsDate + 'T00:00:00Z').getTime()) / 86400000) : null;
    const freshness = gradeFreshness(daysSinceObs, frequency);
    return { id: r.id, label: r.label, unit: r.unit, chartKey: r.series, lastObsDate, frequency, daysSinceObs, freshness, ...(m || { current:null, zscore:null, zscoreAll:null, changes:{} }) };
  });

  const macroTransmission = MACRO_TRANSMISSION_ROWS.map(r => {
    let vals = [];
    if (r.valuation) {
      vals = store.valuation[r.valuation];
    } else if (r.computed === 'real_yoy' || r.computed === 'ratio') {
      const dataA = store.fred[r.a];
      const dataB = store.fred[r.b];
      if (dataA && dataB) {
        const mapB = new Map(dataB.map(([d, v]) => [d, v]));
        for (const [date, valA] of dataA) {
          const valB = mapB.get(date) || getClosestPrior(dataB, date);
          if (valB != null) {
            if (r.computed === 'ratio') vals.push([date, (valA / valB) * 100]);
            else if (r.computed === 'real_yoy') vals.push([date, valA / valB]);
          }
        }
      }
    } else {
      vals = store.fred[r.series];
    }
    if (!vals || vals.length === 0) return { id: r.id, label: r.label, unit: r.unit, chartKey: r.series, current:null, zscore:null, zscoreAll:null, changes:{} };
    if (r.transform === 'yoy' || r.computed === 'real_yoy') {
      const yoyVals = [];
      for (let i = 0; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prevVal = getYearAgoValue(vals, i);
        if (prevVal && prevVal !== 0) yoyVals.push([date, +((val / prevVal - 1) * 100).toFixed(4)]);
      }
      vals = yoyVals;
    } else if (r.transform === '÷1000') {
      vals = vals.map(([d, v]) => [d, +(v / 1000).toFixed(3)]);
    } else if (r.transform === 'mom_abs') {
      const momVals = [];
      for (let i = 1; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 1][1];
        if (prev != null) momVals.push([date, +(val - prev).toFixed(1)]);
      }
      vals = momVals;
    } else if (r.transform === 'mom_pct') {
      const momVals = [];
      for (let i = 1; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 1][1];
        if (prev && prev !== 0) momVals.push([date, +((val / prev - 1) * 100).toFixed(4)]);
      }
      vals = momVals;
    } else if (r.transform === 'ann_1m') {
      // 1-month annualized: (current / prev_1m)^12 - 1
      const annVals = [];
      for (let i = 1; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 1][1];
        if (prev && prev > 0 && val > 0) {
          annVals.push([date, +((Math.pow(val / prev, 12) - 1) * 100).toFixed(4)]);
        }
      }
      vals = annVals;
    } else if (r.transform === 'ann_3m') {
      // 3-month annualized: (current / prev_3m)^4 - 1
      const annVals = [];
      for (let i = 3; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 3][1];
        if (prev && prev > 0 && val > 0) {
          annVals.push([date, +((Math.pow(val / prev, 4) - 1) * 100).toFixed(4)]);
        }
      }
      vals = annVals;
    } else if (r.transform === 'ann_6m') {
      // 6-month annualized: (current / prev_6m)^2 - 1
      const annVals = [];
      for (let i = 6; i < vals.length; i++) {
        const [date, val] = vals[i];
        const prev = vals[i - 6][1];
        if (prev && prev > 0 && val > 0) {
          annVals.push([date, +((Math.pow(val / prev, 2) - 1) * 100).toFixed(4)]);
        }
      }
      vals = annVals;
    } else if (r.transform === 'M→T') {
      vals = vals.map(([d, v]) => [d, +(v / 1_000_000).toFixed(4)]);
    } else if (r.transform === 'B→T') {
      vals = vals.map(([d, v]) => [d, +(v / 1000).toFixed(4)]);
    }
    if (r.postScale && vals) vals = vals.map(([d, v]) => [d, +(v * r.postScale).toFixed(2)]);
    const m = calcMetrics(vals, !!r.absoluteChanges);
    // Freshness metadata
    const lastObsDate = vals && vals.length ? vals[vals.length - 1][0] : null;
    const frequency = medianGapToFrequency(vals);
    const daysSinceObs = lastObsDate ? Math.floor((Date.now() - new Date(lastObsDate + 'T00:00:00Z').getTime()) / 86400000) : null;
    const freshness = gradeFreshness(daysSinceObs, frequency);
    // Dynamic SLOOS classification based on Fed's official bands
    let dynLabel = r.label;
    if (r.sloosType && m && m.current != null) {
      const v = Math.abs(m.current);
      let magnitude;
      if (v < 5) magnitude = '基本不变';
      else if (v < 10) magnitude = '小幅';
      else if (v < 20) magnitude = '中等';
      else magnitude = '大幅';
      if (r.sloosType === 'standards') {
        const dir = m.current > 0 ? '收紧' : m.current < 0 ? '放宽' : '';
        dynLabel = `${r.label} ${magnitude === '基本不变' ? magnitude : magnitude + dir}`;
      } else if (r.sloosType === 'demand') {
        const dir = m.current > 0 ? '增强' : m.current < 0 ? '减弱' : '';
        dynLabel = `${r.label} ${magnitude === '基本不变' ? magnitude : magnitude + dir}`;
      }
    }
    return { id: r.id, label: dynLabel, unit: r.unit, chartKey: r.series, lastObsDate, frequency, daysSinceObs, freshness, ...(m || { current:null, zscore:null, zscoreAll:null, changes:{} }) };
  });

  // Valuation items to inject after S&P 500
  const VALUATION_ITEMS = [
    { id: 'SP500_PE',        label: '  └ S&P 500 PE Ratio',           unit: 'x' },
    { id: 'SHILLER_CAPE',    label: '  └ Shiller CAPE Ratio',          unit: 'x' },
    { id: 'SP500_EPS_GROWTH',label: '  └ S&P 500 EPS Growth (YoY)',    unit: '%', absoluteChanges: true },
  ];

  const stocks = STOCK_GROUPS.map(g => {
    const items = [];
    for (const i of g.items) {
      const vals = pickBest(i.series, i.yahoo);
      const m = calcMetrics(vals);
      const chartKey = i.yahoo || i.series || '';
      const fallbackId = i.yahoo ? i.yahoo.replace('^', '').toLowerCase() : null;
      items.push({ id: i.id || fallbackId, label: i.label, unit: '$', chartKey, ...(m || { current:null, zscore:null, zscoreAll:null, changes:{} }) });

      // Inject valuation rows after S&P 500
      // Synthesize daily PE and CAPE using daily S&P price + last known EPS/CAPE anchor
      if (i.label === 'S&P 500') {
        const spDaily = store.yahoo['^GSPC'];
        
        // --- Daily PE Synthesis ---
        const peMonthly = store.valuation['SP500_PE'];
        let peDailyVals = peMonthly; // fallback to monthly
        if (spDaily && spDaily.length > 20 && peMonthly && peMonthly.length > 5) {
          // Find last known PE anchor point and derive implied trailing EPS
          // EPS = Price / PE at anchor date
          const lastPeDate = peMonthly[peMonthly.length - 1][0];
          const lastPeVal = peMonthly[peMonthly.length - 1][1];
          // Find S&P price on or near last PE date
          let anchorPrice = null;
          for (let k = spDaily.length - 1; k >= 0; k--) {
            if (spDaily[k][0] <= lastPeDate) { anchorPrice = spDaily[k][1]; break; }
          }
          if (anchorPrice && lastPeVal > 0) {
            const impliedEps = anchorPrice / lastPeVal;
            // Build daily PE = daily_price / implied_EPS
            // Keep monthly history, then append daily estimates after last PE date
            const dailyPe = [...peMonthly];
            const peSet = new Set(peMonthly.map(v => v[0]));
            for (const [d, p] of spDaily) {
              if (d > lastPeDate && !peSet.has(d)) {
                dailyPe.push([d, +(p / impliedEps).toFixed(2)]);
              }
            }
            dailyPe.sort((a, b) => a[0].localeCompare(b[0]));
            peDailyVals = dailyPe;
          }
        }
        
        // --- Daily CAPE Synthesis ---
        const capeMonthly = store.valuation['SHILLER_CAPE'];
        let capeDailyVals = capeMonthly; // fallback to monthly
        if (spDaily && spDaily.length > 20 && capeMonthly && capeMonthly.length > 5) {
          const lastCapeDate = capeMonthly[capeMonthly.length - 1][0];
          const lastCapeVal = capeMonthly[capeMonthly.length - 1][1];
          // Find S&P price on or near last CAPE date
          let capeAnchorPrice = null;
          for (let k = spDaily.length - 1; k >= 0; k--) {
            if (spDaily[k][0] <= lastCapeDate) { capeAnchorPrice = spDaily[k][1]; break; }
          }
          if (capeAnchorPrice && capeAnchorPrice > 0 && lastCapeVal > 0) {
            // daily CAPE ≈ last_CAPE × (today_price / anchor_price)
            // because CAPE denominator (10yr avg earnings) barely changes day-to-day
            const dailyCape = [...capeMonthly];
            const capeSet = new Set(capeMonthly.map(v => v[0]));
            for (const [d, p] of spDaily) {
              if (d > lastCapeDate && !capeSet.has(d)) {
                dailyCape.push([d, +(lastCapeVal * (p / capeAnchorPrice)).toFixed(2)]);
              }
            }
            dailyCape.sort((a, b) => a[0].localeCompare(b[0]));
            capeDailyVals = dailyCape;
          }
        }
        
        // Build lookup for synthesized series
        const synthVals = { 'SP500_PE': peDailyVals, 'SHILLER_CAPE': capeDailyVals };
        
        for (const vi of VALUATION_ITEMS) {
          let vvals = synthVals[vi.id] || store.valuation[vi.id];
          const vm = calcMetrics(vvals, !!vi.absoluteChanges);
          const unit = vi.unit;
          const lastObsDate = vvals && vvals.length ? vvals[vvals.length - 1][0] : null;
          const daysSinceObs = lastObsDate ? Math.floor((Date.now() - new Date(lastObsDate + 'T00:00:00Z').getTime()) / 86400000) : null;
          const isSynthesized = synthVals[vi.id] && synthVals[vi.id] !== store.valuation[vi.id];
          items.push({ id: vi.id, label: vi.label, unit, chartKey: 'val:' + vi.id, lastObsDate, daysSinceObs, synthesized: isSynthesized || undefined, ...(vm || { current:null, zscore:null, zscoreAll:null, changes:{} }) });
        }
      }
    }
    return { group: g.name, items };
  });

  const valItems = stocks.flatMap(g => g.items).filter(i => i.id && VALUATION_ITEMS.some(vi => vi.id === i.id));
  
  // Bank Equity Stress Injection (SP500 vs KRE outperformance over 6M)
  const sp500Item = stocks.flatMap(g => g.items).find(i => i.label === 'S&P 500');
  const kreItem = stocks.flatMap(g => g.items).find(i => i.label === 'KRE 区域银行');
  let bank_equity_stress_val = null;
  if (sp500Item && kreItem && sp500Item.changes && kreItem.changes) {
    const sp500_6m = sp500Item.changes['6m'];
    const kre_6m = kreItem.changes['6m'];
    if (sp500_6m != null && kre_6m != null) {
      bank_equity_stress_val = (sp500_6m - kre_6m); 
    }
  }
  const bankEquityStressInd = { id: 'bank_equity_stress', current: bank_equity_stress_val, daysSinceObs: kreItem ? kreItem.daysSinceObs : null, lastObsDate: kreItem ? kreItem.lastObsDate : null, label: 'Bank Equity Stress (SP500 - KRE)' };
  
  const vixItem = stocks.flatMap(g => g.items).find(i => i.id === 'VIX');

  const allDataList = [...economy, ...macroTransmission, ...rates, ...valItems, bankEquityStressInd];
  if (vixItem) allDataList.push(vixItem);
  // Add stock and commodity items for V2 horizon engine
  const allStockItems = stocks.flatMap(g => g.items).filter(i => i.id !== 'VIX'); // VIX already added
  allDataList.push(...allStockItems);
  allDataList.push(...commodities);
  
  const diagnosticEngineOutput = evaluateDiagnostics(allDataList);

  const resPayload = {
    meta: {
      schemaVersion: '2.0.0',
      rulebookVersion: '2.0.0',
      engineVersion: '2.0.0',
      generatedAt: new Date().toISOString(),
      asOf: new Date().toISOString().split('T')[0],
      vintageMode: 'latest_available',
      featureFlags: {
        ruleEngineV2: true,
        eventAttribution: true,
        pca: false,
        inflationForecast: false
      }
    },
    engineStatus: {
      coreDiagnosis: 'ok',
      eventAttribution: 'unavailable',
      qqqStrategy: 'ok'
    },
    updated: new Date().toISOString(),
    fredLoaded: Object.keys(store.fred).length,
    yahooLoaded: Object.keys(store.yahoo).length,
    rates, commodities, stocks,
    fedPathHistory: store.valuation['FED_PATH_HISTORY'] || [],
    sepHistory: store.valuation['SEP_HISTORY'] || [],
    macroState: economy, economy, macroTransmission,
    // conclusions removed — user requested deletion
    cycleAnalysis: generateCycleAnalysis(economy, macroTransmission, rates),
    diagnostics: diagnosticEngineOutput
  };
  
  if (ENABLE_PCA) {
    resPayload.factorModel = loadFactorModel();
  }
  if (ENABLE_INFLATION_FORECAST) {
    resPayload.inflationForecast = loadInflationForecast();
  }

  // V2 Rule Engine Injection (Shadow Run)
  if (USE_RULE_ENGINE_V2) {
    try {
      const ruleEngine = require('./lib/rule_engine');
      const horizonEngine = require('./lib/horizon_engine');
      const registryPath = require('path').join(__dirname, 'config/indicator_registry.json');
      let registry = {};
      try { registry = JSON.parse(require('fs').readFileSync(registryPath, 'utf8')); } catch(e){}

      const v2Classified = {};
      
      // allDataList is just current snapshot (an array of metric objects), we need the historical series for percentiles
      // So we use store.fred and store.yahoo 
      for (const item of allDataList) {
        if (!item.id) continue;
        const storeRef = store.fred[item.id] || store.yahoo[item.id] || store.valuation[item.id] || (item.chartKey && store.yahoo[item.chartKey]) || (item.chartKey && store.fred[item.chartKey]);
        const series = Array.isArray(storeRef) ? storeRef : (storeRef ? storeRef.values : []) || [];
        const indicatorData = {
          current: item.current,
          lastObsDate: item.lastObsDate,
          daysSinceObs: item.daysSinceObs,
          series: series
        };
        
        // 1. Rule Layer (Level / Extremity)
        const ruleEval = ruleEngine.evaluateIndicator(item.id, indicatorData);
        
        // 2. Multi-Horizon Layer (Trend Coherence)
        let horizonEval = null;
        if (series && series.length > 0) {
           const regInfo = registry[item.id];
           if (regInfo && regInfo.frequency && regInfo.horizonMethod) {
              try {
                horizonEval = horizonEngine.calculateTrend({
                  series: series,
                  type: regInfo.horizonMethod,
                  frequency: regInfo.frequency,
                  transformation: regInfo.transformation || 'level',
                  horizonScale: regInfo.horizonScale || 1,
                  changes: item.changes || {},
                  current: item.current
                });
              } catch(e){ console.error(`Horizon error for ${item.id}:`, e.message); }
           }
        }
        
        v2Classified[item.id] = {
           level: ruleEval,
           trend: horizonEval
        };
      }
      
      const actionContextEngine = require('./lib/action_context_engine');
      
      // Map legacy diagnostics to V2 four-module layout for coverage calculation
      const legDiag = resPayload.diagnostics || {};
      const v2ModuleMapping = {
        growth:          [legDiag.recession],
        inflation:       [legDiag.inflation],
        financialSystem: [legDiag.credit, legDiag.longEnd, legDiag.liquidity],
        marketRisk:      [legDiag.stagflation, legDiag.valuation]
      };
      
      const v2Diagnostics = {};
      let implementedCount = 0;
      let totalEvidenceCov = 0;
      let totalStageCount = 0;
      let maxPressureSev = 0;
      let maxDamageSev = 0;
      let hasDamage = false;
      
      // Only recession (growth) module damage counts as systemic stress
      const systemicModules = new Set(['growth']);
      // Only growth + credit damage counts as private-economy damage
      // longEnd damage = fiscal burden, valuation damage = market pricing — tracked separately
      const privateEconomyDamageModules = new Set(['growth']);
      // Which legacy diagnostics count as private damage: recession, credit
      const privateDamageDiags = new Set(['recession', 'credit']);
      
      for (const [modName, legacySources] of Object.entries(v2ModuleMapping)) {
        const validSources = legacySources.filter(s => s && s.stages);
        if (validSources.length > 0) {
          implementedCount++;
          let hasPressureRed = false;
          let hasDamageRed = false;
          for (const src of validSources) {
            const srcQuestion = (src.question || '').toLowerCase();
            // Detect if this source is a private-economy diagnostic
            const isPrivateDamage = privateDamageDiags.has(
              srcQuestion.includes('recession') ? 'recession' :
              srcQuestion.includes('credit') ? 'credit' : ''
            );
            for (const st of src.stages) {
              totalEvidenceCov += (st.coverage || 0);
              totalStageCount++;
              const sev = st.status === 'red' ? 3 : st.status === 'yellow' ? 2 : st.status === 'green' ? 1 : 0;
              // Track pressure severity (all modules)
              if (st.name && /pressure/i.test(st.name)) {
                if (sev > maxPressureSev) maxPressureSev = sev;
                if (st.status === 'red') hasPressureRed = true;
              }
              // Only count private-economy damage for the damage label
              if (st.name && /damage/i.test(st.name) && isPrivateDamage) {
                if (sev > maxDamageSev) maxDamageSev = sev;
                if (st.status === 'red') hasDamageRed = true;
              }
            }
          }
          // Only count as systemic damage if full cascade in growth
          if (systemicModules.has(modName) && hasPressureRed && hasDamageRed) {
            hasDamage = true;
          }
          v2Diagnostics[modName] = { status: 'implemented', sources: validSources.length };
        } else {
          v2Diagnostics[modName] = { status: 'not_implemented' };
        }
      }
      
      const moduleCoverage = implementedCount / 4; // 0 to 1
      const evidenceCoverage = totalStageCount > 0 ? Math.round(totalEvidenceCov / totalStageCount) : 0;
      
      // Fiscal burden: tracked from longEnd (separate from private-economy damage)
      const longEndDiag = legDiag.longEnd;
      let fiscalBurden = 'unknown';
      if (longEndDiag && longEndDiag.stages) {
        const dmgStage = longEndDiag.stages.find(s => /fiscal burden/i.test(s.name) || /damage/i.test(s.name));
        if (dmgStage) {
          fiscalBurden = dmgStage.status === 'red' ? 'confirmed' : dmgStage.status === 'yellow' ? 'elevated' : 'not_confirmed';
        }
      }
      
      // Critical coverage: key indicators that are still missing
      const criticalMissing = [];
      const criticalIndicators = [
        { id: 'treasury_net_issuance', label: 'Treasury Net Issuance' },
        { id: 'repo_fails', label: 'Repo Fails / SRF Usage' },
        { id: 'market_breadth', label: 'Market Breadth' },
      ];
      // Check if any critical indicator is missing from allDataList or has null value
      for (const ci of criticalIndicators) {
        const found = allDataList.find(d => d.id === ci.id);
        if (!found || found.current == null) criticalMissing.push(ci.label);
      }
      const criticalCoverage = criticalMissing.length === 0 ? 'complete' : 'partial';
      
      // Overall risk: based on private-economy damage, not fiscal burden or valuation
      const pressureLabel = maxPressureSev >= 3 ? 'high' : maxPressureSev >= 2 ? 'elevated' : 'low';
      const damageLabel = maxDamageSev >= 3 ? 'confirmed' : maxDamageSev >= 2 ? 'moderate' : 'not_confirmed';
      const overallRisk = hasDamage ? 'high' : (maxDamageSev >= 3 ? 'elevated' : (maxPressureSev >= 3 ? 'elevated' : (maxPressureSev >= 2 ? 'moderate' : 'low')));
      
      // Use legacy contradictions if available
      const hasContradiction = false; // conclusions removed
      
      const actionContextOutput = actionContextEngine.generateActionContext({
         maxRiskSeverity: maxPressureSev,
         hasDamage,
         hasContradiction,
         diagnosticCoverage: moduleCoverage
      });

      resPayload.v2 = {
        classified: v2Classified,
        diagnostics: v2Diagnostics,
        moduleCoverage: Math.round(moduleCoverage * 100),
        evidenceCoverage,
        criticalCoverage,
        criticalMissing,
        risk: {
          overall: overallRisk,
          pressure: pressureLabel,
          damage: damageLabel,
          fiscalBurden,
          systemic: hasDamage ? 'confirmed' : 'not_confirmed'
        },
        summary: {},
        rulebookVersion: "2.0.0"
      };
      
      // Top-level extensions for V2 frontend — Event Attribution (shadow/read-only)
      try {
        const EventScanner = require('./lib/event_scanner');
        const scanner = new EventScanner({ store, indicatorRegistry: null });
        resPayload.eventAttribution = scanner.scan({ lookbackDays: 90 });
      } catch (eaError) {
        resPayload.eventAttribution = {
          status: 'scanner_error',
          events: [],
          error: eaError.message
        };
      }
      resPayload.actionContext = actionContextOutput;
    } catch (e) {
      console.error("V2 Engine Error:", e);
    }
  }

  return resPayload;
}

function loadInflationForecast() {
  const fPath = path.join(DATA_DIR, 'inflation_forecast.json');
  try {
    if (!fs.existsSync(fPath)) return null;
    const raw = JSON.parse(fs.readFileSync(fPath));
    // Return only prediction + metrics (not full backtest array)
    return {
      updated: raw.updated,
      target: raw.target,
      horizon_months: raw.horizon_months,
      method: raw.method,
      n_predictions: raw.n_predictions,
      metrics: raw.metrics,
      prediction: raw.prediction,
    };
  } catch(e) { return null; }
}

function loadFactorModel() {
  const fmPath = path.join(DATA_DIR, 'factor_model.json');
  try {
    if (!fs.existsSync(fmPath)) return null;
    const raw = JSON.parse(fs.readFileSync(fmPath));
    // Return only the latest values + agreement, not full history (too large for API)
    const summary = {
      updated: raw.updated,
      model: raw.model,
      note: raw.note,
      factors: {},
      agreement: raw.agreement,
    };
    for (const [name, factor] of Object.entries(raw.factors || {})) {
      const f = factor.filtered || [];
      const s = factor.smoothed || [];
      const dates = factor.dates || [];
      const trendStates = factor.trend_states || [];
      // Last 24 months for sparkline
      const n = Math.min(24, f.length);
      summary.factors[name] = {
        method: factor.method,
        n_series: factor.n_series,
        series_used: factor.series_used,
        latest: f.length > 0 ? f[f.length - 1] : null,
        latest_smoothed: s.length > 0 ? s[s.length - 1] : null,
        trendState: trendStates.length > 0 ? trendStates[trendStates.length - 1] : null,
        variance_explained: factor.variance_explained || null,
        loadings: factor.loadings || {},
        loading_stability: factor.loading_stability || {},
        warmup_months: factor.warmup_months || null,
        // Sparkline data (last 24 months)
        sparkline: f.slice(-n).map((v, i) => ({ date: dates[dates.length - n + i], value: v })),
      };
    }
    return summary;
  } catch(e) {
    return null;
  }
}



// ============================================================
// CYCLE ANALYSIS — Logic Layer v2
// KEY RULES:
//   Module state  = current level of each indicator
//   Arrow state   = directional change + time lag (NOT level matching)
//   Each arrow has a fixed timeframe — do not mix timeframes
//   ①→② 1D-1M  ②→③ 1Q-6M  ③→④ 1Q-1Y  ④→① 1M-1Q
// ============================================================
function generateCycleAnalysis(macroState, macroTransmission, rates) {
  const gV = (arr, lbl) => (arr||[]).find(r => r.label === lbl)?.current ?? null;
  const gC = (arr, lbl, p='1m') => (arr||[]).find(r => r.label === lbl)?.changes?.[p] ?? null;
  const fmt2 = v => v != null ? v.toFixed(2) : '—';
  const fmt1 = v => v != null ? v.toFixed(1) : '—';
  const fmtBP = v => v != null ? (v > 0 ? `+${Math.round(v)}bp` : `${Math.round(v)}bp`) : '—';
  const fmtK  = v => v != null ? (v > 0 ? `+${Math.round(v)}k` : `${Math.round(v)}k`) : '—';

  // ── raw values ──────────────────────────────────────────
  const dff          = gV(rates, 'Fed Fund Rate');
  const dffChg1M     = gC(rates, 'Fed Fund Rate', '1m');    // bp
  const dffChg6M     = gC(rates, 'Fed Fund Rate', '6m');
  const futuresRate  = gV(rates, 'Fed Fund Futures (12M Path)');
  const corePce      = gV(macroState, 'Core PCE 通胀 (YoY)');
  const corePceChg1M = gC(macroState, 'Core PCE 通胀 (YoY)', '1m');
  const corePceChg6M = gC(macroState, 'Core PCE 通胀 (YoY)', '6m');
  const corePceChg1Y = gC(macroState, 'Core PCE 通胀 (YoY)', '1y');
  // R* estimate ≈ 0.5% real neutral; approximate real policy rate
  const realPolRate  = (dff != null && corePce != null) ? +(dff - corePce).toFixed(2) : null;
  const futuresCuts  = futuresRate; // it's already 12M diff in bp

  const nfci         = gV(macroTransmission, 'Chicago Fed NFCI');
  const nfciChg1M    = gC(macroTransmission, 'Chicago Fed NFCI', '1m');
  const nfciChg3M    = gC(macroTransmission, 'Chicago Fed NFCI', '3m');
  const tips10y      = gV(rates, 'TIP Yield (10Y TIPS)');
  const tipsChg1M    = gC(rates, 'TIP Yield (10Y TIPS)', '1m');
  const tipsChg3M    = gC(rates, 'TIP Yield (10Y TIPS)', '3m');
  const hyig         = gV(rates, '(垃圾-优质) 利差 HY-IG');
  const hyigChg1M    = gC(rates, '(垃圾-优质) 利差 HY-IG', '1m');
  const hyigChg3M    = gC(rates, '(垃圾-优质) 利差 HY-IG', '3m');
  const ciLoans      = gV(macroTransmission, 'C&I Loans (YoY)');
  const ciLoansChg3M = gC(macroTransmission, 'C&I Loans (YoY)', '3m');
  const consLoans    = gV(macroTransmission, 'Consumer Loans (YoY)');
  const ccDeliq      = gV(macroTransmission, 'CC Delinquency Rate');
  const mgtDeliq     = gV(macroTransmission, 'Mortgage Delinquency Rate');

  const gdpnow       = gV(macroState, 'Atlanta Fed GDPNow \u4e9a\u7279\u5170\u5927\u8054\u50a8');
  const ip           = gV(macroState, 'Industrial Production (YoY)');
  const ipChg3M      = gC(macroState, 'Industrial Production (YoY)', '3m');
  const rPce         = gV(macroState, 'Real PCE (MoM)');
  const rPceChg3M    = gC(macroState, 'Real PCE (MoM)', '3m');
  const retailMoM    = gV(macroState, 'Retail Sales Control (MoM)');
  const capex        = gV(macroState, 'Core Capex Orders (YoY, NSA)');
  const capexChg3M   = gC(macroState, 'Core Capex Orders (YoY, NSA)', '3m');
  const nfp          = gV(macroState, 'Nonfarm Payrolls (MoM \u0394)');
  const nfpChg3M     = gC(macroState, 'Nonfarm Payrolls (MoM \u0394)', '3m');
  const unrate       = gV(macroState, 'Unemployment 失业率');
  const unrateChg1M  = gC(macroState, 'Unemployment 失业率', '1m');
  const unrateChg6M  = gC(macroState, 'Unemployment 失业率', '6m');
  const claims       = gV(macroState, 'Initial Claims');
  const tempHelp     = gV(macroState, 'Temp Help Employment (YoY)');
  const wages        = gV(macroState, 'Avg Hourly Wage (YoY)');
  const wagesChg6M   = gC(macroState, 'Avg Hourly Wage (YoY)', '6m');
  const ulc          = gV(macroTransmission, 'Unit Labor Cost (YoY)');
  const prod         = gV(macroTransmission, 'Productivity (YoY)');
  const ppi          = gV(macroTransmission, 'PPI Final Demand (YoY)');
  const cpiGoods     = gV(macroTransmission, 'CPI Core Goods (YoY)');
  const cpiHsng      = gV(macroTransmission, 'CPI Housing (YoY)');
  const govExp       = gV(macroTransmission, 'Federal Expenditures (YoY)');
  const fiscDefGDP   = gV(macroTransmission, 'Fiscal Deficit % GDP');
  const trsyIssue    = gV(macroTransmission, 'Treasury Net Issuance');
  const termPrem     = gV(rates, '10Y ACM Term Premium (Model Est.)');

  const ARROW_LABELS = {
    flowing:'传导顺畅', partially_offset:'部分抵消',
    lagging:'传导滞后', diverging:'出现背离',
    insufficient:'证据不足', dual_constraint:'双目标约束'
  };
  const ARROW_COLORS = {
    flowing:'#22aa55', partially_offset:'#ff9500',
    lagging:'#ccaa33', diverging:'#dd3311',
    insufficient:'#888', dual_constraint:'#6699cc'
  };
  function arrow(st, ev, tf, conf, change_if) {
    return { state:st,
      label_zh: ARROW_LABELS[st] || st,
      label_en: st.replace(/_/g,' ').toUpperCase(),
      color: ARROW_COLORS[st] || '#888',
      evidence:ev, timeframe:tf, confidence:conf, change_if };
  }

  // ================================================================
  // MODULE STATES  (current level — not directional)
  // ================================================================

  // MODULE 1: Fed Policy
  // State based on level of DFF relative to neutral estimate (~2.5% nominal / ~0.5% real)
  const fedEv = [];
  if (dff != null)           fedEv.push(`DFF ${fmt2(dff)}%`);
  if (realPolRate != null)   fedEv.push(`事后实际政策利率 ${fmt2(realPolRate)}% (DFF−CorePCE YoY，R*≈0.5%)`);
  if (futuresCuts != null)   fedEv.push(`期货路径12M ${futuresCuts > 0 ? '+' : ''}${futuresCuts}bp`);

  let fedState, fedLZ, fedLE, fedColor;
  // Real policy rate relative to R* (~0.5%): positive gap = restrictive
  const realRateGap = realPolRate != null ? realPolRate - 0.5 : null; // vs R*
  if (dff == null) {
    fedState='unknown'; fedLZ='数据不足'; fedLE='UNKNOWN'; fedColor='#888';
  } else if (realRateGap != null && realRateGap > 1.5) {
    fedState='tight'; fedLZ='紧缩'; fedLE='TIGHT'; fedColor='#dd3311';
  } else if (realRateGap != null && realRateGap > 0.2) {
    fedState='restrictive'; fedLZ='限制性'; fedLE='RESTRICTIVE'; fedColor='#ff7722';
  } else if (realRateGap != null && realRateGap > -0.5) {
    fedState='neutral'; fedLZ='短端约束有限'; fedLE='SHORT-END MILD'; fedColor='#ccaa33';
  } else {
    fedState='easy'; fedLZ='宽松'; fedLE='EASY'; fedColor='#22aa55';
  }
  // Add long-end assessment from TIPS (tips10y already defined above)
  const longEndTight = tips10y != null && tips10y > 2.0;
  const longEndNote = longEndTight ? `，长端实际融资偏紧（10Y TIPS ${fmt2(tips10y)}%）` : '';
  const fedNote = futuresCuts != null && Math.abs(futuresCuts) < 15
    ? '12M隐含平均EFFR与当前DFF接近，净政策变化定价约零，但期间路径须查看各次FOMC会议概率' : null;

  // MODULE 2: Financial Conditions
  // Key: NFCI (综合), TIPS (长端实际利率), HY-IG (信用), C&I (银行贷款)
  // Two sub-channels tracked separately: broad (NFCI/credit) vs rate (TIPS/term premium)
  const finEv = [];
  const broadLoose  = nfci != null && nfci < -0.3;
  const broadTight  = nfci != null && nfci > 0.3;
  const realRateHigh = tips10y != null && tips10y > 2.0;
  const realRateLow  = tips10y != null && tips10y < 1.0;
  const creditLoose = hyig != null && hyig < 250;
  const creditTight = hyig != null && hyig > 400;
  const lendingTight = ciLoans != null && ciLoans < 0;

  if (nfci != null)    finEv.push(`NFCI ${fmt2(nfci)} (综合)`);
  if (tips10y != null) finEv.push(`10Y实际收益率 ${fmt2(tips10y)}% (TIPS)`);
  if (hyig != null)    finEv.push(`HY-IG ${Math.round(hyig)}bp (信用利差)`);
  if (ciLoans != null) finEv.push(`C&I贷款 ${fmt1(ciLoans)}% YoY (银行贷款)`);

  let finState, finLZ, finLE, finColor;
  // Internal divergence: broad loose but real rate channel tight
  if (broadLoose && realRateHigh && creditLoose) {
    // The key mixed case the user identified
    finState='mixed'; finLZ='综合偏宽松·长端利率偏紧'; finLE='MIXED (BROAD LOOSE / RATES TIGHT)'; finColor='#ccaa33';
  } else if (broadLoose && creditLoose && !realRateHigh) {
    finState='loose'; finLZ='综合宽松'; finLE='LOOSE'; finColor='#22aa55';
  } else if (broadTight && creditTight) {
    finState='tight'; finLZ='全面收紧'; finLE='TIGHT'; finColor='#dd4422';
  } else if (realRateHigh && lendingTight) {
    finState='rate_tight'; finLZ='利率渠道收紧·信用利差尚稳'; finLE='RATE CHANNELS TIGHT'; finColor='#ee8833';
  } else if (broadLoose || creditLoose) {
    finState='slightly_loose'; finLZ='偏宽松'; finLE='SLIGHTLY LOOSE'; finColor='#55bb77';
  } else if (broadTight || creditTight) {
    finState='slightly_tight'; finLZ='偏紧'; finLE='SLIGHTLY TIGHT'; finColor='#ee8833';
  } else {
    finState='neutral'; finLZ='中性'; finLE='NEUTRAL'; finColor='#888';
  }

  // MODULE 3: Real Economy — multi-signal assessment of current level
  const econEv = [];
  let econWeak=0, econStrong=0;
  if (gdpnow!=null) { if(gdpnow>2.5)econStrong++;else if(gdpnow<0.5)econWeak++; econEv.push(`GDPNow ${fmt1(gdpnow)}%`); }
  if (nfp!=null)    { if(nfp>150)econStrong++;else if(nfp<75)econWeak++; econEv.push(`NFP ${fmtK(nfp)} MoM`); }
  if (ip!=null)     { if(ip>2)econStrong++;else if(ip<-0.5)econWeak++; econEv.push(`IP ${fmt1(ip)}% YoY`); }
  if (rPce!=null)   { if(rPce>0.3)econStrong++;else if(rPce<0)econWeak++; econEv.push(`Real PCE ${fmt2(rPce)}% MoM`); }
  if (capex!=null)  { if(capex>5)econStrong++;else if(capex<-2)econWeak++; }
  if (unrateChg6M!=null){ if(unrateChg6M>0.3)econWeak++;else if(unrateChg6M<-0.3)econStrong++; }

  let econState, econLZ, econLE, econColor;
  if      (econWeak>=4) { econState='contracting';econLZ='收缩';econLE='CONTRACTING';econColor='#dd3311'; }
  else if (econWeak>=3) { econState='slowing';econLZ='明显放缓';econLE='SLOWING';econColor='#ee8833'; }
  else if (econWeak>=2&&econStrong<=1) { econState='soft';econLZ='温和·分化';econLE='MODERATE/DIVERGING';econColor='#ff9500'; }
  else if (econStrong>=3) { econState='strong';econLZ='偏强';econLE='STRONG';econColor='#22aa55'; }
  else { econState='moderate';econLZ='温和增长';econLE='MODERATE';econColor='#55bb77'; }

  // MODULE 4: Inflation & Labor — current level vs targets
  const inflEv = [];
  const pceDev = corePce != null ? corePce - 2.0 : null;
  const inflHigh = pceDev != null && pceDev > 0.5;
  const inflVeryHigh = pceDev != null && pceDev > 1.5;
  const unrateRising = unrateChg6M != null && unrateChg6M > 0.3;
  const wagesElevated = wages != null && wages > 3.5;
  if (corePce!=null) inflEv.push(`Core PCE ${fmt2(corePce)}% YoY (目标2%，偏差${corePce>2?'+':''}${fmt2(pceDev)}pp)`);
  if (unrate!=null)  inflEv.push(`失业率 ${fmt2(unrate)}%${unrateChg6M!=null?'（6M '+fmtBP(unrateChg6M*100)+'）':''}`);
  if (wages!=null)   inflEv.push(`工资增长 ${fmt2(wages)}% YoY`);
  if (ulc!=null)     inflEv.push(`ULC ${fmt2(ulc)}% YoY`);

  let inflState, inflLZ, inflLE, inflColor;
  if      (inflVeryHigh&&unrateRising) { inflState='stagflation';inflLZ='滞胀风险';inflLE='STAGFLATION RISK';inflColor='#dd3311'; }
  else if (inflVeryHigh)               { inflState='overheating';inflLZ='过热';inflLE='OVERHEATING';inflColor='#dd3311'; }
  else if (inflHigh&&unrateRising)     { inflState='sticky_cooling';inflLZ='通胀黏性·就业降温';inflLE='STICKY + COOLING LABOR';inflColor='#ff7722'; }
  else if (inflHigh)                   { inflState='sticky';inflLZ='通胀黏性高于目标';inflLE='ABOVE TARGET';inflColor='#ff9500'; }
  else if (pceDev!=null&&pceDev<-0.3) { inflState='deflation_risk';inflLZ='通缩压力';inflLE='DEFLATION RISK';inflColor='#4488ff'; }
  else                                 { inflState='balanced';inflLZ='接近目标';inflLE='NEAR TARGET';inflColor='#22aa55'; }

  // ================================================================
  // ARROW STATES  (directional change + time lag — NOT level matching)
  // ================================================================

  // ①→② (timeframe: 1D–1M)
  // Question: Is Fed's current policy STANCE being transmitted to financial conditions?
  // Not "are both loose" — but: are the channels that SHOULD respond, responding?
  // Key signals: 1M change in TIPS, NFCI, HY-IG vs DFF direction
  let a1;
  {
    const tf = '1D–1M';
    // Channel assessment (level-based, used to identify which channels are offset)
    const longRateTight   = realRateHigh;                          // TIPS > 2% = tightening via rate channel
    const creditChannelLoose = creditLoose;                        // HY-IG < 250bp = credit loose
    const broadChannelLoose  = broadLoose;                         // NFCI < -0.3 = broad loose
    // 1M changes: direction of recent moves
    const tipsRising1M    = tipsChg1M != null && tipsChg1M > 5;   // bp, TIPS rising
    const nfciTightening1M = nfciChg1M != null && nfciChg1M > 0.05;
    const hyigWidening1M  = hyigChg1M != null && hyigChg1M > 10;  // bp, spreads widening

    if (!dff || (!nfci && !tips10y)) {
      a1 = arrow('insufficient', ['缺少DFF或金融条件数据'], tf, 'low', '补充数据后重新计算');
    } else if (longRateTight && creditChannelLoose && broadChannelLoose) {
      // The split: long-rate channel tight, credit/equity channel loose — classic partial offset
      a1 = arrow('partially_offset', [
        `10Y实际收益率偏高（TIPS ${fmt2(tips10y)}%），长期融资成本受限`,
        `但信用利差窄（HY-IG ${hyig!=null?Math.round(hyig):'—'}bp）、NFCI宽松（${fmt2(nfci)}）抵消部分约束`,
        '两个渠道方向相反：利率渠道偏紧，信用与资产价格渠道偏宽松',
        '期限溢价偏高加剧长端压力'
      ], tf, 'high', 'NFCI>0 且 HY-IG>350bp 且 TIPS继续上行，则转为传导顺畅');
    } else if (longRateTight && !creditChannelLoose) {
      a1 = arrow('flowing', [
        '10Y实际收益率偏高，信用渠道也在收紧',
        '多渠道同向传导政策约束'
      ], tf, 'medium', 'NFCI转负或信用利差大幅收窄则转为部分抵消');
    } else if (!longRateTight && broadChannelLoose && creditChannelLoose) {
      a1 = arrow('flowing', [
        '政策偏宽，金融条件各渠道同步宽松',
        '短端、信用、综合方向一致'
      ], tf, 'medium', 'TIPS上行或NFCI转正则需重新评估');
    } else {
      a1 = arrow('lagging', [
        '政策方向已明确，金融条件各渠道响应尚未充分同步'
      ], tf, 'low', '各渠道方向趋于一致后升级');
    }
  }

  // ②→③ (timeframe: 1Q–6M)
  // Question: Are current financial conditions translating into real activity changes?
  // Key: NOT whether conditions are loose/tight NOW, but whether 3M-6M change in conditions
  //      correlates with 3M-6M change in investment, hiring, production
  let a2;
  {
    const tf = '1Q–6M';
    // Investment & production: already weakening (high real rate transmitting with 3-6M lag)
    const investWeak = (capex!=null&&capex<-2) || (ipChg3M!=null&&ipChg3M<-1);
    // Employment: weakening
    const laborWeak  = (nfp!=null&&nfp<75) || (unrateChg6M!=null&&unrateChg6M>0.2);
    // Consumption: still holding
    const consumeOk  = (rPce!=null&&rPce>0) && (retailMoM!=null&&retailMoM>0);
    // Real rate was high for >6 months (tipsChg3M direction tells us trajectory)
    const realRatePersistHigh = realRateHigh && (tipsChg3M!=null ? tipsChg3M > -10 : true);

    if (investWeak && laborWeak && consumeOk) {
      // Classic partial transmission: rate-sensitive sectors hit first, consumer lags
      a2 = arrow('lagging', [
        '投资（Capex偏弱）与就业（NFP仅'+fmtK(nfp)+'）已率先出现放缓迹象',
        '消费端（Real PCE '+fmt2(rPce)+'% MoM）仍有支撑，尚未充分传导',
        '高真实利率（TIPS '+fmt2(tips10y)+'%）通常先压制投资，后影响消费（6-18个月滞后）',
        '传导不完整：生产与就业前端已受压，消费终端仍韧性'
      ], tf, 'high', 'Real PCE转负 或 Claims大幅上升 则升级为传导顺畅');
    } else if (investWeak && laborWeak && !consumeOk) {
      a2 = arrow('flowing', [
        '高真实利率已全面传导：投资、就业与消费同步走弱'
      ], tf, 'high', 'GDP回升2.5%+ 且就业反弹则转为证据不足');
    } else if (!investWeak && !laborWeak && consumeOk) {
      a2 = arrow('lagging', [
        '金融条件（TIPS偏高）尚未充分传导至实体：各项指标仍正常',
        '典型的货币传导滞后窗口（通常需6-18个月）'
      ], tf, 'low', '投资与就业开始减速后重新评估');
    } else if (nfci!=null&&nfci<-0.5&&!investWeak&&!laborWeak) {
      a2 = arrow('flowing', [
        '综合金融条件宽松，经济表现与此一致'
      ], tf, 'medium', '金融条件收紧或经济数据走弱则重新评估');
    } else {
      a2 = arrow('partially_offset', [
        '部分渠道已传导（投资/就业），部分尚未（消费）',
        '财政支出可能在托底需求，延长传导时间'
      ], tf, 'medium', '各分项方向趋于一致后升级');
    }
  }

  // ③→④ (timeframe: 1Q–1Y)
  // Question: Is the real economy slowdown translating into lower inflation?
  // Key: Compare the PACE of economic deceleration vs pace of inflation decline
  // NOT whether current level matches — whether the change direction correlates
  let a3;
  {
    const tf = '1Q–1Y';
    // Economic activity is slowing/soft (level + direction)
    const econSlowing = econState==='slowing'||econState==='soft'||econState==='contracting';
    // Inflation: is it falling fast enough given the slowdown?
    const inflFalling1M = corePceChg1M!=null && corePceChg1M < -0.05;
    const inflFalling6M = corePceChg6M!=null && corePceChg6M < -0.2;
    const inflFallingSlowly = corePceChg6M!=null && corePceChg6M < 0 && corePceChg6M > -0.2;
    // Still above target despite slowdown = sticky / divergence
    const stickyAboveTarget = inflHigh && econSlowing;

    if (econSlowing && inflFalling6M) {
      a3 = arrow('flowing', [
        '经济放缓，通胀同步下降（6M趋势）',
        '需求下降正在压缩价格压力'
      ], tf, 'high', '通胀重新加速或增长明显反弹则转为背离');
    } else if (stickyAboveTarget && !inflFalling6M) {
      // The key current scenario: economy slow but inflation not falling fast
      a3 = arrow('diverging', [
        `招聘与资本开支降温（NFP ${fmtK(nfp)}，Capex YoY偏弱），但总体产出尚未确认放缓（GDPNow ${fmt1(gdpnow)}%）`,
        `Core PCE仍${fmt2(corePce)}%，服务通胀黏性（住房、医疗、保险等）不随短期需求变化快速回落`,
        '工资增长（'+fmt2(wages)+'% YoY）维持通胀下限，能源/关税供给冲击可能额外抬高通胀基准',
        '若招聘和投资降温进一步扩散至消费与总体产出，而Core PCE继续维持高位，滞胀风险将上升'
      ], tf, 'high', 'Core PCE连续3月低于2.5% 或 住房CPI明显回落则降级为传导顺畅');
    } else if (!econSlowing && inflHigh) {
      a3 = arrow('partially_offset', [
        '总量增长强，但就业需求降温；通胀水平高，但传导不完整'
      ], tf, 'medium', '经济明显放缓或通胀实质降温后重新评估');
    } else if (!econSlowing && !inflHigh) {
      a3 = arrow('flowing', [
        '经济温和，通胀接近目标，软着陆状态'
      ], tf, 'medium', '通胀重新上行则转为背离');
    } else if (econSlowing && inflFallingSlowly) {
      a3 = arrow('lagging', [
        '经济放缓，通胀缓慢下行，传导路径正确但速度慢',
        '服务通胀黏性导致传导滞后'
      ], tf, 'medium', 'Core PCE加速下降则转为传导顺畅');
    } else {
      a3 = arrow('insufficient', ['需更多数据判断方向相关性'], tf, 'low', '补充3M以上数据后重新评估');
    }
  }

  // ④→① (timeframe: 1M–1Q)
  // Question: Is Fed policy responding correctly to the inflation + labor outcomes?
  // Key: NOT whether inflation is high and Fed is tight — but whether Fed's ACTION
  //      (or inaction) is consistent with what inflation+labor DATA calls for
  let a4;
  {
    const tf = '1M–1Q';
    const inflAboveTarget = inflHigh;
    const inflVAbove      = inflVeryHigh;
    const laborCooling    = unrateRising || (nfp!=null&&nfp<75);
    const laborStrong     = !unrateRising && (nfp!=null&&nfp>150);
    const fedHolding      = futuresCuts!=null && Math.abs(futuresCuts)<20; // ±20bp = effectively hold
    const fedCutting      = futuresCuts!=null && futuresCuts<-30;
    const fedHiking       = dffChg1M!=null && dffChg1M>0;

    // Dual mandate conflict: inflation high + labor cooling = Fed is constrained in both directions
    if (inflAboveTarget && laborCooling && fedHolding) {
      a4 = arrow('dual_constraint', [
        `通胀${fmt2(corePce)}%（高于目标2%）→ 不支持快速降息`,
        `劳动力降温（NFP ${fmtK(nfp)}，失业率${unrate!=null?fmt2(unrate)+'%':'—'}${unrateRising?'↑':''}）→ 不支持继续加息`,
        '期货路径约0bp：市场预计Fed维持，与双目标约束一致',
        '政策维持是当前数据下合理的反应函数输出'
      ], tf, 'high', '通胀明显重新加速+就业仍强 且 Fed大幅降息，才构成真正背离');
    } else if (inflVAbove && laborStrong && fedCutting) {
      // Real divergence: both mandates scream hold/hike, but Fed cutting
      a4 = arrow('diverging', [
        '通胀严重超标 + 就业强劲，但Fed仍在降息',
        '政策方向与双重目标严重背离'
      ], tf, 'high', 'Fed停止降息或就业开始降温后背离减弱');
    } else if (inflAboveTarget && laborStrong && fedHolding) {
      a4 = arrow('flowing', [
        '通胀高于目标 + 就业强劲 → Fed维持高利率，政策反应一致'
      ], tf, 'high', '通胀下降至目标附近后重新评估');
    } else if (!inflAboveTarget && laborCooling && !fedCutting) {
      a4 = arrow('lagging', [
        '通胀已接近目标 + 劳动力降温，但Fed尚未充分降息（政策滞后）'
      ], tf, 'medium', 'Fed开始降息则转为传导顺畅');
    } else if (inflAboveTarget && laborCooling && fedCutting) {
      a4 = arrow('diverging', [
        '通胀仍高但Fed在降息，且劳动力降温',
        '降息有就业面支撑，但通胀面构成背离'
      ], tf, 'medium', '通胀明显回落后背离消除');
    } else {
      a4 = arrow('flowing', [
        '当前通胀与就业组合支持维持限制性政策立场，但增长—就业分化提高后续调整的不确定性。'
      ], tf, 'medium', '数据明显偏离后重新评估');
    }
  }

  // ================================================================
  // CONTRADICTIONS  (computed from actual data conflicts)
  // ================================================================
  const contradictions = [];
  // Contradiction 1: broad financial conditions loose BUT real rate high
  if (broadLoose && realRateHigh) {
    contradictions.push({ zh:`金融市场综合宽松（NFCI ${fmt2(nfci)}）↔ 10Y实际收益率偏高（TIPS ${fmt2(tips10y)}%）：两个渠道方向相反`, timeframe:'1M' });
  }
  // Contradiction 2: credit market tight/loose vs actual defaults/delinquencies
  if (creditLoose && ccDeliq!=null && ccDeliq>3.0) {
    contradictions.push({ zh:`信用利差窄（HY-IG ${Math.round(hyig)}bp）↔ 信用卡拖欠率偏高（${fmt2(ccDeliq)}%）：市场定价与底层信用质量背离`, timeframe:'1Q' });
  }
  // Contradiction 3: growth vs employment
  if (gdpnow!=null && gdpnow>1.5 && nfp!=null && nfp<75) {
    contradictions.push({ zh:`GDPNow仍正增长（${fmt1(gdpnow)}%）↔ NFP仅${fmtK(nfp)}：增长与就业明显分化，需总工时与GDP分项确认`, timeframe:'1M' });
  }
  // Contradiction 4: economy slowing but inflation not falling
  if ((econState==='soft'||econState==='slowing') && inflHigh) {
    contradictions.push({ zh:`招聘与资本开支降温 ↔ Core PCE仍${fmt2(corePce)}%（高于目标${fmt2(pceDev)}pp）：企业劳动与投资需求转弱，但通胀尚未同步回落`, timeframe:'1Q' });
  }
  // Contradiction 5: real rate rising but credit spreads tight
  if (realRateHigh && creditLoose) {
    contradictions.push({ zh:`10Y实际收益率偏高（TIPS ${fmt2(tips10y)}%）↔ 信用利差窄（HY-IG ${Math.round(hyig)}bp）：利率市场与信用市场风险定价方向相反`, timeframe:'1M' });
  }

  // ================================================================
  // TOP RISKS & WATCH NEXT
  // ================================================================
  const topRisks = [], watchNext = [];

  if (broadLoose&&inflHigh) topRisks.push({ zh:'金融条件宽松 + 通胀黏性 → 降息空间压缩，通胀下行速度受限', en:'Loose fin.conditions + sticky inflation → constrained easing' });
  if ((econState==='soft'||econState==='slowing')&&inflHigh) topRisks.push({ zh:'若招聘与资本开支降温进一步扩散至消费与总体产出，而通胀维持高位 → 滞胀风险上升', en:'If hiring/capex cooling spreads to consumption and output while inflation stays elevated → stagflation risk rises' });
  if (realRateHigh&&(econState==='soft'||econState==='slowing')) topRisks.push({ zh:`10Y实际收益率${fmt2(tips10y)}% + 招聘降温 → 信贷与资产估值滞后压力尚未全面体现`, en:'Elevated 10Y real yield + cooling hiring → lagged credit/valuation pressure' });
  if (termPrem!=null&&termPrem>0.6&&trsyIssue!=null&&trsyIssue>400) topRisks.push({ zh:`国债净发行$${Math.round(trsyIssue)}B + 期限溢价${fmt2(termPrem)}% → 长端利率结构性压力`, en:'Heavy Treasury supply + elevated term premium' });
  else if (termPrem!=null&&termPrem>0.6&&trsyIssue==null) topRisks.push({ zh:`期限溢价${fmt2(termPrem)}% (发行数据待补) → 长端利率结构性压力`, en:'Elevated term premium (issuance pending) → structural rate pressure' });

  if (inflHigh)      watchNext.push({ zh:'Core PCE月度趋势（3M方向）→ 通胀黏性是否开始消退', en:'Core PCE 3-month trend' });
  watchNext.push({ zh:'JOLTS职位空缺 + SLOOS贷款标准 → 就业与信贷冷却速度', en:'JOLTS + SLOOS for labor/credit cooling pace' });
  if (unrateRising)  watchNext.push({ zh:'失业率6M斜率 → 是否触发Sahm Rule（指标=0.5pp）', en:'Unemployment 6M slope → Sahm Rule trigger' });
  watchNext.push({ zh:'Fed会议纪要 & 点阵图 → 政策路径预期是否重新定价', en:'FOMC minutes & dot plot repricing' });
  if (realRateHigh)  watchNext.push({ zh:'TIPS 3M趋势 → 10Y实际收益率压力是否扩大至信用市场', en:'TIPS 3M trend → 10Y real yield pressure spilling to credit' });

  // ================================================================
  // EXTERNAL INPUTS
  // ================================================================
  const fiscal = {
    govExpYoY: govExp, fiscDefGDP, trsyIssue, intExpGDP: gV(macroTransmission, 'Federal Interest Exp / GDP'),
    state: govExp!=null&&govExp>5?'loose':govExp!=null&&govExp>0?'neutral_loose':'unknown',
    label_zh: trsyIssue == null 
      ? '发行数据待补，当前主要由期限溢价与TIPS确认'
      : (govExp!=null&&govExp>5
        ?'财政需求端偏宽松（支出增速偏高、赤字率仍高）；国债融资条件偏紧（净发行高、期限溢价上升）'
        :govExp!=null&&govExp>0?'中性偏松':'数据不足'),
    path_rates: trsyIssue == null ? '发行数据待补，当前主要由期限溢价与TIPS确认长端压力（→②）' : '赤字与国债净发行推升长端利率与期限溢价（→②）',
    path_demand:'政府支出增速直接支撑GDP需求侧，或延缓招聘与投资降温向消费传导（→③）'
  };
  const supplyShocks = {
    ppiYoY: ppi, cpiGoods,
    state: ppi!=null&&ppi>4?'elevated':ppi!=null&&ppi>2?'moderate':'low',
    label_zh: ppi!=null&&ppi>4?'成本压力偏高':ppi!=null&&ppi>2?'温和':'低',
    // Supply shocks have two transmission paths
    path_cost:'企业投入成本上升 → 压缩利润率或转嫁至消费者价格（→③企业端）',
    path_infl:'若转嫁成功 → 直接推高CPI/PCE（→④通胀）'
  };

  return {
    modules: {
      fed:  { state:fedState,  label_zh:fedLZ + longEndNote,  label_en:fedLE,  color:fedColor,  evidence:fedEv,  note:fedNote,  keyMetrics:{dff,realPolRate,futuresCuts,tips10y} },
      fin:  { state:finState,  label_zh:finLZ,  label_en:finLE,  color:finColor,  evidence:finEv,  keyMetrics:{nfci,tips10y,hyig,ciLoans} },
      econ: { state:econState, label_zh:econLZ, label_en:econLE, color:econColor, evidence:econEv, keyMetrics:{gdpnow,nfp,ip,rPce} },
      infl: { state:inflState, label_zh:inflLZ, label_en:inflLE, color:inflColor, evidence:inflEv, keyMetrics:{corePce,unrate,wages,ulc} },
    },
    arrows: { fed_fin:a1, fin_econ:a2, econ_infl:a3, infl_fed:a4 },
    external: { fiscal, supplyShocks },
    topRisks, watchNext, contradictions
  };
}




// ============================================
// HTTP SERVER
// ============================================
function requireLocalAdmin(req, res) {
  const isLocal = req.socket.remoteAddress === '127.0.0.1' || req.socket.remoteAddress === '::ffff:127.0.0.1' || req.socket.remoteAddress === '::1';
  if (!isLocal || req.method !== 'POST') {
    res.writeHead(403);
    res.end(JSON.stringify({ error: 'Access denied: Local POST only' }));
    return false;
  }
  
  const authHeader = req.headers['authorization'];
  if (!authHeader || authHeader !== `Bearer ${process.env.LOCAL_ADMIN_TOKEN}`) {
    res.writeHead(401);
    res.end(JSON.stringify({ error: 'Unauthorized: Invalid token' }));
    return false;
  }
  
  const origin = req.headers['origin'];
  if (origin && !origin.includes('localhost') && !origin.includes('127.0.0.1')) {
    res.writeHead(403);
    res.end(JSON.stringify({ error: 'Access denied: Invalid origin' }));
    return false;
  }
  return true;
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(204); res.end(); return; }

  res.setHeader('Content-Type', 'application/json');
  const p = req.url.split('?')[0];

  if (p === '/api/chart') {
    // Return full time series for charting — prefer source with more history
    const params = new URL(req.url, 'http://localhost').searchParams;
    const key = params.get('key') || '';
    let data = null;
    if (key.startsWith('spread:')) {
      const [, a, b] = key.split(':');
      data = computeSpread(a, b, key.includes('_pct') ? 100 : 1);
    } else {
      const y = store.yahoo[key];
      const f = store.fred[key];
      const v = key.startsWith('val:') ? store.valuation[key.slice(4)] : null;
      if (v) {
        data = v;
      } else if (y && f) {
        data = y.length >= f.length ? y : f;
      } else {
        data = y || f || null;
      }
    }

    // Apply economy transforms so chart matches table values
    const econRow = ECONOMY_ROWS.find(r => r.series === key);
    if (data && econRow?.transform) {
      if (econRow.transform === 'yoy') {
        const dateMap = new Map(data.map(v => [v[0], v[1]]));
        const yoyVals = [];
        for (const [date, val] of data) {
          const yr = parseInt(date.slice(0,4)) - 1;
          const prevDate = `${yr}${date.slice(4)}`;
          let prevVal = dateMap.get(prevDate);
          if (prevVal == null) {
            for (let d = 1; d <= 20; d++) {
              const t = new Date(prevDate + 'T00:00:00Z');
              t.setUTCDate(t.getUTCDate() + d);
              const s = t.toISOString().slice(0,10);
              if (dateMap.has(s)) { prevVal = dateMap.get(s); break; }
              t.setUTCDate(t.getUTCDate() - 2*d);
              const s2 = t.toISOString().slice(0,10);
              if (dateMap.has(s2)) { prevVal = dateMap.get(s2); break; }
            }
          }
          if (prevVal && prevVal !== 0) yoyVals.push([date, +((val / prevVal - 1) * 100).toFixed(4)]);
        }
        data = yoyVals;
      } else if (econRow.transform === 'B→T') {
        data = data.map(([d, v]) => [d, +(v / 1000).toFixed(4)]);
      } else if (econRow.transform === 'M→T') {
        data = data.map(([d, v]) => [d, +(v / 1_000_000).toFixed(4)]);
      }
    }

    if (data) {
      res.end(JSON.stringify({ key, points: data.length, data }));
    } else {
      res.writeHead(404);
      res.end(JSON.stringify({ error: 'Not found', key }));
    }
  } else if (p === '/api/backtrack') {
    // =============================================
    // BACKTRACK: Find most similar historical macro environments
    // =============================================
    try {
      // All available indicators for comparison
      const ALL_COMPARE_KEYS = [
        // Rates
        { key: 'DFF',        label: 'Fed Fund Rate',      src: 'fred',      group: 'Rates' },
        { key: 'SOFR',       label: 'SOFR',               src: 'fred',      group: 'Rates' },
        { key: 'IORB',       label: 'IORB',               src: 'fred',      group: 'Rates' },
        { key: 'DGS3MO',     label: '3M Treasury',        src: 'fred',      group: 'Rates' },
        { key: 'DGS1',       label: '1Y Treasury',        src: 'fred',      group: 'Rates' },
        { key: 'DGS2',       label: '2Y Treasury',        src: 'fred',      group: 'Rates' },
        { key: 'DGS3',       label: '3Y Treasury',        src: 'fred',      group: 'Rates' },
        { key: 'DGS5',       label: '5Y Treasury',        src: 'fred',      group: 'Rates' },
        { key: 'DGS7',       label: '7Y Treasury',        src: 'fred',      group: 'Rates' },
        { key: 'DGS10',      label: '10Y Treasury',       src: 'fred',      group: 'Rates' },
        { key: 'DGS20',      label: '20Y Treasury',       src: 'fred',      group: 'Rates' },
        { key: 'DGS30',      label: '30Y Treasury',       src: 'fred',      group: 'Rates' },
        { key: 'T10Y3M',     label: 'Yield Curve 10Y-3M', src: 'fred',      group: 'Rates' },
        { key: 'DFII10',     label: 'TIPS 10Y Real',      src: 'fred',      group: 'Rates' },
        { key: 'BAMLH0A0HYM2',label:'HY OAS Spread',     src: 'fred',      group: 'Credit' },
        { key: 'BAMLC0A0CM', label: 'IG OAS Spread',      src: 'fred',      group: 'Credit' },
        // Commodities
        { key: 'DCOILWTICO', label: 'WTI Oil',            src: 'fred',      group: 'Commodities' },
        { key: 'DHHNGSP',    label: 'Natural Gas',        src: 'fred',      group: 'Commodities' },
        { key: 'GC=F',       label: 'Gold',               src: 'yahoo',     group: 'Commodities' },
        { key: 'HG=F',       label: 'Copper',             src: 'yahoo',     group: 'Commodities' },
        { key: 'ZW=F',       label: 'Wheat',              src: 'yahoo',     group: 'Commodities' },
        { key: 'ZS=F',       label: 'Soybean',            src: 'yahoo',     group: 'Commodities' },
        { key: 'BDRY',       label: 'Baltic Dry Index',   src: 'yahoo',     group: 'Commodities' },
        // Indices
        { key: 'NASDAQCOM',  label: 'NASDAQ Composite',   src: 'fred',      group: 'Indices' },
        { key: '^GSPC',      label: 'S&P 500',            src: 'yahoo',     group: 'Indices' },
        { key: '^DJI',       label: 'Dow Jones',          src: 'yahoo',     group: 'Indices' },
        { key: '^RUT',       label: 'Russell 2000',       src: 'yahoo',     group: 'Indices' },
        // Sectors
        { key: 'XLK',        label: 'XLK Tech',           src: 'yahoo',     group: 'Sectors' },
        { key: 'SOXX',       label: 'SOXX Semis',         src: 'yahoo',     group: 'Sectors' },
        { key: 'IGV',        label: 'IGV Software',       src: 'yahoo',     group: 'Sectors' },
        { key: 'MAGS',       label: 'MAGS Mag 7',         src: 'yahoo',     group: 'Sectors' },
        { key: 'XLV',        label: 'XLV Healthcare',     src: 'yahoo',     group: 'Sectors' },
        { key: 'IBB',        label: 'IBB Biotech',        src: 'yahoo',     group: 'Sectors' },
        { key: 'XLY',        label: 'XLY Consumer Disc',  src: 'yahoo',     group: 'Sectors' },
        { key: 'XRT',        label: 'XRT Retail',         src: 'yahoo',     group: 'Sectors' },
        { key: 'XLP',        label: 'XLP Consumer Staple',src: 'yahoo',     group: 'Sectors' },
        { key: 'XLE',        label: 'XLE Energy',         src: 'yahoo',     group: 'Sectors' },
        { key: 'ICLN',       label: 'ICLN Clean Energy',  src: 'yahoo',     group: 'Sectors' },
        { key: 'XLB',        label: 'XLB Materials',      src: 'yahoo',     group: 'Sectors' },
        { key: 'GDX',        label: 'GDX Gold Miners',    src: 'yahoo',     group: 'Sectors' },
        { key: 'XLRE',       label: 'XLRE REITs',         src: 'yahoo',     group: 'Sectors' },
        { key: 'XLF',        label: 'XLF Financials',     src: 'yahoo',     group: 'Sectors' },
        { key: 'KRE',        label: 'KRE Regional Banks', src: 'yahoo',     group: 'Sectors' },
        { key: 'KBE',        label: 'KBE Banks',          src: 'yahoo',     group: 'Sectors' },
        // Valuation
        { key: 'SP500_PE',   label: 'S&P 500 PE',         src: 'valuation', group: 'Valuation' },
        { key: 'SHILLER_CAPE',label:'Shiller CAPE',        src: 'valuation', group: 'Valuation' },
        { key: 'SP500_EPS',  label: 'S&P 500 EPS',        src: 'valuation', group: 'Valuation' },
        { key: 'SP500_EARN_YIELD',label:'Earnings Yield',  src: 'valuation', group: 'Valuation' },
        { key: 'SP500_DIV_YIELD',label:'Dividend Yield',   src: 'valuation', group: 'Valuation' },
        // Economy
        { key: 'PCEPILFE',      label: 'Core PCE Inflation', src: 'fred', group: 'Economy' },
        { key: 'UNRATE',        label: 'Unemployment',       src: 'fred', group: 'Economy' },
        { key: 'PCE',           label: 'Consumption PCE',    src: 'fred', group: 'Economy' },
        { key: 'CES0500000003', label: 'Avg Hourly Wage',    src: 'fred', group: 'Economy' },
        { key: 'WM2NS',         label: 'M2 Money Supply',    src: 'fred', group: 'Economy' },
        { key: 'GFDEBTN',       label: 'Gov Debt',           src: 'fred', group: 'Economy' },
        { key: 'WALCL',         label: 'Fed Balance Sheet',  src: 'fred', group: 'Economy' },
        { key: 'UMCSENT',       label: 'Consumer Sentiment', src: 'fred', group: 'Economy' },
        { key: 'MMMFFAQ027S',  label: 'Money Market Funds', src: 'fred', group: 'Economy' },
      ];

      // Filter by selected keys (if provided)
      const params = new URL(req.url, 'http://localhost').searchParams;
      const selectedKeys = params.get('keys') ? params.get('keys').split(',') : null;
      const COMPARE_KEYS = selectedKeys
        ? ALL_COMPARE_KEYS.filter(c => selectedKeys.includes(c.key))
        : ALL_COMPARE_KEYS;

      // Target for forward returns (default: S&P 500)
      const AVAILABLE_TARGETS = [
        { key: '^GSPC',  label: 'S&P 500' },
        { key: '^DJI',   label: 'Dow Jones' },
        { key: '^IXIC',  label: 'NASDAQ Composite' },
        { key: '^RUT',   label: 'Russell 2000' },
        { key: 'XLK',    label: 'XLK Tech' },
        { key: 'SOXX',   label: 'SOXX Semis' },
        { key: 'IGV',    label: 'IGV Software' },
        { key: 'XLV',    label: 'XLV Healthcare' },
        { key: 'IBB',    label: 'IBB Biotech' },
        { key: 'XLY',    label: 'XLY Consumer Disc' },
        { key: 'XLP',    label: 'XLP Consumer Staple' },
        { key: 'XLE',    label: 'XLE Energy' },
        { key: 'XLB',    label: 'XLB Materials' },
        { key: 'GDX',    label: 'GDX Gold Miners' },
        { key: 'XLRE',   label: 'XLRE REITs' },
        { key: 'XLF',    label: 'XLF Financials' },
        { key: 'KRE',    label: 'KRE Regional Banks' },
        { key: 'KBE',    label: 'KBE Banks' },
      ];
      const targetKey = params.get('target') || '^GSPC';
      const targetInfo = AVAILABLE_TARGETS.find(t => t.key === targetKey) || { key: targetKey, label: targetKey };

      // Trend period (configurable: 3m/6m/1y)
      const trendParam = params.get('trend') || '3m';
      const TREND_DAYS_MAP = { '3m': 63, '6m': 126, '1y': 252 };
      const TREND_DAYS = TREND_DAYS_MAP[trendParam] || 63;
      const trendLabel = trendParam.toUpperCase();

      // Binary insert into sorted array, return insertion index
      function binInsert(arr, val) {
        let lo = 0, hi = arr.length;
        while (lo < hi) { const mid = (lo + hi) >> 1; if (arr[mid] < val) lo = mid + 1; else hi = mid; }
        arr.splice(lo, 0, val);
        return lo;
      }

      const indicatorMaps = [];
      for (const c of COMPARE_KEYS) {
        const vals = store[c.src]?.[c.key];
        if (!vals || vals.length < 20) continue;
        const map = new Map(vals.map(v => [v[0], v[1]]));

        // Pre-compute POINT-IN-TIME percentile for each date
        // Each date's value is ranked only against data available up to that date
        const pitPctMap = new Map();  // date -> point-in-time percentile
        const runningSorted = [];
        for (let i = 0; i < vals.length; i++) {
          const pos = binInsert(runningSorted, vals[i][1]);
          pitPctMap.set(vals[i][0], (pos / runningSorted.length) * 100);
        }

        // Full sorted for "today" (latest date = no look-ahead)
        const sorted = vals.map(v => v[1]).sort((a, b) => a - b);

        // Compute momentum + point-in-time momentum percentile
        const momMap = new Map();
        const pitMomPctMap = new Map();
        const runningMomSorted = [];
        for (let i = TREND_DAYS; i < vals.length; i++) {
          const cur = vals[i][1];
          const prev = vals[i - TREND_DAYS][1];
          if (prev !== 0) {
            const roc = (cur - prev) / Math.abs(prev) * 100;
            momMap.set(vals[i][0], roc);
            const pos = binInsert(runningMomSorted, roc);
            pitMomPctMap.set(vals[i][0], (pos / runningMomSorted.length) * 100);
          }
        }
        const momSorted = [...runningMomSorted]; // full sorted for today

        indicatorMaps.push({ ...c, map, sorted, count: sorted.length, momMap, momSorted, pitPctMap, pitMomPctMap });
      }

      if (indicatorMaps.length < 3) {
        res.end(JSON.stringify({ error: 'Not enough indicator data' }));
        return;
      }

      // Target data for forward returns
      const tgtData = store.yahoo[targetKey] || store.fred[targetKey] || [];
      const tgtMap = new Map(tgtData.map(v => [v[0], v[1]]));
      const tgtDates = tgtData.map(v => v[0]);

      // Helper: find percentile of value in sorted array
      function pctRank(sorted, val) {
        if (!sorted || sorted.length === 0) return 50;
        let lo = 0, hi = sorted.length;
        while (lo < hi) {
          const mid = (lo + hi) >> 1;
          if (sorted[mid] < val) lo = mid + 1; else hi = mid;
        }
        return lo / sorted.length * 100;
      }

      // Helper: find closest date on or before target in sorted dates array
      function findClosestDate(dates, target) {
        let lo = 0, hi = dates.length - 1;
        while (lo <= hi) {
          const mid = (lo + hi) >> 1;
          if (dates[mid] <= target) lo = mid + 1; else hi = mid - 1;
        }
        return hi >= 0 ? dates[hi] : null;
      }

      // Weights: level vs trend
      const W_LEVEL = 0.6;
      const W_TREND = 0.4;

      // Compute today's percentile vectors (level + momentum)
      const todayPercentiles = [];
      const todayMomentum = [];
      for (const ind of indicatorMaps) {
        const vals = store[ind.src][ind.key];
        const latestVal = vals[vals.length - 1][1];
        const latestDate = vals[vals.length - 1][0];
        todayPercentiles.push(pctRank(ind.sorted, latestVal));
        // Get today's momentum percentile
        const momVal = ind.momMap.get(latestDate);
        todayMomentum.push(momVal != null ? pctRank(ind.momSorted, momVal) : null);
      }

      // Collect all unique dates from the indicator with the most data
      const allDatesSet = new Set();
      for (const ind of indicatorMaps) {
        for (const [d] of ind.map) allDatesSet.add(d);
      }
      const allDates = [...allDatesSet].sort();

      // Sample every 5 trading days, skip last 30 days (too recent)
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - 30);
      const cutoffStr = cutoff.toISOString().split('T')[0];
      const candidates = [];
      for (let i = 0; i < allDates.length; i += 5) {
        if (allDates[i] > cutoffStr) break;
        candidates.push(allDates[i]);
      }

      // Score each candidate date
      const results = [];
      const MIN_INDICATORS = 4;

      for (const date of candidates) {
        const datePcts = [];
        const dateMom = [];
        const matchedIndicators = [];
        let validCount = 0;

        for (let j = 0; j < indicatorMaps.length; j++) {
          const ind = indicatorMaps[j];
          const val = ind.map.get(date);
          if (val != null) {
            // Use POINT-IN-TIME percentile (no look-ahead bias)
            const lvl = ind.pitPctMap.get(date);
            if (lvl == null) { datePcts.push(null); dateMom.push(null); continue; }
            const mom = ind.pitMomPctMap.get(date);
            datePcts.push(lvl);
            dateMom.push(mom != null ? mom : null);
            matchedIndicators.push({
              label: ind.label,
              pct: Math.round(lvl),
              trend: mom != null ? Math.round(mom) : null,
            });
            validCount++;
          } else {
            datePcts.push(null);
            dateMom.push(null);
          }
        }

        if (validCount < MIN_INDICATORS) continue;

        // Combined Euclidean distance: level + momentum
        let sumSq = 0;
        let matched = 0;
        for (let j = 0; j < todayPercentiles.length; j++) {
          if (datePcts[j] != null) {
            const levelDiff = todayPercentiles[j] - datePcts[j];
            sumSq += W_LEVEL * levelDiff * levelDiff;

            // Add trend distance if both sides have momentum data
            if (todayMomentum[j] != null && dateMom[j] != null) {
              const trendDiff = todayMomentum[j] - dateMom[j];
              sumSq += W_TREND * trendDiff * trendDiff;
            }
            matched++;
          }
        }
        // Require at least 50% of selected indicators to match
        const coverageRatio = matched / indicatorMaps.length;
        if (coverageRatio < 0.5) continue;

        // Normalize: sqrt(avgSquaredDiff) with linear coverage penalty
        // 6/12 → 2.0x,  9/12 → 1.33x,  12/12 → 1.0x
        const distance = Math.sqrt(sumSq / matched) * (indicatorMaps.length / matched);

        // Forward returns from target
        const tgtValNow = tgtMap.get(date);
        if (!tgtValNow) continue;

        const fwd = {};
        for (const [period, days] of [['1m', 22], ['3m', 63], ['1y', 252]]) {
          const targetDate = new Date(date + 'T00:00:00Z');
          targetDate.setUTCDate(targetDate.getUTCDate() + days);
          const targetStr = targetDate.toISOString().split('T')[0];
          const closeDate = findClosestDate(tgtDates, targetStr);
          if (closeDate) {
            const futVal = tgtMap.get(closeDate);
            if (futVal) fwd[period] = +((futVal - tgtValNow) / tgtValNow * 100).toFixed(2);
          }
        }

        results.push({
          date,
          distance: +distance.toFixed(2),
          matchedCount: validCount,
          totalIndicators: indicatorMaps.length,
          indicators: matchedIndicators,
          fwdReturn: fwd,
        });
      }

      // Sort by distance, dedup by month (keep earliest per month), take top 10
      results.sort((a, b) => a.distance - b.distance);
      const seenMonths = new Set();
      const deduped = [];
      for (const r of results) {
        const ym = r.date.slice(0, 7); // "YYYY-MM"
        if (!seenMonths.has(ym)) {
          seenMonths.add(ym);
          deduped.push(r);
        }
        if (deduped.length >= 10) break;
      }
      const top = deduped;

      // Compute average forward returns
      const avgReturn = { '1m': 0, '3m': 0, '1y': 0 };
      const avgCount = { '1m': 0, '3m': 0, '1y': 0 };
      for (const r of top) {
        for (const p of ['1m', '3m', '1y']) {
          if (r.fwdReturn[p] != null) {
            avgReturn[p] += r.fwdReturn[p];
            avgCount[p]++;
          }
        }
      }
      for (const p of ['1m', '3m', '1y']) {
        avgReturn[p] = avgCount[p] > 0 ? +(avgReturn[p] / avgCount[p]).toFixed(2) : null;
      }

      // Current percentiles for display
      const currentIndicators = indicatorMaps.map((ind, i) => ({
        label: ind.label,
        pct: Math.round(todayPercentiles[i]),
        trend: todayMomentum[i] != null ? Math.round(todayMomentum[i]) : null,
      }));

      res.end(JSON.stringify({
        availableFactors: ALL_COMPARE_KEYS.map(c => ({
          key: c.key, label: c.label, group: c.group,
          hasData: !!(store[c.src]?.[c.key]?.length >= 20),
          points: store[c.src]?.[c.key]?.length || 0,
        })),
        availableTargets: AVAILABLE_TARGETS.map(t => ({
          ...t, hasData: !!(store.yahoo[t.key]?.length > 100 || store.fred[t.key]?.length > 100),
        })),
        target: targetInfo,
        selectedKeys: COMPARE_KEYS.map(c => c.key),
        today: currentIndicators,
        matches: top,
        avgReturn,
        candidatesScanned: candidates.length,
        indicatorsUsed: indicatorMaps.length,
        trendPeriod: trendParam,
      }));
    } catch (e) {
      console.error('Backtrack error:', e);
      res.writeHead(500);
      res.end(JSON.stringify({ error: e.message }));
    }
  } else if (p === '/health') {
    res.end(JSON.stringify({ status:'ok', fred: Object.keys(store.fred).length, yahoo: Object.keys(store.yahoo).length }));
  } else if (p === '/api/status') {
    res.end(JSON.stringify(dlStatus));
  } else if (p === '/api/flows' || p === '/api/flows/v3') {
    try {
      const { runProductionFlows } = require('./lib/flow_wrappers');
      const flows = runProductionFlows(store);
      
      const isValid = validateFlowSnapshotV3 ? validateFlowSnapshotV3(flows) : false;
      if (!isValid) {
        console.error('Flow engine generated invalid snapshot schema:', validateFlowSnapshotV3 ? validateFlowSnapshotV3.errors : 'V3 schema missing');
        res.writeHead(500);
        res.end(JSON.stringify({ status: 'error', error: 'Internal API Schema Violation (V3)' }));
        return;
      }
      
      res.end(JSON.stringify(flows));
    } catch (e) {
      console.error('Flow engine error:', e);
      res.end(JSON.stringify({ status: 'error', error: e.message }));
    }
  } else if (p === '/api/flows/v2') {
    // V2 is frozen, returns 410 Gone or mock
    res.writeHead(410);
    res.end(JSON.stringify({ error: 'V2 engine is frozen and no longer supported.' }));
  } else if (p === '/api/schema/flow_v1' || p === '/api/schema/flow_v2') {
    res.end(flowApiSchemaStr);
  } else if (p === '/api/schema/flow_v3') {
    res.end(flowApiSchemaV3Str);
  } else if (p === '/api/data') {
    res.end(JSON.stringify(buildDashboard()));
  } else if (p === '/api/refresh') {
    if (!requireLocalAdmin(req, res)) return;
    if (dlStatus.state === 'downloading' || dlStatus.state === 'updating') {
      res.end(JSON.stringify({ status: 'busy', message: dlStatus.msg }));
    } else {
      res.end(JSON.stringify({ status:'started' }));
      smartUpdate(true).catch(e => console.error('Update error:', e));
    }
  } else if (p === '/api/redownload') {
    if (!requireLocalAdmin(req, res)) return;
    if (dlStatus.state === 'downloading') {
      res.end(JSON.stringify({ status:'busy' }));
    } else {
      res.end(JSON.stringify({ status:'started' }));
      store.fred = {}; store.yahoo = {};
      downloadAll().catch(e => console.error('Download error:', e));
    }
  } else if (p === '/api/update-bdi') {
    if (!requireLocalAdmin(req, res)) return;
    let body = '';
    req.on('data', d => body += d);
    req.on('end', () => {
      try {
        const newVals = JSON.parse(body); // [[date, value], ...]
        if (!Array.isArray(newVals) || newVals.length === 0) throw new Error('Empty data');
        const existing = store.valuation['BDI'] || [];
        const merged = new Map(existing.map(v => [v[0], v[1]]));
        for (const [d, v] of newVals) merged.set(d, v);
        const filtered = [...merged.entries()]
          .sort((a, b) => a[0].localeCompare(b[0]))
          .filter(([d]) => d >= VALUATION_CUTOFF);
        store.valuation['BDI'] = filtered;
        fs.writeFileSync(path.join(VALUATION_DIR, 'BDI.json'), JSON.stringify({
          id: 'BDI', source: 'investing.com',
          updated: new Date().toISOString(), values: filtered
        }));
        const last = filtered[filtered.length - 1];
        res.end(JSON.stringify({ ok: true, points: filtered.length, last }));
      } catch(e) { res.writeHead(400); res.end(JSON.stringify({ error: e.message })); }
    });
   } else if (p === '/api/releases') {
    // ── Economic Release Dates (cached daily) ──
    if (!store._releases || Date.now() - (store._releasesTs || 0) > 86400000) {
      const RELEASE_CONFIG = [
        { id: 10,  label: 'CPI',  tier: 'S', color: '#dc3545', url: 'https://www.bls.gov/cpi/' },
        { id: 50,  label: 'NFP',  tier: 'S', color: '#dc3545', url: 'https://www.bls.gov/news.release/empsit.nr0.htm' },
        { id: 54,  label: 'PCE',  tier: 'A', color: '#f59e0b', url: 'https://www.bea.gov/data/personal-consumption-expenditures-price-index' },
        { id: 53,  label: 'GDP',  tier: 'A', color: '#f59e0b', url: 'https://www.bea.gov/data/gdp/gross-domestic-product' },
        { id: 46,  label: 'PPI',  tier: 'B', color: '#3b82f6', url: 'https://www.bls.gov/ppi/' },
      ];
      // FOMC decision dates — hardcoded from Fed published calendar
      const FOMC_DATES = [
        '2021-01-27','2021-03-17','2021-04-28','2021-06-16','2021-07-28','2021-09-22','2021-11-03','2021-12-15',
        '2022-01-26','2022-03-16','2022-05-04','2022-06-15','2022-07-27','2022-09-21','2022-11-02','2022-12-14',
        '2023-02-01','2023-03-22','2023-05-03','2023-06-14','2023-07-26','2023-09-20','2023-11-01','2023-12-13',
        '2024-01-31','2024-03-20','2024-05-01','2024-06-12','2024-07-31','2024-09-18','2024-11-07','2024-12-18',
        '2025-01-29','2025-03-19','2025-05-07','2025-06-18','2025-07-30','2025-09-17','2025-10-29','2025-12-17',
        '2026-01-28','2026-03-18','2026-04-29','2026-06-17','2026-07-29','2026-09-16','2026-11-04','2026-12-16',
      ];
      const apiKey = process.env.FRED_API_KEY;
      const allDates = [];
      for (const rel of RELEASE_CONFIG) {
        try {
          const url = `https://api.stlouisfed.org/fred/release/dates?release_id=${rel.id}&api_key=${apiKey}&file_type=json&sort_order=desc&limit=60`;
          const resp = await new Promise((resolve, reject) => {
            https.get(url, r => {
              let body = '';
              r.on('data', c => body += c);
              r.on('end', () => resolve(body));
              r.on('error', reject);
            }).on('error', reject);
          });
          const parsed = JSON.parse(resp);
          if (parsed.release_dates) {
            for (const rd of parsed.release_dates) {
              allDates.push({ date: rd.date, label: rel.label, tier: rel.tier, color: rel.color, url: rel.url });
            }
          }
        } catch(e) { console.log(`  ⚠️ Release ${rel.label} fetch failed: ${e.message}`); }
        await sleep(200);
      }
      // Add FOMC meeting dates
      for (const fd of FOMC_DATES) {
        allDates.push({ date: fd, label: 'FOMC', tier: 'S', color: '#dc3545', url: 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm' });
      }
      store._releases = allDates;
      store._releasesTs = Date.now();
    }
    res.end(JSON.stringify({ releases: store._releases || [] }));
  } else if (p === '/api/world') {
    // ── World Overview API ──
    const calcChange = (vals, daysBack) => {
      if (!vals || vals.length < 2) return null;
      const last = vals[vals.length - 1][1];
      const cutoff = new Date();
      cutoff.setDate(cutoff.getDate() - daysBack);
      const cutStr = cutoff.toISOString().slice(0, 10);
      const prev = [...vals].reverse().find(([d]) => d <= cutStr);
      if (!prev || prev[1] === 0) return null;
      return +((last - prev[1]) / prev[1] * 100).toFixed(2);
    };
    const lastVal = (vals) => vals && vals.length ? vals[vals.length - 1][1] : null;
    const lastDate = (vals) => vals && vals.length ? vals[vals.length - 1][0] : null;

    const buildItem = (label, key, vals) => ({
      label, key,
      value: lastVal(vals),
      date: lastDate(vals),
      change1d: calcChange(vals, 1),
      change1w: calcChange(vals, 7),
      change1m: calcChange(vals, 30),
      change1q: calcChange(vals, 90),
    });

    // Pulse items
    const pulseConfig = [
      { label: 'S&P 500',    key: 'sp500',   yahoo: '^GSPC' },
      { label: 'STOXX 600',  key: 'stoxx',   yahoo: '^STOXX' },
      { label: 'Nikkei 225', key: 'nikkei',  yahoo: '^N225' },
      { label: '上证 SSE',    key: 'sse',     yahoo: '000001.SS' },
      { label: 'DXY 美元',    key: 'dxy',     yahoo: 'DX-Y.NYB' },
      { label: '10Y Yield',  key: 'us10y',   fred: 'DGS10' },
      { label: 'Oil WTI',    key: 'oil',     yahoo: 'CL=F' },
      { label: 'Gold',       key: 'gold',    yahoo: 'GC=F' },
      { label: 'VIX',        key: 'vix',     yahoo: '^VIX' },
    ];
    const pulse = pulseConfig.map(pc => {
      const vals = pc.yahoo ? store.yahoo[pc.yahoo] : store.fred[pc.fred];
      return buildItem(pc.label, pc.key, vals);
    });

    // Region status
    const regionStatus = (indicators) => {
      const maxAbs = Math.max(...indicators.map(i => Math.abs(i.change1d || 0)));
      if (maxAbs > 3) return 'red';
      if (maxAbs > 1.5) return 'yellow';
      return 'green';
    };
    const mkInd = (label, key) => {
      const p = pulse.find(x => x.key === key);
      return { label, value: p?.value, change1d: p?.change1d, change1w: p?.change1w, change1m: p?.change1m, change1q: p?.change1q };
    };
    const soxxVals = store.yahoo['SOXX'];
    const soxxInd = buildItem('SOXX 半导体', 'soxx', soxxVals);
    const jpyVals = store.yahoo['JPY=X'];
    const jpyInd = buildItem('USD/JPY', 'jpyx', jpyVals);
    const copperInd = buildItem('Copper 铜', 'copper', store.yahoo['HG=F']);
    const bdiVals = (store.valuation['BDI'] || []);
    const bdiInd = buildItem('BDI', 'bdi', bdiVals);

    const regions = [
      { name: '美国', emoji: '🇺🇸', link: '/', indicators: [mkInd('S&P 500','sp500'), mkInd('DXY','dxy'), mkInd('10Y','us10y')] },
      { name: '中国', emoji: '🇨🇳', link: null, indicators: [mkInd('上证','sse'), copperInd] },
      { name: '欧洲', emoji: '🇪🇺', link: null, indicators: [mkInd('STOXX 600','stoxx')] },
      { name: '日本', emoji: '🇯🇵', link: null, indicators: [mkInd('Nikkei','nikkei'), jpyInd] },
      { name: '中东', emoji: '🛢️', link: null, indicators: [mkInd('Oil','oil'), mkInd('Gold','gold'), bdiInd] },
      { name: '台韩', emoji: '🔬', link: null, indicators: [soxxInd] },
    ];
    regions.forEach(r => { r.status = regionStatus(r.indicators); });

    // Hotspots (manual — stored in valuation or default calm)
    const hotspotData = store.valuation['HOTSPOTS'] || {};
    const hotspots = [
      { name: 'Hormuz',  nameCn: '霍尔木兹', status: hotspotData['hormuz']  || 'calm' },
      { name: '俄乌',     nameCn: '俄乌',     status: hotspotData['ukraine'] || 'calm' },
      { name: '台海',     nameCn: '台湾海峡',  status: hotspotData['taiwan']  || 'calm' },
      { name: '红海',     nameCn: '红海',     status: hotspotData['redsea']  || 'calm' },
      { name: '朝鲜半岛', nameCn: '朝鲜半岛',  status: hotspotData['korea']   || 'calm' },
    ];

    res.end(JSON.stringify({ updated: new Date().toISOString(), pulse, regions, hotspots }));
  } else if (p === '/api/news') {
    const news = loadNewsFromDisk();
    res.end(JSON.stringify(news));
  } else if (p === '/api/news/refresh') {
    if (!requireLocalAdmin(req, res)) return;
    res.end(JSON.stringify({ status: 'started' }));
    fetchAllNews().catch(e => console.error('[News] Refresh error:', e));
  } else {
    // Serve HTML pages
    const fs = require('fs');
    let htmlFile = 'index.html';  // default: US dashboard
    if (p === '/world' || p === '/world.html') htmlFile = 'world.html';
    if (p === '/flow' || p === '/flow.html') htmlFile = 'flow.html';
    const htmlPath = require('path').join(__dirname, htmlFile);
    try {
      const html = fs.readFileSync(htmlPath);
      res.writeHead(200, { 
        'Content-Type': 'text/html; charset=utf-8',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      });
      res.end(html);
    } catch(e) {
      res.writeHead(404);
      res.end(JSON.stringify({ error: htmlFile + ' not found' }));
    }
  }
});

// ============================================
// STARTUP
// ============================================
server.listen(PORT, '127.0.0.1', async () => {
  console.log('');
  console.log('  ╔══════════════════════════════════════════╗');
  console.log('  ║  🔭 宏观观察器 — Data Server              ║');
  console.log('  ╠══════════════════════════════════════════╣');
  console.log(`  ║  🌐 http://localhost:${PORT}               ║`);
  console.log('  ║  GET /api/data      Dashboard data       ║');
  console.log('  ║  GET /api/news      Macro news feed      ║');
  console.log('  ║  GET /api/refresh   Incremental update   ║');
  console.log('  ║  GET /api/status    Download progress    ║');
  console.log('  ║  GET /api/redownload Full re-download    ║');
  console.log('  ╚══════════════════════════════════════════╝');
  console.log('');

  ensureDir(DATA_DIR); ensureDir(FRED_DIR); ensureDir(YAHOO_DIR);
  ensureDir(CSV_DIR); ensureDir(CSV_FRED); ensureDir(CSV_YAHOO);

  const loaded = loadAllFromDisk();
  const fredCount = Object.keys(store.fred).length;
  const yahooCount = Object.keys(store.yahoo).length;
  const yahooNeeded = allYahooSymbols().length;

  if (loaded > 0) {
    console.log(`  📂 Loaded ${loaded} cached files (FRED: ${fredCount}, Yahoo: ${yahooCount})`);
    // Regenerate CSVs from cached data
    let csvCount = 0;
    for (const [id, vals] of Object.entries(store.fred)) { saveCsv('fred', id, vals); csvCount++; }
    for (const [sym, vals] of Object.entries(store.yahoo)) { saveCsv('yahoo', sym, vals); csvCount++; }
    console.log(`  📄 Exported ${csvCount} CSV files to csv/ folder`);
    dlStatus = { state:'ready', progress:loaded, total:loaded, msg:'Loaded from cache' };
  }

  // Download anything that's missing
  const missingFred = FRED_SERIES_IDS.filter(id => !store.fred[id]);
  const missingYahoo = allYahooSymbols().filter(s => !store.yahoo[s]);

  if (missingFred.length > 0 || missingYahoo.length > 0) {
    console.log(`  📥 Missing data: FRED ${missingFred.length}, Yahoo ${missingYahoo.length} — downloading...`);
    await downloadAll(); // downloadAll already skips series that exist in store
  } else if (loaded === 0) {
    console.log('  📥 No cached data found, starting full download...');
    await downloadAll();
  } else {
    console.log('  ✅ All data present, ready!');
  }

  // Auto-refresh: everything once per day
  const DAY = 24 * 60 * 60 * 1000;

  console.log(`\n  ⏰ FRED + Yahoo: once per day\n`);

  // Initial update: 60s after startup
  setTimeout(() => {
    smartUpdate(true).catch(e => console.error('Update error:', e));
  }, 60000);

  // Daily refresh (FRED + Yahoo together)
  setInterval(() => {
    smartUpdate(true).catch(e => console.error('Update error:', e));
  }, DAY);

  // Hourly news refresh (GDELT + Fed RSS)
  const HOUR = 60 * 60 * 1000;
  setInterval(() => {
    fetchAllNews().catch(e => console.error('[News] Hourly refresh error:', e));
  }, HOUR);

  // Initial news fetch: 10s after startup (fast, don't block)
  setTimeout(() => {
    fetchAllNews().catch(e => console.error('[News] Initial fetch error:', e));
  }, 10000);
});
