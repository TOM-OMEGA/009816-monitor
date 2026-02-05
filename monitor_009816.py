import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
from data_engine import get_high_level_insight 

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_realtime_data(ticker):
    """強化版 yfinance 抓取：加入強制超時防止卡死"""
    print(f"🔍 索取 {ticker} 即時報價...")
    try:
        # 💡 使用快速獲取模式，只抓取當日
        t = yf.Ticker(ticker)
        df = t.history(period="2d", timeout=5) # 5秒沒反應就跳過，不准卡住
        if not df.empty and len(df) >= 2:
            curr = float(df['Close'].iloc[-1])
            prev = float(df['Close'].iloc[-2])
            pct = ((curr / prev) - 1) * 100
            print(f"✅ {ticker} 準確報價: {curr}")
            return curr, pct
        return 0.0, 0.0
    except Exception as e:
        print(f"⚠️ yfinance 延遲或封鎖: {e}")
        return 0.0, 0.0

def run_009816_monitor():
    print("\n" + "="*30)
    print("🦅 啟動 009816 精準監控 (Yahoo Finance 優先模式)")
    
    # 1. 抓取最準確的即時報價
    price_00, pct_00 = get_realtime_data("009816.TW")
    _, sox_pct = get_realtime_data("^SOX")
    _, tsm_pct = get_realtime_data("TSM")
    
    # 2. 獲取 FinMind 的 11 維深度指標 (用於 AI 判斷)
    print("📡 同步獲取 FinMind 籌碼面細節...")
    extra_data = get_high_level_insight("009816.TW")

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_time = now_tw.strftime("%H:%M:%S")
    
    gap = round(price_00 - 10.12, 2)
    gap_msg = f"🚩 距離目標 10.12 還差 {gap} 元" if gap > 0 else "🔥 已達 10.12 進場紀律位階！"
    
    summary = (f"009816價:{price_00:.2f} ({pct_00:+.2f}%)\n"
               f"費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%")

    # 3. 呼叫 AI (確保 prompt 包含 2027 結婚基金願景)
    print("🧠 請求 AI 針對最新數據診斷...")
    ai_msg = get_ai_point(summary, "009816 結婚基金", extra_data)

    # 4. 發送 Line
    full_msg = (
        f"🦅 經理人精準戰報 ({current_time})\n"
        f"------------------\n"
        f"{summary}\n"
        f"📊 評價指標: {extra_data.get('valuation', 'N/A')}\n"
        f"📉 盤中力道: {extra_data.get('order_strength', '穩定')}\n"
        f"------------------\n"
        f"{gap_msg}\n"
        f"------------------\n"
        f"🧠 AI 診斷：\n{ai_msg}"
    )
    
    if LINE_TOKEN and USER_ID:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"📊 Line 推送結果: {res.status_code}")
        return res.status_code
    return "No Key"
