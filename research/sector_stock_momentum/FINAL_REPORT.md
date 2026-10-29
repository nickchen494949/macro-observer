# 动量选股研究 · 总报告

**版本**：2026-10-29（第三轮外部审计修复后）　**研究期间**：2009-01 至 2026-09（月度调仓）　**作者**：Antigravity（AI 编码助手），供用户与外部审计使用

> [!IMPORTANT]
> **结论**：在这批数据、这些实现、这些区间和检验标准下，**尚未验证出稳定的超额收益**；"年化 50% 以上并且能持续"没有可靠证据。
>
> 唯一的高收益来自**每月只买 1 只全市场动量最强的股票**：
> - 2009 年起年化 36.6%，2010 年起 40.0%，两者的差别来自起始年份；
> - 2010–2019 只有 19.5%，截至 2025 年底的全期年化是 26.9%；
> - 2026 年 1–9 月这一段（WDC、SNDK）涨了 343%，把全期年化从 27% 拉到 37%；
> - 最大回撤约 −73%（日度）。
>
> 这本账已经由外部审计员用原始价格独立复算核对。但收益高度依赖抓到少数大赢家，最近几年的历史也被反复看过，不能外推到未来。
>
> **唯一一次在没用过的数据（中小盘，2010–2018）上只跑一次的考试里，同样的动量规则年化 −40.5%，所有冻结候选都大幅亏损**（第 9 节）。

---

## 0. 怎么审核

链接都固定在具体的提交上，内容不会再变。

| 仓库 | 内容 | 链接 |
|---|---|---|
| **私有仓库**（需要授权访问） | 全部代码、结果、日志，以及大部分原始价格（不含 WIKI 整库、中小盘 Yahoo 下载、SEC 缓存、成交量，原因见 `AUDIT_INDEX.md`） | [momentum-sector-x-stock @ aec07b0](https://github.com/nickchen494949/momentum-sector-x-stock/tree/aec07b0) |
| **公开仓库** | 代码、**全部 243 个结果文件**（第三轮审计后补齐）、日志、审计记录；不含原始供应商价格 | [macro-observer / research/sector_stock_momentum @ 4644bf0](https://github.com/nickchen494949/macro-observer/tree/4644bf0/research/sector_stock_momentum) |

**审计入口**：
- [`AUDIT_INDEX.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/AUDIT_INDEX.md)：流水线 → 脚本 → 输入 → 输出；测试；冻结规则；提交时间线。
- [`MANIFEST.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/MANIFEST.csv)：6,826 个文件的大小与 sha256。没有入库的原始数据也列了指纹。
- [`README.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/README.md)：分节的详细报告（第 1–16 节；第 16 节是第三轮审计修复后的数字）。
- 三轮审计记录：[第一轮](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/audit/INTERNAL_AUDIT_2026-10-28.md)、[第二轮](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/audit/EXTERNAL_AUDIT_2_2026-10-29.md)、[第三轮](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/audit/EXTERNAL_AUDIT_3_2026-10-29.md)。

**规则先提交、结果后提交**。哈希能证明版本身份和先后顺序，但**不能把已经看过的历史重新变成干净的考试**：主策略的规则是在看过早期结果、审计修复之后、重跑之前冻结的。

| 规则 | 冻结提交 | 结果提交 |
|---|---|---|
| 主策略 [`FROZEN_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/FROZEN_SPEC.md) | [fbc4c51](https://github.com/nickchen494949/momentum-sector-x-stock/commit/fbc4c51) | [3570fd1](https://github.com/nickchen494949/momentum-sector-x-stock/commit/3570fd1) |
| 机器学习 [`ML_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/ML_SPEC.md) | [0235fc3](https://github.com/nickchen494949/momentum-sector-x-stock/commit/0235fc3)；开发期选择 [eb9380a](https://github.com/nickchen494949/momentum-sector-x-stock/commit/eb9380a) | [f114c1b](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f114c1b)（之后修复 bug 又重跑了两次，已说明） |
| 因子体检 [`FACTOR_SCREEN_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/FACTOR_SCREEN_SPEC.md) | [3916ef0](https://github.com/nickchen494949/momentum-sector-x-stock/commit/3916ef0) | [8066f18](https://github.com/nickchen494949/momentum-sector-x-stock/commit/8066f18)，修复后重跑 [aec07b0](https://github.com/nickchen494949/momentum-sector-x-stock/commit/aec07b0) |
| 因子组合体检 [`FACTOR_COMBO_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/FACTOR_COMBO_SPEC.md) | [78c1211](https://github.com/nickchen494949/momentum-sector-x-stock/commit/78c1211) | [60f4efe](https://github.com/nickchen494949/momentum-sector-x-stock/commit/60f4efe)，修复后重跑 [aec07b0](https://github.com/nickchen494949/momentum-sector-x-stock/commit/aec07b0) |
| 找牛股 [`WINNERS_SPEC.md`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/WINNERS_SPEC.md) | [f993bd7](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f993bd7)、[285b8b4](https://github.com/nickchen494949/momentum-sector-x-stock/commit/285b8b4)、[ae612d5](https://github.com/nickchen494949/momentum-sector-x-stock/commit/ae612d5)、第 5c 节 [aec07b0](https://github.com/nickchen494949/momentum-sector-x-stock/commit/aec07b0) | 候选冻结 [f2a1e11](https://github.com/nickchen494949/momentum-sector-x-stock/commit/f2a1e11)；修复后开发结果 [aec07b0](https://github.com/nickchen494949/momentum-sector-x-stock/commit/aec07b0)；中小盘考试结果见第 9 节 |

**复现**：`./run_final.sh`（主回测与全部测试，失败即停，约 6 分钟）；`./run_postaudit3.sh`（全链条，失败即停，约 15 分钟）。重新下载数据需要在 `.env` 里放 Tiingo 和 Nasdaq Data Link 的免费密钥（不在仓库中）。

---

## 1. 数据与测试

| 项目 | 来源 | 说明 |
|---|---|---|
| 标普 500 历史成分 | fja05680/sp500 + 维基百科变更表 | 每个月末的真实成分，含后来退市的股票 |
| 纳斯达克 100 历史成分 | jmccarrell/n100tickers（MIT 许可） | 2007 年起，按指数生效日记录 |
| 股价 | Yahoo（Python，限速）→ Tiingo → WIKI → 免费档案（QSTK、OptionTradingTips、BNSF） | 每个价格都标了来源；改名和代码重用逐条核对身份 |
| 基本面 | SEC 财报数据集（10-K / 10-Q），时点版 | **每个特征按它全部输入（含一年前对比值）中最晚的公开日使用**；EPS 和股数统一拆股口径 |
| 财报日期 | SEC 8-K（item 2.02） | 802 家公司、61,645 次发布 |

**缺口**：标普成分的"股票 × 月份"有 0.62% 没有可用价格（[`results/gap_ledger.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/gap_ledger.csv)）。纳斯达克 100 新增部分缺 0.67%。

**测试**（最新一次运行全部通过；`run_final.sh` 失败即停，每个测试必须打印 PASS）：

| 测试 | 查什么 |
|---|---|
| `pit_truncation_test.py` | 价格路径：假装"今天是过去某天"，删掉之后的价格，选股不变 |
| `pit_fundamentals_truncation_test.py`（第三轮审计后新增） | 基本面路径：删掉截断日（2013、2017、2021）时还没公开的全部财务数据，三个特征构建函数的输出与全数据完全一致 |
| `determinism_test.py` | 换随机种子，结果完全相同 |
| `test_fundamentals_pit.py` | 基本面字段时点、拆股口径 |
| `test_portfolio_ledger.py`（新增） | 6 个月分批账本、日度净值、压力情景 |
| `identity_screen_earnings.py` | 股价序列是否属于所配的 SEC 公司 |

**成交口径**：月末收盘成交，另有次日收盘的敏感性测试；**尚未测试次日开盘成交**。

---

## 2. 主策略与纯动量（只用价格，三轮审计都不受影响）

| 策略（扣成本；年化 / Sharpe / 月末最大回撤） | 样本内 2009–2021.05 | 样本外 2021.06–2026.09 | 全期 |
|---|---|---|---|
| 主策略：最强行业里动量最高的 1 只 | 12.1% / 0.53 / −37% | 71.3% / 1.10 / −51% | 27.4% / 0.74 / −51% |
| 不选行业：全市场动量第 1 名 | 18.2% / 0.61 / −69% | 91.4% / 1.23 / −47% | 36.6% / 0.83 / −69% |
| 全市场动量前 10 名 | 9.9% / 0.53 / −34% | 29.8% / 0.82 / −25% | 15.5% / 0.63 / −34% |
| SPY | 15.4% / 1.02 / −19% | 13.4% / 0.67 / −24% | 14.8% / 0.91 / −24% |

- **外部审计复核**：实际持仓涉及的 125 份价格文件全部取回核对；Top1 全部 213 个月的毛收益与价格端点一致；2010 年起日度最大回撤 −72.57%。
- **集中度**：Top1 截至 2025 年底年化 26.9%，2026 年 1–9 月 +343%。主策略最好的 5 个月占全期对数收益的 44%。
- **样本外不干净**：主策略样本内跑输 SPY；样本外区间在修复前已经被看过，只能叫"回顾性留出"。

数据：[`results/summary.json`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/summary.json)、[`results/monthly_NO_SECTOR_FILTER__top_1_stock.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/monthly_NO_SECTOR_FILTER__top_1_stock.csv)、[`results/monthly_SPEC.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/monthly_SPEC.csv)。

---

## 3. 之后测过的想法（都在同一段历史上测；数字为第三轮修复后）

| # | 想法 | 结果（扣成本） | 判断 |
|---|---|---|---|
| 3.1 | EPS 增长前 10 → 动量最高（2012–2025） | 原版 3.1%；稳健版 21.9%；纯动量 35.4%；SPY 14.9% | 不如纯动量 |
| 3.2 | 不买跌破 200 日均线的股票（2010–2026） | 纯动量第 1 名 40.0% → 45.5%（回撤 −69% → −62%） | 对纯动量小幅有帮助，主要在 2021 年以后 |
| 3.3 | 机器学习（规则先冻结） | 开发期预测力接近 0；考试期选中模型 −7.9%（第三次看同一段历史），SPY 21.7% | 失败 |
| 3.4 | EPS + 动量 + 利润率改善打分，全市场第 1 名（2012–2026） | 20.6% / 0.58 / −55% | 不如纯动量 |
| 3.5 | 动量前 30 → ROE > 20% → EPS 增长最高 | 12.7% / 0.43 / −64% | 差 |
| 3.6 | 只做科技股：动量第 1 名 / 三因子第 1 名（2010–2026） | 39.9% / 0.90 / −54%；38.3% / 0.90 / −47%（XLK 20.0% / 0.99 / −31%） | 前 11 年和 XLK 差不多、回撤大得多；带后见之明 |
| 3.7 | 爆发股因子组合（5 因子），科技前 5，波动倒数加权 | 2015–2022 18.1%（XLK 16.3%）；2015–2026 29.3% / 0.97 / −29%（XLK 22.5% / 1.00） | **不确定**：修一个日期错误就从"跑输"变成"略好"，对实现细节非常敏感 |
| 3.8 | 财报公告收益因子 | 开发期抓大涨和抓大跌一样多 | 没通过事先定的规则 |
| 3.9 | 扩到 标普 + 纳指 100 | 纯动量 36.6% → 24.9%；主策略 27.4% → 26.0%；5 因子科技前 5 27.5% → 28.9% | 没有明显帮助 |

---

## 4. 三轮审计改了什么

| 轮次 | 主要发现 | 对结果的影响 |
|---|---|---|
| 第一轮（内部 + 外部） | 代码重用导致价格属于别的公司、行业用了今天的公司、退市处理、排名平手随机、基本面字段时点 | 全部修复、规则冻结后重跑 |
| 第二轮（外部，对象 `7f24e9b`） | 规模因子用了未来拆股；股数披露日；LSI 身份；6 个月标签漏掉被收购股票；只报月末回撤 | 主策略和纯动量的选股 100% 不变；爆发股结论撤回 |
| 第三轮（外部，对象 `e93da7c`） | 净利润 / 营收借用 EPS 的披露日（AMD 2017）；6 个月持有的账本和日度回撤错误；公开仓库缺结果；脚本失败也显示完成；中小盘考试缺压力情景和下载检查 | 只用价格的策略不变；用到基本面的结果全部重算；暴涨模型明显变差（说明修复前的部分表现来自偷看未来）；新增基本面截断测试，它又抓出两处问题，已修复 |

修复前的结果表另存在 [`audit/before_tiefix/`](https://github.com/nickchen494949/momentum-sector-x-stock/tree/aec07b0/audit/before_tiefix)（第二轮）和 [`audit/before_audit3/`](https://github.com/nickchen494949/momentum-sector-x-stock/tree/aec07b0/audit/before_audit3)（第三轮）。

---

## 5. 因子体检：47 个因子（规则先冻结；修复后重跑）

- **范围**：标普 500，目标是下个月收益，只用 2010-01 至 2019-11 判定。
- **方法**：Romano–Wolf 多重检验、稳定性选择、LightGBM 置换重要性。

**结果：0 个"有用"、36 个"不确定"、11 个"没用"。** 最接近显著的是营收增速加快（校正后 p = 0.28）、上月收益反转（0.53）、研发强度（0.59）、ROE（0.67）；12−1 动量的平均预测力很弱。销售库存比及其变化等新因子都没有通过。
数据：[`results/factor_screen/screen_table.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/factor_screen/screen_table.csv)。

## 6. 因子组合体检：21 个组合（规则先冻结；修复后重跑）

| 家族 | 前 10% 扣成本年化 − 等权年化 | 判定 |
|---|---|---|
| 8 个经典组合，2010–2019 | −3.8% 到 +0.6%；t 最高 2.0（校正后 p = 0.19） | 全部"没用" |
| 47 个因子交给 Ridge / LASSO / LightGBM，2013–2019 样本外 | −6.4% 到 −2.5% | 全部"没用" |
| 自动找交互：用 2010–2015 挑出 10 对，2016–2019 检验 | −4.7% 到 +2.7%；检验期 t 最高 1.7 | 8 对"没用"、2 对"不确定" |

数据：[`results/factor_combo/combo_table.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/factor_combo/combo_table.csv)。

---

## 7. 找牛股三条线（标普 500 上的开发结果，修复后）

| 策略（年化 / Sharpe / **日度**最大回撤） | 2013–2019 | 2020–2026.09 | 全期 |
|---|---|---|---|
| 纯动量第 1 名 | 23.7% / 0.72 / −73% | 77.0% / 1.16 / −56% | 40.0% / 0.88 / −73% |
| 动量前 5 名 + 崩盘过滤 | 16.1% / 0.80 / −27% | 29.1% / 0.77 / −39% | 21.1% / 0.74 / −39% |
| 暴涨模型前 5 名，持有 1 个月 | 7.8% / 0.37 / −47% | 6.8% / 0.29 / −55% | 7.3% / 0.32 / −56% |
| 暴涨模型前 5 名，持有 6 个月（真实账本） | 11.8% / 0.54 / −48% | 14.7% / 0.48 / −48% | 13.2% / 0.49 / −48% |
| SPY | 14.6% / 1.22 / −19% | 15.2% / 0.76 / −34% | 14.2% / 0.90 / −34% |

规律：收益和回撤捆在一起。风控能把回撤压到 −25% 到 −40%，年化也跟着降。全部 57 个策略在 [`results/winners/summary.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/winners/summary.csv)。

## 8. 风险（2012–2026.09，日度净值按实际持仓重建）

| | 年化 | 年化波动 | 月末最大回撤 | 日度最大回撤 | 最好 5 个月占总收益 |
|---|---|---|---|---|---|
| 爆发股科技前 5（波动倒数加权） | 27.5% | 26.5% | −29.4% | −36.4% | 34% |
| 爆发股科技第 1 名 | 39.0% | 45.6% | −68.4% | −70.5% | 38%（MU 27%、WDC 20%） |
| XLK | 21.9% | 18.8% | −31.2% | −33.6% | 25% |

数据：[`results/explosive/risk_report.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/aec07b0/results/explosive/risk_report.csv)。

---

## 9. 中小盘考试：唯一一次在没用过的数据上、只跑一次的检验

- **考场**：标普 500 以外、成交够活跃的美股（价格 ≥ 5 美元、成交额中位数 ≥ 500 万美元）。价格来自 WIKI 整库（含退市股票）+ Yahoo 3,830 只（全部下载成功）。
- **数据清洗**：只按证据修正（64 处，记在 `data/smallcap/price_corrections.csv`），其余可疑价格保留，并另跑"诊断版"作对照。

| 策略（扣成本年化 / Sharpe / 日度最大回撤） | 主考 2010-01 … 2018-02 | 诊断版 | 压力 −100% |
|---|---|---|---|
| 纯动量第 1 名 | **−40.5% / −0.47 / −100%** | −40.5% | −40.5% |
| 动量前 5 名 + 崩盘过滤 | **−9.0% / −0.03 / −87%** | −9.1% | −16.1% |
| 暴涨模型前 5 名，持有 1 个月（2013 年起） | **−10.8% / −0.08 / −79%** | −10.5% | −14.5% |
| 暴涨模型前 5 名，持有 6 个月（2013 年起） | **−0.6% / 0.11 / −62%** | −1.5% | −1.7% |
| 中小盘等权 / SPY | 12.3% / 13.8% | — | — |

**结论**：所有冻结候选在没碰过的股票上全部大幅亏损，去掉可疑价格后结论不变。这是整个研究中最干净的一次检验，它不支持"动量选股是可推广的规律"。数据：[`results/winners_holdout/summary.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/main/results/winners_holdout/summary.csv)、[`summary_STRICT.csv`](https://github.com/nickchen494949/momentum-sector-x-stock/blob/main/results/winners_holdout/summary_STRICT.csv)。

## 9b. 第二轮机器学习：强动量股里，财报变化过程能否帮忙（规则先冻结，只跑一次）

在每月动量前 50 名里，用次日开盘成交、按年份向前走。测试期 2015-01 至 2026-09，扣成本：
- **C-LightGBM（价格 + 基本面 + 财报变化过程）**：Top3 **36.7% / Sharpe 1.09 / −39%**，Top1 **46.1% / 1.00 / −56%**。
- **纯动量**：Top3 26.9% / 0.78 / −41%，Top1 41.7% / 0.86 / −73%。
- **SPY**：14.0%。

逐层比较：
- 只看价格的模型输给纯动量；
- 加当时的基本面，效果不明确；
- **再加财报变化过程，LightGBM 的 Top3 多赚 18 个百分点**（自助法 5%–95%：+8 到 +28；12 年中 10 年更好），Top1 多赚 20 个百分点（+4 到 +37）；
- 线性的 Ridge 没有这个效果；
- 全部 12 条成绩都已列出，最好一条的 Deflated Sharpe 为 0.987。

**这是唯一支持"基本面（尤其是变化过程）有增量价值"的结果。** 但这段历史已被反复看过，模型对 50 只的整体排序并没有更准，也还没有在中小盘或未来数据上检验过。详见 [README 第 18 节](https://github.com/nickchen494949/momentum-sector-x-stock/blob/main/README.md)、[`results/ml2/`](https://github.com/nickchen494949/momentum-sector-x-stock/tree/main/results/ml2)。

## 10. 总结论

1. **在这批数据、这些实现、这些区间和检验标准下，尚未验证出稳定的超额收益**——唯一的例外迹象是第 9b 节：动量前 50 名里，LightGBM 加财报变化过程，回顾性地多赚了约 18–20 个百分点，需要用未来数据确认。 单个因子、经典组合、机器学习、自动找交互、风控叠加，都没有通过事先写好的检验。这**不等于**已经证明基本面、机器学习或先选行业一定没用：一部分实现刚修过时点错误，检验力也有限。
2. **纯动量第 1 名的账本是真实可复现的**，但它的高收益来自少数大赢家和最近一段行情：
   - 2010–2019 年化 19.5%；
   - 截至 2025 年底的全期年化 26.9%；
   - 加上 2026 年 1–9 月以后是 36.6%；
   - 最大回撤约 −73%。
3. **"年化 50% 以上并持续"没有可靠证据。** 要接近这个数字，只能集中押 1 只股票，并承受七成左右的回撤。
4. **中小盘考试**：所有冻结候选在没用过的股票上大幅亏损（纯动量第 1 名年化 −40.5%），这是最干净的一次检验。
5. **审计范围**：外部审计通过的是主策略和纯动量的收益账本。这不等于对每个供应商报价的真实性、全部股票的选股排名或整条研究链做了认证。

**如果要用**（建议，不是承诺）：大部分资金放指数；动量只占小部分，用前 5–20 只、带崩盘过滤的版本；规则从今天起冻结，用以后的真实数据检验。

## 11. 局限

- 免费数据：0.62% 的成分股月份缺价格；部分人工行业分类没有逐个上网核实。
- 外国公司（20-F / 40-F）没有 SEC 基本面。
- 成本只算每边 10 个基点，没有冲击成本和税；尚未测试次日开盘成交。
- 同一段历史被测了很多次（机器学习的考试期已经看了三次），越往后的结果，数据挖掘风险越大。
- 外部审计员的复核脚本和证据包留在审计员的工作区，本仓库里没有；我们新查出的 AGN、CB 身份问题，以及第三轮修复，都待外部复核。
