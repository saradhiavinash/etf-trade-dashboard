import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import yfinance as yf
import ta
import feedparser
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="ETF Trade Signals", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

# ── Auto-refresh every 5 minutes ─────────────────────────────
st_autorefresh(interval=300_000, key="autorefresh")

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
.buy-box  { background:#d4edda; border-left:6px solid #28a745; padding:16px; border-radius:10px; }
.sell-box { background:#f8d7da; border-left:6px solid #dc3545; padding:16px; border-radius:10px; }
.hold-box { background:#fff3cd; border-left:6px solid #ffc107; padding:16px; border-radius:10px; }
.news-bull { color:#28a745; font-weight:700; font-size:0.78rem; }
.news-bear { color:#dc3545; font-weight:700; font-size:0.78rem; }
.news-neut { color:#6c757d; font-weight:700; font-size:0.78rem; }
.big-signal { font-size:2.2rem; font-weight:800; margin:0; }
.price-tag  { font-size:1.7rem; font-weight:700; }
.label-tag  { font-size:0.9rem; color:#555; margin-bottom:4px; }
</style>
""", unsafe_allow_html=True)

# ── Telegram Helper ───────────────────────────────────────────
def send_telegram(token, chat_id, msg):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = requests.post(url, data={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=10)
        return r.ok, r.json().get("description", "")
    except Exception as e:
        return False, str(e)

def build_alert_message(p, sig, pnl_pct, pnl_rs, sl_price, tgt_price):
    action = sig["action"]
    tag    = {"BUY": "BUY SIGNAL", "SELL / WAIT": "SELL SIGNAL", "HOLD": "HOLD"}.get(action, action)
    lines = [
        f"<b>{tag}</b> — {p['label']} ({p['nse_symbol']})",
        f"Price: Rs. {sig['price']}  |  Score: {sig['score']}/3",
        f"P&L: {'+' if pnl_pct>=0 else ''}{pnl_pct}%  |  Rs. {pnl_rs:+,.0f}",
        f"Stop Loss: Rs. {sl_price}",
    ]
    if tgt_price:
        lines.append(f"Target: Rs. {tgt_price}")
    for r in sig["reasons"]:
        lines.append(f"• {r}")
    lines.append(f"\n<i>As of {datetime.now().strftime('%d %b %Y %I:%M %p')} IST</i>")
    return "\n".join(lines)

# ── News Sentiment ────────────────────────────────────────────
@st.cache_data(ttl=1800)
def get_news(query):
    url = f"https://news.google.com/rss/search?q={query}+India+ETF&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        feed = feedparser.parse(url)
        analyzer = SentimentIntensityAnalyzer()
        results = []
        for entry in feed.entries[:5]:
            title = entry.get("title", "")
            score = analyzer.polarity_scores(title)["compound"]
            if score >= 0.05:
                sentiment, css = "BULLISH", "news-bull"
            elif score <= -0.05:
                sentiment, css = "BEARISH", "news-bear"
            else:
                sentiment, css = "NEUTRAL", "news-neut"
            results.append({"title": title, "sentiment": sentiment, "css": css,
                             "link": entry.get("link", "#")})
        return results
    except Exception:
        return []

# ── Position Advice ───────────────────────────────────────────
def position_advice(pnl_pct, signal_action, signal_score):
    if pnl_pct >= 15:
        if signal_action == "SELL / WAIT" or signal_score <= 0:
            return ("BOOK FULL PROFIT",
                    f"You are up {pnl_pct}% — excellent gain. Signal is weakening. Exit now and lock in profit.",
                    "#dc3545", "sell-box")
        else:
            return ("BOOK 50% + HOLD REST",
                    f"You are up {pnl_pct}% — strong gain. Signal still bullish. Sell half to secure profit, hold half to ride further.",
                    "#fd7e14", "hold-box")
    elif pnl_pct >= 8:
        if signal_action == "SELL / WAIT":
            return ("CONSIDER BOOKING PROFIT",
                    f"You are up {pnl_pct}% and signal turned negative. Good time to exit or set a tight stop-loss.",
                    "#fd7e14", "hold-box")
        elif signal_action == "BUY":
            return ("HOLD — LET IT RUN",
                    f"You are up {pnl_pct}% and signal is still bullish. Set trailing stop-loss and stay invested.",
                    "#28a745", "buy-box")
        else:
            return ("HOLD WITH STOP-LOSS",
                    f"You are up {pnl_pct}%. Mixed signals — protect gains with a stop-loss at -2% from current price.",
                    "#fd7e14", "hold-box")
    elif pnl_pct >= 3:
        if signal_action == "BUY":
            return ("HOLD — TREND IS UP",
                    f"You are up {pnl_pct}%. Signal is bullish — stay invested, target is higher.",
                    "#28a745", "buy-box")
        elif signal_action == "SELL / WAIT":
            return ("HOLD FOR NOW / WATCH",
                    f"You are up {pnl_pct}%. Signal is cautious — watch closely. Exit if it drops toward your cost.",
                    "#fd7e14", "hold-box")
        else:
            return ("HOLD",
                    f"You are up {pnl_pct}%. No strong signal either way. Keep holding.",
                    "#6c757d", "hold-box")
    elif pnl_pct >= 0:
        if signal_action == "BUY":
            return ("HOLD — EARLY STAGE PROFIT",
                    f"Small gain of {pnl_pct}%. Signal is bullish — could grow more. Stay patient.",
                    "#28a745", "buy-box")
        else:
            return ("HOLD — NEAR BREAKEVEN",
                    f"You are at {pnl_pct}% gain. Wait for a clearer BUY signal before adding more.",
                    "#6c757d", "hold-box")
    else:
        if signal_action == "BUY":
            return ("HOLD — DO NOT PANIC SELL",
                    f"You are down {abs(pnl_pct)}% but signal shows recovery possible. ETFs bounce back — hold and wait.",
                    "#fd7e14", "hold-box")
        elif signal_action == "SELL / WAIT":
            return ("HOLD — AVOID AVERAGING DOWN",
                    f"You are down {abs(pnl_pct)}% and signal is weak. Do not buy more yet. Wait for BUY signal before any action.",
                    "#dc3545", "sell-box")
        else:
            return ("HOLD — WAIT FOR SIGNAL",
                    f"You are down {abs(pnl_pct)}%. Market is unclear. Hold and wait — ETFs recover over time.",
                    "#6c757d", "hold-box")

# ── Portfolio & Watchlist Config ─────────────────────────────
PORTFOLIO = [
    {"label": "HDFC Smallcap 250 ETF", "nse_symbol": "HDFCSML250", "yf_symbol": "HDFCSML250.NS",
     "invested": 19776.68, "units": 131, "avg_cost": round(19776.68/131, 2), "news_query": "HDFCSML250"},
    {"label": "PSU Bank BeES", "nse_symbol": "PSUBNKBEES", "yf_symbol": "PSUBNKBEES.NS",
     "invested": 35494.57, "units": 364, "avg_cost": round(35494.57/364, 2), "news_query": "PSUBNKBEES"},
]

WATCHLIST = [
    {"label": "Nifty BeES",   "nse_symbol": "NIFTYBEES",  "yf_symbol": "NIFTYBEES.NS",  "news_query": "NIFTYBEES"},
    {"label": "Gold BeES",    "nse_symbol": "GOLDBEES",   "yf_symbol": "GOLDBEES.NS",   "news_query": "gold ETF India"},
    {"label": "Bank BeES",    "nse_symbol": "BANKBEES",   "yf_symbol": "BANKBEES.NS",   "news_query": "BANKBEES"},
    {"label": "Junior BeES",  "nse_symbol": "JUNIORBEES", "yf_symbol": "JUNIORBEES.NS", "news_query": "JUNIORBEES"},
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

    score = 0; reasons = []

    if rsi_val < 40:
        score += 1; reasons.append(f"RSI {rsi_val} — Oversold. Good to BUY")
    elif rsi_val > 65:
        score -= 1; reasons.append(f"RSI {rsi_val} — Overbought. Consider SELLING")
    else:
        reasons.append(f"RSI {rsi_val} — Neutral zone")

    if macd_v > macd_s:
        score += 1; reasons.append("MACD above signal line — Bullish momentum")
    else:
        score -= 1; reasons.append("MACD below signal line — Bearish momentum")

    if ema9 > ema21:
        score += 1; reasons.append("Short-term trend is UP (EMA9 > EMA21)")
    else:
        score -= 1; reasons.append("Short-term trend is DOWN (EMA9 < EMA21)")

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

# ── Sidebar: Telegram Setup ───────────────────────────────────
with st.sidebar:
    st.header("Telegram Alerts")

    default_token = ""
    default_chat  = ""
    try:
        default_token = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
        default_chat  = st.secrets.get("TELEGRAM_CHAT_ID", "")
    except Exception:
        pass

    tg_token = st.text_input("Bot Token", value=default_token, type="password",
                              placeholder="123456:ABC-DEF...")
    tg_chat  = st.text_input("Chat ID",   value=default_chat,  placeholder="-100123456789")

    st.caption("Setup: Search @BotFather on Telegram → /newbot → copy token. Then message your bot and open api.telegram.org/bot<TOKEN>/getUpdates to find your chat_id.")

    auto_alert = st.toggle("Auto-alert on BUY / SELL signals", value=True)

    if st.button("Send Test Message", use_container_width=True):
        if tg_token and tg_chat:
            ok, err = send_telegram(tg_token, tg_chat,
                "<b>ETF Dashboard connected!</b>\nYou will now get BUY/SELL alerts here.")
            st.success("Sent!") if ok else st.error(f"Failed: {err}")
        else:
            st.warning("Enter Bot Token and Chat ID first.")

    if st.button("Send Current Signals Now", use_container_width=True):
        if tg_token and tg_chat:
            sent = 0
            for p in PORTFOLIO:
                df = get_data(p["yf_symbol"])
                if not df.empty:
                    sig       = compute_signals(df)
                    avg       = p["avg_cost"]
                    pnl_pct   = round((sig["price"] - avg) / avg * 100, 2)
                    pnl_rs    = round((sig["price"] - avg) * p["units"], 0)
                    sl_price  = round(sig["price"] * (1 - STOP_LOSS / 100), 2)
                    tgt_price = round(sig["price"] * (1 + sig["target_pct"] / 100), 2) if sig["target_pct"] > 0 else None
                    msg = build_alert_message(p, sig, pnl_pct, pnl_rs, sl_price, tgt_price)
                    ok, _ = send_telegram(tg_token, tg_chat, msg)
                    if ok: sent += 1
            st.success(f"Sent {sent}/{len(PORTFOLIO)} signals!")
        else:
            st.warning("Enter Bot Token and Chat ID first.")

    st.divider()
    st.caption(f"Auto-refreshes every 5 min | Last loaded: {datetime.now().strftime('%I:%M %p')}")

# ── Main Header ───────────────────────────────────────────────
now_str = datetime.now().strftime("%d %b %Y, %I:%M %p")
st.title("ETF Trade Signal Dashboard")
st.caption(f"As of: {now_str} IST  |  Auto-refreshes every 5 min  |  Prices from NSE via yfinance")

if st.button("Refresh Now", type="primary"):
    st.cache_data.clear()
    st.rerun()

st.markdown("---")
st.subheader("My Portfolio")

# ── Portfolio Cards ───────────────────────────────────────────
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
        action_icons = {"BUY": "[BUY]", "SELL / WAIT": "[SELL]", "HOLD": "[HOLD]"}
        icon = action_icons.get(sig["action"], "")

        # Auto Telegram alert (once per signal per day)
        if auto_alert and tg_token and tg_chat and sig["action"] in ("BUY", "SELL / WAIT"):
            alert_key = f"alerted_{p['nse_symbol']}_{sig['action']}_{datetime.now().strftime('%Y%m%d')}"
            if alert_key not in st.session_state:
                msg = build_alert_message(p, sig, pnl_pct, pnl_rs, sl_price, tgt_price)
                ok, _ = send_telegram(tg_token, tg_chat, msg)
                st.session_state[alert_key] = ok

        st.markdown(f"""
        <div class="{sig['box']}">
            <div class="label-tag">{p['label']}  —  {p['nse_symbol']}</div>
            <div class="big-signal">{icon} {sig['action']}</div>
            <div class="price-tag">Rs. {price}</div>
            <div style="margin-top:6px;font-size:0.95rem">Today: <b>{'+' if sig['day_chg']>=0 else ''}{sig['day_chg']}%</b></div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")

        st.markdown("##### Price Levels")
        st.dataframe(pd.DataFrame({
            "Level": ["Your Avg Cost", "Current Price", "Stop Loss", "Target"],
            "Price (Rs.)": [avg, price, sl_price, tgt_price if tgt_price else "Wait for BUY signal"],
        }), hide_index=True, use_container_width=True)

        st.markdown(
            f"<div style='padding:10px;background:#f8f9fa;border-radius:8px'>"
            f"<b>Your P&L:</b> "
            f"<span style='color:{pnl_color};font-size:1.2rem'>"
            f"{'+' if pnl_pct>=0 else ''}{pnl_pct}%  |  Rs. {pnl_rs:+,.0f}</span></div>",
            unsafe_allow_html=True)
        st.markdown("")

        adv_title, adv_text, adv_color, adv_box = position_advice(pnl_pct, sig["action"], sig["score"])
        st.markdown(f"""
        <div class="{adv_box}" style="margin-bottom:12px;">
            <div style="font-size:0.82rem;color:#555;margin-bottom:4px;">What should I do with my position?</div>
            <div style="font-size:1.2rem;font-weight:800;color:{adv_color}">{adv_title}</div>
            <div style="font-size:0.9rem;margin-top:6px">{adv_text}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("##### Why this signal?")
        for r in sig["reasons"]:
            st.markdown(f"- {r}")
        st.markdown(f"**Score: {sig['score']} / 3**  (2+ = BUY | 0/1 = HOLD | -2/-3 = SELL)")

        st.markdown("##### 3-Month Price Chart")
        ema9_s  = df["Close"].ewm(span=9).mean()
        ema21_s = df["Close"].ewm(span=21).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Price", line=dict(color="#2196F3", width=2)))
        fig.add_trace(go.Scatter(x=df.index, y=ema9_s,  name="EMA9",  line=dict(color="orange", width=1.5, dash="dot")))
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
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### Latest News & Sentiment")
        news = get_news(p["news_query"])
        if news:
            for item in news:
                st.markdown(
                    f"<span class='{item['css']}'>[{item['sentiment']}]</span> "
                    f"<a href='{item['link']}' target='_blank' style='font-size:0.87rem;text-decoration:none;color:#222'>{item['title']}</a>",
                    unsafe_allow_html=True)
        else:
            st.caption("No news found.")
        st.markdown("")

# ── Watchlist ─────────────────────────────────────────────────
st.markdown("---")
st.subheader("Watchlist — Other ETFs")
wcols = st.columns(len(WATCHLIST))
for wcol, w in zip(wcols, WATCHLIST):
    with wcol:
        wdf = get_data(w["yf_symbol"])
        if wdf.empty:
            st.warning(f"No data: {w['nse_symbol']}")
            continue
        wsig = compute_signals(wdf)
        wicons = {"BUY": "[BUY]", "SELL / WAIT": "[SELL]", "HOLD": "[HOLD]"}
        wicon = wicons.get(wsig["action"], "")
        wchg_str = f"{'+' if wsig['day_chg']>=0 else ''}{wsig['day_chg']}%"

        st.markdown(f"""
        <div class="{wsig['box']}" style="padding:12px;">
            <div class="label-tag">{w['label']}  —  {w['nse_symbol']}</div>
            <div style="font-size:1.4rem;font-weight:800">{wicon} {wsig['action']}</div>
            <div style="font-size:1.1rem;font-weight:700">Rs. {wsig['price']}</div>
            <div style="font-size:0.85rem">Today: <b>{wchg_str}</b>  |  Score: {wsig['score']}/3</div>
        </div>
        """, unsafe_allow_html=True)
        for r in wsig["reasons"]:
            st.markdown(f"<small>• {r}</small>", unsafe_allow_html=True)
        st.markdown("")

# ── Rules ─────────────────────────────────────────────────────
st.markdown("---")
st.subheader("Simple Trading Rules")
c1, c2, c3, c4 = st.columns(4)
c1.success("BUY WHEN\nScore is 2 or 3 out of 3\nRSI below 40 (oversold)\nTrend turning UP")
c2.error("SELL WHEN\nTarget price hit (+3 to 5%)\nOR stop-loss hit (-2%)\nOR score is -2 or -3")
c3.warning("HOLD WHEN\nScore is 0 or 1\nMarket is sideways\nNo clear direction")
c4.info("WEEKLY RULE\nBuy on Monday dip\nBook profit on Thursday\nExit before Friday 2 PM")

st.markdown("---")
st.caption("For informational use only. Not financial advice.")
