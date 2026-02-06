import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
from data_engine import get_high_level_insight, get_fm_data
from hard_risk_gate import hard_risk_gate
import pandas as pd

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

# --------------------------------------------------
# 即時價格（失敗回 None）
# --------------------------------------------------
def get_realtime_data(ticker):
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="2d", timeout=5)
        if df is not None and not df.empty:
            curr = round(float(df["Close"].iloc[-1]), 2)
            prev = float(df["Close"].iloc[-2]) if len(df) >= 2 else curr
            pct = round(((curr / prev) - 1) * 100, 2) if prev else 0
            return curr, pct
    except Exception as e:
        print(f"⚠️ yfinance error {ticker}: {e}")
    return None, None

# --------------------------------------------------
# AI 安全包裝（永不失效）
# --------------------------------------------------
def safe_ai_point(extra, target_name, summary):
    try:
        ai = get_ai_point(extra, target_name, summary_override=summary)
        if not ai or "decision" not in ai:
            return {
                "decision": "中性觀望",
                "confidence": 30,
                "reason": "資料不足，採保守中性判斷"
            }
        return ai
    except Exception as e:
        return {
            "decision": "中性觀望",
            "confidence": 20,
            "reason": f"AI 降級執行（{e}）"
        }

# --------------------------------------------------
# 主程式
# --------------------------------------------------
def run_009816_monitor():
    print("🦅 啟動 009816 AI 存股引擎（最終完整版）")

    # === 即時價格 ===
    price, _ = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # === 歷史資料 ===
    df = get_fm_data("TaiwanStockPrice", "009816.TW", days=60)
    if df is None or df.empty:
        df = pd.DataFrame({"close": [price]*15})  # fallback
    closes = df["close"].astype(float)

    # 價格 fallback
    if price is None:
        price = round(closes.iloc[-1], 2)

    # === 月低 / 月高（fallback）===
    month_low = closes.min()
    month_high = closes.max()
    pct_from_low = round((price - month_low) / month_low * 100, 2)

    # === RSI（ETF 友善）===
    if len(closes) >= 14:
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain.iloc[-1] / (loss.iloc[-1] + 1e-6)
        rsi = round(100 - 100 / (1 + rs), 1)
    else:
        rsi = 50

    # === 趨勢（ETF 低標準）===
    trend = "盤整"
    if len(closes) >= 20:
        ma10 = closes.rolling(10).mean().iloc[-1]
        ma20 = closes.rolling(20).mean().iloc[-1]
        if price > ma10 > ma20:
            trend = "多頭"
        elif price < ma10 < ma20:
            trend = "空頭"

    # === 技術結構 ===
    tech = []

    # 布林
    if len(closes) >= 20:
        mid = closes.rolling(20).mean().iloc[-1]
        std = closes.rolling(20).std().iloc[-1]
        if price < mid - 2 * std:
            tech.append("布林:超跌")
        elif price > mid + 2 * std:
            tech.append("布林:過熱")
        else:
            tech.append("布林:區間")
    else:
        tech.append("布林:N/A")

    # MACD
    if len(closes) >= 26:
        ema12 = closes.ewm(span=12).mean()
        ema26 = closes.ewm(span=26).mean()
        macd = ema12.iloc[-1] - ema26.iloc[-1]
        tech.append("MACD:正動能" if macd > 0 else "MACD:負動能")
    else:
        tech.append("MACD:N/A")

    # RSI 標示
    if rsi <= 30:
        tech.append("RSI:超賣")
    elif rsi >= 70:
        tech.append("RSI:過熱")
    else:
        tech.append("RSI:中性")

    # === 存股買點邏輯（主引擎）===
    buy_signal = False
    buy_reason = f"距月低 {pct_from_low:.2f}%"

    if pct_from_low <= 2 and rsi < 50 and trend != "空頭":
        buy_signal = True
        buy_reason = f"接近月低 {pct_from_low:.2f}%"

    # === 籌碼 ===
    extra = get_high_level_insight("009816.TW") or {}

    # === AI 摘要 ===
    summary = (
        f"現價:{price:.2f}, 月低:{month_low:.2f}, 月高:{month_high:.2f}, 距月低:{pct_from_low:.2f}%\n"
        f"RSI:{rsi}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
        f"技術結構:{' / '.join(tech)}\n"
        f"法人:{extra.get('inst','N/A')}, 大戶:{extra.get('holders','N/A')}"
    )

    ai = safe_ai_point(extra, "009816 結婚基金", summary)

    # === 風控 ===
    gate_ok, gate_reason = hard_risk_gate(price, extra)

    # === 最終動作 ===
    if buy_signal and gate_ok:
        action = f"🟢【可分批佈局】{buy_reason}"
    elif not gate_ok:
        action = f"⛔【風控封鎖】{gate_reason}"
    else:
        action = f"⏸【觀望】{buy_reason}"

    # === 推播 ===
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    msg = (
        f"🦅 經理人 AI 存股提醒 ({now_tw})\n"
        f"------------------\n"
        f"{summary}\n"
        f"------------------\n"
        f"{action}\n"
        f"🤖 AI 信心:{ai.get('confidence',0)}\n"
        f"🧠 理由:{ai.get('reason','')}"
    )

    if LINE_TOKEN and USER_ID:
        try:
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {LINE_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={"to": USER_ID, "messages": [{"type": "text", "text": msg}]},
                timeout=10
            )
        except Exception as e:
            print(f"⚠️ LINE 推播失敗: {e}")

    return ai
