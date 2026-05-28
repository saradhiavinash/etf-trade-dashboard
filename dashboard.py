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

# ── Portfolio helpers ─────────────────────────────────────────
DEFAULT_PORTFOLIO = [
    {"label": "HDFC Smallcap 250 ETF", "nse_symbol": "HDFCSML250",
     "yf_symbol": "HDFCSML250.NS", "units": 131, "avg_cost": 150.96},
    {"label": "PSU Bank BeES", "nse_symbol": "PSUBNKBEES",
     "yf_symbol": "PSUBNKBEES.NS", "units": 364, "avg_cost": 97.51},
]

# Portfolio lives in session_state — persists until browser window closes
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = DEFAULT_PORTFOLIO

def load_portfolio():
    return st.session_state["portfolio"]

def save_portfolio(data):
    st.session_state["portfolio"] = data

# ── All ETFs catalog ──────────────────────────────────────────
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
    """Smart signal for ETFs you own — combines P&L with technical."""
    if pnl_pct >= 15:
        return "🔴 BOOK PROFIT" if technical_action in ("SELL", "HOLD") else "🟡 HOLD (trailing SL)"
    elif pnl_pct >= 8:
        return "🔴 SELL NOW"   if technical_action == "SELL" else "🟡 HOLD (protect gains)"
    elif pnl_pct >= 3:
        return "🟢 BUY MORE"   if technical_action == "BUY"  else "🟡 HOLD"
    elif pnl_pct >= 0:
        return "🟢 BUY MORE"   if technical_action == "BUY"  else "🟡 HOLD (near breakeven)"
    else:  # loss
        return "🟡 HOLD (wait)" if technical_action == "BUY"  else "⚪ WAIT / AVOID AVERAGING"

# ── Hide sidebar toggle arrow ────────────────────────────────
st.markdown('<style>[data-testid="collapsedControl"]{display:none}</style>', unsafe_allow_html=True)

# ── Main ──────────────────────────────────────────────────────
portfolio     = load_portfolio()
portfolio_map = {p["nse_symbol"]: p for p in portfolio}

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

    total_pnl    = round(total_current - total_invested, 2)
    total_pnl_pct = round((total_current - total_invested) / total_invested * 100, 2) if total_invested else 0
    pnl_color    = "#28a745" if total_pnl >= 0 else "#dc3545"
    pnl_arrow    = "▲" if total_pnl >= 0 else "▼"

    # Overall summary bar
    bg    = "#d4edda" if total_pnl >= 0 else "#f8d7da"
    st.markdown(f'''
    <div style="background:{bg};padding:14px 20px;border-radius:10px;border-left:6px solid {pnl_color};display:flex;gap:40px;flex-wrap:wrap;margin-bottom:10px">
        <div><div style="font-size:0.8rem;color:#555">Total Invested</div>
             <div style="font-size:1.3rem;font-weight:700">&#8377;{total_invested:,.0f}</div></div>
        <div><div style="font-size:0.8rem;color:#555">Current Value</div>
             <div style="font-size:1.3rem;font-weight:700">&#8377;{total_current:,.0f}</div></div>
        <div><div style="font-size:0.8rem;color:#555">Overall P&amp;L</div>
             <div style="font-size:1.3rem;font-weight:700;color:{pnl_color}">{pnl_arrow} &#8377;{abs(total_pnl):,.0f} ({abs(total_pnl_pct)}%)</div></div>
        <div><div style="font-size:0.8rem;color:#555">Holdings</div>
             <div style="font-size:1.3rem;font-weight:700">{len(summary_items)} ETFs</div></div>
    </div>
    ''', unsafe_allow_html=True)

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
        p        = portfolio_map[nse]
        avg      = p["avg_cost"]
        units    = p["units"]
        pnl_pct  = round((price - avg) / avg * 100, 2)
        pnl_rs   = round((price - avg) * units, 0)
        signal   = portfolio_signal(sig["action"], pnl_pct)
        rows.append({
            "ETF":          etf["label"],
            "Symbol":       nse,
            "Risk":         etf["risk"],
            "Signal":       signal,
            "Score":        f"{sig['score']}/3",
            "Price (Rs.)":  price,
            "Today %":      day_str,
            "RSI":          sig["rsi"],
            "My Units":     units,
            "Avg Cost":     avg,
            "P&L %":        f"{'+' if pnl_pct>=0 else ''}{pnl_pct}%",
            "P&L Rs.":      f"{'+' if pnl_rs>=0 else ''}{pnl_rs:,.0f}",
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
            "Score":        f"{sig['score']}/3",
            "Price (Rs.)":  price,
            "Today %":      day_str,
            "RSI":          sig["rsi"],
            "My Units":     0.0,
            "Avg Cost":     0.0,
            "P&L %":        "—",
            "P&L Rs.":      "—",
            "Src":          price_src,
            "Buy Prob %":   sig["buy_prob"],
            "Stop Loss":    sl_price,
            "Target":       tgt_price if tgt_price else "—",
        })

df_table = pd.DataFrame(rows)

# Styling
def color_signal(val):
    v = str(val)
    if "BUY MORE" in v or v == "🟢 BUY":   return "color:#28a745;font-weight:700"
    if "SELL" in v or "BOOK" in v:          return "color:#dc3545;font-weight:700"
    if "HOLD" in v or "WAIT" in v:          return "color:#fd7e14;font-weight:700"
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

styled = (
    df_table.style
    .map(color_signal, subset=["Signal"])
    .map(color_pnl,    subset=["P&L %", "P&L Rs."])
    .map(color_risk,   subset=["Risk"])
    .map(color_prob,   subset=["Buy Prob %"])
    .map(color_src,    subset=["Src"])
    .set_properties(**{"font-size": "0.88rem"})
)

st.caption("💡 **Signal** for your portfolio ETFs is based on your P&L + technical score combined. For others it's pure technical.")
st.dataframe(styled, hide_index=True, use_container_width=True, height=380)

# ── Inline portfolio editor below table ───────────────────────
st.divider()
st.subheader("✏️ Edit My Portfolio")
st.caption("Change units or avg cost below and hit Save.")

edit_rows = []
for etf in ALL_ETFS:
    p = portfolio_map.get(etf["nse_symbol"])
    edit_rows.append({
        "In Portfolio": etf["nse_symbol"] in portfolio_map,
        "ETF":          etf["label"],
        "Symbol":       etf["nse_symbol"],
        "My Units":     float(p["units"])    if p else 0.0,
        "Avg Cost (Rs.)": float(p["avg_cost"]) if p else 0.0,
    })

edited = st.data_editor(
    pd.DataFrame(edit_rows),
    hide_index=True,
    use_container_width=True,
    column_config={
        "In Portfolio":   st.column_config.CheckboxColumn("In Portfolio"),
        "ETF":            st.column_config.TextColumn("ETF",    disabled=True),
        "Symbol":         st.column_config.TextColumn("Symbol", disabled=True),
        "My Units":       st.column_config.NumberColumn("My Units",       min_value=0.0, step=1.0,    format="%.0f"),
        "Avg Cost (Rs.)": st.column_config.NumberColumn("Avg Cost (Rs.)", min_value=0.0, step=0.01,   format="%.2f"),
    },
    key="portfolio_editor",
)

if st.button("💾 Apply Portfolio Changes", type="primary"):
    new_portfolio = []
    for _, row in edited.iterrows():
        if row["In Portfolio"] and row["My Units"] > 0:
            match = next((e for e in ALL_ETFS if e["nse_symbol"] == row["Symbol"]), None)
            yf_sym = match["yf_symbol"] if match else row["Symbol"] + ".NS"
            new_portfolio.append({
                "label":      row["ETF"],
                "nse_symbol": row["Symbol"],
                "yf_symbol":  yf_sym,
                "units":      float(row["My Units"]),
                "avg_cost":   float(row["Avg Cost (Rs.)"])
            })
    save_portfolio(new_portfolio)
    st.success(f"✅ Portfolio updated ({len(new_portfolio)} ETFs) — active until window closes.")
    st.rerun()

# ── File Load / Save ─────────────────────────────────────────
st.divider()
st.subheader("📂 Load / Save Portfolio File")
col_load, col_save = st.columns(2)

with col_load:
    st.caption("📥 Load from JSON file (from your device)")
    uploaded = st.file_uploader("Choose portfolio JSON", type="json", label_visibility="collapsed")
    if uploaded:
        try:
            data = json.load(uploaded)
            save_portfolio(data)
            st.success(f"✅ Loaded {len(data)} ETFs from file!")
            st.rerun()
        except Exception as e:
            st.error(f"Invalid file: {e}")

with col_save:
    st.caption("📤 Save current portfolio to JSON file")
    portfolio_json = json.dumps(load_portfolio(), indent=2)
    st.download_button(
        label="⬇️ Download portfolio.json",
        data=portfolio_json,
        file_name="portfolio.json",
        mime="application/json",
        use_container_width=True,
    )

st.divider()
st.caption("For informational use only. Not financial advice.")
