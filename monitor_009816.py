import yfinance as yf
import requests
import os
import sys
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
# ✅ 引入精準數據引擎
from data_engine import get_high_level_insight 

# 直接對齊您指定的 Render 環境變數名稱
LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_data(ticker):
    print(f"🔍 正在向 yfinance 索取 {ticker} 數據...")
    try:
        t = yf.Ticker(ticker)
        # 加上縮短天數以加快讀取速度
        hist = t.history(period="3d")
        if hist.empty or len(hist) < 2:
            print(f"⚠️ {ticker} 數據回傳為空或不足天數")
            return 0.0, 0.0
        close = float(hist['Close'].iloc[-1])
        pct = ((hist['Close'].iloc[-1] / hist['Close'].iloc[-2]) - 1) * 100
        print(f"✅ {ticker} 獲取成功: {close}")
        return close, pct
    except Exception as e:
        print(f"❌ {ticker} 抓取崩潰: {e}")
        return 0.0, 0.0

def run_009816_monitor():
    print("\n" + "="*30)
    print("🚀 啟動 009816 存股專屬監控系統")
    print(f"⏰ 啟動時間: {datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 檢查 Key 是否存在
    if not LINE_TOKEN or not USER_ID:
        print("❌ 關鍵警告：LINE_ACCESS_TOKEN 或 USER_ID 缺失！")
    
    # 1. 抓取即時報價與技術指標
    price_00, _ = get_data("009816.TW")
    _, sox_pct = get_data("^SOX")
    _, tsm_pct = get_data("TSM")
    
    # 計算 RSI
    print("📊 正在計算 RSI 技術指標...")
    try:
        h_hist = yf.Ticker("009816.TW").history(period="2mo", interval="1h")['Close']
        if not h_hist.empty:
            delta = h_hist.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
            rs = gain / loss.replace(0, 1e-6)
            rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))
            print(f"✅ RSI 計算完成: {rsi_val:.2f}")
        else:
            rsi_val = 50.0
    except Exception as e:
        print(f"⚠️ RSI 計算失敗: {e}")
        rsi_val = 50.0

    # 2. ✅ 從 FinMind 調閱數據 (包含 11 項細節)
    print("📡 正在調閱 FinMind 11 維度全籌碼數據...")
    extra_data = get_high_level_insight("009816.TW")
    print(f"✅ FinMind 數據欄位: {list(extra_data.keys())}")

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_time = now_tw.strftime("%H:%M:%S")
    
    gap = round(price_00 - 10.12, 2)
    gap_msg = f"🚩 距離目標 10.12 還差 {gap} 元" if gap > 0 else "🔥 已達 10.12 進場紀律位階！"
    
    summary = f"009816價:{price_00:.2f}, RSI:{rsi_val:.1f}\n費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%"

    # ✅ 呼叫 AI 專家
    print("🧠 正在啟動 Gemini 3 Pro 預覽版進行深度診斷...")
    try:
        ai_msg = get_ai_point(summary, "009816 結婚基金", extra_data)
        print("✅ AI 診斷報告生成成功")
    except Exception as e:
        print(f"❌ AI 診斷環節報錯: {e}")
        ai_msg = "💡 AI 顧問目前連線不穩，請參照紀律操作。"

    # 構建完整戰報內容
    full_msg = (
        f"🦅 經理人精準戰報 ({current_time})\n"
        f"------------------\n"
        f"{summary}\n"
        f"📊 籌碼指標: {extra_data.get('valuation', 'N/A')}\n"
        f"📈 盤中力道: {extra_data.get('order_strength', '穩定')}\n"
        f"------------------\n"
        f"{gap_msg}\n"
        f"------------------\n"
        f"🧠 AI 診斷：\n{ai_msg}"
    )
    
    # ✅ 關鍵發送
    if LINE_TOKEN and USER_ID:
        print("📤 準備推送訊息至 Line...")
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            print(f"📊 Line 回應狀態碼: {res.status_code}")
            if res.status_code != 200:
                print(f"❌ Line 發送失敗原因: {res.text}")
            return f"STATUS_{res.status_code}"
        except Exception as e:
            print(f"❌ Line 連線過程崩潰: {e}")
            return "CONNECTION_FAILED"
    else:
        print("❌ 無法發送：環境變數缺失")
        return "MISSING_ENV"
