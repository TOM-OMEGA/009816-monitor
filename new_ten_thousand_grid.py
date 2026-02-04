import yfinance as yf
import requests
import os
import pandas as pd
from datetime import datetime
from ai_expert import get_ai_point  # 👈 串接你的 AI 專家模組

# --- 1. 一萬元實驗配置 ---
TARGETS = {
    "00929.TW": {"cap": 3333, "gap_pct": 0.012, "name": "00929 科技優息"},
    "2317.TW":  {"cap": 3334, "gap_pct": 0.015, "name": "2317 鴻海"},
    "00878.TW": {"cap": 3333, "gap_pct": 0.008, "name": "00878 永續高股息"}
}

def check_trend(df):
    """ AI 多空判斷標準：參考葛蘭碧法則 """
    curr_p = df['Close'].iloc[-1]
    ma20 = df['Close'].rolling(20).mean().iloc[-1]
    ma60 = df['Close'].rolling(60).mean().iloc[-1]
    
    if curr_p > ma20 > ma60: return "🟢 多頭排列 (建議守住獲利)"
    if curr_p < ma20 < ma60: return "🔴 空頭排列 (建議暫緩買入)"
    return "🟡 區間震盪 (網格套利機會)"

def run_unified_experiment():
    line_token = os.environ.get('LINE_TOKEN')
    report = f"🦅 經理人「一萬元實驗」AI 總體診斷\n日期: {datetime.now().strftime('%Y-%m-%d')}\n"
    report += "----------------------------"

    for symbol, cfg in TARGETS.items():
        ticker = yf.Ticker(symbol)
        # 抓取 60 天數據以計算趨勢
        df = ticker.history(period="60d").ffill()
        curr_p = df['Close'].iloc[-1]
        
        # 1. 多空診斷
        trend_status = check_trend(df)
        
        # 2. 技術指標計算 (餵給 AI)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rsi = 100 - (100 / (1 + (gain / loss).iloc[-1]))
        bias_5 = ((curr_p - df['Close'].rolling(5).mean().iloc[-1]) / df['Close'].rolling(5).mean().iloc[-1]) * 100
        
        # 3. 呼叫你的 AI.py 進行點評
        summary = f"現價:{curr_p:.2f}, RSI:{rsi:.1f}, 5日乖離:{bias_5:.2f}%, 盤勢:{trend_status}"
        ai_comment = get_ai_point(summary, cfg['name'])
        
        # 4. 網格建議 (國泰 1 元手續費優化)
        trade_shares = int((cfg["cap"] / 5) / curr_p)
        
        report += f"\n\n📍 {cfg['name']}\n📊 指標: {summary}"
        report += f"\n🛡️ 診斷: {trend_status}"
        report += f"\n🧠 AI 專家: {ai_comment}"
        
        if "🔴" in trend_status and bias_5 > -2.5:
            report += f"\n🚫 [行動] 空頭回檔中，暫緩加碼以防虧損。"
        else:
            report += f"\n✅ [行動] 建議單筆網格交易 {trade_shares} 股。"

    # 發送 LINE
    if line_token:
        requests.post("https://notify-api.line.me/api/notify", 
                      headers={"Authorization": f"Bearer {line_token}"}, 
                      data={"message": report})

if __name__ == "__main__":
    run_unified_experiment()
