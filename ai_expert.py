# ai_expert.py - 三階段 AI 決策系統
import os
import requests
import json
from datetime import datetime
import time
import logging

logging.basicConfig(level=logging.INFO)

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_LAST_CALL = {}
AI_COOLDOWN_MINUTES = 5

# === 全域變數：儲存美股分析結果 ===
US_MARKET_SENTIMENT = {
    "analyzed": False,
    "sentiment": "中性",  # 多頭/空頭/中性
    "strength": 50,       # 0-100
    "tsm_trend": "持平",
    "tech_outlook": "觀望",
    "next_day_prediction": "震盪"  # 上漲/下跌/震盪
}

def analyze_us_market(extra_data, debug=False):
    """
    階段一：美股盤後綜合分析
    產生市場情緒指標供台股參考
    """
    global US_MARKET_SENTIMENT
    
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        logging.error("❌ 未設定 GEMINI_API_KEY")
        return {"decision": "ERROR", "confidence": 0, "reason": "未設定 API Key"}

    # 美股專用 Prompt
    prompt = f"""你是專業美股分析師，請分析今日盤後數據並預測台股明日開盤：

美股數據：
- 標普500: {extra_data.get('spx', 'N/A')}
- 那斯達克: {extra_data.get('nasdaq', 'N/A')}
- 台積電ADR: {extra_data.get('tsm', 'N/A')}
- 技術面: {extra_data.get('tech', 'N/A')}

請分析：
1. 美股整體情緒（多頭/空頭/中性）
2. 科技股動能強度（0-100）
3. 台積電ADR表現（強勢/弱勢/持平）
4. 台股明日開盤預測（上漲/下跌/震盪）
5. 投資建議（30字內）

只輸出一行 JSON：
{{"sentiment":"多頭","strength":75,"tsm_trend":"強勢","next_day":"上漲","reason":"美股科技股強勁台股可望跟漲"}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 512
        }
    }

    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemma-3-27b-it:generateContent?key={gemini_key}"

    for attempt in range(3):
        try:
            if debug:
                logging.info(f"🔄 美股分析 - 第 {attempt+1} 次呼叫 gemma-3-27b-it...")

            res = requests.post(api_url, json=payload, timeout=30)
            
            if res.status_code == 429:
                time.sleep(25 + attempt * 5)
                continue
                
            if res.status_code != 200:
                logging.error(f"API 錯誤 {res.status_code}")
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "ERROR", "confidence": 0, "reason": f"API錯誤 {res.status_code}"}

            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            # 清理並解析
            clean_text = text.strip().replace("```json", "").replace("```", "").strip()
            start_idx = clean_text.find("{")
            end_idx = clean_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                clean_text = clean_text[start_idx:end_idx]
            
            try:
                result = json.loads(clean_text)
                
                # 更新全域市場情緒
                US_MARKET_SENTIMENT = {
                    "analyzed": True,
                    "sentiment": result.get("sentiment", "中性"),
                    "strength": result.get("strength", 50),
                    "tsm_trend": result.get("tsm_trend", "持平"),
                    "tech_outlook": result.get("reason", ""),
                    "next_day_prediction": result.get("next_day", "震盪")
                }
                
                if debug:
                    logging.info(f"✅ 美股分析完成: {US_MARKET_SENTIMENT}")
                
                return {
                    "decision": result.get("next_day", "震盪"),
                    "confidence": result.get("strength", 50),
                    "reason": result.get("reason", "美股分析完成")
                }
                
            except json.JSONDecodeError:
                # 備用解析
                result = {
                    "decision": "震盪",
                    "confidence": 50,
                    "reason": "美股數據解析異常"
                }
                US_MARKET_SENTIMENT["analyzed"] = True
                break
                
        except Exception as e:
            logging.error(f"美股分析異常: {str(e)[:50]}")
            if attempt < 2:
                time.sleep(5)
                continue
            return {"decision": "ERROR", "confidence": 0, "reason": str(e)[:50]}

    return result


def analyze_taiwan_stock(extra_data, target_name="台股標的", debug=False):
    """
    階段二：台股存股分析
    結合美股情緒進行判斷
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "觀望", "confidence": 0, "reason": "未設定 API Key"}

    # 取得美股情緒
    us_sentiment = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "未知", "sentiment": "未知"}

    prompt = f"""你是專業存股經理人，分析台股標的「{target_name}」：

技術數據：
{extra_data.get('tech_summary', 'N/A')}

美股參考（昨日盤後）：
- 市場情緒: {us_sentiment.get('sentiment', '未知')}
- 台積電ADR: {us_sentiment.get('tsm_trend', '未知')}
- 明日預測: {us_sentiment.get('next_day_prediction', '未知')}

存股策略評估：
1. 系統評分: {extra_data.get('score', 'N/A')}
2. 價格位階: {extra_data.get('position', 'N/A')}
3. 長期展望: {extra_data.get('outlook', 'N/A')}

請判斷今日開盤策略（考量美股影響）：
- 決策：積極買進/定期定額/觀望等待
- 信心度：0-100
- 理由：考量美股情緒、技術面、價格位階（40字內）

只輸出一行 JSON：
{{"decision":"定期定額","confidence":70,"reason":"美股偏多但台股位階偏高建議定期定額"}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 512
        }
    }

    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemma-3-27b-it:generateContent?key={gemini_key}"
    
    for attempt in range(3):
        try:
            if debug:
                logging.info(f"🔄 台股存股分析 - 第 {attempt+1} 次呼叫 gemma-3-27b-it...")

            res = requests.post(api_url, json=payload, timeout=30)
            
            if res.status_code == 429:
                time.sleep(25 + attempt * 5)
                continue
                
            if res.status_code != 200:
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "觀望", "confidence": 50, "reason": f"API錯誤 {res.status_code}"}

            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            clean_text = text.strip().replace("```json", "").replace("```", "").strip()
            start_idx = clean_text.find("{")
            end_idx = clean_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                clean_text = clean_text[start_idx:end_idx]
            
            try:
                result = json.loads(clean_text)
                if debug:
                    logging.info(f"✅ 台股分析完成: {result}")
                return result
            except json.JSONDecodeError:
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "觀望", "confidence": 50, "reason": "格式解析異常"}
                
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return {"decision": "觀望", "confidence": 50, "reason": str(e)[:40]}

    return {"decision": "觀望", "confidence": 50, "reason": "分析超時"}


def analyze_grid_trading(extra_data, target_name="網格標的", debug=False):
    """
    階段三：網格交易分析
    結合美股情緒進行判斷
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "觀望", "confidence": 0, "reason": "未設定 API Key"}

    us_sentiment = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "未知"}

    prompt = f"""你是網格交易專家，分析「{target_name}」：

技術面：
- 現價: {extra_data.get('price', 'N/A')}
- 趨勢: {extra_data.get('trend', 'N/A')}
- RSI: {extra_data.get('rsi', 'N/A')}
- 補倉點: {extra_data.get('grid_buy', 'N/A')}

美股參考（昨日盤後）：
- 明日預測: {us_sentiment.get('next_day_prediction', '未知')}
- 台積電ADR: {us_sentiment.get('tsm_trend', '未知')}

網格策略判斷（今日開盤）：
1. 美股若偏多，台股可能高開 → 是否等回檔
2. 美股若偏空，台股可能低開 → 是否提早佈局
3. 結合 RSI 和趨勢

請給出今日策略：
- 決策：立即買進/等待回檔/觀望
- 信心度：0-100
- 理由：考量美股開盤影響（40字內）

只輸出一行 JSON：
{{"decision":"等待回檔","confidence":65,"reason":"美股偏多台股恐高開建議等回補倉點"}}"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 512
        }
    }

    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemma-3-27b-it:generateContent?key={gemini_key}"
    
    for attempt in range(3):
        try:
            if debug:
                logging.info(f"🔄 網格交易分析 - 第 {attempt+1} 次呼叫 gemma-3-27b-it...")

            res = requests.post(api_url, json=payload, timeout=30)
            
            if res.status_code == 429:
                time.sleep(25 + attempt * 5)
                continue
                
            if res.status_code != 200:
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "觀望", "confidence": 50, "reason": f"API錯誤"}

            data = res.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            clean_text = text.strip().replace("```json", "").replace("```", "").strip()
            start_idx = clean_text.find("{")
            end_idx = clean_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                clean_text = clean_text[start_idx:end_idx]
            
            try:
                result = json.loads(clean_text)
                if debug:
                    logging.info(f"✅ 網格分析完成: {result}")
                return result
            except json.JSONDecodeError:
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "觀望", "confidence": 50, "reason": "格式解析異常"}
                
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return {"decision": "觀望", "confidence": 50, "reason": str(e)[:40]}

    return {"decision": "觀望", "confidence": 50, "reason": "分析超時"}


def get_us_market_sentiment():
    """取得當前美股市場情緒（供台股模組使用）"""
    return US_MARKET_SENTIMENT


# === 向後相容的舊函式 ===
def get_ai_point(extra_data=None, target_name="標的", summary_override=None, debug=False):
    """向後相容：自動判斷使用哪種分析"""
    if "US_MARKET" in target_name or "美股" in target_name:
        return analyze_us_market(extra_data or {}, debug)
    elif "網格" in target_name or "grid" in target_name.lower():
        return analyze_grid_trading(extra_data or {}, target_name, debug)
    else:
        return analyze_taiwan_stock(extra_data or {}, target_name, debug)


def get_us_ai_point(extra_data, debug=False):
    """美股專用（向後相容）"""
    return analyze_us_market(extra_data, debug)


# === 測試 ===
if __name__ == "__main__":
    logging.info("🧪 測試三階段 AI 系統...")
    
    # 階段一：美股
    us_data = {
        "spx": "6,932 (+1.97%)",
        "nasdaq": "23,031 (+2.18%)",
        "tsm": "348.85 (+5.48%)",
        "tech": "科技股強勁"
    }
    us_result = analyze_us_market(us_data, debug=True)
    print(f"美股: {us_result}")
    
    # 階段二：台股
    tw_data = {
        "tech_summary": "現價10.09, 年化報酬17.74, RSI 55",
        "score": "70/100",
        "position": "31%",
        "outlook": "複利穩定"
    }
    tw_result = analyze_taiwan_stock(tw_data, "009816", debug=True)
    print(f"台股: {tw_result}")
    
    # 階段三：網格
    grid_data = {
        "price": 215.0,
        "trend": "空頭",
        "rsi": 32.1,
        "grid_buy": 210.49
    }
    grid_result = analyze_grid_trading(grid_data, "2317", debug=True)
    print(f"網格: {grid_result}")
