import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
from ai_expert import get_ai_point

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_data(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="5d")
        if len(hist) < 2: return 0.0, 0.0
        # 取得最新價與前一交易日漲跌幅
        return float(hist['Close'].iloc[-1]), ((hist['Close'].iloc[-1] / hist['Close'].iloc[-2]) - 1) * 100
    except:
        return 0.0, 0.0

def monitor():
    print("🚀 執行經理人實時戰報校對...")
    
    # 1. 抓取精準數據
    price_00, _ = get_data("009816.TW")
    _, sox_pct = get_data("^SOX")
    _, tsm_pct = get_data("TSM")
    
    # 2. 計算 RSI (維持小時級別靈敏度)
    h_hist = yf.Ticker("009816.TW").history(period="2mo", interval="1h")['Close']
    delta = h_hist.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0, 1e-6)
    rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))

    # 3. 新增細節：時間戳記與目標價距離 [cite: 2026-02-02]
    now_tw = datetime.utcnow() + timedelta(hours=8)
    current_time = now_tw.strftime("%H:%M:%S")
    
    gap = round(price_00 - 10.12, 2)
    gap_msg = f"🚩 距離目標 10.12 還差 {gap} 元" if gap > 0 else "🔥 已達 10.12 進場紀律位階！"

    # 4. 彙整數據摘要
    summary = f"009816價:{price_00:.2f}, RSI:{rsi_val:.1f}\n費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%"

    # 5. 呼叫 AI 專家 (注入一年後預測邏輯) [cite: 2026-02-02]
    try:
        ai_msg = get_ai_point(summary)
    except Exception as e:
        ai_msg = f"💡 經理人提醒：數據讀取中，請嚴守 10.12 紀律。"

    # 6. 重新組合視覺化戰報
    full_msg = (
        f"🦅 經理人戰報 ({current_time})\n"
        f"------------------\n"
        f"{summary}\n"
        f"{gap_msg}\n"
        f"------------------\n"
        f"💡 AI 點評：\n{ai_msg}"
    )
    
    # 7. LINE 發送
    if LINE_TOKEN and USER_ID:
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
        res = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)
        print(f"✅ 戰報已送達: {res.status_code}")
    else:
        print("❌ LINE Token 或 UserID 缺失")

if __name__ == "__main__":
    monitor()
