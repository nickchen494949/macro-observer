# 动量选股研究 · 总报告

**日期**：2026-10-29　**研究期间**：2009-01 至 2026-09（月度调仓）　**作者**：Antigravity（AI 编码助手），供用户与外部审计使用

> [!IMPORTANT]
> **一句话结论**：在标普 500（以及扩到纳斯达克 100）里，我们测了近百种做法。没有任何一种方法能**稳定地**跑赢指数，扣除多次尝试的运气以后，也没有任何因子或因子组合有统计上可信的预测力。唯一的"高收益"来自**每月只买 1 只动量最强的股票**：全期年化约 37–40%，但前 10 年只有约 19%，最大回撤 −69% 到 −73%，收益集中在 NVDA、WDC、SNDK 等少数几只股票上，而且最近几年的那段历史我们已经反复看过。**年化 50% 以上且能持续，没有找到证据。**

---

## 0. 怎么审核（GitHub 链接）

所有链接都固定在具体的提交上，内容不会再变。

| 仓库 | 内容 | 链接 |
|---|---|---|
| **私有仓库**（完整，含原始价格数据；需要授权访问） | 全部代码、数据、结果、日志 | [momentum-sector-x-stock @ e93da7c](https://github.com/nickchen494949/momentum-sector-x-stock/tree/e93da7c) |
| **公开仓库**（不含原始供应商数据，其余相同） | 同上，减去 `data/raw*` 等原始数据 | [macro-observer / research/sector_stock_momentum @ 432c853](https://github.com/nickchen494949/macro-observer/tree/432c853/research/sector_stock_momentum) |

**审计入口**：
- [`AUDIT_INDEX.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/AUDIT_INDEX.md)：流水线 → 脚本 → 输入 → 输出；测试；冻结规则；提交时间线。
- [`MANIFEST.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/MANIFEST.csv)：6,295 个文件的大小与 sha256，用来核对文件是否被改过。
- [`README.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/README.md)：分节的详细报告（第 1–15 节）。

**"先写规则、后看结果"的证据**：每个规则文件都在跑结果之前单独提交，可以按时间顺序核对。

| 规则 | 冻结提交 | 结果提交 |
|---|---|---|
| 主策略 [`FROZEN_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/FROZEN_SPEC.md) | [fbc4c51](https://github.com/nickchen494949/momentum-sector-x-stock/commit/fbc4c51) | [3570fd1](https://github.com/nickchen494949/momentum-sector-x-stock/commit/3570fd1) |
| 机器学习 [`ML_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/ML_SPEC.md) | [0235fc3](https://github.com/nickchen494949/momentum-sector-x-stock/commit/0235fc3)；开发期选择 [eb9380a](https://github.com/nickchen494949/momentum-sector-x-stock/commit/eb9380a) | [f114c1b](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f114c1b) |
| 因子体检 [`FACTOR_SCREEN_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/FACTOR_SCREEN_SPEC.md) | [3916ef0](https://github.com/nickchen494949/momentum-sector-x-stock/commit/3916ef0) | [8066f18](https://github.com/nickchen494949/momentum-sector-x-stock/commit/8066f18) |
| 因子组合体检 [`FACTOR_COMBO_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/FACTOR_COMBO_SPEC.md) | [78c1211](https://github.com/nickchen494949/momentum-sector-x-stock/commit/78c1211) | [60f4efe](https://github.com/nickchen494949/momentum-sector-x-stock/commit/60f4efe) |
| 找牛股三条线 [`WINNERS_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/WINNERS_SPEC.md) | [f993bd7](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f993bd7)、[285b8b4](https://github.com/nickchen494949/momentum-sector-x-stock/commit/285b8b4)、[ae612d5](https://github.com/nickchen494949/momentum-sector-x-stock/commit/ae612d5) | 候选冻结 [f2a1e11](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f2a1e11)；结果 [e93da7c](https://github.com/nickchen494949/momentum-sector-x-stock/commit/e93da7c) |

**一键复现**：`./run_final.sh`（主回测与测试，约 6 分钟）；`./run_postaudit2.sh`（全链条，约 10 分钟）。重新下载数据需要在 `.env` 里放 Tiingo 和 Nasdaq Data Link 的免费 API 密钥（不在仓库中）。

---

## 1. 数据

| 项目 | 来源 | 说明 |
|---|---|---|
| 标普 500 历史成分（时点） | fja05680/sp500 + 维基百科变更表 | 2008 年以来每个月末的真实成分，含后来退市的股票 |
| 纳斯达克 100 历史成分 | jmccarrell/n100tickers（MIT 许可） | 2007 年起，按指数生效日记录 |
| 股价 | Yahoo（Python，限速）→ Tiingo → Nasdaq WIKI → 免费档案（QSTK、OptionTradingTips、BNSF） | 每个价格都标了来源；改名和代码重用逐条核对身份 |
| 基本面 | SEC 财报数据集（FSDS，10-K/10-Q），时点版 | 每个数字只在自己的披露日 + 1 天之后才用；EPS 和股数统一到同一拆股口径 |
| 财报日期 | SEC 8-K（item 2.02） | 802 家公司、61,645 次财报发布 |
| 中小盘（考试用） | WIKI 整库（3,199 只，含退市，到 2018-03）+ Yahoo 当前上市股票（3,830 只，下载中） | 详见第 9 节 |

**数据缺口**：标普成分的"股票 × 月份"中有 0.62%（107,065 个里缺 659 个，38 个代码）没有可用价格，逐个列在 [`results/gap_ledger.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/gap_ledger.csv)。纳斯达克 100 新增部分缺 0.67%（[`results/ndx/gap_ndx.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/ndx/gap_ndx.csv)）。

**防止偷看未来的测试**（最新一次运行全部通过）：截断测试（假装"今天是过去某天"，那天之前的选股必须完全不变）、可重复性测试（换随机种子，结果完全相同）、基本面时点测试、财报日期身份检查。

---

## 2. 主策略：最强行业里动量最强的股票（规则在跑之前冻结）

**规则**：每月末，按行业内成分股 12−1 动量的平均值排出最强行业，买这个行业里动量最高的 1 只，持有 1 个月；每边成本 10 个基点。样本内 2009-01 至 2021-05（149 个月），样本外 2021-06 至 2026-09（64 个月）。

| 策略（扣成本；年化 / Sharpe / 月末最大回撤） | 样本内 | 样本外 | 全期 |
|---|---|---|---|
| **主策略** | 12.1% / 0.53 / −37% | 71.3% / 1.10 / −51% | 27.4% / 0.74 / −51% |
| 不选行业：全市场动量第 1 名 | 18.2% / 0.61 / −69% | 91.4% / 1.23 / −47% | 36.6% / 0.83 / −69% |
| 全市场动量前 10 名 | 9.9% / 0.53 / −34% | 29.8% / 0.82 / −25% | 15.5% / 0.63 / −34% |
| 样本内选出的最优参数（6−1 动量、1 行业、3 只） | 24.3% / 0.99 / −32% | 33.2% / 0.74 / −43% | 26.9% / 0.84 / −43% |
| SPY | 15.4% / 1.02 / −19% | 13.4% / 0.67 / −24% | 14.8% / 0.91 / −24% |

**结论**：
- 主策略样本内**跑输** SPY；样本外的高收益靠少数几个月（最好 5 个月占全期对数收益的 44%），主要赢家是 NVDA、DVN、SNDK、NFLX、WDC。
- "先选行业"没有带来增量，不选行业的版本反而更高。
- 96 组参数的样本内排名和样本外排名负相关（−0.25），说明调参没有用。
- 主策略日度最大回撤 −56%。

详见 [README 第 2–3 节](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/README.md)，数据在 [`results/summary.json`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/summary.json)、[`results/monthly_SPEC.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/monthly_SPEC.csv)。

---

## 3. 在主策略之后又测了什么

以下都是在同一段历史上另外测的想法，数据挖掘的风险逐次累积。

| # | 想法 | 结果（扣成本） | 结论 |
|---|---|---|---|
| 3.1 | EPS 增长前 10 名 → 动量最高（2012–2025） | 原版 3.1%；稳健版（EPS 变化 ÷ 股价）21.9%；纯动量第 1 名 35.4%；SPY 14.9% | 不如纯动量 |
| 3.2 | 不买跌破 200 日均线的股票（2010–2026） | 纯动量第 1 名 40.0% → 45.5%（回撤 −69% → −62%）；主策略 30.0% → 31.3%；EPS 策略反而变差 | 对纯动量小幅有用，主要在 2021 年以后 |
| 3.3 | 机器学习（25 个特征，Ridge / LightGBM 等，规则先冻结） | 开发期所有模型的预测力接近 0；考试期选中的模型 −15.5%（修复前 13.6%），SPY 21.7% | 失败 |
| 3.4 | EPS 增长 + 动量 + 利润率改善打分，全市场第 1 名（2012–2026） | 23.6% / 0.64 / −50% | 不如纯动量 |
| 3.5 | 动量前 30 → ROE > 20% → EPS 增长最高（2012–2026） | 12.5% / 0.42 / −65% | 差 |
| 3.6 | 只做科技股：动量第 1 名 / 三因子第 1 名（2010–2026） | 39.9% / 0.90 / −54%；43.5% / 0.99 / −39%（XLK 20.0% / 0.99 / −31%） | 前 11 年和 XLK 一样，回撤大得多；带后见之明 |
| 3.7 | "爆发股"因子组合（第二轮外部审计后修正） | 科技前 5：2015–2022 13.2%（XLK 16.3%），全期 23.7% / Sharpe 0.80（XLK 22.5% / 1.00） | **撤回**，见第 4 节 |
| 3.8 | 财报公告收益因子 | 开发期抓大涨和抓大跌一样多 | 失败 |
| 3.9 | 扩到 标普 500 + 纳斯达克 100 | 纯动量第 1 名 36.6% → 24.9%；主策略 27.4% → 26.0%；四因子科技前 5 23.0% → 24.7% | 扩池救不回来 |

---

## 4. 两轮审计，以及审计改掉了什么

| 轮次 | 审计方 | 主要发现 | 处理 |
|---|---|---|---|
| 第一轮 | 内部独立子代理 + 外部（ChatGPT） | 代码重用导致价格属于别的公司（EP、CPWR、DD、CB、JCI、CCE、PARA）；行业用了现在占用代码的公司；月中退市处理；排名平手时结果随机；基本面字段时点 | 全部修复，规则先冻结再重跑（[`audit/INTERNAL_AUDIT_2026-10-28.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/audit/INTERNAL_AUDIT_2026-10-28.md)） |
| 第二轮 | 外部（ChatGPT），对象是提交 [7f24e9b](https://github.com/nickchen494949/momentum-sector-x-stock/commit/7f24e9b) | 小市值因子用了未来拆股；股数没有按自己的披露日用；LSI 的价格是另一家公司；6 个月标签漏掉被收购的股票；回撤只算月末；"2023–2026 是真正的检验"不成立 | 全部修复；我们修复时另外查出同日多财季取季随机、AGN 和 CB 的价格与基本面不是同一家公司，并新增财报日期身份检查（[`audit/EXTERNAL_AUDIT_2_2026-10-29.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/audit/EXTERNAL_AUDIT_2_2026-10-29.md)） |

**第二轮审计对结论的影响**：
- 主策略和纯动量的选股 **100% 不变**。
- "爆发股"策略从 34.9% / Sharpe 1.14 掉到 23.7% / 0.80，开发期跑输 XLK，**结论撤回**。
- 机器学习仍然失败。

修复前的结果表另存在 [`audit/before_tiefix/`](https://github.com/nickchen494949/momentum-sector-x-stock/tree/e93da7c/audit/before_tiefix)。

---

## 5. 因子体检：47 个因子，单个看（规则先冻结）

- **范围**：标普 500，目标是下个月收益，只用 2010-01 至 2019-11 判定。
- **方法**：逐个算 IC，并用 Romano–Wolf 扣除多次尝试的运气；稳定性选择（反复抽样跑 LASSO）；LightGBM 置换重要性。
- **新加的因子**：销售库存比及其变化、存货增速 − 营收增速、资产周转、营收 ÷ 市值、毛利 ÷ 总资产、ROE、应计利润、负债率、增发 / 回购、股息率、经营现金流 ÷ 市值、资产增速、账面市值比。

**结果：0 个有用，33 个不确定，14 个没用。** 最接近显著的是营收增速加快（校正后 p = 0.37）、上月收益反转（0.54）、研发强度（0.56）、ROE（0.67）。12−1 动量的 IC 只有 0.009（p = 1.00）。
数据：[`results/factor_screen/screen_table.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/factor_screen/screen_table.csv)。

## 6. 因子组合体检（规则先冻结）

| 家族 | 结果（前 10% 扣成本年化 − 等权年化） | 判定 |
|---|---|---|
| 8 个经典组合（价值+动量、质量+价值、动量+低波动、动量+盈利惊喜、GARP、动量+营收毛利加速、质量+动量+价值、动量+短期反转），2010–2019 | −3.7% 到 +1.1%；t 最高 2.0（校正后 p = 0.18） | 全部没用 |
| 47 个因子全给 Ridge / LASSO / LightGBM，2013–2019 样本外 | −2.7% 到 −0.6% | 全部没用 |
| 自动找交互：扫 2,162 对，用 2010–2015 挑前 10 对，2016–2019 检验 | 搜索期 t 值 3.0–4.4，检验期全部掉到 1.5 以下，2 对方向相反 | 9 对没用，1 对不确定 |

等权买入全部成分股在 2010–2019 年化 14.2%。数据：[`results/factor_combo/combo_table.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/factor_combo/combo_table.csv)。

---

## 7. 找牛股三条线（规则先冻结；标普 500 上的开发结果）

| 策略（扣成本；年化 / Sharpe / **日度**最大回撤） | 2010–2019 | 2020–2026.09 | 全期 |
|---|---|---|---|
| 纯动量第 1 名 | 19.5% / 0.64 / −73% | 77.0% / 1.16 / −56% | 40.0% / 0.88 / −73% |
| 动量前 5 名 + 崩盘过滤 | 16.0% / 0.80 / −27% | 29.1% / 0.77 / −39% | 21.1% / 0.74 / −39% |
| 暴涨分类模型前 5 名（2013 年起） | 16.4% / 0.63 / −43% | 14.8% / 0.45 / −54% | 15.6% / 0.52 / −54% |
| 暴涨分类模型前 1 名（2013 年起） | −22.0% / −0.27 / −92% | 2.2% / 0.31 / −78% | −10.9% / 0.06 / −95% |
| 动量前 5 名 + 200 日线空仓 | 13.5% / 0.80 / −29% | 10.2% / 0.38 / −39% | 12.2% / 0.57 / −39% |
| SPY | 13.4% / 1.03 / −19% | 15.2% / 0.76 / −34% | 14.2% / 0.90 / −34% |

全部 57 个策略（含基准）在 [`results/winners/summary.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/winners/summary.csv)。规律：**收益和回撤是捆在一起的。** 风控能把回撤从 −73% 压到 −25% 到 −40%，年化也跟着降到 10–20%。

---

## 8. 风险的真实面貌（第二轮审计要求补充）

以原来最好看的爆发股科技前 5 名为例（2012–2026.09）：

| | 年化 | 年化波动 | 月末最大回撤 | 日度最大回撤 | 最好 5 个月占总收益 |
|---|---|---|---|---|---|
| 科技前 5（波动倒数加权） | 23.0% | 27.5% | −40.7% | −45.2% | 38% |
| 科技第 1 名 | 28.6% | 48.3% | −65.4% | −67.0% | 51%（PLTR 32%、MU 30%） |
| XLK | 21.9% | 18.8% | −31.2% | −33.6% | 25% |

月末回撤会低估持有期间实际经历的亏损，所以报告同时给出日度回撤。数据：[`results/explosive/risk_report.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/results/explosive/risk_report.csv)。

---

## 9. 进行中：中小盘"真正的考试"

- **为什么要考**：上面所有结果用的都是被反复看过的标普数据。中小盘（标普 500 以外、成交够活跃的美股）在本研究里**从没用过**，是唯一干净的考场。
- **考什么**：按事先定的规则选出 3 个最终候选，在考试之前冻结（[f2a1e11](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f2a1e11)）：暴涨模型前 5 名（持有 1 个月）、暴涨模型前 5 名（持有 6 个月）、动量前 5 名 + 崩盘过滤；纯动量第 1 名作为基准一起考。
- **怎么考**：
  - 主考区间 2010-01 至 2018-02（WIKI 时代，含退市股票）；每月约 820–1,350 只股票合格。
  - 2018 年以后只作参考，因为那几年退市的股票缺数据，结果会偏高。
  - 中小盘里一律不用基本面，因为"有没有财报数据"本身就泄露了公司后来是否活下来（[`WINNERS_SPEC.md` 第 5b 节](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/WINNERS_SPEC.md)）。
- **状态**：Yahoo 数据大约在 2026-10-30 上午下完，之后**只运行一次**，结果补进本报告和 README 第 15 节。

---

## 10. 总结论

1. **没有找到稳定的超额收益来源。** 在标普 500 大盘股里，单个因子、经典组合、机器学习、自动找交互、风控叠加，统统没有通过事先写好的检验。
2. **唯一高收益的是"每月只买 1 只动量最强的股票"。** 全期年化 37–40%，但：
   - 前 10 年只有约 19%，和指数差不多；
   - 最大回撤 −69% 到 −73%；
   - 收益靠少数几只暴涨股（NVDA、WDC、SNDK、VST…）；
   - 2021 年以后那段历史我们已经反复看过，不是干净的样本外。
3. **"年化 50% 以上并且持续"没有证据。** 要接近这个数字，只能集中押 1 只股票，并承受七成左右的回撤。
4. **几条已被证据否定的说法**："先选行业能提高效果""EPS / ROE / 销售库存比等基本面能在大盘股里预测收益""机器学习能找出有用的因子组合""爆发股因子组合比 XLK 好"。
5. **还没有结论的**：中小盘考试（第 9 节）。

**如果要用**（这是建议，不是承诺）：
- 大部分资金放指数（SPY / XLK）。
- 动量只占小部分，用前 5 到 20 只、带崩盘过滤的版本，而不是只买 1 只。
- 规则从今天起冻结，用以后的真实数据来检验。

---

## 11. 局限

- 免费数据：0.62% 的成分股月份没有价格；部分人工行业分类没有逐个上网核实（见 [`data/sector_overrides.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/data/sector_overrides.csv)、[`data/ndx_sectors.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/e93da7c/data/ndx_sectors.csv)）。
- 外国公司（20-F / 40-F）没有 SEC 基本面。
- 成本只算每边 10 个基点，没有算冲击成本和税；单只小盘股的实际成本更高。
- 同一段历史被测了很多次，越往后的结果，数据挖掘的风险越大。报告里凡是"回顾性"的结果，都不能当作样本外证据。
- 外部审计员的复现脚本和证据包留在审计员的工作区，本仓库里没有。我们新查出的两处身份错误（AGN、CB）尚待外部复核。
