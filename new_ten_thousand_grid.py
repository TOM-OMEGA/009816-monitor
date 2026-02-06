import yfinance as yf
import requests, os, json, time
from datetime import datetime, timezone, timedelta
import pandas as pd
import logging

# --- 強制修復：防止伺服器環境卡死 ---
import matplotlib
matplotlib.use('Agg')

# ================= 設定 =================
# 💡 改為純回傳模式，不再從這裡發送 Discord
LEDGER_FILE = "/tmp/ledger.json"  # 在 Render 環境中，/tmp 是唯一可寫的地方，但重啟仍會消失

GRID_LEVELS = 5
GRID_GAP_PCT = 0.03      # 3%
TAKE_PROFIT_PCT = 0.05   # 5%

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
        except: return {}
    return {}

def save_ledger(l):
    try:
        with open(LEDGER_FILE, "w", encoding="utf-8") as f:
            json.dump(l, f, indent=2, ensure_ascii=False)
    except: pass

def trend_check(df):
    if len(df) < 60: return "🟡 盤整"
    # 確保處理多層索引
    close = df['Close']
    if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
    
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1]
    c = close.iloc[-1]
    
    if c > ma20 > ma60: return "🟢 多頭"
    if c < ma20 < ma60: return "🔴 空頭"
    return "🟡 盤整"

def build_grid(price):
    return [round(price*(1-GRID_GAP_PCT*(i+1)), 2) for i in range(GRID_LEVELS)]

# ================= 主程式 =================
def run_unified_experiment():
    ledger = load_ledger()
    # 設定台灣時區
    tw_tz = timezone(timedelta(hours=8))
    now = datetime.now(tw_tz)
    
    report = [f"# 🦅 AI 存股網格報告", f"**時間:** `{now:%Y-%m-%d %H:%M}`", "-"*25]

    for symbol, cfg in TARGETS.items():
        try:
            # 加入偽裝 headers 避免被擋
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="6mo", timeout=15)
            
            if df.empty:
                report.append(f"❌ {cfg['name']} 數據抓取為空"); continue
            
            # 確保價格處理正確 (排除多層索引)
            if isinstance(df['Close'], pd.DataFrame):
                price = float(df['Close'].iloc[-1, 0])
                low_series = df['Low'].iloc[:, 0]
                close_series = df['Close'].iloc[:, 0]
            else:
                price = float(df['Close'].iloc[-1])
                low_series = df['Low']
                close_series = df['Close']

            trend = trend_check(df)

            # RSI 計算
            delta = close_series.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            last_gain = gain.iloc[-1]; last_loss = loss.iloc[-1]
            rsi = 100 - 100/(1 + (last_gain / (last_loss if last_loss > 0 else 0.001)))

            month_low = low_series.tail(20).min()

            report.append(
                f"\n### 📍 {cfg['name']}\n"
                f"💰 **現價:** `{price:.2f}` | **月低:** `{month_low:.2f}`\n"
                f"📈 **趨勢:** {trend} | **RSI:** `{rsi:.1f}`"
            )

            # 邏輯判斷
            if "🔴" in trend:
                report.append("⚠️ **趨勢轉空，網格買入暫停**")
            else:
                book = ledger.get(symbol, {"shares": 0, "cost": 0.0, "grid": {}})
                # 這裡暫時省略了 AI API 的調用以確保穩定，預設為觀望
                report.append(f"⏸ **AI 建議:** 觀望")

            # 損益摘要
            book = ledger.get(symbol, {"shares": 0, "cost": 0.0, "grid": {}})
            if book["shares"] > 0:
                avg = book["cost"] / book["shares"]
                roi = ((price - avg) / avg * 100)
                report.append(f"📒 持股: `{book['shares']}` | 均價: `{avg:.2f}` | 損益: (**{roi:.1f}%**)")

        except Exception as e:
            report.append(f"❌ {symbol} 異常: `{str(e)[:30]}`")

    save_ledger(ledger)
    return "\n".join(report)

# ================= 入口 =================
def run_grid():
    try:
        return run_unified_experiment()
    except Exception as e:
        return f"❌ 網格模組執行失敗: {e}"
