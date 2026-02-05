import yfinance as yf
import requests
import os
import pandas as pd
import time  # 💡 核心修正：引入 time
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
from data_engine import get_high_level_insight 

# --- 1. 一萬元實驗配置 ---
TARGETS = {
    "00929.TW": {"cap": 3333, "gap_pct": 0.012, "name": "00929 科技優息"},
    "2317.TW":  {"cap": 3334, "gap_pct": 0.015, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "gap_pct": 0.008, "name": "00878 永續高股息"}
}

def check_trend(df):
    """ AI 多空判斷標準：葛蘭碧法則與均線扣抵預判 """
    if len(df) < 60: return "⚪ 數據不足"
    curr_p = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    
    if curr_p > ma20 > ma60: return "🟢 多頭排列 (強勢區)"
    if curr_p < ma20 < ma60: return "🔴 空頭排列 (弱勢區)"
    return "🟡 區間震盪 (網格套利)"

def run_unified_experiment():
    line_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('USER_ID')
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    report = f"🦅 經理人「萬元實驗」精準診斷\n日期: {now_tw.strftime('%Y-%m-%d %H:%M')}\n"
    report += "----------------------------"

    for symbol, cfg in TARGETS.items():
        try:
            ticker = yf.Ticker(symbol, session=session)
            df = ticker.history(period="60d", timeout=10).ffill()
            
            if df.empty or len(df) < 14: 
                report += f"\n\n📍 {cfg['name']}\n⚠️ 報價數據獲取失敗"
                continue
            
            curr_p = df['Close'].iloc[-1]
            trend_status = check_trend(df)
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss.replace(0, 1e-6)
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            bias_5 = ((curr_p - ma5) / ma5) * 100
            
            print(f"📡 獲取 {cfg['name']} 精準籌碼與盤中數據...")
            extra_data = get_high_level_insight(symbol)
            
            # C. 呼叫 AI
            summary = f"現價:{curr_p:.2f}, RSI:{rsi:.1f}, 5日乖離:{bias_5:.2f}%, 趨勢:{trend_status}"
            ai_comment = get_ai_point(summary, cfg['name'], extra_data)
            
            # 💡 核心修正：每診斷完一個標的，強制冷卻 5 秒，防止觸發 AI Quota 限流
            time.sleep(5) 
            
            trade_shares = int((cfg["cap"] / 5) / curr_p)
            
            report += f"\n\n📍 {cfg['name']}"
            report += f"\n📊 評價: {extra_data.get('valuation', 'N/A')}"
            report += f"\n📉 力道: {extra_data.get('order_strength', '穩定')}"
            report += f"\n🧠 AI 診斷: {ai_comment}"
            
            if "🔴" in trend_status and "賣單" in extra_data.get('order_strength', ''):
                report += f"\n🚫 [行動] 趨勢偏空且力道轉弱，暫緩補貨。"
            else:
                report += f"\n✅ [行動] 符合網格紀律，建議執行 {trade_shares} 股。"

        except Exception as e:
            print(f"❌ {cfg['name']} 診斷出錯: {e}")
            report += f"\n\n📍 {cfg['name']} 診斷暫時中斷"

    if line_token and user_id:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {line_token}", "Content-Type": "application/json"}
        payload = {"to": user_id, "messages": [{"type": "text", "text": report}]}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            return f"SUCCESS_{res.status_code}"
        except:
            return "LINE_SEND_FAILED"
    return "MISSING_KEYS"
