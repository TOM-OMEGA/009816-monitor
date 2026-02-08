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

def get_ai_point(target_name=None, strategy_type=None, extra_data=None, debug=False, **kwargs):
    """
    通用 AI 判斷函式 (全能相容版)
    自動偵測舊版呼叫方式，並自動補齊 strategy_type
    """
    global AI_CACHE
    now = datetime.now()

    # ==========================================
    # 🛠️ 自動修復參數 (相容性適配層)
    # ==========================================
    
    if isinstance(target_name, dict) and extra_data is None:
        extra_data = target_name
        target_name = kwargs.get('target_name', 'Unknown_Target')
    
    if 'summary_override' in kwargs and kwargs['summary_override']:
        extra_data = kwargs['summary_override']
        strategy_type = "us_market"
        target_name = "US_MARKET"

    if not strategy_type:
        if isinstance(extra_data, dict):
            if 'grid_buy' in extra_data or 'rsi' in extra_data:
                strategy_type = "grid_trading"
            elif 'projected_1y' in extra_data or 'dist' in extra_data:
                strategy_type = "stock_audit"
            else:
                strategy_type = "stock_audit"
        elif isinstance(extra_data, str):
            strategy_type = "us_market"
        else:
            strategy_type = "stock_audit"

    # ==========================================
    # 建立 Cache Key
    # ==========================================
    key = f"{target_name}_{strategy_type}_{now.strftime('%H%M')}"

    if key in AI_CACHE:
        return AI_CACHE[key]

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "尚未設定 GEMINI_API_KEY", "status": "系統異常"}

    # ==========================================
    # 🧠 策略分流與 Prompt 組裝
    # ==========================================
    prompt_context = ""
    status_template = ""
    d = extra_data if isinstance(extra_data, dict) else {}

    if strategy_type == "stock_audit":
        status_template = "AI 狀態：複利計算中 🤖\n💡 提醒：複利效果穩定，已納入 2027 投影計畫。"
        prompt_context = f"""
你是一位長期價值投資經理人，請評估 "{target_name}" 的存股價值。
【關鍵數據】
- 目前股價: {d.get('price', 'N/A')}
- 2027年投影目標價: {d.get('projected_1y', 'N/A')}
- 系統綜合評分: {d.get('score', 'N/A')} / 100
- 距離發行價: {d.get('dist', 'N/A')}%
【指令】
1. 判斷股價相對於 2027 年目標是否具有安全邊際。
2. 給出「買進」、「持有」或「觀望」的明確建議。
"""

    elif strategy_type == "grid_trading":
        status_template = "AI 狀態：網格監控中 📉\n💡 提醒：嚴守動態間距，避免情緒化手動交易。"
        prompt_context = f"""
你是一位高頻網格交易員，請評估 "{target_name}" 的短線波動機會。
【關鍵數據】
- 現價: {d.get('price', 'N/A')}
- 短線趨勢: {d.get('trend', 'N/A')}
- RSI (14): {d.get('rsi', 'N/A')}
- 布林下緣 (補倉點): {d.get('grid_buy', 'N/A')}
【指令】
1. 若 RSI < 35 且趨勢超跌，建議積極補倉。
2. 若 RSI > 70，建議暫停買入。
"""

    elif strategy_type == "us_market":
        status_template = "AI 狀態：全球聯動分析中 🌏\n💡 提醒：科技股波動劇烈，注意 TSM 溢價風險。"
        market_info = extra_data if isinstance(extra_data, str) else str(extra_data)
        prompt_context = f"""
你是一位宏觀市場分析師，請解讀以下美股數據並預測明日台股開盤氣氛。
【市場摘要】
{market_info}
【指令】重點關注科技股 (TSM/SOX) 對台股的影響，判斷情緒是樂觀、悲觀還是震盪。
"""

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

    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json"
        }
    }

    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 連線逾時", "status": status_template}
    
    # 4. 呼叫 API + 強化重試機制
    # 根據用戶提供的模型列表，gemini-2.0-flash 是可用的
    # 如果 v1 失敗，嘗試 v1beta
    for attempt in range(3):
        try:
            # 🔧 修正：根據列表，使用 gemini-2.0-flash，並先嘗試 v1 版本
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            res = requests.post(api_url, json=payload, timeout=30)

            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                logging.warning(f"⚠️ API 速率限制，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            # 如果 v1 報 404，嘗試切換到 v1beta
            if res.status_code == 404:
                logging.info("🔄 v1 找不到模型，嘗試切換到 v1beta 版本...")
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={gemini_key}"
                res = requests.post(api_url, json=payload, timeout=30)

            if res.status_code != 200:
                logging.error(f"❌ API 回應錯誤 (狀態碼 {res.status_code}): {res.text}")
            
            res.raise_for_status()
            data = res.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            try:
                ai_result = json.loads(text)
            except json.JSONDecodeError:
                logging.warning("⚠️ 標準 JSON 解析失敗，嘗試 Regex 救援...")
                ai_result = _rescue_json(text, status_template)

            if "status" not in ai_result or not ai_result["status"]:
                ai_result["status"] = status_template

            logging.info(f"✅ AI 分析成功: {ai_result.get('decision', 'N/A')}")
            break 

        except Exception as e:
            logging.error(f"❌ AI 請求異常 (第 {attempt + 1} 次嘗試): {e}")
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"系統異常: {str(e)[:20]}", "status": status_template}

    AI_CACHE[key] = ai_result
    return ai_result

def get_us_ai_point(extra_data, debug=False):
    return get_us_ai_point(target_name="US_MARKET", strategy_type="us_market", extra_data=extra_data, debug=debug)

def _rescue_json(text, default_status):
    """ Regex Rescue """
    result = {"decision": "觀望", "confidence": 50, "reason": "解析錯誤", "status": default_status}
    m_dec = re.search(r'"decision"\s*:\s*"([^"]+)"', text)
    if m_dec: result["decision"] = m_dec.group(1)
    
    m_conf = re.search(r'"confidence"\s*:\s*(\d+)', text)
    if m_conf: result["confidence"] = int(m_conf.group(1))
    
    m_reason = re.search(r'"reason"\s*:\s*"([^"]*?)"', text, re.DOTALL)
    if m_reason: result["reason"] = m_reason.group(1)
    return result
