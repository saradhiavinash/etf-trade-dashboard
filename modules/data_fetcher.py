import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta


def get_etf_data(symbol: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch ETF historical OHLCV data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        df.index = pd.to_datetime(df.index)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        df.dropna(inplace=True)
        return df
    except Exception as e:
        print(f"[DataFetcher] Error fetching {symbol}: {e}")
        return pd.DataFrame()


def get_current_price(symbol: str) -> dict:
    """Get current price, day change and volume using historical data (reliable)."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="5d", interval="1d")
        hist = hist[hist["Close"] > 0].dropna(subset=["Close"])

        if len(hist) < 1:
            return {}

        current_price = round(float(hist["Close"].iloc[-1]), 2)
        prev_close = round(float(hist["Close"].iloc[-2]), 2) if len(hist) >= 2 else current_price
        day_change = round(current_price - prev_close, 2)
        day_change_pct = round((day_change / prev_close) * 100, 2) if prev_close else 0.0
        volume = int(hist["Volume"].iloc[-1])

        return {
            "symbol": symbol,
            "current_price": current_price,
            "prev_close": prev_close,
            "day_change": day_change,
            "day_change_pct": day_change_pct,
            "volume": volume,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        print(f"[DataFetcher] Error fetching current price for {symbol}: {e}")
        return {}


def get_portfolio_summary(holdings: list) -> list:
    """
    Calculate current portfolio value for each holding.
    holdings = [{"symbol": "PSUBNKBEES.NS", "invested": 25494, "units": 100}, ...]
    """
    summary = []
    for h in holdings:
        price_data = get_current_price(h["symbol"])
        if price_data and price_data.get("current_price"):
            current_value = round(h["units"] * price_data["current_price"], 2)
            pnl = round(current_value - h["invested"], 2)
            pnl_pct = round((pnl / h["invested"]) * 100, 2)
            summary.append({
                **h,
                **price_data,
                "current_value": current_value,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
            })
        else:
            summary.append({**h, "current_value": None, "pnl": None, "pnl_pct": None})
    return summary
