import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
from data_engine import get_high_level_insight
from hard_risk_gate import hard_risk_gate
from decision_logger import log_decision

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
    print("🦅 啟動 009816 AI 決策監控")

    # === 1. 報價 ===
    price_00, pct_00 = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # === 2. 籌碼 / 盤中數據 ===
    print("📡 取得 FinMind 全維度數據...")
    extra_data = get_high_level_insight("009816.TW")

    # === 3. AI 判斷（核心）===
    summary_override = (
        f"009816價:{price_00:.2f} ({pct_00:+.2f}%)\n"
        f"費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%"
    )
    ai_result = get_ai_point(extra_data, target_name="009816 結婚基金", summary_override=summary_override)

    ai_decision = ai_result.get("decision", "觀望")
    ai_conf = ai_result.get("confidence", 0)
    ai_reason = ai_result.get("reason", "N/A")

    # === 4. 硬風控 ===
    gate_ok, gate_reason = hard_risk_gate(price_00, extra_data)

    # === 5. 最終決策 ===
    if gate_ok and ai_decision == "可行" and ai_conf >= 60:
        final_action = "✅【最終決策】AI 判斷可買入"
    elif not gate_ok:
        final_action = f"⛔【風控封鎖】{gate_reason}"
    else:
        final_action = f"⏸【觀望】AI 判斷 {ai_decision}"

    # === 6. 紀錄決策 ===
    log_decision(
        symbol="009816",
        price=price_00,
        ai_result=ai_result,
        gate_result=(gate_ok, gate_reason)
    )

    # === 7. Line 推播 ===
    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_time = now_tw.strftime("%H:%M:%S")
    full_msg = (
        f"🦅 經理人 AI 決策戰報 ({current_time})\n"
        f"------------------\n"
        f"📊 技術摘要: {summary_override}\n"
        f"📊 評價: {extra_data.get('valuation','N/A')}\n"
        f"📉 盤中力道: {extra_data.get('order_strength','穩定')}\n"
        f"------------------\n"
        f"{final_action}\n"
        f"🤖 AI 信心: {ai_conf}\n"
        f"🧠 AI 理由: {ai_reason}"
    )
    if LINE_TOKEN and USER_ID:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
            payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"📊 Line 推送結果: {res.status_code}")
        except Exception as e:
            print(f"⚠️ Line 推播失敗: {e}")

    return ai_result
