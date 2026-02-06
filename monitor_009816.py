import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
from data_engine import get_high_level_insight, get_fm_data
from hard_risk_gate import hard_risk_gate
from decision_logger import log_decision
import pandas as pd

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_realtime_data(ticker):
    """使用 yfinance Close，避免卡死"""
    print(f"🔍 索取 {ticker} 即時報價...")
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="2d", timeout=5)
        if not df.empty and len(df) >= 2:
            curr = round(float(df['Close'].iloc[-1]), 2)
            prev = float(df['Close'].iloc[-2])
            pct = round(((curr / prev) - 1) * 100, 2)
            return curr, pct
        return 0.0, 0.0
    except Exception as e:
        print(f"⚠️ yfinance 錯誤: {e}")
        return 0.0, 0.0

def run_009816_monitor():
    print("\n" + "=" * 30)
    print("🦅 啟動 009816 AI 月底低點判斷（穩定版）")

    # === 1. 即時報價 ===
    price_00, pct_00 = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # === 2. 高階籌碼資料 ===
    extra_data = get_high_level_insight("009816.TW") or {}

    # === 3. 本月價格 ===
    df_month = get_fm_data("TaiwanStockPrice", "009816.TW", days=40)
    if df_month is None or df_month.empty:
        df_month = pd.DataFrame({"close": [price_00]})

    closes = df_month["close"].astype(float)

    month_low = closes.min()
    month_high = closes.max()
    pct_from_low = round((price_00 - month_low) / month_low * 100, 2) if month_low > 0 else 0

    # === 4. RSI（保證不 NaN）===
    rsi = 50
    if len(closes) >= 15:
        delta = closes.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain.iloc[-1] / (loss.iloc[-1] + 1e-6)
        rsi = round(100 - (100 / (1 + rs)), 1)

    # === 5. 趨勢（20 / 30 MA）===
    trend = "盤整"
    if len(closes) >= 30:
        ma20 = closes.rolling(20).mean().iloc[-1]
        ma30 = closes.rolling(30).mean().iloc[-1]
        if price_00 > ma20 > ma30:
            trend = "多頭"
        elif price_00 < ma20 < ma30:
            trend = "空頭"

    # === 6. 技術三要素 ===
    tech_summary = []

    # 空間：布林通道
    if len(closes) >= 20:
        mid = closes.rolling(20).mean().iloc[-1]
        std = closes.rolling(20).std().iloc[-1]
        upper = mid + 2 * std
        lower = mid - 2 * std
        if price_00 < lower:
            tech_summary.append("布林:超跌")
        elif price_00 > upper:
            tech_summary.append("布林:過熱")
        else:
            tech_summary.append("布林:區間內")
    else:
        tech_summary.append("布林:N/A")

    # 動能：MACD
    if len(closes) >= 35:
        ema12 = closes.ewm(span=12).mean()
        ema26 = closes.ewm(span=26).mean()
        macd_hist = (ema12 - ema26).iloc[-1]
        tech_summary.append("MACD:正動能" if macd_hist > 0 else "MACD:負動能")
    else:
        tech_summary.append("MACD:N/A")

    # 熱度：RSI
    if rsi <= 30:
        tech_summary.append("RSI:超賣")
    elif rsi >= 70:
        tech_summary.append("RSI:過熱")
    else:
        tech_summary.append("RSI:中性")

    # === 7. 給 AI 的摘要（已防呆）===
    summary_override = (
        f"現價:{price_00:.2f}, 月低:{month_low:.2f}, 月高:{month_high:.2f}, 距月低:{pct_from_low:.2f}%\n"
        f"RSI:{rsi}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
        f"技術結構:{' / '.join(tech_summary)}\n"
        f"法人:{extra_data.get('inst','N/A')}, 大戶:{extra_data.get('holders','N/A')}"
    )

    # === 8. AI 判斷（失敗可存活）===
    try:
        ai_result = get_ai_point(
            extra_data,
            target_name="009816 結婚基金",
            summary_override=summary_override
        )
    except Exception as e:
        ai_result = {"decision": "觀望", "confidence": 0, "reason": f"AI 失效:{e}"}

    ai_decision = ai_result.get("decision", "觀望")
    ai_conf = ai_result.get("confidence", 0)
    ai_reason = ai_result.get("reason", "N/A")

    # === 9. 硬風控 ===
    gate_ok, gate_reason = hard_risk_gate(price_00, extra_data)

    # === 10. 最終動作 ===
    if gate_ok and ai_decision == "可行" and ai_conf >= 60:
        final_action = f"✅【可分批佈局】接近月低 {pct_from_low:.2f}%"
    elif not gate_ok:
        final_action = f"⛔【風控封鎖】{gate_reason}"
    else:
        final_action = "⏸【觀望】條件尚未成熟"

    # === 11. 推播 ===
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    full_msg = (
        f"🦅 經理人 AI 存股提醒 ({now_tw})\n"
        f"------------------\n"
        f"{summary_override}\n"
        f"------------------\n"
        f"{final_action}\n"
        f"🤖 AI 信心:{ai_conf}\n"
        f"🧠 理由:{ai_reason}"
    )

    if LINE_TOKEN and USER_ID:
        try:
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={
                    "Authorization": f"Bearer {LINE_TOKEN}",
                    "Content-Type": "application/json"
                },
                json={"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]},
                timeout=10
            )
        except Exception as e:
            print(f"⚠️ LINE 推播失敗: {e}")

    return ai_result
