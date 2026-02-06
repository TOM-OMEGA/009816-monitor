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
            # --- 關鍵修正：數據校驗 ---
            # 009816 如果抓到 10.0 或 0.0，通常是 yfinance 抓取失敗的佔位符
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
# AI 安全包裝（維持您的穩健判斷邏輯）
# --------------------------------------------------
def safe_ai_point(extra, target_name, summary):
    try:
        # 增加超時保護，避免 AI 卡死
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

    # 1. 抓取即時價格
    price, _ = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # 2. 抓取 FinMind 歷史資料（天數拉長到 45 天確保 RSI 準確）
    df = get_fm_data("TaiwanStockPrice", "009816.TW", days=45)
    
    # 3. 數據完整性檢查
    if (df is None or df.empty) and price is None:
        print("❌ 完全抓不到數據，終止監控"); return

    if df is not None and not df.empty:
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df = df.dropna(subset=['close'])
        closes = df["close"]
    else:
        # 如果 FinMind 掛了但即時價格還有，建立最小 DataFrame
        closes = pd.Series([price] * 20)

    # 如果即時價格失效，用歷史最後一筆補位
    if price is None or price == 10.0:
        price = round(float(closes.iloc[-1]), 2)
        if price == 10.0: # 如果連歷史最後一筆都是 10.0，代表數據源徹底髒了
            print("⚠️ 歷史數據庫也存在離譜值，停止分析"); return

    # 4. 計算指標
    month_low = closes.tail(22).min() # 取最近一個月的最低
    month_high = closes.tail(22).max()
    pct_from_low = round((price - month_low) / month_low * 100, 2)

    # RSI 計算（修正 nan 問題）
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(14).mean().iloc[-1]
    loss = -delta.clip(upper=0).rolling(14).mean().iloc[-1]
    if loss == 0: rsi = 100 if gain > 0 else 50
    else: rsi = round(100 - (100 / (1 + (gain/loss))), 1)

    # 5. 趨勢與技術結構
    trend = "盤整"
    if len(closes) >= 20:
        ma10 = closes.rolling(10).mean().iloc[-1]
        ma20 = closes.rolling(20).mean().iloc[-1]
        if price > ma10 > ma20: trend = "多頭"
        elif price < ma10 < ma20: trend = "空頭"

    tech = []
    # 布林帶判斷
    if len(closes) >= 20:
        std = closes.tail(20).std()
        ma20 = closes.tail(20).mean()
        if price < ma20 - 2*std: tech.append("布林:超跌")
        elif price > ma20 + 2*std: tech.append("布林:過熱")
        else: tech.append("布林:中軌區域")

    # 6. 籌碼與 AI 分析
    extra = get_high_level_insight("009816.TW") or {}
    
    # 強化摘要：直接告訴 AI 哪些數據是準確的，防止它參考錯誤資訊
    summary = (
        f"現價:{price:.2f}, 月低:{month_low:.2f}, 距月低:{pct_from_low:.2f}%\n"
        f"RSI:{rsi}, 趨勢:{trend}, 費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%\n"
        f"技術結構:{' / '.join(tech)}, 法人:{extra.get('inst','normal')}"
    )

    ai = safe_ai_point(extra, "009816", summary)
    gate_ok, gate_reason = hard_risk_gate(price, extra)

    # 7. 最終決策
    buy_signal = (pct_from_low <= 1.5 or rsi < 35) and trend != "空頭"
    
    if not gate_ok:
        action = f"⛔【風控攔截】{gate_reason}"
    elif buy_signal and ai.get('decision') == "可行":
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
        requests.post("https://api.line.me/v2/bot/message/push",
                      headers={"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"},
                      json={"to": USER_ID, "messages": [{"type": "text", "text": msg}]}, timeout=10)

    return ai
