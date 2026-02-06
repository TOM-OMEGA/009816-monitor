import yfinance as yf
import requests
import os
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import logging

# --- 導入自定義模組 ---
try:
    from ai_expert import get_ai_point
    from data_engine import get_high_level_insight, get_fm_data
    from hard_risk_gate import hard_risk_gate
except ImportError as e:
    print(f"❌ 導入自定義模組失敗: {e}")

# --- 強制修復：防止 Render 環境卡死 ---
import matplotlib
matplotlib.use('Agg') 
logging.getLogger('matplotlib.font_manager').disabled = True

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_realtime_data(ticker):
    """強化版即時價格抓取，增加多重過濾與 Timeout"""
    try:
        t = yf.Ticker(ticker)
        # 增加 timeout 避免 Render 線程永久卡死
        df = t.history(period="5d", timeout=15)
        
        if df is not None and not df.empty and len(df) >= 1:
            curr = round(float(df["Close"].iloc[-1]), 2)
            
            # --- 髒數據修復：009816 經常抓到 10.0 或 10.1 的錯誤佔位符 ---
            if (ticker == "009816.TW" and (10.0 <= curr <= 10.15)) or curr <= 0:
                print(f"⚠️ {ticker} 偵測到疑似無效價格: {curr}，嘗試使用昨日收盤或 info...")
                # 嘗試拿 info
                info_price = t.info.get('regularMarketPrice') or t.info.get('previousClose')
                if info_price and not (10.0 <= info_price <= 10.15):
                    curr = round(float(info_price), 2)
                else:
                    return None, None
            
            # 計算漲跌幅
            if len(df) >= 2:
                prev = float(df["Close"].iloc[-2])
                pct = round(((curr / prev) - 1) * 100, 2)
            else:
                pct = 0.0
            return curr, pct
    except Exception as e:
        print(f"⚠️ yfinance 抓取 {ticker} 異常: {e}")
    return None, None

def run_009816_monitor(force_send=False):
    """
    主監控任務
    :param force_send: 是否無視買入訊號，強迫發送 LINE (診斷用)
    """
    print(f"🦅 [{datetime.now().strftime('%H:%M:%S')}] 啟動 009816 監控程序...")

    # 1. 抓取關鍵價格
    price, _ = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")

    # 2. 抓取 FinMind 數據
    df_fm = get_fm_data("TaiwanStockPrice", "009816.TW", days=45)
    
    # 數據補位邏輯
    if (df_fm is None or df_fm.empty) and price is None:
        print("❌ 核心數據源完全斷線")
        return

    # 歷史數據清洗
    if df_fm is not None and not df_fm.empty:
        df_fm['close'] = pd.to_numeric(df_fm['close'], errors='coerce')
        # 過濾 FinMind 的 10.0 髒數據
        df_fm = df_fm[(df_fm['close'] > 10.15) | (df_fm['close'] < 9.9)].dropna(subset=['close'])
        closes = df_fm["close"]
    else:
        closes = pd.Series([price] * 20) if price else pd.Series([])

    # 如果即時價抓不到或又是 10.1，用 FinMind 最後一筆有效價補位
    if (price is None or (10.0 <= price <= 10.15)) and not closes.empty:
        price = round(float(closes.iloc[-1]), 2)
        print(f"🔄 價格已校準為歷史有效價: {price}")

    if not price or price <= 0:
        print("❌ 無法取得有效價格，終止本輪巡檢")
        return

    # 3. 技術指標計算 (RSI)
    delta = closes.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rsi = 50.0
    if not down.empty and down.iloc[-1] != 0:
        rsi = round(100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1]))), 1)

    # 月高低位
    recent_22 = closes.tail(22)
    m_low = recent_22.min() if not recent_22.empty else price
    pct_low = round((price - m_low) / m_low * 100, 2)

    # 4. 籌碼與 AI 分析
    extra = get_high_level_insight("009816.TW") or {}
    
    # 建構給 AI 的上下文 (移除可能誤導的數據)
    summary = (
        f"現價:{price:.2f}, 月低:{m_low:.2f}, 距月低:{pct_low:.2f}%\n"
        f"RSI:{rsi}, 費半:{sox_pct if sox_pct else 0:+.2f}%, TSM:{tsm_pct if tsm_pct else 0:+.2f}%\n"
        f"法人:{extra.get('order_level','未知')}, 評價:{extra.get('valuation_level','未知')}"
    )

    # 呼叫 AI 診斷
    try:
        ai = get_ai_point(extra, "009816", summary_override=summary)
    except Exception as e:
        print(f"⚠️ AI 判斷超時或失敗: {e}")
        ai = {"decision": "觀望", "reason": "AI 連線不穩", "confidence": 0}

    # 5. 風控閘門
    gate_ok, gate_reason = hard_risk_gate(price, extra)

    # 6. 最終策略決策
    ai_dec = ai.get('decision', '')
    # 只要 RSI 低於 35 或 接近月低 1.5% 且 AI 不反對
    buy_signal = (pct_low <= 1.5 or rsi < 35) and ("觀望" not in ai_dec)
    
    if not gate_ok:
        action = f"⛔【風控攔截】{gate_reason}"
    elif buy_signal:
        action = f"🟢【分批佈局】條件達成"
    else:
        action = f"⏸【觀望】未達買入標竿"

    # 7. LINE 推播發送
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
    msg = (
        f"🦅 經理人 009816 監測 ({now_tw})\n"
        f"------------------\n"
        f"{summary}\n"
        f"------------------\n"
        f"{action}\n"
        f"🧠 AI: {ai.get('reason','')[:60]}"
    )

    # 關鍵：如果是測試模式 (force_send)，不論訊號強迫發送
    if (buy_signal or force_send or "⛔" in action):
        if LINE_TOKEN and USER_ID:
            try:
                url = "https://api.line.me/v2/bot/message/push"
                headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
                payload = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
                res = requests.post(url, headers=headers, json=payload, timeout=15)
                print(f"✅ LINE 發送結果: {res.status_code}")
            except Exception as e:
                print(f"❌ LINE 推播異常: {e}")
    else:
        print(f"⏭ 訊號為觀望且非強制模式，不發送推播。摘要: {price} / RSI:{rsi}")

    return ai
