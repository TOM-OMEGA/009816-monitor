import yfinance as yf
import requests
import os
import time # 💡 必須引入
import pandas as pd
from datetime import datetime, timezone, timedelta
from ai_expert import get_ai_point
# ✅ 引入精準數據引擎
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
    # 統一環境變數命名
    line_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('USER_ID')
    
    # 統一台灣時間
    now_tw = datetime.now(timezone(timedelta(hours=8)))
    report = f"🦅 經理人「萬元實驗」精準診斷\n日期: {now_tw.strftime('%Y-%m-%d %H:%M')}\n"
    report += "----------------------------"

    for symbol, cfg in TARGETS.items():
        try:
            # A. 抓取技術面數據 (yfinance)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="60d").ffill()
            if df.empty: 
                print(f"⚠️ {symbol} 抓不到數據")
                continue
            
            curr_p = df['Close'].iloc[-1]
            trend_status = check_trend(df)
            
            # RSI 計算
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss.replace(0, 1e-6)
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            
            ma5 = df['Close'].rolling(5).mean().iloc[-1]
            bias_5 = ((curr_p - ma5) / ma5) * 100
            
            # B. ✅ 抓取 FinMind 全維度數據 (11項指標)
            print(f"📡 獲取 {cfg['name']} 精準籌碼與盤中數據...")
            extra_data = get_high_level_insight(symbol)
            
            # 💡 核心必要修改：在呼叫 AI 診斷前強制排隊冷卻
            # 確保 00929, 2317, 00878 不會在同一秒鐘衝撞 API 配額
            print(f"⏳ 正在排隊發送 {cfg['name']} AI 診斷 (冷卻 25 秒)...")
            time.sleep(25)
            
            # C. 呼叫 AI 進行深度診斷
            summary = f"現價:{curr_p:.2f}, RSI:{rsi:.1f}, 5日乖離:{bias_5:.2f}%, 趨勢:{trend_status}"
            ai_comment = get_ai_point(summary, cfg['name'], extra_data)
            
            # D. 網格交易決策
            trade_shares = int((cfg["cap"] / 5) / curr_p)
            
            report += f"\n\n📍 {cfg['name']}"
            report += f"\n📊 評價: {extra_data.get('valuation', 'N/A')}"
            report += f"\n📉 力道: {extra_data.get('order_strength', '穩定')}"
            report += f"\n🧠 AI 診斷: {ai_comment}"
            
            # 加上邏輯鎖：若空頭且 5s 力道偏弱，建議審慎
            if "🔴" in trend_status and "賣單" in extra_data.get('order_strength', ''):
                report += f"\n🚫 [行動] 技術面與盤中力道雙弱，暫緩補貨。"
            else:
                report += f"\n✅ [行動] 符合網格紀律，建議執行 {trade_shares} 股。"

        except Exception as e:
            print(f"❌ {cfg['name']} 診斷過程出錯: {e}")
            report += f"\n\n📍 {cfg['name']} 診斷中斷"

    # ✅ 強化後的發送邏輯
    if line_token and user_id:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {line_token}", "Content-Type": "application/json"}
        payload = {"to": user_id, "messages": [{"type": "text", "text": report}]}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=10)
            print(f"📊 萬元實驗 Line 發送狀態: {res.status_code}")
            return f"SUCCESS_{res.status_code}"
        except Exception as e:
            print(f"❌ Line 發送失敗: {e}")
            return "LINE_SEND_FAILED"
    else:
        print("❌ 錯誤: 缺少 LINE_ACCESS_TOKEN 或 USER_ID")
        return "MISSING_KEYS"

if __name__ == "__main__":
    print(run_unified_experiment())
