# tech_signal_engine.py
import numpy as np

def tech_signal_summary(close):
    """
    回傳 AI 與人都能用的結構化訊號
    """
    if len(close) < 30:
        return {}

    # === Bollinger ===
    ma = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = ma + 2 * std
    lower = ma - 2 * std

    price = close.iloc[-1]
    bb_pos = (price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])

    # === MACD Histogram ===
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    macd_now = hist.iloc[-1]
    macd_prev = hist.iloc[-2]
    macd_trend = "收斂" if abs(macd_now) < abs(macd_prev) else "擴大"

    # === RSI ===
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-6)
    rsi = 100 - (100 / (1 + rs.iloc[-1]))

    heat = (
        "超賣" if rsi < 30 else
        "超買" if rsi > 70 else
        "中性"
    )

    return {
        "space": round(bb_pos, 2),       # 0~1（越接近0越超跌）
        "momentum": macd_trend,          # 收斂 / 擴大
        "momentum_value": round(macd_now, 4),
        "heat": heat,
        "rsi": round(rsi, 1)
    }
