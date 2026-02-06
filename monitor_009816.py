import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
from data_engine import get_high_level_insight, get_fm_data
from hard_risk_gate import hard_risk_gate
import pandas as pd

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

# --------------------------------------------------
# 即時價格（加入防錯：排除 10.0 這種離譜數據）
# --------------------------------------------------
def get_realtime_data(ticker):
    try:
        t = yf.Ticker(ticker)
        # 抓取 5 天確保有足夠樣本
        df = t.history(period="5d", timeout=10)
        if df is not None and not df.empty and len(df) >= 2:
            curr = round(float(df["Close"].iloc[-1]), 2)
            # --- 數據校驗 ---
            if (ticker == "009816.TW" and curr == 10.0) or curr <= 0:
                print(f"⚠️ 偵測到離譜即時價格: {curr}，嘗試改從 info 抓取...")
                curr = t.info.get('regularMarketPrice', None)
                if not curr or curr == 10.0: return None, None
            
            prev = float(df["Close"].iloc[-2])
            pct = round(((curr / prev) - 1) * 100, 2)
            return curr, pct
    except Exception as e:
        print(f"⚠️ yfinance error {ticker}: {e}")
    return None, None

# --------------------------------------------------
# AI 安全包裝
# --------------------------------------------------
def safe_ai_point(extra, target_name, summary):
    try:
        ai = get_ai_point(extra, target_name, summary_override=summary)
        if not ai or "decision" not in ai:
            return {"decision": "中性觀望", "confidence": 30, "reason": "AI 回傳格式不符"}
        return ai
    except Exception as e:
        return {"decision": "中性觀望", "confidence": 20, "reason": f"AI 異常: {str(e)[:20]}"}

# --------------------------------------------------
# 主程式
# --------------------------------------------------
def run_009816_monitor():
    print("🦅 啟動 009816 AI 數據精準校準引擎")

    # 1. 抓取即時價格 (加入 None 保護)
    price, _ = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # 避免格式化 None 報錯
    sox_pct = sox_pct if sox_pct is not None else 0.0
    tsm_pct = tsm_pct if tsm_pct is not None else 0.0

    # 2. 抓取 FinMind 歷史資料
    df = get_fm_data("TaiwanStockPrice", "009816.TW", days=45)
    
    if df is not None and not df.empty:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close'])
        df = df[df['close'] != 10.0] # 💡 同步過濾歷史髒數據
        closes = df["close"]
    else:
        closes = pd.Series([price] * 20) if price else pd.Series([])

    # 數據徹底失效檢查
    if (price is None or price == 10.0) and (not closes.empty):
        price = round(float(closes.iloc[-1]), 2)
    
    if price is None or price <= 0 or price == 10.0:
        print("❌ 數據源髒污且無法修復，終止監控"); return

    # 4. 計算指標
    recent_22 = closes.tail(22)
    month_low = recent_22.min() if not recent_22.empty else price
    pct_from_low = round((price - month_low) / month_low * 100, 2)

    # RSI 計算強化 (修正滾動 NaN 問題)
    delta = closes.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    if not down.empty and down.iloc[-1] != 0:
        rsi = round(100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1]))), 1)
    else:
        rsi = 50.0

    # 5. 趨勢判斷
    trend = "盤整"
    if len(closes) >= 20:
        ma10 = closes.rolling(10).mean().iloc[-1]
        ma20 = closes.rolling(20).mean().iloc[-1]
        if price > ma10 > ma20: trend = "多頭"
        elif price < ma10 < ma20: trend = "空頭"

    tech = []
    if len(closes) >= 20:
        std = closes.tail(20).std()
        ma20_val = closes.tail(20).mean()
        if price < ma20_val - 2*std: tech.append("布林:超跌")
        elif price > ma20_val + 2*std: tech.append("布林:過熱")
        else: tech.append("布林:中軌區域")

    # 6. 籌碼與 AI 分析
    extra = get_high_level_insight("009816.TW") or {}
    summary = (
        f"現價:{price:.2f}, 月低:{month_low:.2f}, 距月低:{pct_from_low:.2f}%\n"
        f"RSI:{rsi}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
        f"技術結構:{' / '.join(tech) if tech else '正常'}, 法人:{extra.get('inst','normal')}"
    )

    ai = safe_ai_point(extra, "009816", summary)
    gate_ok, gate_reason = hard_risk_gate(price, extra)

    # 7. 最終決策 (放寬判定條件，增加 "可行" 字串包含判斷)
    ai_decision = ai.get('decision', '觀望')
    buy_signal = (pct_from_low <= 1.5 or rsi < 35) and trend != "空頭"
    
    if not gate_ok:
        action = f"⛔【風控攔截】{gate_reason}"
    elif buy_signal and ("可行" in ai_decision or "買入" in ai_decision):
        action = f"🟢【可分批佈局】接近月低 ({pct_from_low}%)"
    else:
        action = f"⏸【觀望】數據未達買入標準"

    # 8. LINE 推播
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M:%S")
    msg = (
        f"🦅 AI 數據校準提醒 ({now_tw})\n"
        f"------------------\n"
        f"{summary}\n"
        f"------------------\n"
        f"{action}\n"
        f"🧠 AI 理由: {ai.get('reason','')}"
    )

    if LINE_TOKEN and USER_ID:
        try:
            res = requests.post("https://api.line.me/v2/bot/message/push",
                          headers={"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"},
                          json={"to": USER_ID, "messages": [{"type": "text", "text": msg}]}, timeout=10)
            res.raise_for_status()
        except Exception as e:
            print(f"❌ LINE 推播失敗: {e}")

    return ai
