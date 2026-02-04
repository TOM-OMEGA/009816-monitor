import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
from ai_expert import get_ai_point
from flask import Flask  # 新增：建立網頁服務

app = Flask(__name__)

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

def monitor():
    print("🚀 啟動實時數據抓取與分析...")
    price_00, _ = get_data("009816.TW")
    _, sox_pct = get_data("^SOX")
    _, tsm_pct = get_data("TSM")
    
    h_hist = yf.Ticker("009816.TW").history(period="2mo", interval="1h")['Close']
    delta = h_hist.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
    rs = gain / loss.replace(0, 1e-6)
    rsi_val = float(100 - (100 / (1 + rs.iloc[-1])))

    now_tw = datetime.utcnow() + timedelta(hours=8)
    current_time = now_tw.strftime("%H:%M:%S")
    
    gap = round(price_00 - 10.12, 2)
    gap_msg = f"🚩 距離目標 10.12 還差 {gap} 元" if gap > 0 else "🔥 已達 10.12 進場紀律位階！"

    summary = f"009816價:{price_00:.2f}, RSI:{rsi_val:.1f}\n費半:{sox_pct:+.2f}%, TSM:{tsm_pct:+.2f}%"

    try:
        ai_msg = get_ai_point(summary)
    except Exception as e:
        ai_msg = f"💡 經理人提醒：數據解析中，請堅持 10.12 紀律。"

    full_msg = (
        f"🦅 經理人戰報 ({current_time})\n"
        f"------------------\n"
        f"{summary}\n"
        f"{gap_msg}\n"
        f"------------------\n"
        f"💡 AI 點評：\n{ai_msg}"
    )
    
    if LINE_TOKEN and USER_ID:
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
        requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload)
        return f"戰報已送達 - {current_time}"
    return "Token 遺失"

# 當 UptimeRobot 訪問你的網址時，會觸發這個路徑
@app.route('/')
def home():
    # 每次被訪問就執行一次監控，確保準時
    result = monitor()
    return f"<h1>系統運行中</h1><p>{result}</p>"

if __name__ == "__main__":
    # Render 會自動分配 PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
