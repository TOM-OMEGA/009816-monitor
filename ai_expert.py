import os
import requests
import json
import time
from datetime import datetime

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_LAST_CALL = {}
AI_COOLDOWN_MINUTES = 1

def get_ai_point(target_name, strategy_type, extra_data):
    """
    通用 AI 判斷函式 (支援三種策略分流)
    """
    global AI_CACHE, AI_LAST_CALL
    now = datetime.now()
    
    # 建立 Cache Key
    key = f"{target_name}_{strategy_type}_{now.strftime('%H%M')}"

    # 1. 檢查 Cache
    if key in AI_CACHE:
        return AI_CACHE[key]

    # 2. 檢查 API Key
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "尚未設定 GEMINI_API_KEY", "status": "系統異常"}

    # ==========================================
    # 🧠 策略分流與狀態範本設定
    # ==========================================
    prompt_context = ""
    status_template = ""
    
    if strategy_type == "stock_audit":
        d = extra_data
        status_template = "AI 狀態：複利計算中 🤖\n💡 提醒：複利效果穩定，已納入 2027 投影計畫。"
        prompt_context = f"""
你是一位長期價值投資經理人，請評估 "{target_name}" 的存股價值。
【關鍵數據】
- 目前股價: {d.get('price')}
- 2027年投影目標價: {d.get('projected_1y')}
- 系統綜合評分: {d.get('score')} / 100
- 距離發行價: {d.get('dist')}%
【指令】判斷安全邊際，給出買進/持有/觀望建議。"""

    elif strategy_type == "grid_trading":
        d = extra_data
        status_template = "AI 狀態：網格監控中 📉\n💡 提醒：嚴守動態間距，避免情緒化手動交易。"
        prompt_context = f"""
你是一位高頻網格交易員，請評估 "{target_name}" 的短線波動機會。
【關鍵數據】
- 現價: {d.get('price')}
- 短線趨勢: {d.get('trend')}
- RSI (14): {d.get('rsi')}
- 布林下緣 (補倉點): {d.get('grid_buy')}
【指令】針對是否執行網格補倉給出建議。"""

    elif strategy_type == "us_market":
        status_template = "AI 狀態：全球聯動分析中 🌏\n💡 提醒：科技股波動劇烈，注意 TSM 溢價風險。"
        prompt_context = f"""
你是一位宏觀市場分析師，請解讀以下美股數據並預測明日台股開盤氣氛。
【市場摘要】
{extra_data}
【指令】給出對台股投資人的操作提醒。"""

    # 加上統一的 JSON 輸出要求 (包含 status 欄位)
    prompt = f"""
{prompt_context}

⚠️ 嚴格輸出 JSON 格式，不要有 Markdown，不要有多餘文字：
{{
  "decision": "決策結果",
  "confidence": 0-100,
  "reason": "50字內理由",
  "status": "{status_template}"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {"temperature": 0.3}
    }

    # 4. 呼叫 API + 強化重試機制
    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 連線逾時", "status": status_template}
    
    for attempt in range(3):
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            res = requests.post(api_url, json=payload, timeout=30)

            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                time.sleep(wait_time)
                continue

            res.raise_for_status()
            data = res.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_text = text.replace("```json", "").replace("```", "").strip()
            ai_result = json.loads(clean_text)
            break 

        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"異常: {str(e)[:20]}", "status": status_template}

    AI_CACHE[key] = ai_result
    return ai_result
