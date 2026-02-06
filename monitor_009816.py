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
# 即時報價（失敗不回 0，回 None）
# --------------------------------------------------
def get_realtime_data(ticker):
    print(f"🔍 索取 {ticker} 即時報價...")
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="2d", timeout=5)
        if df is not None and not df.empty and len(df) >= 2:
            curr = round(float(df["Close"].iloc[-1]), 2)
            prev = float(df["Close"].iloc[-2])
            pct = round(((curr / prev) - 1) * 100, 2)
            return curr, pct
    except Exception as e:
        print(f"⚠️ yfinance 錯誤: {e}")
    return None, None


# --------------------------------------------------
# 主程式
# --------------------------------------------------
def run_009816_monitor():
    print("\n" + "=" * 30)
    print("🦅 啟動 009816 AI 月低存股判斷（穩定完整版）")

    # === 1. 即時報價 ===
    price_00, pct_00 = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # === 2. 歷史資料（核心）===
    df_month = get_fm_data("TaiwanStockPrice", "009816.TW", days=60)
    data_ok = True

    if df_month is None or df_month.empty or len(df_month) < 15:
        data_ok = False
        closes = None
    else:
        closes = df_month["close"].astype(float)

    # === 3. 價格 fallback（禁止 0 價）===
    if price_00 is None:
        if data_ok:
            price_00 = round(float(closes.iloc[-1]), 2)
        else:
            raise RuntimeError("❌ 無法取得任何有效價格資料")

    # === 4. 高階籌碼 ===
    extra_data = get_high_level_insight("009816.TW") or {}

    # === 5. 月高 / 月低 ===
    if data_ok:
        month_low = closes.min()
        month_high = closes.max()
        pct_from_low = round((price_00 - month_low) / month_low * 100, 2)
    else:
        month_low = None
        month_high = None
        pct_from_low = None

    # === 6. RSI ===
    rsi = None
    if data_ok and len(closes) >= 20:
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain.iloc[-1] / (loss.iloc[-1] + 1e-6)
        rsi = round(100 - (100 / (1 + rs)), 1)

    # === 7. 趨勢 ===
    trend = "N/A"
    if data_ok and len(closes) >= 30:
        ma20 = closes.rolling(20).mean().iloc[-1]
        ma30 = closes.rolling(30).mean().iloc[-1]
        if price_00 > ma20 > ma30:
            trend = "多頭"
        elif price_00 < ma20 < ma30:
            trend = "空頭"
        else:
            trend = "盤整"

    # === 8. 技術結構 ===
    tech_summary = []

    # 布林
    if data_ok and len(closes) >= 20:
        mid = closes.rolling(20).mean().iloc[-1]
        std = closes.rolling(20).std().iloc[-1]
        if price_00 < mid - 2 * std:
            tech_summary.append("布林:超跌")
        elif price_00 > mid + 2 * std:
            tech_summary.append("布林:過熱")
        else:
            tech_summary.append("布林:區間")
    else:
        tech_summary.append("布林:N/A")

    # MACD
    if data_ok and len(closes) >= 35:
        ema12 = closes.ewm(span=12).mean()
        ema26 = closes.ewm(span=26).mean()
        macd = ema12.iloc[-1] - ema26.iloc[-1]
        tech_summary.append("MACD:正動能" if macd > 0 else "MACD:負動能")
    else:
        tech_summary.append("MACD:N/A")

    # RSI 標示
    if rsi is None:
        tech_summary.append("RSI:N/A")
    elif rsi <= 30:
        tech_summary.append("RSI:超賣")
    elif rsi >= 70:
        tech_summary.append("RSI:過熱")
    else:
        tech_summary.append("RSI:中性")

    # === 9. 月低買點引擎（不靠 AI）===
    buy_signal = False
    buy_reason = "觀望"

    if data_ok and pct_from_low is not None:
        if pct_from_low <= 2:
            if rsi is not None and rsi < 45:
                if trend != "空頭":
                    buy_signal = True
                    buy_reason = f"接近月低 {pct_from_low:.2f}%"
                else:
                    buy_reason = "接近月低但趨勢轉空"
            else:
                buy_reason = "價格低但動能未冷卻"
        else:
            buy_reason = f"距月低 {pct_from_low:.2f}%"

    # === 10. AI（只在資料完整時啟用）===
    if data_ok:
        summary_override = (
            f"現價:{price_00:.2f}, 月低:{month_low:.2f}, 月高:{month_high:.2f}, 距月低:{pct_from_low:.2f}%\n"
            f"RSI:{rsi}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
            f"技術結構:{' / '.join(tech_summary)}\n"
            f"法人:{extra_data.get('inst','N/A')}, 大戶:{extra_data.get('holders','N/A')}"
        )
        try:
            ai_result = get_ai_point(
                extra_data,
                target_name="009816 結婚基金",
                summary_override=summary_override
            )
        except Exception as e:
            ai_result = {"decision": "觀望", "confidence": 0, "reason": f"AI 失效:{e}"}
    else:
        summary_override = "歷史資料不足，未啟用 AI"
        ai_result = {"decision": "觀望", "confidence": 0, "reason": "資料不足"}

    ai_conf = ai_result.get("confidence", 0)
    ai_reason = ai_result.get("reason", "")

    # === 11. 風控 ===
    gate_ok, gate_reason = hard_risk_gate(price_00, extra_data)

    # === 12. 最終動作 ===
    if buy_signal and gate_ok:
        final_action = f"🟢【可分批佈局】{buy_reason}"
    elif not gate_ok:
        final_action = f"⛔【風控封鎖】{gate_reason}"
    else:
        final_action = f"⏸【觀望】{buy_reason}"

    # === 13. 推播 ===
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    msg = (
        f"🦅 經理人 AI 存股提醒 ({now_tw})\n"
        f"------------------\n"
        f"{summary_override}\n"
        f"------------------\n"
        f"{final_action}\n"
        f"🤖 AI 信心:{ai_conf}\n"
        f"🧠 理由:{ai_reason}"
    )

    if LINE_TOKEN and USER_ID:
        requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {LINE_TOKEN}",
                "Content-Type": "application/json"
            },
            json={"to": USER_ID, "messages": [{"type": "text", "text": msg}]},
            timeout=10
        )

    return ai_result
