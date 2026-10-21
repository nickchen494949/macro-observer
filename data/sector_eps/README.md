# S&P 500 板块 EPS（季度）数据说明

## 来源（当前：Yardeni / LSEG I/B/E/S 经营性 EPS）
Yardeni Research「S&P 500 Sectors Quarterly Metrics」图 11（EPS），底层为 LSEG I/B/E/S：
<https://yardeni.com/charts/us-stock-market/stock-market-fundamentals/sp-500-quarterly-metrics>

- 原始文件：`source/Yardeni_Sector_Operating_EPS.xlsm`（工作表 `取值明细`），图表下载日 2026-10-19。
- 覆盖 11 个 GICS 板块，2010Q1–2026Q2，共 700 个数；房地产从 2016Q3 开始（之前无同口径数据，空缺不是 0）。
- **只有 operating（经营性）口径**；没有 GAAP 报告口径，也没有 S&P 500 整体行。

## 数据真实状态（务必阅读）
- 700 个数里 **689 个是从图表曲线读取的近似值**（`method=curve_approx`），只有 2026Q2 的 11 个是图上印刷值（`method=printed`）。
- `sens_2px` = 纵坐标偏移 2 像素时 EPS 的变化量，**不是误差上限**。
- 与旧版 S&P DJI 官方数据对比（2010Q1–2025Q2，643 个重叠值）：单季误差中位数 8%；多数板块水平相关 0.87–0.99，
  但医疗保健偏高约 19%、信息技术约 12%、房地产约 58%（**口径差异**，不是读图误差）；公用事业/材料/金融同比相关性很弱。
  审计脚本：`scratch/audit_yardeni.py`。
- 2026Q2 印刷值相对 2026Q1 曲线读数跳升明显（如能源 +136%、可选消费 +64%），可能是口径/坐标轴问题，未核实——解读该季变化时要谨慎。
- 板块 EPS 是“板块指数口径”，**各板块水平不可相加，也不可与 S&P DJI 口径互相比较或拼接**。适合看趋势/同比。

## 如何更新到最新季度
1. 打开 Yardeni 页面，把新季度数值记入 xlsm（或按同格式生成新文件）。
2. `python3 scripts/sector_eps/build_yardeni_eps.py <xlsm路径> data/sector_eps`
3. 刷新页面即可（`/api/sector-eps` 每次读取 CSV，无需重启）。

## 文件
- `sector_eps_quarterly.csv`：长表（index, sector, basis, period, period_end, eps, status, method, sens_2px）
- `sector_eps_meta.json`：来源、文件日期、最新季度、近似值计数
- `source/previous_sp_dji/`：被替换的旧版 S&P DJI 数据（含 S&P 400/600/1500、GAAP 口径）及其 README，保留备查
- 接口：`GET /api/sector-eps`
