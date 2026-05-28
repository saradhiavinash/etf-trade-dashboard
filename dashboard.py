import streamlit as st
import pandas as pd
import yfinance as yf
import ta
import json
import os
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="ETF Signals", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

st_autorefresh(interval=300_000, key="autorefresh")

# ── Portfolio helpers ─────────────────────────────────────────
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
    return dict(price=price, day_chg=day_chg, rsi=rsi_val,
                score=score, action=action, target_pct=target_pct)

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

# ── Sidebar: sidebar collapsed by default on mobile ──────────
with st.sidebar:
    st.header("My Portfolio")
    portfolio = load_portfolio()

    updated = []
    remove_idx = None
    for i, p in enumerate(portfolio):
        c1, c2 = st.columns([4, 1])
        with c1: st.markdown(f"**{p['label']}**")
        with c2:
            if st.button("🗑", key=f"rm_{i}", help="Remove"): remove_idx = i
        units    = st.number_input("Units",         value=float(p["units"]),    min_value=0.0,            key=f"u_{i}")
        avg_cost = st.number_input("Avg cost (Rs.)",value=float(p["avg_cost"]), min_value=0.0, step=0.01, key=f"a_{i}")
        updated.append({**p, "units": units, "avg_cost": avg_cost})
        st.divider()

    if remove_idx is not None:
        updated.pop(remove_idx)
        save_portfolio(updated)
        st.rerun()

    with st.expander("➕ Add new ETF"):
        new_label = st.text_input("Name",            placeholder="e.g. Nifty BeES")
        new_nse   = st.text_input("NSE Symbol",      placeholder="e.g. NIFTYBEES")
        new_units = st.number_input("Units",          min_value=0.0, value=0.0, key="nu")
        new_avg   = st.number_input("Avg cost (Rs.)", min_value=0.0, value=0.0, step=0.01, key="na")
        if st.button("Add to Portfolio", use_container_width=True):
            if new_label and new_nse:
                updated.append({"label": new_label, "nse_symbol": new_nse.upper().strip(),
                                 "yf_symbol": new_nse.upper().strip() + ".NS",
                                 "units": new_units, "avg_cost": new_avg})
                save_portfolio(updated)
                st.rerun()
            else:
                st.warning("Enter Name and NSE Symbol.")

    if st.button("💾 Save Changes", use_container_width=True, type="primary"):
        if remove_idx is None:
            save_portfolio(updated)
            st.success("Saved!")
            st.rerun()

    st.divider()
    st.caption(f"Auto-refreshes every 5 min | {datetime.now().strftime('%I:%M %p')}")

# ── Main ──────────────────────────────────────────────────────
portfolio     = load_portfolio()
portfolio_map = {p["nse_symbol"]: p for p in portfolio}

st.title("📈 ETF Signal Dashboard")
st.caption(f"{datetime.now().strftime('%d %b %Y, %I:%M %p')} IST  |  Auto-refreshes every 5 min")
st.divider()

# Build rows
rows = []
for etf in ALL_ETFS:
    df = get_price_data(etf["yf_symbol"])
    if df.empty:
        continue
    sig   = compute_signals(df)
    price = sig["price"]
    nse   = etf["nse_symbol"]
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

styled = (
    df_table.style
    .map(color_signal, subset=["Signal"])
    .map(color_pnl,    subset=["P&L %", "P&L Rs."])
    .map(color_risk,   subset=["Risk"])
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

if st.button("💾 Save Portfolio Changes", type="primary"):
    new_portfolio = []
    for _, row in edited.iterrows():
        if row["In Portfolio"] and row["My Units"] > 0:
            # find yf_symbol from ALL_ETFS
            match = next((e for e in ALL_ETFS if e["nse_symbol"] == row["Symbol"]), None)
            yf_sym = match["yf_symbol"] if match else row["Symbol"] + ".NS"
            new_portfolio.append({
                "label":      row["ETF"],
                "nse_symbol": row["Symbol"],
                "yf_symbol":  yf_sym,
                "units":      float(row["My Units"]),
                "avg_cost":   float(row["Avg Cost (Rs.)"]),
            })
    save_portfolio(new_portfolio)
    st.success(f"Saved {len(new_portfolio)} ETFs to portfolio!")
    st.rerun()

st.divider()
st.caption("For informational use only. Not financial advice.")
