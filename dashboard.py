import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import json
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="ETF Signals", page_icon="📈",
                   layout="centered", initial_sidebar_state="expanded")

st_autorefresh(interval=300_000, key="autorefresh")

# ── Portfolio file helpers ────────────────────────────────────
PORTFOLIO_FILE = "portfolio.json"

DEFAULT_PORTFOLIO = [
    {"label": "HDFC Smallcap 250 ETF", "nse_symbol": "HDFCSML250",
     "yf_symbol": "HDFCSML250.NS", "units": 131, "avg_cost": 150.96},
    {"label": "PSU Bank BeES", "nse_symbol": "PSUBNKBEES",
     "yf_symbol": "PSUBNKBEES.NS", "units": 364, "avg_cost": 97.51},
]

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PORTFOLIO

def save_portfolio(data):
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Signal logic ─────────────────────────────────────────────
BASE_TARGET = 3.0
STOP_LOSS   = 2.0

@st.cache_data(ttl=600)
def get_price_data(symbol):
    df = yf.Ticker(symbol).history(period="3mo", interval="1d")
    return df[df["Close"] > 0].dropna(subset=["Close"])

def compute_signals(df):
    close   = df["Close"]
    rsi_val = round(float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]), 1)
    macd_o  = ta.trend.MACD(close)
    macd_v  = float(macd_o.macd().iloc[-1])
    macd_s  = float(macd_o.macd_signal().iloc[-1])
    ema9    = float(close.ewm(span=9).mean().iloc[-1])
    ema21   = float(close.ewm(span=21).mean().iloc[-1])
    price   = round(float(close.iloc[-1]), 2)
    prev    = round(float(close.iloc[-2]), 2)
    day_chg = round(((price - prev) / prev) * 100, 2)

    score = 0
    if rsi_val < 40:   score += 1
    elif rsi_val > 65: score -= 1
    if macd_v > macd_s: score += 1
    else:               score -= 1
    if ema9 > ema21:    score += 1
    else:               score -= 1

    if score >= 2:
        action, color = "BUY", "green"
        target_pct = 5.0 if score == 3 else BASE_TARGET
    elif score <= -2:
        action, color = "SELL", "red"
        target_pct = 0.0
    else:
        action, color = "HOLD", "orange"
        target_pct = 0.0

    return dict(price=price, day_chg=day_chg, rsi=rsi_val,
                score=score, action=action, color=color, target_pct=target_pct)

# ── Sidebar: Edit Portfolio ───────────────────────────────────
with st.sidebar:
    st.header("My Portfolio")
    portfolio = load_portfolio()

    updated = []
    remove_idx = None
    for i, p in enumerate(portfolio):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{p['label']}**")
        with c2:
            if st.button("🗑", key=f"rm_{i}", help="Remove this ETF"):
                remove_idx = i
        units    = st.number_input("Units held",     value=float(p["units"]),    min_value=0.0,             key=f"units_{i}")
        avg_cost = st.number_input("Avg cost (Rs.)", value=float(p["avg_cost"]), min_value=0.0, step=0.01,  key=f"avg_{i}")
        updated.append({**p, "units": units, "avg_cost": avg_cost})
        st.divider()

    if remove_idx is not None:
        updated.pop(remove_idx)
        save_portfolio(updated)
        st.rerun()

    # ── Add new ETF ──────────────────────────────────────
    with st.expander("➕ Add new ETF"):
        new_label  = st.text_input("Name",              placeholder="e.g. Nifty BeES")
        new_nse    = st.text_input("NSE Symbol",        placeholder="e.g. NIFTYBEES")
        new_units  = st.number_input("Units held",      min_value=0.0, value=0.0, key="new_units")
        new_avg    = st.number_input("Avg cost (Rs.)",  min_value=0.0, value=0.0, step=0.01, key="new_avg")
        if st.button("Add to Portfolio", use_container_width=True):
            if new_label and new_nse:
                yf_sym = new_nse.upper().strip() + ".NS"
                updated.append({"label": new_label, "nse_symbol": new_nse.upper().strip(),
                                 "yf_symbol": yf_sym, "units": new_units, "avg_cost": new_avg})
                save_portfolio(updated)
                st.success(f"Added {new_label}!")
                st.rerun()
            else:
                st.warning("Enter Name and NSE Symbol.")

    if st.button("💾 Save Changes", use_container_width=True, type="primary"):
        if remove_idx is None:
            save_portfolio(updated)
            st.success("Saved!")
            st.rerun()

    st.divider()
    st.caption("Auto-refreshes every 5 min")
    st.caption(f"Last loaded: {datetime.now().strftime('%I:%M %p')}")

# ── Main Dashboard ────────────────────────────────────────────
portfolio = load_portfolio()

st.title("📈 ETF Signals")
st.caption(f"{datetime.now().strftime('%d %b %Y, %I:%M %p')} IST")

if st.button("🔄 Refresh", type="primary"):
    st.cache_data.clear()
    st.rerun()

st.divider()

for p in portfolio:
    df = get_price_data(p["yf_symbol"])
    if df.empty:
        st.error(f"No data for {p['nse_symbol']}")
        continue

    sig      = compute_signals(df)
    price    = sig["price"]
    avg      = p["avg_cost"]
    units    = p["units"]
    pnl_pct  = round((price - avg) / avg * 100, 2)
    pnl_rs   = round((price - avg) * units, 0)
    sl_price = round(price * (1 - STOP_LOSS / 100), 2)
    tgt_price = round(price * (1 + sig["target_pct"] / 100), 2) if sig["target_pct"] > 0 else None
    pnl_sign = "+" if pnl_pct >= 0 else ""
    day_sign = "+" if sig["day_chg"] >= 0 else ""

    col1, col2 = st.columns([2, 1])

    with col1:
        action_badge = {"BUY": "🟢 BUY", "SELL": "🔴 SELL", "HOLD": "🟡 HOLD"}.get(sig["action"])
        st.markdown(f"### {p['label']}")
        st.markdown(f"**{action_badge}** &nbsp; Score: {sig['score']}/3 &nbsp; | &nbsp; RSI: {sig['rsi']}")
        st.markdown(f"**Rs. {price}** &nbsp; <span style='color:gray;font-size:0.9rem'>({day_sign}{sig['day_chg']}% today)</span>", unsafe_allow_html=True)

    with col2:
        pnl_color = "green" if pnl_pct >= 0 else "red"
        st.markdown(f"<div style='text-align:right'>"
                    f"<div style='font-size:0.85rem;color:#666'>Your P&L</div>"
                    f"<div style='font-size:1.3rem;font-weight:700;color:{pnl_color}'>{pnl_sign}{pnl_pct}%</div>"
                    f"<div style='font-size:1rem;color:{pnl_color}'>Rs. {pnl_sign}{pnl_rs:,.0f}</div>"
                    f"</div>", unsafe_allow_html=True)

    # Compact info row
    tgt_str = f"Rs. {tgt_price}" if tgt_price else "—"
    st.markdown(
        f"<div style='background:#f8f9fa;padding:8px 12px;border-radius:8px;font-size:0.88rem;'>"
        f"Avg cost: <b>Rs. {avg}</b> &nbsp;|&nbsp; "
        f"Stop Loss: <b>Rs. {sl_price}</b> &nbsp;|&nbsp; "
        f"Target: <b>{tgt_str}</b> &nbsp;|&nbsp; "
        f"Units: <b>{units}</b>"
        f"</div>", unsafe_allow_html=True)

    st.divider()

# ── Suggested ETFs ───────────────────────────────────────────
st.divider()

SUGGESTED = [
    {"label": "Nifty BeES",    "nse_symbol": "NIFTYBEES",  "yf_symbol": "NIFTYBEES.NS",
     "risk": "Stable",         "risk_color": "#28a745"},
    {"label": "Gold BeES",     "nse_symbol": "GOLDBEES",   "yf_symbol": "GOLDBEES.NS",
     "risk": "Stable",         "risk_color": "#28a745"},
    {"label": "Bank BeES",     "nse_symbol": "BANKBEES",   "yf_symbol": "BANKBEES.NS",
     "risk": "Aggressive",     "risk_color": "#fd7e14"},
    {"label": "IT BeES",       "nse_symbol": "ITBEES",     "yf_symbol": "ITBEES.NS",
     "risk": "Aggressive",     "risk_color": "#fd7e14"},
    {"label": "Junior BeES",   "nse_symbol": "JUNIORBEES", "yf_symbol": "JUNIORBEES.NS",
     "risk": "Very Aggressive","risk_color": "#dc3545"},
    {"label": "Momentum 100",  "nse_symbol": "MOM100",     "yf_symbol": "MOM100.NS",
     "risk": "Very Aggressive","risk_color": "#dc3545"},
]

portfolio_symbols = [p["nse_symbol"] for p in load_portfolio()]

scols = st.columns(3)
for i, s in enumerate(SUGGESTED):
    with scols[i % 3]:
        sdf = get_price_data(s["yf_symbol"])
        if sdf.empty:
            st.warning(f"No data: {s['nse_symbol']}")
            continue
        ssig   = compute_signals(sdf)
        sbadge = {"BUY": "🟢 BUY", "SELL": "🔴 SELL", "HOLD": "🟡 HOLD"}.get(ssig["action"])
        sday   = f"{'+' if ssig['day_chg']>=0 else ''}{ssig['day_chg']}%"
        already = s["nse_symbol"] in portfolio_symbols

        st.markdown(
            f"<div style='border:1px solid #dee2e6;border-radius:10px;padding:12px;margin-bottom:8px'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:4px'>"
            f"<span style='font-weight:700'>{s['label']}</span>"
            f"<span style='background:{s['risk_color']};color:#fff;font-size:0.68rem;"
            f"font-weight:700;padding:2px 7px;border-radius:20px'>{s['risk']}</span>"
            f"</div>"
            f"<div style='font-size:0.8rem;color:#888;margin-bottom:4px'>{s['nse_symbol']}</div>"
            f"<div>{sbadge} &nbsp; Score: {ssig['score']}/3 &nbsp; RSI: {ssig['rsi']}</div>"
            f"<div style='font-size:1.05rem;font-weight:600;margin:3px 0'>Rs. {ssig['price']} "
            f"<span style='font-size:0.82rem;color:gray'>({sday})</span></div>"
            f"</div>",
            unsafe_allow_html=True)

        if not already:
            with st.expander("Add to Portfolio"):
                with st.form(key=f"add_{s['nse_symbol']}"):
                    su = st.number_input("Units", min_value=0.0, value=0.0, key=f"su_{s['nse_symbol']}")
                    sa = st.number_input("Avg cost (Rs.)", min_value=0.0, value=float(ssig["price"]), step=0.01, key=f"sa_{s['nse_symbol']}")
                    if st.form_submit_button("Add", use_container_width=True):
                        cur = load_portfolio()
                        cur.append({"label": s["label"], "nse_symbol": s["nse_symbol"],
                                    "yf_symbol": s["yf_symbol"], "units": su, "avg_cost": sa})
                        save_portfolio(cur)
                        st.rerun()

st.divider()
st.caption("For informational use only. Not financial advice.")
