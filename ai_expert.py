import os
import requests
import json
import time
import re
import logging
from datetime import datetime

# === 設定 logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_COOLDOWN_MINUTES = 1

def get_ai_point(target_name, strategy_type, extra_data):
    """
    通用 AI 判斷函式 (支援三種策略分流) - 強固 JSON 版
    """
    global AI_CACHE
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
    # 🧠 策略分流與 Prompt 組裝
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
【指令】
1. 判斷股價相對於 2027 年目標是否具有安全邊際。
2. 給出「買進」、「持有」或「觀望」的明確建議。
"""

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
【指令】
1. 若 RSI < 35 且趨勢超跌，建議積極補倉。
2. 若 RSI > 70，建議暫停買入。
"""

    elif strategy_type == "us_market":
        status_template = "AI 狀態：全球聯動分析中 🌏\n💡 提醒：科技股波動劇烈，注意 TSM 溢價風險。"
        prompt_context = f"""
你是一位宏觀市場分析師，請解讀以下美股數據並預測明日台股開盤氣氛。
【市場摘要】
{extra_data}
【指令】重點關注科技股 (TSM/SOX) 對台股的影響，判斷情緒是樂觀、悲觀還是震盪。
"""

    # 加上統一的 JSON 輸出要求
    prompt = f"""
{prompt_context}

⚠️ Output strictly in JSON format. No Markdown.
Required fields:
{{
  "decision": "Your decision here",
  "confidence": 80,
  "reason": "Short explanation in Traditional Chinese (max 50 words)",
  "status": "{status_template}"
}}
"""

    # 3. 設定 API Payload (強制 JSON 模式)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json"  # <--- 關鍵修改：強制 API 回傳 JSON
        }
    }

    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 連線逾時", "status": status_template}
    
    # 4. 呼叫 API + 強化重試機制
    for attempt in range(3):
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            res = requests.post(api_url, json=payload, timeout=30)

            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                logging.warning(f"⚠️ AI 限流 (429)，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            res.raise_for_status()
            data = res.json()

            # 解析與清洗
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # 嘗試標準 JSON 解析
            try:
                ai_result = json.loads(text)
            except json.JSONDecodeError:
                logging.warning("⚠️ 標準 JSON 解析失敗，嘗試 Regex 救援...")
                ai_result = _rescue_json(text, status_template)

            # 確保 status 欄位存在 (防呆)
            if "status" not in ai_result or not ai_result["status"]:
                ai_result["status"] = status_template

            break 

        except Exception as e:
            logging.error(f"AI 請求異常 (第 {attempt+1} 次): {e}")
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"系統異常: {str(e)[:20]}", "status": status_template}

    AI_CACHE[key] = ai_result
    return ai_result

def _rescue_json(text, default_status):
    """
    當 json.loads 失敗時的備用解析器 (Regex Rescue)
    """
    result = {
        "decision": "觀望",
        "confidence": 50,
        "reason": "解析錯誤，請查看原始日誌",
        "status": default_status
    }
    
    # 1. 嘗試抓取 decision
    m_dec = re.search(r'"decision"\s*:\s*"([^"]+)"', text)
    if m_dec: result["decision"] = m_dec.group(1)
    
    # 2. 嘗試抓取 confidence (數字)
    m_conf = re.search(r'"confidence"\s*:\s*(\d+)', text)
    if m_conf: result["confidence"] = int(m_conf.group(1))
    
    # 3. 嘗試抓取 reason (最容易出錯的地方)
    # 使用非貪婪匹配，直到遇到下一個引號結束
    m_reason = re.search(r'"reason"\s*:\s*"([^"]*?)"', text, re.DOTALL)
    if m_reason: 
        result["reason"] = m_reason.group(1)
    else:
        # 如果失敗，嘗試寬鬆抓取
        clean_text = text.replace('"', '').replace('{', '').replace('}', '')
        if "reason:" in clean_text:
            parts = clean_text.split("reason:")
            if len(parts) > 1:
                result["reason"] = parts[1].split(",")[0].strip()

    return result
