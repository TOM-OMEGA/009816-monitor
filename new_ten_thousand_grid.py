import yfinance as yf
import requests
import os
import time
import json
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
from data_engine import get_high_level_insight

# =====================
# 一萬元實驗配置
# =====================
TARGETS = {
    "00929.TW": {"cap": 3333, "name": "00929 科技優息"},
    "2317.TW": {"cap": 3334, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "name": "00878 永續高股息"}
}

LEDGER_FILE = "ledger.json"

# AI 冷卻全局
AI_CACHE = {}
AI_COOLDOWN_MINUTES = 1  # 測試可設 1 分鐘，實盤可改
AI_LAST_CALL = {}

# =====================
# 工具區
# =====================
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_ledger(ledger):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

def parse_ai_action(ai_text):
    if not ai_text:
        return "WAIT"
    if isinstance(ai_text, dict):
        decision = ai_text.get("decision", "觀望")
    else:
        decision = str(ai_text)
    if "可行" in decision:
        return "BUY"
    if "不可行" in decision:
        return "NO"
    if "觀望" in decision:
        return "WAIT"
    return "WAIT"

def hard_grid_gate(trend, extra):
    if "🔴" in trend:
        return False, "趨勢空頭"
    if extra.get("valuation") and "高" in extra.get("valuation"):
        return False, "估值偏高"
    if "賣" in extra.get("order_strength", ""):
        return False, "盤中賣壓偏重"
    return True, "通過"

def check_trend(df):
    if len(df) < 60:
        return "⚪ 數據不足"
    c = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    if c > ma20 > ma60:
        return "🟢 多頭排列"
    if c < ma20 < ma60:
        return "🔴 空頭排列"
    return "🟡 區間震盪"

# =====================
# 主程式
# =====================
def run_unified_experiment():
    global AI_CACHE, AI_LAST_CALL
    line_token = os.environ.get("LINE_ACCESS_TOKEN")
    user_id = os.environ.get("USER_ID")
    ledger = load_ledger()

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    report = f"🦅 一萬元 AI 網格實驗報告\n{now_tw.strftime('%Y-%m-%d %H:%M')}\n"
    report += "----------------------------"

    for symbol, cfg in TARGETS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="90d").ffill()
            if df.empty:
                report += f"\n\n❌ {cfg['name']} 資料抓取失敗"
                continue

            price = df['Close'].iloc[-1]
            trend = check_trend(df)

            # RSI 計算
            delta = df['Close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = -delta.where(delta < 0, 0).rolling(14).mean()
            rs = gain / loss.replace(0, 1e-6)
            rsi = 100 - (100 / (1 + rs.iloc[-1]))

            # 高階資料
            extra = get_high_level_insight(symbol)
            if extra is None:
                report += f"\n\n❌ {cfg['name']} 高階資料不可用，本輪略過"
                continue

            # ============================
            # AI 判斷（加 cache / 冷卻）
            # ============================
            now = datetime.now()
            last_call = AI_LAST_CALL.get(symbol)
            if last_call and (now - last_call).total_seconds() < AI_COOLDOWN_MINUTES*60:
                ai_text = AI_CACHE.get(symbol, {"decision":"觀望","confidence":0,"reason":"冷卻中"})
            else:
                summary = f"現價:{price:.2f}, RSI:{rsi:.1f}, 趨勢:{trend}"
                ai_text = get_ai_point(summary, cfg["name"], extra)
                # 若 AI error → 冷卻
                if ai_text.get("decision") == "ERROR":
                    AI_LAST_CALL[symbol] = now
                    ai_text = {"decision":"觀望","confidence":0,"reason":"AI error, 略過"}
                else:
                    AI_CACHE[symbol] = ai_text
                    AI_LAST_CALL[symbol] = now

            ai_action = parse_ai_action(ai_text)
            grid_ok, gate_reason = hard_grid_gate(trend, extra)

            # ===== 帳本初始化 =====
            book = ledger.get(symbol, {"shares":0,"cost":0.0})

            report += f"\n\n📍 {cfg['name']}"
            report += f"\n💵 現價: {price:.2f}"
            report += f"\n📊 趨勢: {trend}"
            report += f"\n🧠 AI: {ai_text}"

            # ===== 下網格單（模擬） =====
            if ai_action == "BUY" and grid_ok:
                # 單檔網格上限: cap / 5 次
                buy_cap = cfg["cap"] / 5
                buy_shares = int(buy_cap / price)
                if buy_shares > 0:
                    cost = buy_shares * price
                    book["shares"] += buy_shares
                    book["cost"] += cost
                    report += f"\n✅ 買入 {buy_shares} 股 (模擬)"
                else:
                    report += f"\n🚫 單次購買股數為 0，本輪略過"
            else:
                report += f"\n🚫 暫停（{gate_reason if ai_action=='BUY' else 'AI未授權'}）"

            ledger[symbol] = book

            # ===== 損益計算 =====
            if book["shares"] > 0:
                avg_cost = book["cost"] / book["shares"]
                pnl = (price - avg_cost) * book["shares"]
                roi = pnl / book["cost"] * 100
                report += (
                    f"\n📒 持股:{book['shares']} "
                    f"成本:{avg_cost:.2f} "
                    f"損益:{pnl:.0f} "
                    f"({roi:.2f}%)"
                )

        except Exception as e:
            report += f"\n\n❌ {cfg['name']} 發生錯誤: {e}"

        # 迴圈間隔，避免 yfinance / AI 秒刷
        time.sleep(5)

    # 儲存帳本
    save_ledger(ledger)

    # Line 推播
    if line_token and user_id:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {line_token}", "Content-Type": "application/json"}
        payload = {"to": user_id, "messages": [{"type": "text", "text": report}]}
        try:
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Line 推播失敗: {e}")

    return report

if __name__ == "__main__":
    print(run_unified_experiment())
