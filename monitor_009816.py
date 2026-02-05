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
    print("🦅 啟動 009816 AI 月底低點判斷")

    # === 1. 即時報價 ===
    price_00, pct_00 = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # === 2. 取得高階數據 ===
    extra_data = get_high_level_insight("009816.TW")

    # === 3. 取得本月歷史價格 ===
    df_month = get_fm_data("TaiwanStockPrice", "009816.TW", days=30)
    if df_month.empty:
        df_month = pd.DataFrame({'close':[price_00]})

    month_low = df_month['close'].min()
    month_high = df_month['close'].max()
    pct_from_low = (price_00 - month_low) / month_low * 100

    # === 4. 計算 RSI ===
    delta = df_month['close'].diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rs = gain / loss.replace(0,1e-6)
    rsi = 100 - (100 / (1 + rs.iloc[-1])) if not rs.empty else 50

    # === 5. 趨勢判斷 (20日/30日均線) ===
    trend = "盤整"
    if len(df_month) >= 20:
        ma20 = df_month['close'].rolling(20).mean().iloc[-1]
        ma30 = df_month['close'].rolling(min(30,len(df_month))).mean().iloc[-1]
        if price_00 > ma20 > ma30:
            trend = "多頭"
        elif price_00 < ma20 < ma30:
            trend = "空頭"

    # === 6. 技術摘要給 AI ===
    summary_override = (
        f"現價:{price_00:.2f}, 本月最低:{month_low:.2f}, 本月最高:{month_high:.2f}, 距月低:{pct_from_low:.2f}%\n"
        f"RSI:{rsi:.1f}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
        f"K線/量:{extra_data.get('k_line','N/A')}, 盤中力道:{extra_data.get('order_strength','N/A')}\n"
        f"法人:{extra_data.get('inst','N/A')}, 大戶:{extra_data.get('holders','N/A')}, 基本面:{extra_data.get('rev','N/A')}"
    )

    # === 7. AI 判斷 ===
    ai_result = get_ai_point(extra_data, target_name="009816 結婚基金", summary_override=summary_override)
    ai_decision = ai_result.get("decision", "觀望")
    ai_conf = ai_result.get("confidence", 0)
    ai_reason = ai_result.get("reason", "N/A")

    # === 8. 硬風控 ===
    gate_ok, gate_reason = hard_risk_gate(price_00, extra_data)

    # === 9. 最終決策 ===
    if gate_ok and ai_decision == "可行" and ai_conf >= 60:
        final_action = f"✅【建議買入】價格接近本月低點 ({pct_from_low:.2f}%)"
    elif not gate_ok:
        final_action = f"⛔【風控封鎖】{gate_reason}"
    else:
        final_action = f"⏸【觀望】AI 判斷 {ai_decision}"

    # === 10. 紀錄決策 ===
    log_decision(
        symbol="009816",
        price=price_00,
        ai_result=ai_result,
        gate_result=(gate_ok, gate_reason)
    )

    # === 11. Line 推播 ===
    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_time = now_tw.strftime("%H:%M:%S")
    full_msg = (
        f"🦅 經理人 AI 存股提醒 ({current_time})\n"
        f"------------------\n"
        f"現價:{price_00:.2f}, 本月最低:{month_low:.2f}, 本月最高:{month_high:.2f}, 距月低:{pct_from_low:.2f}%\n"
        f"RSI:{rsi:.1f}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
        f"K線/量:{extra_data.get('k_line','N/A')}, 盤中力道:{extra_data.get('order_strength','N/A')}\n"
        f"法人:{extra_data.get('inst','N/A')}, 大戶:{extra_data.get('holders','N/A')}, 基本面:{extra_data.get('rev','N/A')}\n"
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
