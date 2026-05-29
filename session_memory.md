# Session Memory — Updated 29 May 2026 (End of Session)

## Project
- **App:** ETF Signal Dashboard — Streamlit
- **Repo:** https://github.com/saradhiavinash/etf-trade-dashboard.git (branch: main)
- **Live:** Streamlit Cloud (auto-deploys on push)
- **Local:** `C:\Users\z003y41h\Desktop\Stock Trading`
- **venv:** `.venv\Scripts\python.exe`
- **HEAD:** `43275eb`

## Portfolio (from Google Sheet — auto-loaded every 60s)
| ETF | Units | Avg Cost | Notes |
|-----|-------|----------|-------|
| HDFCSML250 | 131 | ₹150.96 | Sold 32 units @₹172.27 (profit booked) |
| PSUBNKBEES | 364 | ₹97.51 | |
| GOLDBEES | 193 | ₹126.64 | |
| JUNIORBEES | 45 | ₹776.74 | -0.41%, Buy Prob 79% — hold/accumulate |

## Google Sheet
- **Edit URL:** https://docs.google.com/spreadsheets/d/1irjEYSjtaH60N_AcmPACxPvAbEmQwQzhgAYsPzSb6Iw/edit
- **CSV export:** https://docs.google.com/spreadsheets/d/1irjEYSjtaH60N_AcmPACxPvAbEmQwQzhgAYsPzSb6Iw/export?format=csv (no gid needed)
- **Sheet layout (rows 4+ = data, row 3 = headers):**
  - Col B = NSE Symbol (e.g. GOLDBEES) — UPPERCASE
  - Col C = Units held
  - Col D = Avg cost
  - Col E = Invested (auto-calculated in sheet)
  - Col G = Profit booked symbol
  - Col H = Units sold
  - Col I = Sell price
  - Col J = Sale proceeds (pre-calc)

## How to add a new ETF
- Just add the NSE symbol in **column B** of the sheet
- Leave units/avg blank or 0 for watchlist (signals only, no P&L)
- Fill units + avg cost to track as a holding with full P&L
- Dashboard auto-detects risk category from internal ETF_METADATA lookup
- Unknown symbols default to **"Aggressive"** risk

## Features Implemented (current — HEAD 43275eb)
- ✅ Auto-load portfolio + profit booked from Google Sheet (60s cache)
- ✅ Fallback to portfolio.json (utf-8-sig encoding fix for PowerShell BOM)
- ✅ ETF_METADATA dict + etf_meta() function for risk/label/yf_symbol lookup
- ✅ load_sheet_etfs() — drives signals table from sheet (not hardcoded list)
- ✅ Any ETF added to sheet auto-appears in signals table with full analysis
- ✅ Summary bar: Total Invested, Current Value, Unrealised P&L, Profit Booked (₹ + %), Total Gain (₹ + %)
- ✅ Profit Booked % = realized_pnl / (total_invested + sold_units_cost) — portfolio-level wealth view
- ✅ Profit Booked detail expander with per-trade % column
- ✅ Per-ETF mini cards with live price, P&L%, units, avg cost
- ✅ Signals table: RSI, Buy Prob%, Signal, Sell Qty, Trail SL, Score, Today%, Source
- ✅ NSE live price (primary), YF 15min (fallback), EOD (last resort)
- ✅ NaN guard for empty sheet cells (math.isnan check)
- ✅ Google Sheets info banner at bottom of dashboard
- ✅ Edit My Portfolio section removed (sheet is source of truth)

## ETF_METADATA — Known ETFs (risk auto-assigned)
| Symbol | Label | Risk |
|--------|-------|------|
| HDFCSML250 | HDFC Smallcap 250 ETF | Very Aggressive |
| PSUBNKBEES | PSU Bank BeES | Aggressive |
| NIFTYBEES | Nifty BeES | Stable |
| GOLDBEES | Gold BeES | Stable |
| BANKBEES | Bank BeES | Aggressive |
| ITBEES | IT BeES | Aggressive |
| JUNIORBEES | Junior BeES | Very Aggressive |
| MOM100 | Momentum 100 | Very Aggressive |
| SILVERBEES | Silver BeES | Aggressive |
| CPSEETF | CPSE ETF | Aggressive |
| ICICIB22 | Bharat 22 ETF | Aggressive |
| SETFNIF50 | SBI Nifty 50 ETF | Stable |
| PHARMABEES | Pharma BeES | Aggressive |
| Unknown | symbol itself | Aggressive (default) |

## Features Lost in Revert (657685d) — NOT yet re-implemented
- ❌ Buy Prob% fix (cheapness bonus requires score >= 0 / neutral trend)
- ❌ Risk-based tranche thresholds (Stable 8/12/18, Aggressive 12/18/25, Very Aggressive 15/22/30)
- ❌ Tranche tracker (original_units, tranches_sold in portfolio)
- ❌ Next Trigger column (next P&L% threshold + price)

## Key Technical Rules
- NEVER mix string "—" with float columns in dataframes → Arrow serialization crash
- NEVER use avg_cost=0 in portfolio → ZeroDivisionError
- Always `math.isnan()` after `float()` on sheet cells — NaN passes `<= 0` silently
- Always validate with `ast.parse(open('dashboard.py', encoding='utf-8').read())` before committing
- PowerShell `Set-Content` writes UTF-8 BOM → use `encoding='utf-8-sig'` to read, or rewrite with Python
- `save_portfolio()` removed — sheet is sole source of truth
- Always `git add`, `git commit`, `git push` after every file change

## Realized P&L Calculation
- **Profit Booked (₹):** `(sell_price - avg_cost) × units_sold` = actual profit earned
- **Profit Booked (%):** `realized_pnl / (total_current_invested + sold_units_cost)` = wealth-level %
- **Total Gain %:** `(unrealised + realised) / total_capital_deployed`


## Portfolio (from Google Sheet — auto-loaded every 60s)
| ETF | Units | Avg Cost | Notes |
|-----|-------|----------|-------|
| HDFCSML250 | 131 | ₹150.96 | Sold 32 units @₹172.27 (profit booked) |
| PSUBNKBEES | 364 | ₹97.51 | |
| GOLDBEES | 193 | ₹126.64 | |
| JUNIORBEES | 45 | ₹776.74 | -0.41%, Buy Prob 79% — hold/accumulate |

## Google Sheet
- **URL:** https://docs.google.com/spreadsheets/d/1irjEYSjtaH60N_AcmPACxPvAbEmQwQzhgAYsPzSb6Iw/edit
- **CSV export:** https://docs.google.com/spreadsheets/d/1irjEYSjtaH60N_AcmPACxPvAbEmQwQzhgAYsPzSb6Iw/export?format=csv
- **Layout (no gid needed — first sheet):**
  - Col 1=ETF symbol, 2=units, 3=avg_cost (Dashboard portfolio, rows 3+)
  - Col 6=ETF symbol, 7=units_sold, 8=sell_price, 9=proceeds (Profit Booked section)

## Features Implemented (current)
- ✅ Auto-load portfolio from Google Sheet (60s cache, fallback to portfolio.json)
- ✅ Auto-load profit booked from Google Sheet
- ✅ Summary bar: Total Invested, Current Value, Unrealised P&L, Profit Booked (₹ + % of total capital), Total Gain (Realised+Unrealised + %)
- ✅ Profit Booked % = realized_pnl / (total_invested + sold_units_cost) — portfolio-level wealth view
- ✅ Per-ETF mini cards with live price, P&L%, units, avg cost
- ✅ Signals table with RSI, Buy Prob%, Signal, Sell Qty, Trail SL
- ✅ NSE live price (primary), YF 15min delayed (fallback), EOD (last resort)
- ✅ NaN guard for empty sheet cells
- ✅ ALL_ETFS defined before load_portfolio (fixes Streamlit Cloud cache issue)
- ✅ portfolio.json updated with all 4 ETFs as fallback
- ✅ Edit My Portfolio section removed (sheet is source of truth)
- ✅ Google Sheets link shown at bottom of dashboard

## Features Lost in Revert (657685d) — NOT yet re-implemented
- ❌ Buy Prob% fix (cheapness bonus requires neutral trend / score >= 0)
- ❌ Risk-based tranche thresholds (Stable 8/12/18, Aggressive 12/18/25, Very Aggressive 15/22/30)
- ❌ Tranche tracker (original_units, tranches_sold in portfolio)
- ❌ Next Trigger column (next P&L% threshold + price)

## Key Technical Notes
- NEVER mix string "—" with float columns in dataframes → Arrow serialization crash
- NEVER use avg_cost=0 in portfolio → ZeroDivisionError
- Always `math.isnan()` check after `float()` on sheet cells — NaN passes `<= 0` silently
- Always validate with `ast.parse()` before committing
- `save_portfolio()` removed — sheet is sole source of truth

## Realized P&L Calculation
- **Correct:** `(sell_price - avg_cost) × units_sold` = actual profit earned
- **Profit Booked %:** `realized_pnl / (total_current_invested + sold_units_cost)` = wealth-level %
- **Total Gain %:** `(unrealised + realised) / total_capital_deployed`
