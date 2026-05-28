import pandas as pd
import ta


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate RSI, MACD, Bollinger Bands and Moving Averages."""
    if df.empty or len(df) < 20:
        return df

    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # RSI (14)
    df["RSI"] = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd_ind = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df["MACD"] = macd_ind.macd()
    df["MACD_Signal"] = macd_ind.macd_signal()
    df["MACD_Hist"] = macd_ind.macd_diff()

    # Bollinger Bands (20, 2)
    bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df["BB_Upper"] = bb.bollinger_hband()
    df["BB_Mid"] = bb.bollinger_mavg()
    df["BB_Lower"] = bb.bollinger_lband()

    # Moving Averages (EMA via pandas)
    df["EMA_9"] = close.ewm(span=9, adjust=False).mean()
    df["EMA_21"] = close.ewm(span=21, adjust=False).mean()
    df["SMA_50"] = close.rolling(window=50).mean()

    # Volume MA
    df["Vol_MA"] = volume.rolling(window=10).mean()

    return df


def get_latest_signals(df: pd.DataFrame) -> dict:
    """Extract latest indicator values and generate technical signals."""
    if df.empty:
        return {}

    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest

    signals = {}

    # --- RSI Signal ---
    rsi = latest.get("RSI")
    if rsi is not None:
        signals["RSI"] = round(rsi, 2)
        if rsi < 35:
            signals["RSI_signal"] = "OVERSOLD (BUY)"
        elif rsi > 65:
            signals["RSI_signal"] = "OVERBOUGHT (SELL)"
        else:
            signals["RSI_signal"] = "NEUTRAL"

    # --- MACD Signal ---
    macd = latest.get("MACD")
    macd_sig = latest.get("MACD_Signal")
    prev_macd = prev.get("MACD")
    prev_macd_sig = prev.get("MACD_Signal")
    if macd is not None and macd_sig is not None:
        signals["MACD"] = round(macd, 4)
        signals["MACD_Signal_Line"] = round(macd_sig, 4)
        # Crossover detection
        if prev_macd is not None and prev_macd_sig is not None:
            if prev_macd < prev_macd_sig and macd > macd_sig:
                signals["MACD_signal"] = "BULLISH CROSSOVER (BUY)"
            elif prev_macd > prev_macd_sig and macd < macd_sig:
                signals["MACD_signal"] = "BEARISH CROSSOVER (SELL)"
            elif macd > macd_sig:
                signals["MACD_signal"] = "BULLISH"
            else:
                signals["MACD_signal"] = "BEARISH"

    # --- Bollinger Bands ---
    close = latest["Close"]
    bb_upper = latest.get("BB_Upper")
    bb_lower = latest.get("BB_Lower")
    if bb_upper and bb_lower:
        signals["BB_Upper"] = round(bb_upper, 2)
        signals["BB_Lower"] = round(bb_lower, 2)
        signals["BB_Mid"] = round(latest.get("BB_Mid", 0), 2)
        if close <= bb_lower:
            signals["BB_signal"] = "NEAR LOWER BAND (BUY)"
        elif close >= bb_upper:
            signals["BB_signal"] = "NEAR UPPER BAND (SELL)"
        else:
            signals["BB_signal"] = "WITHIN BANDS (NEUTRAL)"

    # --- Trend (EMA) ---
    ema9 = latest.get("EMA_9")
    ema21 = latest.get("EMA_21")
    if ema9 and ema21:
        signals["EMA_9"] = round(ema9, 2)
        signals["EMA_21"] = round(ema21, 2)
        signals["Trend"] = "UPTREND" if ema9 > ema21 else "DOWNTREND"

    # --- Volume ---
    vol_ma = latest.get("Vol_MA")
    volume = latest.get("Volume")
    if vol_ma and volume:
        signals["Volume_vs_Avg"] = "HIGH" if volume > vol_ma * 1.2 else "NORMAL"

    return signals
