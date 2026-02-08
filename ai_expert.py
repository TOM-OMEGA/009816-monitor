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

def get_ai_point(target_name=None, strategy_type=None, extra_data=None, debug=False, **kwargs):
    """
    通用 AI 判斷函式 (未來相容版)
    支援從 Gemma 3 到 Gemini 1.5 的全自動備援切換
    """
    global AI_CACHE
    now = datetime.now()

    # ==========================================
    # 🛠️ 參數處理
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
    # 🧠 Prompt 組裝
    # ==========================================
    prompt_context = ""
    status_template = ""
    d = extra_data if isinstance(extra_data, dict) else {}

    if strategy_type == "stock_audit":
        status_template = "AI 狀態：複利計算中 🤖"
        prompt_context = f"請評估 '{target_name}' 的存股價值。數據：股價 {d.get('price', 'N/A')}, 2027目標 {d.get('projected_1y', 'N/A')}, 評分 {d.get('score', 'N/A')}。"
    elif strategy_type == "grid_trading":
        status_template = "AI 狀態：網格監控中 📉"
        prompt_context = f"請評估 '{target_name}' 的網格交易機會。數據：現價 {d.get('price', 'N/A')}, RSI {d.get('rsi', 'N/A')}, 趨勢 {d.get('trend', 'N/A')}。"
    elif strategy_type == "us_market":
        status_template = "AI 狀態：全球聯動分析中 🌏"
        market_info = extra_data if isinstance(extra_data, str) else str(extra_data)
        prompt_context = f"請解讀美股數據並預測明日台股開盤氣氛：{market_info}"

    prompt = f"""
{prompt_context}
⚠️ 要求：必須以 JSON 格式輸出，不要包含 Markdown 標記。
格式範例：
{{
  "decision": "買進/持有/觀望",
  "confidence": 80,
  "reason": "繁體中文簡短原因",
  "status": "{status_template}"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 800
        }
    }

    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 連線逾時", "status": status_template}
    
    # 🔧 未來相容序列：Gemma 3 -> Gemini 2.5 -> Gemini 2.0 -> Gemini 1.5
    # 根據您的列表，gemma-3-27b-it 是可用的最強開源架構
    models_to_try = [
        "gemma-3-27b-it", 
        "gemini-2.5-flash", 
        "gemini-2.0-flash", 
        "gemini-1.5-flash"
    ]
    
    for model_name in models_to_try:
        success = False
        for attempt in range(2):
            try:
                # 統一使用 v1beta 端點
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                res = requests.post(api_url, json=payload, timeout=25)

                if res.status_code == 429:
                    logging.warning(f"⚠️ 模型 {model_name} 額度耗盡，嘗試下一個...")
                    break 

                if res.status_code != 200:
                    logging.error(f"❌ {model_name} 錯誤 ({res.status_code}): {res.text[:150]}")
                    break

                res.raise_for_status()
                data = res.json()

                text = data["candidates"][0]["content"]["parts"][0]["text"]
                text = re.sub(r'```json\n?|\n?```', '', text).strip()
                
                try:
                    ai_result = json.loads(text)
                except:
                    ai_result = _rescue_json(text, status_template)

                success = True
                logging.info(f"✅ 成功使用 {model_name} 完成分析")
                break 

            except Exception as e:
                logging.error(f"❌ {model_name} 請求異常: {e}")
                time.sleep(2)
        
        if success:
            break

    AI_CACHE[key] = ai_result
    return ai_result

def get_us_ai_point(extra_data, debug=False):
    """
    美股分析入口
    """
    return get_ai_point(target_name="US_MARKET", strategy_type="us_market", extra_data=extra_data, debug=debug)

def _rescue_json(text, default_status):
    result = {"decision": "觀望", "confidence": 50, "reason": "解析錯誤", "status": default_status}
    try:
        m_dec = re.search(r'"decision"\s*:\s*"([^"]+)"', text)
        if m_dec: result["decision"] = m_dec.group(1)
        m_conf = re.search(r'"confidence"\s*:\s*(\d+)', text)
        if m_conf: result["confidence"] = int(m_conf.group(1))
        m_reason = re.search(r'"reason"\s*:\s*"([^"]*?)"', text)
        if m_reason: result["reason"] = m_reason.group(1)
    except:
        pass
    return result
