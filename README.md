# 🔭 宏观观察器 — Macro Dashboard

A macroeconomic dashboard tracking rates, commodities, equities, and macro indicators — all stored locally, updated once per day.

---

## 🚀 How to Start

```bash
cd ~/Desktop/宏观观察器
node server.js
```

Then open **http://localhost:8765** in your browser.

---

## 📊 Dashboard Sections

| Section | What's Inside |
|---|---|
| **利率 Rates** | TIPS yield, HY-IG spread (bp), SOFR-IORB spread (bp), Fed Funds, Yield curve (03M–30Y), 03M-10Y spread |
| **期货 Futures** | Fed Funds Futures — implied rate (100−price) + diff vs DFF in bp |
| **大宗商品 Commodities** | Oil, Gas, Gold, Copper, Wheat, Soybean, Baltic Dry Index |
| **宏观经济 Economy** | 21 indicators across Inflation, Activity, Labour, JOLTS, Fiscal |
| **估值 Valuation** | S&P 500 PE, Shiller CAPE, EPS Growth YoY |
| **股票 Stocks** | Major indices + sector ETFs |

### Economy Indicators Detail

| Group | Indicators |
|---|---|
| Inflation/Monetary | Core PCE YoY, PCE YoY, Avg Hourly Wage YoY, M2 YoY |
| Activity | Real PCE MoM, Retail Sales Control MoM, Industrial Production YoY, Core Capex Orders MoM, GDPNow |
| Labour | NFP MoM Δ (k), Unemployment, Initial Claims (k), Continuing Claims (k), Avg Weekly Hours (hrs), Temp Help YoY |
| JOLTS | Job Openings (M), Quits Rate |
| Fiscal/Financial | Gov Debt YoY, Fed Balance Sheet (T$), Money Market Funds (T$), Consumer Sentiment |

---

## 📁 Local Data Storage

All data is cached locally — the server works offline using cached data.

```
data/fred/         — 42 FRED series JSON files (full history)
data/yahoo/        — 26 Yahoo Finance tickers JSON files (full history)
data/valuation/    — Shiller CAPE, PE, EPS, BDI, etc.
```

Each JSON file format:
```json
{ "id": "DGS10", "values": [["2020-01-02", 1.88], ["2020-01-03", 1.81], ...] }
```

---

## 🔄 Update Logic — Incremental Only

**Data is never fully re-downloaded.** Full history was fetched once at startup and stays on disk. Daily updates only append new rows.

```
On startup:
  1. Load all JSON files from data/ into memory
  2. 60s after startup → run daily update

Daily update (smartUpdate):
  FRED:  fetch last 10 days from FRED API
         → compare against last stored date
         → append only rows where date > lastStoredDate
         → save updated JSON to disk

  Yahoo: fetch last 5 days via Python (fetch_yahoo.py)
         → same incremental logic
         → save updated JSON to disk

  BDI:   manually entered via dashboard ✏️ button
         → saved to data/valuation/BDI.json immediately
```

---

## 🗂 Display Units & Transforms

| Transform | Used For | Logic |
|---|---|---|
| `yoy` | PCE, M2, IP, Wages, etc. | `(val / val_1yr_ago − 1) × 100` |
| `mom_pct` | Core Capex Orders, etc. | `(val / val_prev_month − 1) × 100` |
| `mom_abs` | Nonfarm Payrolls | `val − val_prev_month` (in k jobs) |
| `÷1000` | Claims, JOLTS Openings | raw (thousands) → display unit |
| `M→T` | Fed balance sheet, Money Market | millions → trillions |
| `bpValue` | HY-IG spread, 03M-10Y spread | raw % × 100 → basis points |
| `bpChanges` | All yield curve rates | changes × 100 → basis points |

---

## 🗺 Baltic Dry Index (BDI)

BDI is not available via any free API (proprietary Baltic Exchange data). Workflow:

1. Download CSV from [Investing.com BDI page](https://www.investing.com/indices/baltic-dry-historical-data) (free account required)
2. Run: `python3 import_bdi.py "Baltic Dry Index Historical Data.csv"`
   — or — use the **✏️ button** on the BDI row in the dashboard to enter values manually

**Manual update flow:**
- Dashboard shows a red banner when BDI data is stale (business days behind)
- Click banner or ✏️ → popup opens + Investing.com page opens in new tab
- Enter date (pre-filled to next missing business day) + value → Save
- If multiple days behind, popup auto-advances to next date after each save
- Data saved immediately to `data/valuation/BDI.json`

---

## ⚠️ Yahoo Finance Rules — Do NOT Change

**Yahoo Finance blocked our IP** when old code hammered their API. These rules must never be reverted:

| Rule | Why |
|---|---|
| **Python fetcher** (`fetch_yahoo.py`) | Yahoo blocks Node.js by TLS fingerprint. Never switch back to Node.js. |
| **Once per day** Yahoo updates | 26 symbols × 1/day = safe. Hourly = IP ban within days. |
| **5–10s random delay** between symbols | Looks like human browsing. Never remove. |
| **Concurrent lock** (`isUpdating`) | Prevents two Yahoo batches running simultaneously. |

### If Yahoo Stops Working

```bash
python3 fetch_yahoo.py "^GSPC" 5d   # test connection
```
- `"ok": true` → working, problem elsewhere
- `HTTP 429` → IP blocked — wait 12–24h, do NOT restart server repeatedly

---

## 🎨 UI/UX Design Preferences — Must Follow

The user has confirmed these design choices. All future UI work must respect them.

### Overall Theme

| Principle | Rule |
|---|---|
| **Background** | White (`#f8fafc` / `#ffffff`). No dark mode for the cycle section. The rest of the dashboard remains dark. |
| **Card style** | White cards, `border-radius: 16px`, subtle `box-shadow`, `1px solid #e2e8f0` border. Cards should feel floating and premium. |
| **Hover** | Cards lift on hover (`translateY(-2px)`) with deeper shadow. Micro-animation required. |
| **Typography** | System font stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto`). Titles 800 weight, body 500. No browser defaults. |
| **Color philosophy** | Never use raw saturated colors (`#ff0000`, `#0000ff`). Use Tailwind-inspired soft palettes. |

### Cycle Diagram — Fixed Color Mapping

| Module | Num Badge | Status Background | Status Text | Status Border |
|---|---|---|---|---|
| ① Fed政策 | `#3b82f6` (blue) | `#eff6ff` | `#1d4ed8` | `#bfdbfe` |
| ② 金融条件 | `#10b981` (emerald) | `#ecfdf5` | `#047857` | `#a7f3d0` |
| ③ 实体经济 | `#8b5cf6` (violet) | `#f5f3ff` | `#6d28d9` | `#ddd6fe` |
| ④ 通胀就业 | `#f43f5e` (rose) | `#fff1f2` | `#be123c` | `#fecdd3` |

### Arrow Design

- Arrows must visually **connect card to card** — not float in empty space.
- Each arrow shows: **state badge** (colored pill) + **timeframe** (e.g. `1D–1M`) + **one-line evidence**.
- Arrow line: `2px solid #cbd5e1` with triangular tip. Badge sits on a white background that "cuts" the line.
- Center of the 2×2 grid has a minimal `↻ CYCLE` icon.

### Layout Structure

```
[Sidebar Left]  [  2×2 Card Grid  ]  [Sidebar Right (optional)]
                [  Bottom Bar x3  ]
```

- Sidebar: `240px`, white cards, used for Fiscal / Supply / Chain Diagnosis.
- Grid: `3 cols × 3 rows` — 4 module cards in corners, 4 arrows in edges, center icon.
- Bottom bar: 3-column grid for Risks / Watch / Contradictions.

### What NOT to Do

- ❌ Dark backgrounds for the cycle section
- ❌ Raw colored borders or glowing neon effects
- ❌ Arrows that "float" between cards without a visible connecting line
- ❌ Inline styles that override the design system with hardcoded hex colors
- ❌ Generic sans-serif or Times New Roman fonts

---

## 🔌 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/data` | GET | Full dashboard snapshot |
| `/api/refresh` | GET | Trigger incremental update (FRED + Yahoo) |
| `/api/status` | GET | Download progress |
| `/api/redownload` | GET | Wipe cache and re-download everything from scratch |
| `/api/update-bdi` | POST | Update BDI data point(s) — body: `[[date, value], ...]` |
| `/api/chart` | GET | Chart data for a given series key |
| `/health` | GET | Health check |

---

## 📁 File Structure

```
server.js            — Main server (Node.js, port 8765)
index.html           — Frontend dashboard
fetch_yahoo.py       — Python Yahoo fetcher (DO NOT DELETE)
import_bdi.py        — One-time BDI CSV importer (Investing.com)
data/fred/           — Cached FRED JSON (42 series)
data/yahoo/          — Cached Yahoo JSON (26 tickers)
data/valuation/      — Valuation & BDI JSON files
csv/                 — CSV exports
```
