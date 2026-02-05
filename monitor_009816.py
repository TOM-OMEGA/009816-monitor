import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
# ✅ 引入精準數據引擎
from data_engine import get_high_level_insight 

# 直接對齊您指定的 Render 環境變數名稱
LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_data(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if len(hist) < 2: return 0.0, 0.0
        return float(hist['Close'].iloc[-1]), ((hist['Close'].iloc[-1] / hist['Close'].iloc[-2]) - 1) * 100
    except:
        return 0.0, 0.0

def run_009816_monitor():
    print("🚀 啟動 009816 存股專屬監控 (精準數據版)...")
    
    # 1. 抓取即時報價與技術指標
    price_00, _ = get_data("009816.TW")
    _, sox_pct = get_data("^SOX")
    _, tsm_pct = get_data("TSM")
    
    # 計算 RSI (小時線)
    try:
        h_hist = yf.Ticker("009816.TW").history(period="2mo", interval="1h")['Close']
        delta = h_hist.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
        rs = gain / loss.replace(0, 1e-6)
        rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))
    except:
        rsi_val = 50.0 # 若計算失敗則給予中位數

    # 2. ✅ 從 FinMind 調閱數據 (包含 11 項細節)
    print("📡 正在向 FinMind 調閱法人與全維度數據...")
    extra_data = get_high_level_insight("009816.TW")

    # 統一台灣時間 (符合 2026 最新語法)
    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_time = now_tw.strftime("%H:%M:%S")
    
    gap = round(price_00 - 10.12, 2)
    gap_msg = f"🚩 距離目標 10.12 還差 {gap} 元" if gap > 0 else "🔥 已達 10.12 進場紀律位階！"
    
    # 整理摘要資訊
    summary = f"009816價:{price_00:.2f}, RSI:{rsi_val:.1f}\n費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%"

    # ✅ 呼叫 AI 專家 (注入 2027 結婚基金邏輯)
    try:
        ai_msg = get_ai_point(summary, "009816 結婚基金", extra_data)
    except Exception as e:
        print(f"⚠️ AI 診斷異常: {e}")
        ai_msg = "💡 AI 顧問目前進行數據微調中，請依紀律操作。"

    # 構建完整戰報內容 (確保 N/A 數據能正確顯示)
    full_msg = (
        f"🦅 經理人精準戰報 ({current_time})\n"
        f"------------------\n"
        f"{summary}\n"
        f"📊 籌碼: {extra_data.get('inst', '數據讀取中')}\n"
        f"📈 營收: {extra_data.get('rev', '數據讀取中')}\n"
        f"🏛️ 大戶: {extra_data.get('holders', '數據讀取中')}\n"
        f"------------------\n"
        f"{gap_msg}\n"
        f"------------------\n"
        f"🧠 AI 診斷：\n{ai_msg}"
    )
    
    # ✅ 關鍵：強化後的 Line 發送邏輯 (防斷連與報錯)
    if LINE_TOKEN and USER_ID:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            if res.status_code == 200:
                print(f"✅ Line 戰報發送成功 (009816)")
                return "SUCCESS"
            else:
                print(f"❌ Line API 拒絕發送: {res.status_code} - {res.text}")
                return f"LINE_ERROR_{res.status_code}"
        except Exception as e:
            print(f"❌ Line 連線崩潰: {e}")
            return "CONNECTION_FAILED"
    else:
        print("❌ 警告：缺少 LINE_ACCESS_TOKEN 或 USER_ID 環境變數")
        return "MISSING_ENV"
