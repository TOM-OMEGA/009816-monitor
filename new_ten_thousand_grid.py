import yfinance as yf
import requests
import os
import time
import json
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
from data_engine import get_high_level_insight

# === 一萬元實驗配置 ===
TARGETS = {
    "00929.TW": {"cap": 3333, "name": "00929 科技優息"},
    "2317.TW": {"cap": 3334, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "name": "00878 永續高股息"}
}
LEDGER_FILE = "ledger.json"

# === 工具函數 ===
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_ledger(ledger):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

def parse_ai_action(ai_text):
    if not ai_text: return "WAIT"
    if "可行" in ai_text.get("decision", ""): return "BUY"
    if "不可行" in ai_text.get("decision", ""): return "NO"
    return "WAIT"

def hard_grid_gate(trend, extra):
    if "🔴" in trend: return False, "趨勢空頭"
    if extra.get("valuation") and "高" in extra.get("valuation"): return False, "估值偏高"
    if "賣" in extra.get("order_strength", ""): return False, "盤中賣壓偏重"
    return True, "通過"

def check_trend(df):
    if len(df) < 60: return "⚪ 數據不足"
    c = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    if c > ma20 > ma60: return "🟢 多頭排列"
    if c < ma20 < ma60: return "🔴 空頭排列"
    return "🟡 區間震盪"

# === 主程式 ===
def run_unified_experiment():
    line_token = os.environ.get("LINE_ACCESS_TOKEN")
    user_id = os.environ.get("USER_ID")
    ledger = load_ledger()

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    report = f"🦅 一萬元 AI 網格實驗報告\n{now_tw.strftime('%Y-%m-%d %H:%M')}\n----------------------------"

    for symbol, cfg in TARGETS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="90d").ffill()
            if df.empty: continue

            price = df['Close'].iloc[-1]
            trend = check_trend(df)

            delta = df['Close'].diff()
            gain = delta.where(delta>0,0).rolling(14).mean()
            loss = -delta.where(delta<0,0).rolling(14).mean()
            rs = gain / loss.replace(0,1e-6)
            rsi = 100 - (100 / (1+rs.iloc[-1]))

            extra = get_high_level_insight(symbol)
            summary_override = f"現價:{price:.2f}, RSI:{rsi:.1f}, 趨勢:{trend}"
            ai_text = get_ai_point(extra, cfg["name"], summary_override=summary_override)
            ai_action = parse_ai_action(ai_text)

            grid_ok, gate_reason = hard_grid_gate(trend, extra)

            book = ledger.get(symbol, {"shares":0, "cost":0.0})
            report += f"\n\n📍 {cfg['name']}\n💵 現價: {price:.2f}\n📊 趨勢: {trend}\n🧠 AI: {ai_text}"

            if ai_action=="BUY" and grid_ok:
                buy_cap = cfg["cap"] / 5
                buy_shares = int(buy_cap / price)
                if buy_shares>0:
                    cost = buy_shares*price
                    book["shares"] += buy_shares
                    book["cost"] += cost
                    report += f"\n✅ 買入 {buy_shares} 股"
            else:
                report += f"\n🚫 暫停（{gate_reason if ai_action=='BUY' else 'AI未授權'}）"

            ledger[symbol] = book
            if book["shares"]>0:
                avg_cost = book["cost"]/book["shares"]
                pnl = (price-avg_cost)*book["shares"]
                roi = pnl/book["cost"]*100
                report += f"\n📒 持股:{book['shares']} 成本:{avg_cost:.2f} 損益:{pnl:.0f} ({roi:.2f}%)"

        except Exception as e:
            report += f"\n\n❌ {cfg['name']} 發生錯誤: {e}"

    save_ledger(ledger)

    if line_token and user_id:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {line_token}", "Content-Type": "application/json"}
            payload = {"to": user_id, "messages":[{"type":"text","text":report}]}
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Line 推播失敗: {e
