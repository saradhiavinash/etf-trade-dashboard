import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import yfinance as yf
import ta

st.set_page_config(page_title="ETF Trade Signals", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.buy-box  { background:#d4edda; border-left:6px solid #28a745; padding:20px; border-radius:10px; }
.sell-box { background:#f8d7da; border-left:6px solid #dc3545; padding:20px; border-radius:10px; }
.hold-box { background:#fff3cd; border-left:6px solid #ffc107; padding:20px; border-radius:10px; }
.big-signal { font-size:2.5rem; font-weight:800; margin:0; }
.price-tag  { font-size:1.8rem; font-weight:700; }
.label-tag  { font-size:0.9rem; color:#555; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)

PORTFOLIO = [
    {"label": "HDFC Smallcap 250 ETF", "nse_symbol": "HDFCSML250", "yf_symbol": "HDFCSML250.NS",
     "invested": 19776.68, "units": 131, "avg_cost": round(19776.68/131, 2)},
    {"label": "PSU Bank BeES", "nse_symbol": "PSUBNKBEES", "yf_symbol": "PSUBNKBEES.NS",
     "invested": 35494.57, "units": 364, "avg_cost": round(35494.57/364, 2)},
]

BASE_TARGET = 3.0
STOP_LOSS   = 2.0

@st.cache_data(ttl=600)
def get_data(symbol):
    df = yf.Ticker(symbol).history(period="3mo", interval="1d")
    return df[df["Close"] > 0].dropna(subset=["Close"])

def compute_signals(df):
    close   = df["Close"]
    rsi_val = round(float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]), 1)
    macd_o  = ta.trend.MACD(close)
    macd_v  = float(macd_o.macd().iloc[-1])
    macd_s  = float(macd_o.macd_signal().iloc[-1])
    ema9    = round(float(close.ewm(span=9).mean().iloc[-1]), 2)
    ema21   = round(float(close.ewm(span=21).mean().iloc[-1]), 2)
    price   = round(float(close.iloc[-1]), 2)
    prev    = round(float(close.iloc[-2]), 2)
    day_chg = round(((price - prev) / prev) * 100, 2)

    score = 0
    reasons = []

    if rsi_val < 40:
        score += 1
        reasons.append(f"RSI {rsi_val} - Oversold. Good to BUY")
    elif rsi_val > 65:
        score -= 1
        reasons.append(f"RSI {rsi_val} - Overbought. Consider SELLING")
    else:
        reasons.append(f"RSI {rsi_val} - Neutral zone")

    if macd_v > macd_s:
        score += 1
        reasons.append("MACD above signal line - Bullish momentum")
    else:
        score -= 1
        reasons.append("MACD below signal line - Bearish momentum")

    if ema9 > ema21:
        score += 1
        reasons.append("Short-term trend is UP (EMA9 > EMA21)")
    else:
        score -= 1
        reasons.append("Short-term trend is DOWN (EMA9 < EMA21)")

    if score >= 2:
        action, box = "BUY", "buy-box"
        target_pct = 5.0 if score == 3 else BASE_TARGET
    elif score <= -2:
        action, box = "SELL / WAIT", "sell-box"
        target_pct = 0.0
    else:
        action, box = "HOLD", "hold-box"
        target_pct = 0.0

    return dict(price=price, day_chg=day_chg, rsi=rsi_val, ema9=ema9, ema21=ema21,
                score=score, action=action, box=box, target_pct=target_pct, reasons=reasons)

now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
st.title("ETF Trade Signal Dashboard")
st.caption(f"As of: {now_str} IST  |  Prices from NSE via yfinance  |  Cache: 10 min")

if st.button("Refresh Now", type="primary"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")

cols = st.columns(len(PORTFOLIO))
for col, p in zip(cols, PORTFOLIO):
    with col:
        df = get_data(p["yf_symbol"])
        if df.empty:
            st.error(f"No data for {p['label']}")
            continue

        sig       = compute_signals(df)
        price     = sig["price"]
        avg       = p["avg_cost"]
        pnl_pct   = round((price - avg) / avg * 100, 2)
        pnl_rs    = round((price - avg) * p["units"], 0)
        sl_price  = round(price * (1 - STOP_LOSS / 100), 2)
        tgt_price = round(price * (1 + sig["target_pct"] / 100), 2) if sig["target_pct"] > 0 else None
        pnl_color = "green" if pnl_pct >= 0 else "red"
        action_tag = {"BUY": "[BUY]", "SELL / WAIT": "[SELL]", "HOLD": "[HOLD]"}[sig["action"]]

        st.markdown(f"""
        <div class="{sig['box']}">
            <div class="label-tag">{p['label']}  -  {p['nse_symbol']}</div>
            <div class="big-signal">{action_tag} {sig['action']}</div>
            <div class="price-tag">Rs. {price}</div>
            <div style="margin-top:6px; font-size:0.95rem">Today change: <b>{sig['day_chg']}%</b></div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")

        st.markdown("##### Price Levels")
        st.dataframe(pd.DataFrame({
            "Level": ["Your Avg Cost", "Current Price", "Stop Loss (exit if falls to)", "Target (book profit at)"],
            "Price (Rs.)": [avg, price, sl_price, tgt_price if tgt_price else "Wait for BUY signal"],
        }), hide_index=True, width="stretch")

        st.markdown(
            f"<div style='padding:10px;background:#f8f9fa;border-radius:8px'>"
            f"<b>Your P&L:</b> "
            f"<span style='color:{pnl_color};font-size:1.2rem'>"
            f"{abs(pnl_pct)}%  |  Rs. {abs(pnl_rs):,.0f}</span></div>",
            unsafe_allow_html=True)
        st.markdown("")

        st.markdown("##### Why this signal?")
        for r in sig["reasons"]:
            st.markdown(f"- {r}")
        st.markdown(f"**Score: {sig['score']} out of 3** &nbsp; (2 or 3 = BUY  |  0 or 1 = HOLD  |  -2 or -3 = SELL)")

        st.markdown("##### 3-Month Price Chart")
        ema9_s  = df["Close"].ewm(span=9).mean()
        ema21_s = df["Close"].ewm(span=21).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Price", line=dict(color="#2196F3", width=2)))
        fig.add_trace(go.Scatter(x=df.index, y=ema9_s, name="EMA9", line=dict(color="orange", width=1.5, dash="dot")))
        fig.add_trace(go.Scatter(x=df.index, y=ema21_s, name="EMA21", line=dict(color="purple", width=1.5, dash="dash")))
        fig.add_hline(y=avg, line_dash="dash", line_color="gray",
                      annotation_text=f"Avg Rs.{avg}", annotation_position="bottom right")
        if tgt_price:
            fig.add_hline(y=tgt_price, line_dash="dot", line_color="green",
                          annotation_text=f"Target Rs.{tgt_price}", annotation_position="top right")
        fig.add_hline(y=sl_price, line_dash="dot", line_color="red",
                      annotation_text=f"SL Rs.{sl_price}", annotation_position="bottom right")
        fig.update_layout(height=300, template="plotly_white",
                          margin=dict(l=0, r=0, t=10, b=0),
                          legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, width="stretch")

st.markdown("---")
st.subheader("Simple Trading Rules")
c1, c2, c3, c4 = st.columns(4)
c1.success("BUY WHEN\nScore is 2 or 3 out of 3\nRSI below 40 (oversold)\nTrend turning UP")
c2.error("SELL WHEN\nTarget price hit (+3 to 5%)\nOR stop-loss hit (-2%)\nOR score is -2 or -3")
c3.warning("HOLD WHEN\nScore is 0 or 1\nMarket is sideways\nNo clear direction")
c4.info("WEEKLY RULE\nBuy on Monday dip\nBook profit on Thursday\nExit before Friday 2 PM")

st.markdown("---")
st.caption("For informational use only. Not financial advice.")
