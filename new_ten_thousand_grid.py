import yfinance as yf
import requests, os, json
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
from data_engine import get_high_level_insight
from decision_logger import log_decision

# ================= 設定 =================
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")
LEDGER_FILE = "ledger.json"

GRID_LEVELS = 5
GRID_GAP_PCT = 0.03          # 3%
TAKE_PROFIT_PCT = 0.05      # 5%

TARGETS = {
    "00929.TW": {"cap": 3333, "name": "00929 科技優息"},
    "2317.TW": {"cap": 3334, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "name": "00878 永續高股息"}
}

# ================= 工具 =================
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        return json.load(open(LEDGER_FILE, "r", encoding="utf-8"))
    return {}

def save_ledger(l):
    json.dump(l, open(LEDGER_FILE,"w",encoding="utf-8"), indent=2, ensure_ascii=False)

def safe_ai(extra, name, summary):
    try:
        return get_ai_point(extra, name, summary_override=summary)
    except Exception as e:
        return {"decision":"AI失效，保守處理","reason":str(e)}

def trend_check(df):
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    c = df['Close'].iloc[-1]
    if c > ma20 > ma60: return "🟢 多頭"
    if c < ma20 < ma60: return "🔴 空頭"
    return "🟡 盤整"

def build_grid(price):
    return [round(price*(1-GRID_GAP_PCT*(i+1)),2) for i in range(GRID_LEVELS)]

# ================= 主程式 =================
def run_unified_experiment():
    ledger = load_ledger()
    now = datetime.now(timezone(timedelta(hours=8)))
    report = [f"🦅 AI 存股網格 {now:%Y-%m-%d %H:%M}", "-"*20]

    for symbol,cfg in TARGETS.items():
        try:
            df = yf.Ticker(symbol).history(period="6mo").ffill()
            if df.empty: continue

            price = float(df['Close'].iloc[-1])
            trend = trend_check(df)

            # RSI
            delta = df['Close'].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss.replace(0,1e-6)
            rsi = 100 - 100/(1+rs.iloc[-1])

            # 月內高低
            month_df = df[df.index.month == now.month]
            month_low = month_df['Low'].min()
            month_high = month_df['High'].max()
            dist_low = (price/month_low-1)*100

            extra = get_high_level_insight(symbol)
            summary = (
                f"現價:{price:.2f}, 月低:{month_low:.2f}, "
                f"距低:{dist_low:.2f}%, RSI:{rsi:.1f}, 趨勢:{trend}"
            )

            ai = safe_ai(extra, cfg["name"], summary)
            allow_buy = "可行" in ai.get("decision","")

            book = ledger.get(symbol,{
                "shares":0,"cost":0.0,"grid":{}
            })

            report.append(
                f"\n📍 {cfg['name']}\n"
                f"💵 {price:.2f} | 月低 {month_low:.2f}\n"
                f"📊 {trend} | RSI {rsi:.1f}"
            )

            if "🔴" in trend:
                report.append("⛔ 趨勢轉空，停機")
            else:
                grid = build_grid(price)
                per_cap = cfg["cap"]/GRID_LEVELS

                if allow_buy:
                    for i,gp in enumerate(grid):
                        if price<=gp and str(i) not in book["grid"]:
                            qty = int(per_cap/price)
                            if qty>0:
                                book["grid"][str(i)]={"price":price,"qty":qty}
                                book["shares"]+=qty
                                book["cost"]+=qty*price
                                report.append(f"🧩 買入 第{i+1}格 {qty} 股")
                            break
                else:
                    report.append("⏸ AI 未授權")

                # 反向賣出
                for k,v in list(book["grid"].items()):
                    if price>=v["price"]*(1+TAKE_PROFIT_PCT):
                        book["shares"]-=v["qty"]
                        book["cost"]-=v["price"]*v["qty"]
                        del book["grid"][k]
                        report.append(f"💰 賣出 第{int(k)+1}格")

            if book["shares"]>0:
                avg = book["cost"]/book["shares"]
                pnl = (price-avg)*book["shares"]
                report.append(f"📒 持股 {book['shares']} | 成本 {avg:.2f} | 損益 {pnl:.0f}")

            ledger[symbol]=book
            log_decision(symbol, price, ai, trend)

        except Exception as e:
            report.append(f"❌ {symbol} 錯誤 {e}")

    save_ledger(ledger)

    # LINE
    if LINE_TOKEN and USER_ID:
        for i in range(0,len(report),20):
            requests.post(
                "https://api.line.me/v2/bot/message/push",
                headers={"Authorization":f"Bearer {LINE_TOKEN}"},
                json={"to":USER_ID,"messages":[{"type":"text","text":"\n".join(report[i:i+20])}]}
            )

    return "\n".join(report)
