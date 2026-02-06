import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

def smart_dca_009816():
    symbol = "009816.TW"
    name = "凱基台灣top50 (009816)"

    ticker = yf.Ticker(symbol)
    df = ticker.history(period="max", timeout=15)

    if df.empty or len(df) < 10:
        return f"❌ {name}: 掛牌資料不足，暫不評分"

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    close = df["Close"]
    price = close.iloc[-1]

    # =====================
    # 模組 1：價格位階 (40)
    # =====================
    low_1m = close.tail(20).min()
    low_3m = close.tail(60).min()
    high_3m = close.tail(60).max()

    dist_1m = (price / low_1m - 1) * 100
    dist_3m_high = (price / high_3m - 1) * 100

    score_price = 40
    if dist_1m < 2: score_price += 10
    if dist_3m_high < -8: score_price += 10
    score_price = min(score_price, 50)

    # =====================
    # 模組 2：趨勢結構 (25)
    # =====================
    ma20 = close.rolling(20).mean().iloc[-1]
    ma20_prev = close.rolling(20).mean().iloc[-5]

    score_trend = 25
    if price > ma20 and ma20 > ma20_prev:
        score_trend -= 5  # 避免追高
    if price < ma20:
        score_trend += 5

    score_trend = max(min(score_trend, 25), 0)

    # =====================
    # 模組 3：RSI 動能 (15)
    # =====================
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    rsi_val = rsi.iloc[-1]

    score_rsi = 15
    if rsi_val < 35: score_rsi += 5
    if rsi_val > 65: score_rsi -= 5
    score_rsi = max(min(score_rsi, 15), 0)

    # =====================
    # 模組 4：市場環境 (10)
    # =====================
    score_env = 10
    try:
        sox = yf.Ticker("^SOX").history(period="5d")["Close"]
        if sox.pct_change().iloc[-1] < -1:
            score_env -= 3
    except:
        pass

    # =====================
    # 模組 5：月存時間 (10)
    # =====================
    today = datetime.now(timezone(timedelta(hours=8)))
    score_time = 10 if today.day <= 20 else 5

    # =====================
    # 總分與決策
    # =====================
    total_score = score_price + score_trend + score_rsi + score_env + score_time

    if total_score >= 75:
        action = "🟢 強烈佈局（可加碼）"
    elif total_score >= 60:
        action = "🟡 正常定期"
    elif total_score >= 45:
        action = "🟠 保守佈局（少量）"
    else:
        action = "🔴 暫緩，等回檔"

    report = f"""
🦅 經理人 AI 存股決策 ({today:%Y-%m-%d})
------------------
📌 標的: {name}
現價: {price:.2f}
月低距離: {dist_1m:.2f}%
RSI: {rsi_val:.1f}

🧠 決策分數: {total_score} / 100
📊 行動建議: {action}

📖 經理人解讀:
- 本系統不追最低點，只買在「結構合理偏低」
- 若未達理想位階，最多延後至月底執行
- 長期目標：降低平均成本，而非抓轉折
"""

    return report