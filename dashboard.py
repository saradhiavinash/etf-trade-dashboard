import io
import math
import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import json
import os
import requests
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="ETF Signals", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")

st_autorefresh(interval=300_000, key="autorefresh")

# ── All ETFs catalog ────────────────────────────────────────────────────────
ALL_ETFS = [
    {"label": "HDFC Smallcap 250 ETF", "nse_symbol": "HDFCSML250",  "yf_symbol": "HDFCSML250.NS",  "risk": "Very Aggressive", "risk_color": "#dc3545"},
    {"label": "PSU Bank BeES",          "nse_symbol": "PSUBNKBEES",  "yf_symbol": "PSUBNKBEES.NS",  "risk": "Aggressive",      "risk_color": "#fd7e14"},
    {"label": "Nifty BeES",             "nse_symbol": "NIFTYBEES",   "yf_symbol": "NIFTYBEES.NS",   "risk": "Stable",          "risk_color": "#28a745"},
    {"label": "Gold BeES",              "nse_symbol": "GOLDBEES",    "yf_symbol": "GOLDBEES.NS",    "risk": "Stable",          "risk_color": "#28a745"},
    {"label": "Bank BeES",              "nse_symbol": "BANKBEES",    "yf_symbol": "BANKBEES.NS",    "risk": "Aggressive",      "risk_color": "#fd7e14"},
    {"label": "IT BeES",                "nse_symbol": "ITBEES",      "yf_symbol": "ITBEES.NS",      "risk": "Aggressive",      "risk_color": "#fd7e14"},
    {"label": "Junior BeES",            "nse_symbol": "JUNIORBEES",  "yf_symbol": "JUNIORBEES.NS",  "risk": "Very Aggressive", "risk_color": "#dc3545"},
    {"label": "Momentum 100",           "nse_symbol": "MOM100",      "yf_symbol": "MOM100.NS",      "risk": "Very Aggressive", "risk_color": "#dc3545"},
]

# ── Portfolio helpers ─────────────────────────────────────────
GOOGLE_SHEET_CSV = (
    "https://docs.google.com/spreadsheets/d/"
    "1irjEYSjtaH60N_AcmPACxPvAbEmQwQzhgAYsPzSb6Iw/export?format=csv"
)
PORTFOLIO_FILE = os.path.join(os.path.dirname(__file__), "portfolio.json")

@st.cache_data(ttl=60)
def load_portfolio():
    """Always loads from Google Sheet (cached 60s). Falls back to portfolio.json."""
    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV, header=None)
        # Sheet layout: row 1 = column headers (ETF, Units, Avg price), data from row 2
        # Columns: index 1=ETF symbol, 2=units, 3=avg_cost
        etf_lookup = {e["nse_symbol"]: e for e in ALL_ETFS}
        portfolio = []
        for i in range(2, len(df)):
            row = df.iloc[i]
            sym = str(row[1]).strip().upper()
            if not sym or sym in ("NAN", "ETF", ""):
                continue
            try:
                units    = float(row[2])
                avg_cost = float(row[3])
            except (ValueError, TypeError):
                continue
            if math.isnan(units) or math.isnan(avg_cost) or units <= 0 or avg_cost <= 0:
                continue
            meta = etf_lookup.get(sym)
            portfolio.append({
                "label":      meta["label"]     if meta else sym,
                "nse_symbol": sym,
                "yf_symbol":  meta["yf_symbol"] if meta else sym + ".NS",
                "units":      units,
                "avg_cost":   avg_cost,
            })
        if portfolio:
            return portfolio
    except Exception:
        pass
    # fallback to local portfolio.json
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return []

@st.cache_data(ttl=60)
def load_profit_booked():
    """Reads 'Profit booked' columns from Google Sheet (cols 6=symbol,7=units,8=sell price,9=proceeds)."""
    try:
        df = pd.read_csv(GOOGLE_SHEET_CSV, header=None)
        booked = []
        for i in range(3, len(df)):
            row = df.iloc[i]
            sym = str(row[6]).strip().upper()
            if not sym or sym in ("NAN", "ETF", ""):
                continue
            try:
                units_sold = float(row[7])
                sell_price = float(row[8])
                # col 9 = pre-calculated sale proceeds from user's sheet
                proceeds   = float(row[9])
            except (ValueError, TypeError):
                continue
            if math.isnan(units_sold) or math.isnan(sell_price) or units_sold <= 0 or sell_price <= 0:
                continue
            # Use sheet's proceeds column if valid, else fallback to sell_price * units_sold
            if math.isnan(proceeds) or proceeds <= 0:
                proceeds = round(sell_price * units_sold, 2)
            booked.append({"nse_symbol": sym, "units_sold": units_sold, "sell_price": sell_price, "proceeds": proceeds})
        return booked
    except Exception:
        return []

BASE_TARGET = 3.0
STOP_LOSS   = 2.0

# NSE India requires a session cookie obtained by hitting the homepage first
_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

@st.cache_data(ttl=30)   # NSE price cached 30s — near real-time
def get_nse_price(nse_symbol):
    """Fetch live LTP from NSE India public API (~real-time, no login needed)."""
    try:
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=_NSE_HEADERS, timeout=5)
        url  = f"https://www.nseindia.com/api/quote-equity?symbol={nse_symbol}"
        resp = session.get(url, headers=_NSE_HEADERS, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            ltp  = data.get("priceInfo", {}).get("lastPrice")
            if ltp and float(ltp) > 0:
                return round(float(ltp), 2)
    except Exception:
        pass
    return None

@st.cache_data(ttl=60)
def get_live_price_yf(symbol):
    """Fallback: yfinance fast_info (~15 min delay)."""
    try:
        fi = yf.Ticker(symbol).fast_info
        p  = float(fi["last_price"])
        if p and p > 0:
            return round(p, 2)
    except Exception:
        pass
    try:
        df = yf.Ticker(symbol).history(period="1d", interval="1m")
        if not df.empty:
            return round(float(df["Close"].dropna().iloc[-1]), 2)
    except Exception:
        pass
    return None

@st.cache_data(ttl=600)
def get_price_data(symbol):
    df = yf.Ticker(symbol).history(period="3mo", interval="1d")
    return df[df["Close"] > 0].dropna(subset=["Close"])

def compute_signals(df, avg_cost=None):
    close   = df["Close"]
    rsi_val = round(float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]), 1)
    macd_o  = ta.trend.MACD(close)
    macd_v  = float(macd_o.macd().iloc[-1])
    macd_s  = float(macd_o.macd_signal().iloc[-1])
    ema9    = float(close.ewm(span=9).mean().iloc[-1])
    ema21   = float(close.ewm(span=21).mean().iloc[-1])
    ema200  = float(close.ewm(span=200).mean().iloc[-1])
    price   = round(float(close.iloc[-1]), 2)
    prev    = round(float(close.iloc[-2]), 2)
    day_chg = round(((price - prev) / prev) * 100, 2)
    low_52w = round(float(close.tail(252).min()), 2)
    score = 0
    if rsi_val < 40:    score += 1
    elif rsi_val > 65:  score -= 1
    if macd_v > macd_s: score += 1
    else:               score -= 1
    if ema9 > ema21:    score += 1
    else:               score -= 1
    if score >= 2:
        action = "BUY";  target_pct = 5.0 if score == 3 else BASE_TARGET
    elif score <= -2:
        action = "SELL"; target_pct = 0.0
    else:
        action = "HOLD"; target_pct = 0.0
    # ── Buy probability ───────────────────────────────────────
    score_base = {-3: 10, -2: 20, -1: 35, 0: 45, 1: 55, 2: 68, 3: 83}[score]
    rsi_bonus  = round((50 - rsi_val) * 0.3)      # oversold → higher; overbought → lower
    macd_bonus = 5 if macd_v > macd_s else -5
    # Extra ETF-specific factors
    deep_oversold  = 15 if rsi_val < 35 else 0                                          # deeply oversold
    below_avg      = 10 if (avg_cost and price < avg_cost) else 0                       # good to average down
    near_52w_low   = 10 if low_52w > 0 and (price - low_52w) / low_52w < 0.08 else 0  # within 8% of 52w low
    above_ema200   = -10 if price > ema200 * 1.15 else 0                               # >15% above 200 EMA = extended
    buy_prob = min(95, max(5, score_base + rsi_bonus + macd_bonus
                              + deep_oversold + below_avg + near_52w_low + above_ema200))
    return dict(price=price, day_chg=day_chg, rsi=rsi_val,
                score=score, action=action, target_pct=target_pct, buy_prob=buy_prob)

def portfolio_signal(technical_action, pnl_pct):
    # Partial booking: sell in tranches — never sell everything at once
    if pnl_pct >= 25:
        return "🔴 SELL 75% — Keep 25% riding"
    elif pnl_pct >= 18:
        return "🔴 SELL 50% — Book half, ride half"
    elif pnl_pct >= 12:
        return "🔴 SELL 25% — First partial profit"
    elif pnl_pct >= 8:
        return "🔴 SELL 25%" if technical_action in ("SELL", "HOLD") else "🟡 HOLD (trail SL)"
    elif pnl_pct >= 5:
        return "🔴 SELL NOW" if technical_action == "SELL" else "🟡 HOLD (protect gains)"
    elif pnl_pct >= 2:
        return "🟢 BUY MORE" if technical_action == "BUY" else "🟡 HOLD"
    elif pnl_pct >= 0:
        return "🟢 BUY MORE" if technical_action == "BUY" else "🟡 HOLD (near breakeven)"
    elif pnl_pct >= -5:
        return "🟢 BUY MORE (avg down)" if technical_action == "BUY" else "🟡 HOLD (wait)"
    else:
        return "🟢 BUY MORE (avg down)" if technical_action == "BUY" else "⚪ AVOID — Cut Loss?"

def trailing_sl(df, trail_pct=3.0):
    # Highest close in last 10 trading days → trail SL is 3% below that peak
    recent_high = round(float(df["Close"].tail(10).max()), 2)
    return round(recent_high * (1 - trail_pct / 100), 2)

def partial_qty(units, pnl_pct):
    # How many units to sell at each tranche
    if pnl_pct >= 25: return int(units * 0.75)
    if pnl_pct >= 18: return int(units * 0.50)
    if pnl_pct >= 12: return int(units * 0.25)
    if pnl_pct >= 8:  return int(units * 0.25)
    return 0

# ── Hide sidebar toggle arrow ────────────────────────────────
st.markdown('<style>[data-testid="collapsedControl"]{display:none}</style>', unsafe_allow_html=True)

# ── Main ──────────────────────────────────────────────────────
portfolio     = load_portfolio()
portfolio_map = {p["nse_symbol"]: p for p in portfolio}
profit_booked = load_profit_booked()
profit_booked_map = {b["nse_symbol"]: b for b in profit_booked}

st.title("📈 ETF Signal Dashboard")
st.caption(f"{datetime.now().strftime('%d %b %Y, %I:%M %p')} IST  |  Auto-refreshes every 5 min  |  🟢 NSE Live = real-time  🟡 YF ~15m = 15min delayed  ⚪ EOD = prev close")


# ── Portfolio Summary Cards ───────────────────────────────────
if portfolio:
    total_invested = 0.0
    total_current  = 0.0
    summary_items  = []
    for p in portfolio:
        df_p = get_price_data(p["yf_symbol"])
        if df_p.empty:
            continue
        nse_p   = get_nse_price(p["nse_symbol"])
        yf_p    = get_live_price_yf(p["yf_symbol"]) if not nse_p else None
        price_p = nse_p or yf_p or round(float(df_p["Close"].iloc[-1]), 2)
        invested  = round(p["avg_cost"] * p["units"], 2)
        current   = round(price_p * p["units"], 2)
        pnl_rs    = round(current - invested, 2)
        pnl_pct   = round((price_p - p["avg_cost"]) / p["avg_cost"] * 100, 2)
        total_invested += invested
        total_current  += current
        summary_items.append((p["label"], p["nse_symbol"], price_p, pnl_pct, pnl_rs, p["units"], p["avg_cost"]))

    # Realized profit from booked trades
    total_realized = 0.0
    realized_rows  = []
    for b in profit_booked:
        sym = b["nse_symbol"]
        # find avg_cost for this symbol from portfolio OR summary_items
        avg_c = portfolio_map[sym]["avg_cost"] if sym in portfolio_map else None
        if avg_c is None:
            # try summary_items
            for lbl, s, pr, pp, prs, u, av in summary_items:
                if s == sym:
                    avg_c = av
                    break
        realized_pnl = b["proceeds"]  # full sale proceeds reinvested by user
        total_realized += realized_pnl
realized_rows.append((sym, b["units_sold"], b["sell_price"], round(b["proceeds"], 2)))

    total_realized   = round(total_realized, 2)
    total_pnl        = round(total_current - total_invested, 2)
    total_pnl_pct    = round(total_pnl / total_invested * 100, 2) if total_invested else 0
    total_gain       = round(total_pnl + total_realized, 2)
    total_cost_basis = total_invested + sum(
        (portfolio_map[b["nse_symbol"]]["avg_cost"] if b["nse_symbol"] in portfolio_map else 0) * b["units_sold"]
        for b in profit_booked
    )
    total_gain_pct   = round(total_gain / total_cost_basis * 100, 2) if total_cost_basis else 0
    pnl_color    = "#28a745" if total_pnl >= 0 else "#dc3545"
    pnl_arrow    = "▲" if total_pnl >= 0 else "▼"
    gain_color   = "#28a745" if total_gain >= 0 else "#dc3545"
    gain_arrow   = "▲" if total_gain >= 0 else "▼"

    # Overall summary bar
    bg    = "#d4edda" if total_gain >= 0 else "#f8d7da"
    realized_html = (
        f'<div><div style="font-size:0.8rem;color:#555">Profit Booked (Reinvested)</div>'
        f'<div style="font-size:1.3rem;font-weight:700;color:#17a2b8">&#8377;{total_realized:,.0f}</div></div>'
    ) if total_realized else ""
    st.markdown(f'''
    <div style="background:{bg};padding:14px 20px;border-radius:10px;border-left:6px solid {gain_color};display:flex;gap:40px;flex-wrap:wrap;margin-bottom:10px">
        <div><div style="font-size:0.8rem;color:#555">Total Invested</div>
             <div style="font-size:1.3rem;font-weight:700">&#8377;{total_invested:,.0f}</div></div>
        <div><div style="font-size:0.8rem;color:#555">Current Value</div>
             <div style="font-size:1.3rem;font-weight:700">&#8377;{total_current:,.0f}</div></div>
        <div><div style="font-size:0.8rem;color:#555">Unrealised P&amp;L</div>
             <div style="font-size:1.3rem;font-weight:700;color:{pnl_color}">{pnl_arrow} &#8377;{abs(total_pnl):,.0f} ({abs(total_pnl_pct)}%)</div></div>
        {realized_html}
        <div><div style="font-size:0.8rem;color:#555">Total Gain (Realised+Unrealised)</div>
             <div style="font-size:1.3rem;font-weight:700;color:{gain_color}">{gain_arrow} &#8377;{abs(total_gain):,.0f} ({abs(total_gain_pct)}%)</div></div>
        <div><div style="font-size:0.8rem;color:#555">Holdings</div>
             <div style="font-size:1.3rem;font-weight:700">{len(summary_items)} ETFs</div></div>
    </div>
    ''', unsafe_allow_html=True)

    # Profit booked detail table
    if realized_rows:
        with st.expander(f"📋 Profit Booked Details — ₹{total_realized:,.0f} reinvested", expanded=False):
            df_real = pd.DataFrame(realized_rows, columns=["Symbol", "Units Sold", "Sell Price (₹)", "Proceeds Reinvested (₹)"])
            st.dataframe(df_real, hide_index=True, use_container_width=True)

    # Per-ETF mini cards
    cols_s = st.columns(len(summary_items)) if len(summary_items) <= 4 else st.columns(4)
    for i, (label, sym, price_p, pnl_pct, pnl_rs, units, avg) in enumerate(summary_items):
        c = "#28a745" if pnl_pct >= 0 else "#dc3545"
        a = "▲" if pnl_pct >= 0 else "▼"
        with cols_s[i % len(cols_s)]:
            st.markdown(f'''
            <div style="background:#f8f9fa;border-radius:8px;padding:10px 14px;border-top:4px solid {c};margin-bottom:4px">
                <div style="font-size:0.75rem;color:#666">{sym}</div>
                <div style="font-size:1rem;font-weight:700">&#8377;{price_p}</div>
                <div style="font-size:0.85rem;color:{c};font-weight:600">{a} {abs(pnl_pct)}% &nbsp;&middot;&nbsp; &#8377;{abs(pnl_rs):,.0f}</div>
                <div style="font-size:0.75rem;color:#888">{units} units @ &#8377;{avg}</div>
            </div>
            ''', unsafe_allow_html=True)

st.divider()

# Build rows
rows = []
for etf in ALL_ETFS:
    df = get_price_data(etf["yf_symbol"])
    if df.empty:
        continue
    nse        = etf["nse_symbol"]
    avg_cost   = portfolio_map[nse]["avg_cost"] if nse in portfolio_map else None
    sig        = compute_signals(df, avg_cost=avg_cost)
    nse_price  = get_nse_price(etf["nse_symbol"])
    yf_price   = get_live_price_yf(etf["yf_symbol"]) if not nse_price else None
    price      = nse_price or yf_price or sig["price"]
    price_src  = "🟢 NSE Live" if nse_price else ("🟡 YF ~15m" if yf_price else "⚪ EOD")
    sl_price  = round(price * (1 - STOP_LOSS / 100), 2)
    tgt_price = round(price * (1 + sig["target_pct"] / 100), 2) if sig["target_pct"] > 0 else None
    day_str   = f"{'+' if sig['day_chg']>=0 else ''}{sig['day_chg']}%"

    in_portfolio = nse in portfolio_map
    if in_portfolio:
        p       = portfolio_map[nse]
        avg     = p["avg_cost"]
        units   = p["units"]
        pnl_pct = round((price - avg) / avg * 100, 2)
        pnl_rs  = round((price - avg) * units, 0)
        signal  = portfolio_signal(sig["action"], pnl_pct)
        trail   = trailing_sl(df)
        sell_q  = partial_qty(units, pnl_pct)
        rows.append({
            "ETF":          etf["label"],
            "Symbol":       nse,
            "Risk":         etf["risk"],
            "Signal":       signal,
            "Sell Qty":     sell_q if sell_q > 0 else "—",
            "Score":        f"{sig['score']}/3",
            "Price (Rs.)":  price,
            "Today %":      day_str,
            "RSI":          sig["rsi"],
            "My Units":     units,
            "Avg Cost":     avg,
            "P&L %":        f"{'+' if pnl_pct>=0 else ''}{pnl_pct}%",
            "P&L Rs.":      f"{'+' if pnl_rs>=0 else ''}{pnl_rs:,.0f}",
            "Trail SL":     trail,
            "Src":          price_src,
            "Buy Prob %":   sig["buy_prob"],
            "Stop Loss":    sl_price,
            "Target":       tgt_price if tgt_price else "—",
        })
    else:
        tech_icon = {"BUY": "🟢 BUY", "SELL": "🔴 SELL", "HOLD": "🟡 HOLD"}.get(sig["action"])
        rows.append({
            "ETF":          etf["label"],
            "Symbol":       nse,
            "Risk":         etf["risk"],
            "Signal":       tech_icon,
            "Sell Qty":     "—",
            "Score":        f"{sig['score']}/3",
            "Price (Rs.)":  price,
            "Today %":      day_str,
            "RSI":          sig["rsi"],
            "My Units":     0.0,
            "Avg Cost":     0.0,
            "P&L %":        "—",
            "P&L Rs.":      "—",
            "Trail SL":     "—",
            "Src":          price_src,
            "Buy Prob %":   sig["buy_prob"],
            "Stop Loss":    sl_price,
            "Target":       tgt_price if tgt_price else "—",
        })

df_table = pd.DataFrame(rows)

# Styling
def color_signal(val):
    v = str(val)
    if "BUY" in v:              return "color:#28a745;font-weight:700"
    if "SELL" in v or "BOOK" in v or "EXIT" in v: return "color:#dc3545;font-weight:700"
    if "HOLD" in v or "WAIT" in v: return "color:#fd7e14;font-weight:700"
    return "color:#6c757d"

def color_pnl(val):
    v = str(val)
    if v == "—": return ""
    return "color:#28a745;font-weight:600" if "+" in v else "color:#dc3545;font-weight:600"

def color_risk(val):
    m = {"Stable": "#28a745", "Aggressive": "#fd7e14", "Very Aggressive": "#dc3545"}
    return f"color:{m.get(val,'#333')};font-weight:600"

def color_prob(val):
    try:
        v = int(val)
        if v >= 70:   return "color:#28a745;font-weight:700"   # green
        elif v >= 50: return "color:#fd7e14;font-weight:700"   # orange
        else:         return "color:#dc3545;font-weight:700"   # red
    except: return ""

def color_src(val):
    v = str(val)
    if "NSE" in v:  return "color:#28a745;font-weight:600"
    if "YF"  in v:  return "color:#fd7e14;font-weight:600"
    return "color:#6c757d"

def color_trail_sl(val):
    if str(val) == "—": return ""
    return "color:#e65100;font-weight:600"  # orange-red for trailing SL

def color_sell_qty(val):
    if str(val) == "—": return ""
    return "color:#dc3545;font-weight:700"

styled = (
    df_table.style
    .map(color_signal,   subset=["Signal"])
    .map(color_sell_qty, subset=["Sell Qty"])
    .map(color_pnl,      subset=["P&L %", "P&L Rs."])
    .map(color_risk,     subset=["Risk"])
    .map(color_prob,     subset=["Buy Prob %"])
    .map(color_trail_sl, subset=["Trail SL"])
    .map(color_src,      subset=["Src"])
    .set_properties(**{"font-size": "0.88rem"})
)

st.caption("💡 **Signal** = partial profit booking at 12% / 18% / 25% P&L.  **Sell Qty** = units to sell at this tranche.  **Trail SL** = 3% below 10-day high — exit if price falls here.")
st.dataframe(styled, hide_index=True, use_container_width=True, height=380)

# ── Portfolio source info ─────────────────────────────────────
st.divider()
st.info(
    "📊 Portfolio is loaded automatically from your **[Google Sheet]("
    "https://docs.google.com/spreadsheets/d/1irjEYSjtaH60N_AcmPACxPvAbEmQwQzhgAYsPzSb6Iw/edit)"
    "** every 60 seconds. Edit the sheet and the dashboard will refresh automatically.",
    icon="🔄",
)

st.divider()
st.caption("For informational use only. Not financial advice.")
