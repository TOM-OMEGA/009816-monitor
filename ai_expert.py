# ai_expert.py - 三階段 AI 決策系統（使用可運作的 API 配置）
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
    統一的 Gemini API 呼叫函式（使用已驗證的配置）
    """
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        logging.error("❌ 未設定 GEMINI_API_KEY")
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,      # 降低隨機性，提高準確度
            "topK": 64,              # 配合 thinking 模式
            "topP": 0.95,            # 保持多樣性
            "maxOutputTokens": 2048  # 提高輸出長度以容納深度思考
        }
    }

    # 使用支援深度思考的 Gemini 2.5/2.0 系列（已確認可用）
    # gemini-2.5-flash: 最新穩定版，支援 thinking，100萬 token 輸入
    # gemini-2.5-pro: Pro 級別，最強分析能力
    # gemini-2.0-flash: 備援選擇
    # gemma-3-27b-it: 開源備援（你之前驗證過）
    models_to_try = [
        "gemini-2.5-flash",      # 最佳選擇：thinking + 大輸出
        "gemini-2.5-pro",        # Pro 級分析
        "gemini-2.0-flash",      # 穩定備援
        "gemma-3-27b-it"         # 開源備援
    ]

    for model_name in models_to_try:
        for attempt in range(2):
            try:
                # 使用 v1beta 端點（已驗證）
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
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                
                # 清理 Markdown 標記
                text = re.sub(r'```json\n?|\n?```', '', text).strip()
                
                # 嘗試解析 JSON
                try:
                    result = json.loads(text)
                    logging.info(f"✅ 成功使用 {model_name} 完成分析")
                    return result
                except json.JSONDecodeError:
                    # 備用解析
                    result = _rescue_json(text)
                    if result:
                        logging.info(f"✅ 成功使用 {model_name} 完成分析（備用解析）")
                        return result

            except Exception as e:
                logging.error(f"❌ {model_name} 請求異常: {e}")
                time.sleep(2)

    return None

def _rescue_json(text):
    """備用 JSON 解析器"""
    result = {"decision": "觀望", "confidence": 50, "reason": "解析錯誤"}
    try:
        m_dec = re.search(r'"decision"\s*:\s*"([^"]+)"', text)
        if m_dec: result["decision"] = m_dec.group(1)
        m_conf = re.search(r'"confidence"\s*:\s*(\d+)', text)
        if m_conf: result["confidence"] = int(m_conf.group(1))
        m_reason = re.search(r'"reason"\s*:\s*"([^"]*?)"', text)
        if m_reason: result["reason"] = m_reason.group(1)
        return result
    except:
        return None

def analyze_us_market(extra_data, debug=False):
    """
    階段一：美股盤後綜合分析
    產生市場情緒指標供台股參考
    """
    global US_MARKET_SENTIMENT

    prompt = f"""你是專業美股分析師，請深度分析今日盤後數據並預測台股明日開盤。

美股數據：
- 標普500: {extra_data.get('spx', 'N/A')}
- 那斯達克: {extra_data.get('nasdaq', 'N/A')}
- 台積電ADR: {extra_data.get('tsm', 'N/A')}
- 技術面: {extra_data.get('tech', 'N/A')}

分析步驟：
1. 評估美股整體情緒（多頭/空頭/中性）
2. 分析科技股動能強度（0-100）
3. 判斷台積電ADR表現對台股的影響
4. 預測台股明日開盤方向（上漲/下跌/震盪）
5. 給出投資建議

請輸出 JSON（不要包含 Markdown 標記）：
{{
  "sentiment": "多頭/空頭/中性",
  "strength": 75,
  "tsm_trend": "強勢/弱勢/持平",
  "next_day": "上漲/下跌/震盪",
  "reason": "簡短理由（40字內）"
}}"""

    result = _call_gemini_api(prompt, debug)
    
    if result:
        # 更新全域市場情緒
        US_MARKET_SENTIMENT = {
            "analyzed": True,
            "sentiment": result.get("sentiment", "中性"),
            "strength": result.get("strength", 50),
            "tsm_trend": result.get("tsm_trend", "持平"),
            "tech_outlook": result.get("reason", ""),
            "next_day_prediction": result.get("next_day", "震盪")
        }
        
        return {
            "decision": result.get("next_day", "震盪"),
            "confidence": result.get("strength", 50),
            "reason": result.get("reason", "美股分析完成")
        }
    else:
        # API 失敗時的備用值
        US_MARKET_SENTIMENT["analyzed"] = True
        return {
            "decision": "震盪",
            "confidence": 50,
            "reason": "美股數據分析異常"
        }

def analyze_taiwan_stock(extra_data, target_name="台股標的", debug=False):
    """
    階段二：台股存股分析
    結合美股情緒進行判斷
    """
    us_sentiment = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "未知", "sentiment": "未知"}

    prompt = f"""你是專業存股經理人，請深度分析台股標的「{target_name}」。

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

分析步驟：
1. 考量美股開盤方向（可能高開/低開/平盤）
2. 評估當前價格位階（低檔適合積極/高檔宜觀望）
3. 結合技術面與基本面
4. 給出今日開盤策略

請輸出 JSON（不要包含 Markdown 標記）：
{{
  "decision": "積極買進/定期定額/觀望等待",
  "confidence": 70,
  "reason": "理由（50字內，需說明美股影響）"
}}"""

    result = _call_gemini_api(prompt, debug)
    
    if result:
        return {
            "decision": result.get("decision", "觀望"),
            "confidence": result.get("confidence", 50),
            "reason": result.get("reason", "分析完成")
        }
    else:
        return {
            "decision": "觀望",
            "confidence": 50,
            "reason": "AI 分析異常"
        }

def analyze_grid_trading(extra_data, target_name="網格標的", debug=False):
    """
    階段三：網格交易分析
    結合美股情緒進行判斷
    """
    us_sentiment = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "未知"}

    prompt = f"""你是網格交易專家，請深度分析「{target_name}」的網格策略。

技術面：
- 現價: {extra_data.get('price', 'N/A')}
- 趨勢: {extra_data.get('trend', 'N/A')}
- RSI: {extra_data.get('rsi', 'N/A')}
- 補倉點: {extra_data.get('grid_buy', 'N/A')}

美股參考（昨日盤後）：
- 明日預測: {us_sentiment.get('next_day_prediction', '未知')}
- 台積電ADR: {us_sentiment.get('tsm_trend', '未知')}

分析步驟：
1. 判斷美股對台股開盤的影響
   - 美股偏多 → 台股可能高開 → 是否等回檔
   - 美股偏空 → 台股可能低開 → 是否提早佈局
2. 評估 RSI 超買/超賣狀態
3. 結合趨勢與補倉點
4. 給出今日策略

請輸出 JSON（不要包含 Markdown 標記）：
{{
  "decision": "立即買進/等待回檔/觀望",
  "confidence": 65,
  "reason": "理由（50字內，需說明美股影響）"
}}"""

    result = _call_gemini_api(prompt, debug)
    
    if result:
        return {
            "decision": result.get("decision", "觀望"),
            "confidence": result.get("confidence", 50),
            "reason": result.get("reason", "分析完成")
        }
    else:
        return {
            "decision": "觀望",
            "confidence": 50,
            "reason": "AI 分析異常"
        }

def get_us_market_sentiment():
    """取得當前美股市場情緒（供台股模組使用）"""
    return US_MARKET_SENTIMENT

# === 向後相容的舊函式 ===
def get_ai_point(target_name=None, strategy_type=None, extra_data=None, debug=False, **kwargs):
    """
    向後相容函式：自動判斷使用哪種分析
    """
    # 處理舊版呼叫方式
    if isinstance(target_name, dict) and extra_data is None:
        extra_data = target_name
        target_name = kwargs.get('target_name', 'Unknown_Target')
    
    if 'summary_override' in kwargs and kwargs['summary_override']:
        extra_data = kwargs['summary_override']
        strategy_type = "us_market"
        target_name = "US_MARKET"

    # 自動判斷策略類型
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

    # 根據策略類型呼叫對應函式
    if "US_MARKET" in str(target_name) or strategy_type == "us_market":
        return analyze_us_market(extra_data or {}, debug)
    elif strategy_type == "grid_trading":
        return analyze_grid_trading(extra_data or {}, str(target_name), debug)
    else:
        return analyze_taiwan_stock(extra_data or {}, str(target_name), debug)

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
