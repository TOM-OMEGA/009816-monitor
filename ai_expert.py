# ai_expert.py - 三階段 AI 決策系統（強化台股與網格模組）
import os
import requests
import json
import time
import re
import logging

# === 設定 logging ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# === 全域變數：儲存美股分析結果 ===
US_MARKET_SENTIMENT = {
    "analyzed": False,
    "sentiment": "中性",
    "strength": 50,
    "tsm_trend": "持平",
    "next_day_prediction": "震盪"
}

def _get_historical_context():
    """提供 2026 年所需的跨年度數據背景"""
    return (
        "\n[決策基準]\n"
        "- 歷史基準 (2003-2025): 平均年化 12.5%。\n"
        "- 往前看一年 (2025): 考量 2025 年的收盤位階與增長點。\n"
        "- 預測一年後 (2027): 評估產業長期循環位置。\n"
    )

def _call_gemini_api(prompt, debug=False):
    """統一 API 呼叫函式"""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        logging.error("❌ 未設定 GEMINI_API_KEY")
        return None

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2, # 降低隨機性，更依賴數據
            "maxOutputTokens": 1000
        }
    }

    # 優先使用 gemma-3-27b-it (你驗證過的主力)
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemma-3-27b-it:generateContent?key={gemini_key}"
    
    try:
        res = requests.post(api_url, json=payload, timeout=20)
        if res.status_code == 200:
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r'```json\n?|\n?```', '', text).strip()
            return json.loads(text)
    except Exception as e:
        logging.error(f"AI 呼叫失敗: {e}")
    return None

def analyze_taiwan_stock(extra_data, target_name="台股標的", debug=False):
    """階段二：台股存股分析 - 補強技術指標"""
    global US_MARKET_SENTIMENT
    time_ctx = _get_historical_context()
    
    # 讀取美股情緒
    us_info = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"sentiment": "未知", "tsm_trend": "未知"}

    prompt = f"""你是專業存股分析師，分析標的「{target_name}」。
{time_ctx}
[核心技術數據]
- 現價: {extra_data.get('price', 'N/A')}
- 系統評分: {extra_data.get('score', 'N/A')}
- 價格位階: {extra_data.get('position', 'N/A')} (全年度位階)
- 2027 展望: {extra_data.get('outlook', 'N/A')} (預期報酬/年化)

[美股盤後參考]
- 市場情緒: {us_info.get('sentiment')}
- 台積電ADR: {us_info.get('tsm_trend')}

請根據「2025實績」與「2027展望」，給出決策。
請輸出 JSON：
{{
  "decision": "積極買進/定期定額/觀望等待",
  "confidence": 0-100,
  "reason": "需結合美股ADR強勢(5.48%)對台股開盤的影響，並解釋為何選擇該決策（100字內）"
}}"""

    result = _call_gemini_api(prompt, debug)
    return result if result else {"decision": "觀望", "confidence": 50, "reason": "AI 解析異常"}

def analyze_grid_trading(extra_data, target_name="網格標的", debug=False):
    """階段三：網格交易分析 - 補強網格點位指標"""
    global US_MARKET_SENTIMENT
    time_ctx = _get_historical_context()
    us_info = US_MARKET_SENTIMENT if US_MARKET_SENTIMENT["analyzed"] else {"next_day_prediction": "上漲"}

    prompt = f"""你是網格交易專家，分析「{target_name}」。
{time_ctx}
[網格監控指標]
- 現價: {extra_data.get('price', 'N/A')}
- 趨勢狀態: {extra_data.get('trend', 'N/A')}
- RSI 指標: {extra_data.get('rsi', 'N/A')}
- 網格補倉點: {extra_data.get('grid_buy', 'N/A')}

[外部環境]
- 台股開盤預測: {us_info.get('next_day_prediction')} (受美股大漲影響)

請評估在「2026年高基期」下，此點位是否具備安全邊際。
請輸出 JSON：
{{
  "decision": "立即買進/等待回檔/觀望",
  "confidence": 0-100,
  "reason": "說明 RSI 與補倉點的關係，並指出美股對開盤點位的影響（100字內）"
}}"""

    result = _call_gemini_api(prompt, debug)
    return result if result else {"decision": "觀望", "confidence": 50, "reason": "AI 解析異常"}
