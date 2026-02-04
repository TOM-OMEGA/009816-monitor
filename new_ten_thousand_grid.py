import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime
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
    curr_p = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    
    if curr_p > ma20 > ma60: return "🟢 多頭排列 (強勢區)"
    if curr_p < ma20 < ma60: return "🔴 空頭排列 (弱勢區)"
    return "🟡 區間震盪 (網格套利)"

def run_unified_experiment():
    line_token = os.environ.get('LINE_ACCESS_TOKEN')
    user_id = os.environ.get('USER_ID')
    
    report = f"🦅 經理人「萬元實驗」精準診斷\n日期: {datetime.now().strftime('%Y-%m-%d')}\n"
    report += "----------------------------"

    for symbol, cfg in TARGETS.items():
        try:
            # A. 抓取技術面數據 (yfinance)
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="60d").ffill()
            if df.empty: continue
            
            curr_p = df['Close'].iloc[-1]
            trend_status = check_trend(df)
            
            # RSI 計算
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss.replace(0, 1e-6)
            rsi = 100 - (100 / (1 + rs.iloc[-1]))
            bias_5 = ((curr_p - df['Close'].rolling(5).mean().iloc[-1]) / df['Close'].rolling(5).mean().iloc[-1]) * 100
            
            # B. ✅ 抓取籌碼面數據 (FinMind API)
            print(f"📡 獲取 {cfg['name']} 精準籌碼數據...")
            extra_data = get_high_level_insight(symbol)
            
            # C. 呼叫 AI 進行「一年預判」點評
            summary = f"現價:{curr_p:.2f}, RSI:{rsi:.1f}, 5日乖離:{bias_5:.2f}%, 趨勢:{trend_status}"
            ai_comment = get_ai_point(summary, cfg['name'], extra_data)
            
            # D. 網格交易決策
            trade_shares = int((cfg["cap"] / 5) / curr_p)
            
            report += f"\n\n📍 {cfg['name']}"
            report += f"\n📊 籌碼: {extra_data.get('inst')}"
            report += f"\n📈 營收: {extra_data.get('rev')}"
            report += f"\n🧠 AI 診斷: {ai_comment}"
            
            # 加上邏輯鎖：若空頭且法人大賣，強制暫停買入
            if "🔴" in trend_status and "外資:-" in extra_data.get('inst'):
                report += f"\n🚫 [行動] 籌碼面與技術面雙弱，暫緩買入以避開急跌。"
            else:
                report += f"\n✅ [行動] 符合網格紀律，建議執行 {trade_shares} 股。"

        except Exception as e:
            report += f"\n\n📍 {cfg['name']} 診斷失敗: {str(e)[:20]}"

    # 發送訊息
    if line_token and user_id:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {line_token}", "Content-Type": "application/json"}
        payload = {"to": user_id, "messages": [{"type": "text", "text": report}]}
        res = requests.post(url, headers=headers, json=payload)
        return f"🟢 萬元實驗戰報送達: {res.status_code}"
    return "❌ 權限錯誤"

if __name__ == "__main__":
    print(run_unified_experiment())
