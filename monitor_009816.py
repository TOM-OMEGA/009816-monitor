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

# --- 環境隔離 ---
import matplotlib
matplotlib.use('Agg') 
logging.getLogger('matplotlib.font_manager').disabled = True

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_realtime_data(ticker):
    """診斷版：加入極短 timeout 與詳細 Log"""
    print(f"🔍 [數據抓取] 正在讀取 {ticker}...")
    try:
        t = yf.Ticker(ticker)
        # 縮短 timeout 到 7 秒，避免 Render 線程卡死
        df = t.history(period="3d", timeout=7)
        
        if df is not None and not df.empty:
            curr = round(float(df["Close"].iloc[-1]), 2)
            print(f"✅ {ticker} 抓取成功: {curr}")
            return curr, 0.0
        else:
            print(f"⚠️ {ticker} 回傳空資料")
    except Exception as e:
        print(f"❌ {ticker} 抓取崩潰: {e}")
    return None, None

def run_009816_monitor(force_send=True): # 預設改為 True 強制運行
    print(f"🦅 === 進入診斷監控模式 [{datetime.now().strftime('%H:%M:%S')}] ===")

    # 1. 抓取價格 (分段 Log 鎖定卡死點)
    print("STEP 1: 抓取 009816 價格...")
    price, _ = get_realtime_data("009816.TW")
    
    print("STEP 2: 抓取 ^SOX 價格...")
    _, sox_pct = get_realtime_data("^SOX")
    
    print("STEP 3: 抓取 TSM 價格...")
    _, tsm_pct = get_realtime_data("TSM")

    # 2. 抓取 FinMind 數據 (最容易超時的地方)
    print("STEP 4: 抓取 FinMind 歷史數據...")
    try:
        df_fm = get_fm_data("TaiwanStockPrice", "009816.TW", days=45)
        print(f"✅ FinMind 抓取完成，筆數: {len(df_fm) if df_fm is not None else 0}")
    except Exception as e:
        print(f"❌ FinMind 執行異常: {e}")
        df_fm = None

    # 3. 數據校準與防髒數據邏輯
    if not price or (10.0 <= price <= 10.15):
        if df_fm is not None and not df_fm.empty:
            price = round(float(df_fm['close'].iloc[-1]), 2)
            print(f"🔄 即時價無效，校準為歷史價: {price}")
        else:
            price = 10.12 # 強制保底價，防止後續計算崩潰
            print(f"⚠️ 數據全斷，使用保底佔位價: {price}")

    # 4. 技術指標計算
    print("STEP 5: 計算技術指標...")
    # (此處簡化計算，確保不卡死)
    rsi = 50.0
    m_low = price * 0.98
    pct_low = 1.0

    # 5. AI 與 風控 (增加 Timeout 保護)
    print("STEP 6: 呼叫 AI 專家...")
    summary = f"現價:{price}, 測試模式"
    try:
        extra = get_high_level_insight("009816.TW") or {}
        ai = get_ai_point(extra, "009816", summary_override=summary)
    except Exception as e:
        print(f"⚠️ AI 模組卡死或異常: {e}")
        ai = {"decision": "中性", "reason": "診斷模式自動跳過"}

    # 6. 強制發送 LINE (診斷核心)
    print("STEP 7: 執行 LINE 推播發送...")
    msg = (
        f"🛠 009816 診斷報告\n"
        f"------------------\n"
        f"狀態: 伺服器存活\n"
        f"偵測價: {price}\n"
        f"時區: {datetime.now().strftime('%H:%M:%S')}\n"
        f"AI 回應: {ai.get('decision','無')}\n"
        f"------------------\n"
        f"✅ 看到此訊息代表發送功能正常"
    )

    if LINE_TOKEN and USER_ID:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
            payload = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"📬 LINE 最終回傳碼: {res.status_code}")
        except Exception as e:
            print(f"❌ LINE 物理性連線失敗: {e}")
    else:
        print("❌ 缺少 Token 或 ID，取消發送")

    print("🏁 診斷任務全流程結束")
    return ai
