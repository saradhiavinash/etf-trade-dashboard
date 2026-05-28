from modules.data_fetcher import get_etf_data, get_current_price
from modules.sentiment_analyzer import get_sentiment_for_etf
from modules.technical_indicators import get_latest_signals
from datetime import datetime


# Sentiment score → numeric
SENTIMENT_SCORE_MAP = {"BULLISH": 1, "NEUTRAL": 0, "BEARISH": -1}

# Technical signals → numeric
TECH_SIGNAL_MAP = {
    "OVERSOLD (BUY)": 2, "BULLISH CROSSOVER (BUY)": 2,
    "NEAR LOWER BAND (BUY)": 2,
    "BULLISH": 1, "UPTREND": 1, "WITHIN BANDS (NEUTRAL)": 0,
    "NEUTRAL": 0,
    "BEARISH": -1, "DOWNTREND": -1,
    "OVERBOUGHT (SELL)": -2, "BEARISH CROSSOVER (SELL)": -2,
    "NEAR UPPER BAND (SELL)": -2,
}


def generate_signal(etf_symbol: str, etf_news_key: str, invested: float, units: float) -> dict:
    """
    Full signal generation pipeline for one ETF.
    Returns a complete recommendation dict.
    """
    # 1. Fetch price data
    df = get_etf_data(etf_symbol, period="3mo")
    price_data = get_current_price(etf_symbol)

    # 2. Technical indicators
    tech = get_latest_signals(df) if not df.empty else {}

    # 3. Sentiment
    sentiment = get_sentiment_for_etf(etf_news_key)

    # 4. Score calculation
    tech_score = 0
    for key in ["RSI_signal", "MACD_signal", "BB_signal", "Trend"]:
        val = tech.get(key, "NEUTRAL")
        tech_score += TECH_SIGNAL_MAP.get(val, 0)

    sentiment_score = SENTIMENT_SCORE_MAP.get(sentiment.get("label", "NEUTRAL"), 0)

    # Weighted total: 60% technical, 40% sentiment
    total_score = (tech_score / 8) * 0.6 + (sentiment_score / 1) * 0.4

    # 5. Decision
    action, target_pct, color = _decide(total_score)

    # 6. Portfolio P&L
    current_price = price_data.get("current_price") if price_data else None

    # Sanity check: price should be within 50% of avg cost
    avg_cost = round(invested / units, 2) if units else None
    if current_price and avg_cost:
        ratio = current_price / avg_cost
        if ratio > 2.0 or ratio < 0.2:
            print(f"[SignalEngine] ⚠️ Suspicious price {current_price} for {etf_symbol} (avg cost: {avg_cost}). Skipping.")
            current_price = None

    current_value = round(units * current_price, 2) if current_price else None
    pnl = round(current_value - invested, 2) if current_value else None
    pnl_pct = round((pnl / invested) * 100, 2) if pnl is not None else None

    return {
        "symbol": etf_symbol,
        "news_key": etf_news_key,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_price": current_price,
        "day_change_pct": price_data.get("day_change_pct") if price_data else None,
        "invested": invested,
        "units": units,
        "current_value": current_value,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "sentiment": sentiment.get("label"),
        "sentiment_score": sentiment.get("score"),
        "news_articles": sentiment.get("details", []),
        "tech_signals": tech,
        "total_score": round(total_score, 3),
        "action": action,
        "target_pct": target_pct,
        "color": color,
        "df": df,
    }


def _decide(score: float) -> tuple:
    """Convert composite score to action, target % and UI color."""
    if score >= 0.5:
        return "🟢 STRONG BUY", 7.0, "green"
    elif score >= 0.2:
        return "🟢 BUY", 5.0, "green"
    elif score >= 0.05:
        return "🟡 HOLD / WATCH", 3.0, "orange"
    elif score >= -0.2:
        return "🟡 NEUTRAL", 0.0, "orange"
    elif score >= -0.5:
        return "🔴 CAUTION / WAIT", 0.0, "red"
    else:
        return "🔴 AVOID / SELL", 0.0, "red"
