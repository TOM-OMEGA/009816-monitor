import yfinance as yf
import requests
import os
import json
from datetime import datetime, timedelta, timezone

from ai_expert import get_ai_point
from data_engine import get_high_level_insight
from hard_risk_gate import hard_risk_gate
from decision_logger import log_decision

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

LEDGER_FILE = "ledger.json"

# AI 冷卻 / cache
AI_CACHE = {}
AI_COOLDOWN_MINUTES = 1
AI_LAST_CALL = {}

def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_ledger(ledger):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

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
    global AI_CACHE, AI_LAST_CALL

    print("\n" + "=" * 30)
    print("🦅 啟動 009816 AI 存股監控")

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_month = now_tw.strftime("%Y-%m")
    ledger = load_ledger()
    book = ledger.get("009816", {"shares":0, "cost":0.0, "last_buy_month":""})

    # === 1. 報價 ===
    price_00, pct_00 = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    if price_00 <= 0:
        print("⚠️ 當前價格異常，本輪略過")
        return

    # === 2. 籌碼 / 高階資料 ===
    print("📡 取得 FinMind 全維度數據...")
    extra_data = get_high_level_insight("009816.TW")
    if extra_data is None:
        print("⚠️ 高階資料不可用，本輪略過")
        return

    # === 3. 基本摘要 ===
    summary = (
        f"009816價:{price_00:.2f} ({pct_00:+.2f}%)\n"
        f"費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%"
    )

    # === 4. AI 判斷（冷卻 + cache） ===
    last_call = AI_LAST_CALL.get("009816")
    now = datetime.now()
    if last_call and (now - last_call).total_seconds() < AI_COOLDOWN_MINUTES*60:
        ai_result = AI_CACHE.get("009816", {"decision":"觀望","confidence":0,"reason":"冷卻中"})
    else:
        ai_result = get_ai_point(summary, "009816 結婚基金", extra_data)
        if ai_result.get("decision") == "ERROR":
            ai_result = {"decision":"觀望","confidence":0,"reason":"AI error, 略過"}
        AI_CACHE["009816"] = ai_result
        AI_LAST_CALL["009816"] = now

    ai_decision = ai_result.get("decision", "觀望")
    ai_conf = ai_result.get("confidence", 0)
    ai_reason = ai_result.get("reason", "N/A")

    # === 5. 硬風控 ===
    gate_ok, gate_reason = hard_risk_gate(price_00, extra_data)

    # === 6. 月度存股判斷 ===
    if book.get("last_buy_month") == current_month:
        final_action = "⏸ 本月已執行存股，暫停購買"
    elif gate_ok and ai_decision == "可行" and ai_conf >= 60:
        final_action = "✅ AI 判斷可買入，本月存股執行"
        # 模擬每月買一張
        buy_shares = 1000  # 以實際需求調整股數
        cost = buy_shares * price_00
        book["shares"] += buy_shares
        book["cost"] += cost
        book["last_buy_month"] = current_month
        ledger["009816"] = book
        save_ledger(ledger)
    else:
        final_action = f"⏸ 觀望 / 風控阻止: {gate_reason if not gate_ok else ai_decision}"

    # === 7. 紀錄決策 ===
    log_decision(
        symbol="009816",
        price=price_00,
        ai_result=ai_result,
        gate_result=(gate_ok, gate_reason)
    )

    # === 8. Line 推播 ===
    full_msg = (
        f"🦅 009816 AI 存股戰報 ({now_tw.strftime('%Y-%m-%d %H:%M:%S')})\n"
        f"------------------\n"
        f"{summary}\n"
        f"📊 評價: {extra_data.get('valuation', 'N/A')}\n"
        f"📉 盤中力道: {extra_data.get('order_strength', '穩定')}\n"
        f"------------------\n"
        f"{final_action}\n"
        f"🤖 AI 信心: {ai_conf}\n"
        f"🧠 AI 理由: {ai_reason}"
    )

    if LINE_TOKEN and USER_ID:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {
                "Authorization": f"Bearer {LINE_TOKEN}",
                "Content-Type": "application/json"
            }
            payload = {
                "to": USER_ID,
                "messages": [{"type": "text", "text": full_msg}]
            }
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"📊 Line 推送結果: {res.status_code}")
        except Exception as e:
            print(f"⚠️ Line 推播失敗: {e}")

    return
