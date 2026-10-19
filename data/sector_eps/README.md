# S&P 500 板块 EPS（季度）数据说明

## 来源（免费、官方）
S&P Dow Jones Indices 官方文件 `sp-500-eps-est.xlsx`，工作表 `SECTOR EPS`：
<https://www.spglobal.com/spdji/en/documents/additional-material/sp-500-eps-est.xlsx>

覆盖 11 个 GICS 板块 + S&P 500 整体，**两种口径**，2008Q1 起按季度：
- `operating`：经营性 EPS（S&P 口径的 non-GAAP）
- `as_reported`：GAAP 报告 EPS

## 当前数据的真实状态（务必阅读）
- 官方直链会拦截脚本（HTTP 403）。本仓库使用的是 Wayback 存档 `20260527232437`，
  文件自身标注 **数据截至 2026-01-29**，SHA-256 `2fed7a13e117d077e061c4b5a1f8ddd0a5f3b768e737d9688a857888a5e3dfd6`
  （原文件：`source/sp-500-eps-est_wayback_20260527232437.xlsx`）。
- 因此最新**实际**季度：`operating` 到 **2025Q2**，`as_reported` 到 **2025Q3**。
  更新的季度尚未收录——**不要把预估当实际**。文件中 2025E Q3–2026E Q4 为 S&P 当时的预估，
  CSV 中标记 `status=estimate`，看板表格不显示。
- `operating` 比 `as_reported` 晚确认，所以两者截止季度不同。

## 口径提醒
板块 EPS 是“该板块指数口径”（板块盈利 ÷ 板块指数除数），**各板块水平不可相加，也不等于 S&P 500 整体**
（如 2009Q1 各板块之和 24.41 ≠ 整体 10.11）。适合看趋势、同比、与板块指数价格配合算 P/E；
不适合横向比较各板块的绝对 EPS 数值。

## 校验
- 内部一致性（`validate_sector_eps.py`）：12 个序列 × 17 个完整年度共 204 格，四个季度之和与表内年度 EPS
  最大差 0.02（舍入），两种口径均通过。
- 与 S&P 500 整体公开头条数字抽查一致（如 2008 报告 EPS 14.88、2009 经营 EPS 56.86）——此项为人工记忆比对，**未做自动化独立来源核验**。
- 曾尝试用 multpl.com 对照，**已作废**：其数据为通胀调整后的实际美元，与名义 EPS 不可比。
- Damodaran `histimpl.xls` 的 S&P 500 年度盈利仅作粗略参照：其口径逐年混用，不构成验证。

## 如何更新到最新季度
1. 用浏览器下载最新文件（上面直链，免费）。
2. `python3 scripts/sector_eps/build_sector_eps.py <下载的xlsx> data/sector_eps`
3. `python3 scripts/sector_eps/validate_sector_eps.py <下载的xlsx> data/sector_eps`
4. 重启服务（`launchctl kickstart -k gui/$(id -u)/com.macro-observer.dashboard`），页面 `/` 的“板块 EPS”卡片自动更新。

## 文件
- `sector_eps_quarterly.csv`：长表（index, sector, basis, period, period_end, eps, status），含 S&P 400/600/1500 板块
- `sector_eps_meta.json`：来源、文件日期、各口径最新实际季度
- `validation_annual_vs_quarters.csv`：内部一致性明细
- 接口：`GET /api/sector-eps`（仅 S&P 500）
