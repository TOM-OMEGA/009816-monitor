# ai_expert.py - 三階段 AI 決策系統（優化 JSON 提取與思考型模型對接）
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

# === 全域變數：儲存美股分析結果 ===
US_MARKET_SENTIMENT = {
    "analyzed": False,
    "sentiment": "中性",
    "strength": 50,
    "tsm_trend": "持平",
    "tech_outlook": "觀望",
    "next_day_prediction": "震盪"
}

def _call_gemini_api(prompt, debug=False):
    """
    統一的 Gemini API 呼叫函式
    優化點：增加 JSON 區塊定位與 Token 長度限制調高
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        logging.error("❌ 未設定 GEMINI_API_KEY")
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,  # 降低隨機性，讓 JSON 更穩定
            "maxOutputTokens": 1500  # 給予足夠空間容納思考過程與完整 JSON
        }
    }

    # 推薦模型序列：思考型優先
    models_to_try = [
        "gemini-3-flash-preview",
        "gemma-3-27b-it",
        "gemini-2.5-flash",
        "gemini-1.5-flash"
    ]

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
                
                if debug:
                    logging.info(f"🔄 嘗試使用 {model_name}...")

                res = requests.post(api_url, json=payload, timeout=25)

                if res.status_code == 429:
                    logging.warning(f"⚠️ 模型 {model_name} 額度耗盡，嘗試下一個...")
                    break

                if res.status_code != 200:
                    logging.error(f"❌ {model_name} 錯誤 ({res.status_code})")
                    break

                data = res.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                
                # --- [優化] JSON 提取邏輯：跳過思考過程 ---
                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                if json_match:
                    clean_text = json_match.group(0)
                    try:
                        result = json.loads(clean_text)
                        logging.info(f"✅ 成功使用 {model_name} 完成分析")
                        return result
                    except json.JSONDecodeError:
                        # 如果標準解析失敗，嘗試救援
                        result = _rescue_json(raw_text)
                        if result:
                            logging.info(f"✅ 成功使用 {model_name} (透過備用救援)")
                            return result
                
            except Exception as e:
                logging.error(f"❌ {model_name} 請求異常: {e}")
                time.sleep(2)

    return None

def _rescue_json(text):
    """
    強化版備用 JSON 解析器
    優化點：支援跨行 (re.S) 與排除干擾字元
    """
    result = {"decision": "觀望", "confidence": 50, "reason": "分析解析異常"}
    try:
        # 使用 re.S 旗標讓 . 匹配換行符
        m_dec = re.search(r'"decision"\s*:\s*"([^"]+)"', text, re.S)
        if m_dec: result["decision"] = m_dec.group(1).strip()
        
        m_conf = re.search(r'"confidence"\s*:\s*(\d+)', text)
        if m_conf: result["confidence"] = int(m_conf.group(1))
        
        m_reason = re.search(r'"reason"\s*:\s*"([^"]*?)"', text, re.S)
        if m_reason: 
            # 清理換行符讓發送至 LINE 時顯示整齊
            result["reason"] = m_reason.group(1).replace('\n', ' ').strip()
        
        return result
    except:
        return None

def analyze_us_market(extra_data, debug=False):
    global US_MARKET_SENTIMENT
    prompt = f"""你是專業美股分析師，請分析今日盤後數據並預測台股明日開盤。
請務必輸出 JSON 格式。

數據：
- 標普500: {extra_data.get('spx')}
- 那斯達克: {extra_data.get('nasdaq')}
- 台積電ADR: {extra_data.get('tsm')}

輸出範例：
{{
  "sentiment": "多頭",
  "strength": 80,
  "tsm_trend": "強勢",
  "next_day": "上漲",
  "reason": "台積電ADR強勁反彈"
}}"""
    result = _call_gemini_api(prompt, debug)
    if result:
        US_MARKET_SENTIMENT.update({
            "analyzed": True,
            "sentiment": result.get("sentiment", "中性"),
            "strength": result.get("strength", 50),
            "tsm_trend": result.get("tsm_trend", "持平"),
            "tech_outlook": result.get("reason", ""),
            "next_day_prediction": result.get("next_day", "震盪")
        })
        return {"decision": result.get("next_day"), "confidence": result.get("strength"), "reason": result.get("reason")}
    return {"decision": "震盪", "confidence": 50, "reason": "美股數據讀取異常"}

def analyze_taiwan_stock(extra_data, target_name="台股標的", debug=False):
    us_sentiment = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "未知", "sentiment": "未知"}
    
    prompt = f"""你是專業存股經理人，分析「{target_name}」。
特別提醒：若為新掛牌 ETF（如 009816），應重點關注發行價 10.00 之偏離度與成分股走勢。

技術數據：{extra_data.get('tech_summary')}
美股情緒：{us_sentiment.get('sentiment')} / 明日預測：{us_sentiment.get('next_day_prediction')}

請輸出 JSON：
{{
  "decision": "定期定額/觀望",
  "confidence": 75,
  "reason": "具體分析理由"
}}"""
    return _call_gemini_api(prompt, debug)

def analyze_grid_trading(extra_data, target_name="網格標的", debug=False):
    us_sentiment = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "未知"}
    
    prompt = f"""你是網格交易專家，分析「{target_name}」。
目前現價: {extra_data.get('price')}，補倉點: {extra_data.get('grid_buy')}。
明日台股預測: {us_sentiment.get('next_day_prediction')}

請考慮是否因美股大漲導致開盤過高，建議「等待回檔」還是「立即執行」。
請輸出 JSON：
{{
  "decision": "等待回檔/立即執行",
  "confidence": 70,
  "reason": "理由"
}}"""
    return _call_gemini_api(prompt, debug)

# === 保持原本的 get_ai_point 兼容邏輯 ===
def get_ai_point(target_name=None, strategy_type=None, extra_data=None, debug=False, **kwargs):
    if isinstance(target_name, dict) and extra_data is None:
        extra_data = target_name
        target_name = kwargs.get('target_name', 'Unknown')
    
    if strategy_type == "us_market" or "US_MARKET" in str(target_name):
        return analyze_us_market(extra_data or {}, debug)
    elif "grid" in str(strategy_type):
        return analyze_grid_trading(extra_data or {}, str(target_name), debug)
    else:
        return analyze_taiwan_stock(extra_data or {}, str(target_name), debug)

if __name__ == "__main__":
    # 測試執行
    test_data = {"spx": "6932", "nasdaq": "23031", "tsm": "348 (+5%)"}
    print(analyze_us_market(test_data, debug=True))
