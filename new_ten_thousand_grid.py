import yfinance as yf
import requests
import os
import json
import time
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
from data_engine import get_high_level_insight
from hard_risk_gate import hard_risk_gate
from decision_logger import log_decision

# === 設定 ===
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")
LEDGER_FILE = "ledger.json"

# === 一萬元網格實驗標的 ===
TARGETS = {
    "00929.TW": {"cap": 3333, "name": "00929 科技優息"},
    "2317.TW": {"cap": 3334, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "name": "00878 永續高股息"}
}

# === 工具函數 ===
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_ledger(ledger):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2, ensure_ascii=False)

def parse_ai_action(ai_result):
    if not ai_result: return "WAIT"
    if "可行" in ai_result.get("decision",""): return "BUY"
    if "不可行" in ai_result.get("decision",""): return "NO"
    return "WAIT"

def check_trend(df):
    if len(df) < 60: return "⚪ 數據不足"
    c = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    if c > ma20 > ma60: return "🟢 多頭排列"
    if c < ma20 < ma60: return "🔴 空頭排列"
    return "🟡 區間震盪"

def hard_grid_gate(price, extra, trend):
    if "🔴" in trend: return False, "趨勢空頭"
    if extra.get("valuation") and "高" in extra.get("valuation"): return False, "估值偏高"
    if "賣" in extra.get("order_strength","") : return False, "盤中賣壓偏重"
    return True, "風控通過"

# === 網格策略主程式 ===
def run_unified_grid():
    ledger = load_ledger()
    now_tw = datetime.now(timezone(timedelta(hours=8)))
    report = f"🦅 AI 網格實驗報告 {now_tw.strftime('%Y-%m-%d %H:%M')}\n---------------------"

    for symbol, cfg in TARGETS.items():
        try:
            # 1. 取得歷史價格
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="90d").ffill()
            if df.empty: continue
            price = df['Close'].iloc[-1]
            trend = check_trend(df)

            # RSI 計算
            delta = df['Close'].diff()
            gain = delta.where(delta>0,0).rolling(14).mean()
            loss = -delta.where(delta<0,0).rolling(14).mean()
            rs = gain / loss.replace(0,1e-6)
            rsi = 100 - (100 / (1+rs.iloc[-1]))

            # 2. 高階數據
            extra = get_high_level_insight(symbol)
            summary_override = (
                f"現價:{price:.2f}, RSI:{rsi:.1f}, 趨勢:{trend}, "
                f"盤中力道:{extra.get('order_strength','穩定')}, 估值:{extra.get('valuation','N/A')}, "
                f"法人:{extra.get('inst','N/A')}, 大戶:{extra.get('holders','N/A')}, 日內交易:{extra.get('day_trade','N/A')}"
            )

            # 3. AI 判斷
            ai_result = get_ai_point(extra, cfg["name"], summary_override=summary_override)
            ai_action = parse_ai_action(ai_result)

            # 4. 硬風控
            gate_ok, gate_reason = hard_grid_gate(price, extra, trend)

            # 5. 帳本初始化
            book = ledger.get(symbol, {"shares":0,"cost":0.0})
            report += f"\n\n📍 {cfg['name']}\n💵 現價:{price:.2f}\n📊 趨勢:{trend}\n🧠 AI:{ai_result}"

            # 6. 決定是否買入
            if ai_action=="BUY" and gate_ok:
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

            # 7. 計算持股損益
            if book["shares"]>0:
                avg_cost = book["cost"]/book["shares"]
                pnl = (price-avg_cost)*book["shares"]
                roi = pnl/book["cost"]*100
                report += f"\n📒 持股:{book['shares']} 成本:{avg_cost:.2f} 損益:{pnl:.0f} ({roi:.2f}%)"

            # 8. 紀錄決策
            log_decision(symbol, price, ai_result, (gate_ok, gate_reason))

        except Exception as e:
            report += f"\n❌ {cfg['name']} 發生錯誤: {e}"

    save_ledger(ledger)

    # 9. LINE 推播
    if LINE_TOKEN and USER_ID:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_TOKEN}","Content-Type":"application/json"}
            payload = {"to": USER_ID,"messages":[{"type":"text","text":report}]}
            requests.post(url, headers=headers, json=payload, timeout=10)
        except Exception as e:
            print(f"⚠️ Line 推播失敗: {e}")

    return report
