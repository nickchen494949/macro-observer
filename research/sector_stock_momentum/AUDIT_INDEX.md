# 审计索引（AUDIT_INDEX）

这份文件告诉审计者：每个结论出自哪段代码、用了哪些输入、产出哪些文件，以及哪些测试和审计记录可以对照。
所有文件的大小和 sha256 列在 `MANIFEST.csv` 里（由 `build_manifest.py` 生成）。原始供应商数据不进公开仓库，但哈希值列在清单中。私有仓库保存全部文件，只有两项例外：`data/sec_submissions/`（424 MB 的 SEC 缓存，可用 `fetch_earnings_dates.py` 重新下载，派生结果 `data/earnings_dates.csv` 已入库）和 `data/raw_volume/`（成交量还在下载中）。

## 1. 流水线（按运行顺序）

| 阶段 | 脚本 | 输入 | 输出 |
|---|---|---|---|
| 成分股 | （fja05680/sp500 下载）、`fetch_sectors.py` | — | `data/sp500_hist_components.csv`、`sp500_ticker_start_end.csv`、`wiki_changes.csv`、`wiki_current_constituents.csv`、`sectors.csv` |
| 股价 | `fetch_prices.py`（Yahoo）、`fetch_tiingo.py`、`fetch_wiki.py`、`fetch_archives.py`、`resolve_successors.py` | 成分股列表 | `data/raw/`、`raw_tiingo/`、`raw_wiki/`、`raw_archive/`（每个 JSON 带 source 字段） |
| 身份核对 | `identity_check.py`、`fetch_wiki_crosscheck.py`、`identity_screen_earnings.py` | 股价、SEC 财报日期 | `data/identity_flags.csv`、`results/identity_screen_earnings.csv` |
| 人工身份/退出/行业修正 | （人工研究，每行带证据） | — | `data/identity_resolutions.csv`、`exit_resolutions.csv`、`sector_overrides.csv`、`membership_additions.csv`、`cik_validity.csv` |
| SEC 基本面 | `fetch_sec_fundamentals.py` → `build_fundamentals.py`；接口 `fundamentals_pit.py` | SEC FSDS 季度包 | `data/fundamentals/`（`cik_map.csv`、`pit_long/`、`eps_quarterly_pit.parquet`） |
| 财报日期 | `fetch_earnings_dates.py` | SEC submissions | `data/earnings_dates.csv` |
| 主回测 | `backtest.py`（规则冻结在 `FROZEN_SPEC.md`） | 以上全部 | `results/summary.json`、`monthly_*.csv`、`coverage_*`、`price_integrity.csv`、`runs/*_manifest.json` |
| 缺口总账 | `build_gap_ledger.py` | 主回测 | `results/gap_ledger.csv`、`gap_summary_by_year.csv` |
| EPS 另测 | `eps_momentum.py` | 主回测 + 基本面 | `results/eps_momentum/` |
| 机器学习 | `ml_features.py` → `ml_pipeline.py dev` → `ml_pipeline.py holdout`（规则冻结在 `ML_SPEC.md`） | 主回测 + 基本面 | `results/ml/panel.parquet`、`selection.json`、`holdout.json` |
| 其他组合 | `sma200_overlay.py`、`composite3.py`、`mom30_roe.py`、`tech_only.py` | `results/ml/panel.parquet` | `results/ml/*` |
| 爆发股因子 | `explosive_factors.py` → `explosive_v2.py` → `improve_v3.py`；`earnings_factor.py`；`risk_report.py` | ML 面板 + 基本面 | `results/explosive/*` |
| 纳斯达克 100 扩池 | `build_ndx_membership.py`、`fetch_ndx_prices.py`、`fetch_ndx_meta.py`、`ndx_fundamentals.py`、`ndx_universe.py`、`ndx_expand.py` | `data/nasdaq100_src/`（来源见 SOURCE.txt） | `data/ndx_*.csv`、`data/raw_ndx/`、`data/fundamentals_ndx/`、`results/ndx/` |
| 文件清单 | `build_manifest.py` | 整个文件夹 | `MANIFEST.csv` |

一键重跑：`./run_final.sh`（主回测与测试）；`./run_postaudit2.sh`（第二轮审计修复后的全链条）。日志都在 `logs/`。

## 2. 测试

| 测试 | 查什么 | 日志 |
|---|---|---|
| `pit_truncation_test.py` | 假装“今天是 C 日”，截掉之后的价格，C 日之前的选股必须完全相同 | `logs/pit_truncation_test.log` |
| `determinism_test.py` | 不同 PYTHONHASHSEED 下选股完全相同 | `logs/determinism_test.log` |
| `test_fundamentals_pit.py` | 基本面每个字段只在自己的披露日之后可用、拆股口径统一 | （命令行输出） |
| `identity_screen_earnings.py` | 股价序列是否属于所配的 SEC 公司：公司自己的财报日附近股价波动应明显大于平时 | `results/identity_screen_earnings.csv` |
| `ndx_expand.py` 第一步 | 用扩池加载器只放标普成分，必须和冻结的主回测选股 100% 相同 | `results/ndx/sanity_sp_only_diffs.csv` |

## 3. 规则冻结与审计记录

| 文件 | 内容 |
|---|---|
| `FROZEN_SPEC.md` | 主策略规则（提交 `fbc4c51`，在最终结果之前） |
| `ML_SPEC.md` | 机器学习规则（提交 `0235fc3`，在训练之前）；开发期选择在 `eb9380a` 冻结后才跑考试期 |
| `audit/WORKFLOW_AUDIT.md` | 自查记录 |
| `audit/INTERNAL_AUDIT_2026-10-28.md` | 第一轮审计（内部 + 外部）的发现与修复 |
| `audit/EXTERNAL_AUDIT_2_2026-10-29.md` | 第二轮外部审计（针对 `7f24e9b` 六因子策略）的发现、修复与前后对比 |
| `audit/before_tiefix/` | 第二轮修复之前的结果表副本（用于前后对比） |

## 4. 提交时间线（私有仓库 momentum-sector-x-stock）

| 提交 | 内容 |
|---|---|
| `ba751e7` | 初版 |
| `fbc4c51` | 第一轮审计修复，规则冻结（在重跑之前） |
| `3570fd1` | 重跑结果 |
| `db34e3d` | 免费档案补数据 |
| `0235fc3` | ML_SPEC 冻结（训练之前） |
| `eb9380a` | ML 开发期选择冻结（考试期之前） |
| `f114c1b` | ML 考试期结果 + SMA200 |
| `7f24e9b` | 组合 / ROE / 科技股 / 爆发股因子研究（第二轮外部审计的对象） |
| 本次提交 | 第二轮审计修复、财报日期因子、纳斯达克 100 扩池、审计索引与清单 |

## 5. README 各节 → 结果文件

| README 节 | 结果文件 |
|---|---|
| 2 结果 | `results/summary.json`、`results/monthly_SPEC.csv`、`results/grid_is_oos.csv` |
| 5 数据缺口 | `results/gap_ledger.csv`、`gap_summary_by_year.csv` |
| 8 EPS 另测 | `results/eps_momentum/summary.csv` |
| 10 SMA200 + 机器学习 | `results/ml/selection.json`、`holdout.json`、`sma200_overlay_summary.csv` |
| 11 组合与爆发股因子 | `results/ml/composite3_summary.csv`、`mom30roe_summary.csv`、`tech_only_summary.csv`、`results/explosive/lift_*.csv`、`v2_selected_factors.json`、`v2_portfolios.csv`、`v3_summary.csv`、`risk_report.csv`、`risk_calendar_years.csv`、`ear_lift.csv`、`ear_portfolios.csv` |
| 12 纳斯达克 100 扩池 | `results/ndx/summary.csv`、`coverage_ndx_only.csv` |

## 6. 已知限制（审计时请留意）

- 2023–2026 在整个研究里多次被看过，只能叫“回顾性留出期”，不是未接触的样本外。
- 单只股票策略对细节极其敏感；报告里的收益是在一个免费数据样本上的历史模拟。
- 规模因子是“加权平均稀释股数 × 复权价”构造的代理，不是精确的历史市值。
- 外国公司（20-F / 40-F）没有 SEC FSDS 基本面；它们只能用价格类因子。
- `data/sector_overrides.csv` 中 8 行、`data/ndx_sectors.csv` 中标为 `manual_gics` 的行没有逐个上网核实。
