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

def run_009816_monitor(force_send=True):
    print(f"🦅 === 啟動 FinMind 優先監控模式 [{datetime.now().strftime('%H:%M:%S')}] ===")

    # 💡 修改點 1：放棄 yfinance，直接從 FinMind 拿數據
    print("STEP 1: 透過 FinMind 抓取 009816 歷史與當前價...")
    try:
        # 抓 45 天確保 RSI 與均線正確
        df_fm = get_fm_data("TaiwanStockPrice", "009816.TW", days=45)
        
        if df_fm is None or df_fm.empty:
            print("❌ FinMind 回傳空資料，無法繼續")
            return
        
        # 數據清洗 (過濾你提到的 10.1 髒數據)
        df_fm['close'] = pd.to_numeric(df_fm['close'], errors='coerce')
        df_fm = df_fm[(df_fm['close'] > 10.15) | (df_fm['close'] < 9.9)].dropna(subset=['close'])
        
        closes = df_fm["close"]
        price = round(float(closes.iloc[-1]), 2)
        print(f"✅ 取得有效價格: {price} (來自 FinMind)")
    except Exception as e:
        print(f"❌ FinMind 執行異常: {e}")
        return

    # 💡 修改點 2：暫時跳過 ^SOX/TSM (因為它們也依賴 yfinance)
    # 我們先確保主體能跑通
    sox_pct = 0.0
    tsm_pct = 0.0

    # 💡 修改點 3：計算指標 (RSI / 月高低)
    print("STEP 2: 計算技術指標...")
    recent_22 = closes.tail(22)
    m_low = recent_22.min()
    pct_low = round((price - m_low) / m_low * 100, 2)
    
    delta = closes.diff()
    up = delta.clip(lower=0).rolling(14).mean()
    down = -delta.clip(upper=0).rolling(14).mean()
    rsi = 50.0
    if not down.empty and down.iloc[-1] != 0:
        rsi = round(100 - (100 / (1 + (up.iloc[-1] / down.iloc[-1]))), 1)

    # 💡 修改點 4：AI 與 風控
    print("STEP 3: 執行 AI 判斷與風控閘門...")
    try:
        extra = get_high_level_insight("009816.TW") or {}
        summary = f"現價:{price}, RSI:{rsi}, 距月低:{pct_low}%"
        ai = get_ai_point(extra, "009816", summary_override=summary)
    except Exception as e:
        print(f"⚠️ AI 失敗: {e}")
        ai = {"decision": "觀望", "reason": "AI 分析跳過"}

    gate_ok, gate_reason = hard_risk_gate(price, extra)

    # 💡 修改點 5：發送 LINE
    print("STEP 4: 準備推送 LINE...")
    now_tw = datetime.now().strftime("%H:%M:%S")
    msg = (
        f"🦅 009816 監控 (FinMind 數據源)\n"
        f"------------------\n"
        f"現價: {price}\n"
        f"RSI: {rsi}\n"
        f"距月低: {pct_low}%\n"
        f"AI 建議: {ai.get('decision','N/A')}\n"
        f"------------------\n"
        f"⏰ 台北時間: {now_tw}\n"
        f"✅ 看到此訊息代表 yfinance 阻塞已繞過"
    )

    if LINE_TOKEN and USER_ID:
        try:
            url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
            payload = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"📬 LINE 推送完成, 狀態碼: {res.status_code}")
        except Exception as e:
            print(f"❌ LINE 發送失敗: {e}")

    print("🏁 巡檢結束")
    return ai
