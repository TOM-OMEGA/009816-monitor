import os
import requests
import json
import time
import logging

# 設定 AI 冷卻時間 (避免重複發問浪費 Quota)
AI_CACHE = {}
AI_COOLDOWN = 600  # 10分鐘內問同一支股票，直接回傳舊結果

def get_ai_suggestion(symbol, price, trend, rsi, technical_summary):
    """
    通用 AI 分析介面
    Args:
        symbol: 股票代號 (e.g. "009816.TW")
        price: 目前價格
        trend: 趨勢描述 (e.g. "強勢多頭")
        rsi: RSI 數值
        technical_summary: 其他技術指標文字 (e.g. "MACD收斂, 2027投影樂觀")
    """
    global AI_CACHE
    
    # 1. 檢查 API Key
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return "⚠️ AI 尚未啟用 (未設定 GEMINI_API_KEY)"

    # 2. 檢查 Cache (省錢/省流量邏輯)
    current_time = time.time()
    cache_key = f"{symbol}_{trend}" # 如果趨勢變了就重新問
    
    if cache_key in AI_CACHE:
        last_time, last_reply = AI_CACHE[cache_key]
        if current_time - last_time < AI_COOLDOWN:
            logging.info(f"🧠 {symbol} 使用 AI 快取")
            return last_reply

    # 3. 組合 Prompt (經理人思維)
    prompt = f"""
你是一位專業的基金經理人，請根據以下數據對 "{symbol}" 進行簡短的投資判斷。

【市場數據】
- 現價: {price}
- 趨勢: {trend}
- RSI: {rsi}
- 技術細節: {technical_summary}

【指令】
1. 請給出一個明確的決策（買入 / 觀望 / 減碼）。
2. 用一句話解釋理由 (繁體中文)。
3. 語氣要專業、冷靜，不要有免責聲明。
4. 字數限制：50字以內。

回傳格式範例：
"🎯 決策：觀望。理由：RSI 過熱且乖離過大，建議等待回測月線支撐再行佈局。"
"""

    # 4. 呼叫 Gemini API
    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 100}
    }
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            ai_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            
            # 寫入 Cache
            AI_CACHE[cache_key] = (current_time, ai_text)
            return ai_text
        else:
            logging.error(f"AI API Error: {response.text}")
            return "⚠️ AI 連線忙碌中"
            
    except Exception as e:
        logging.error(f"AI Exception: {e}")
        return "⚠️ AI 目前無法回應"
