import yfinance as yf
import requests, os, json
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
from data_engine import get_high_level_insight
from decision_logger import log_decision
import pandas as pd

# --- 強制修復：防止伺服器環境卡死 ---
import matplotlib
matplotlib.use('Agg')
# -------------------------------

# ================= 設定 =================
# 💡 已改用 Discord Webhook
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
LEDGER_FILE = "ledger.json"

GRID_LEVELS = 5
GRID_GAP_PCT = 0.03      # 3%
TAKE_PROFIT_PCT = 0.05      # 5%

TARGETS = {
    "00929.TW": {"cap": 3333, "name": "00929 科技優息"},
    "2317.TW": {"cap": 3334, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "name": "00878 永續高股息"}
}

# ================= 工具 =================
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_ledger(l):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(l, f, indent=2, ensure_ascii=False)

def safe_ai(extra, name, summary):
    try:
        return get_ai_point(extra, name, summary_override=summary)
    except Exception as e:
        return {"decision": "觀望", "reason": f"AI失效: {str(e)[:20]}"}

def trend_check(df):
    if len(df) < 60: return "🟡 數據不足"
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    c = df['Close'].iloc[-1]
    if c > ma20 > ma60: return "🟢 多頭"
    if c < ma20 < ma60: return "🔴 空頭"
    return "🟡 盤整"

def build_grid(price):
    return [round(price*(1-GRID_GAP_PCT*(i+1)), 2) for i in range(GRID_LEVELS)]

# ================= 主程式 =================
def run_unified_experiment():
    ledger = load_ledger()
    now = datetime.now(timezone(timedelta(hours=8)))
    # 💡 使用 Discord 的 Markdown 語法讓標題更顯眼
    report = [f"# 🦅 AI 存股網格報告", f"**時間:** `{now:%Y-%m-%d %H:%M}`", "-"*25]

    for symbol, cfg in TARGETS.items():
        try:
            df = yf.Ticker(symbol).history(period="6mo", timeout=15)
            if df.empty:
                report.append(f"❌ {cfg['name']} 抓不到數據"); continue
            df = df.ffill().dropna(subset=['Close'])

            price = float(df['Close'].iloc[-1])
            trend = trend_check(df)

            delta = df['Close'].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            
            last_gain = gain.iloc[-1] if not gain.empty else 0
            last_loss = loss.iloc[-1] if not loss.empty else 0
            
            if last_loss == 0:
                rsi = 100.0 if last_gain > 0 else 50.0
            else:
                rsi = 100 - 100/(1 + (last_gain / last_loss))

            month_df = df[df.index.month == now.month]
            if month_df.empty: month_df = df.tail(20)
            month_low = month_df['Low'].min()
            dist_low = (price/month_low-1)*100 if month_low > 0 else 0

            extra = get_high_level_insight(symbol) or {}
            summary = (
                f"現價:{price:.2f}, 月低:{month_low:.2f}, "
                f"距低:{dist_low:.2f}%, RSI:{rsi:.1f}, 趨勢:{trend}"
            )

            ai = safe_ai(extra, cfg["name"], summary)
            ai_decision = ai.get("decision", "")
            allow_buy = "可行" in ai_decision or "買入" in ai_decision

            book = ledger.get(symbol, {
                "shares": 0, "cost": 0.0, "grid": {}
            })

            report.append(
                f"\n### 📍 {cfg['name']}\n"
                f"💰 **現價:** `{price:.2f}` | **月低:** `{month_low:.2f}`\n"
                f"📈 **趨勢:** {trend} | **RSI:** `{rsi:.1f}`"
            )

            if "🔴" in trend:
                report.append("⚠️ **趨勢轉空，網格買入暫停**")
            else:
                grid = build_grid(price)
                per_cap = cfg["cap"]/GRID_LEVELS

                if allow_buy:
                    for i, gp in enumerate(grid):
                        if price <= gp and str(i) not in book["grid"]:
                            qty = int(per_cap/price)
                            if qty > 0:
                                book["grid"][str(i)] = {"price": price, "qty": qty}
                                book["shares"] += qty
                                book["cost"] += qty * price
                                report.append(f"✅ **買入** 第{i+1}格 {qty} 股")
                            break
                else:
                    report.append(f"⏸ **AI 建議:** {ai_decision}")

                for k, v in list(book["grid"].items()):
                    if price >= v["price"] * (1 + TAKE_PROFIT_PCT):
                        book["shares"] -= v["qty"]
                        book["cost"] -= v["price"] * v["qty"]
                        del book["grid"][k]
                        report.append(f"🎊 **賣出** 第{int(k)+1}格 (獲利結清)")

            if book["shares"] > 0:
                avg = book["cost"] / book["shares"]
                pnl = (price - avg) * book["shares"]
                roi = (pnl / book["cost"] * 100) if book["cost"] > 0 else 0
                report.append(f"📒 持股: `{book['shares']}` | 均價: `{avg:.2f}` | 損益: `{pnl:.0f}` (**{roi:.1f}%**)")

            ledger[symbol] = book
            log_decision(symbol, price, ai, (True, trend))

        except Exception as e:
            report.append(f"❌ {symbol} 異常: `{str(e)[:30]}`")

    save_ledger(ledger)

    # 💡 替換為 Discord Webhook 發送邏輯
    if DISCORD_WEBHOOK_URL:
        # Discord 單次訊息上限為 2000 字，將報告分段發送
        full_msg = "\n".join(report)
        for i in range(0, len(full_msg), 1900):
            payload = {
                "username": "AI 網格交易員",
                "content": full_msg[i:i+1900]
            }
            try:
                # Discord 成功回傳的是 204 No Content
                res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
                if res.status_code != 204:
                    print(f"❌ Discord 報錯: {res.text}")
            except Exception as e:
                print(f"❌ Discord 請求失敗: {e}")

    return "\n".join(report)
