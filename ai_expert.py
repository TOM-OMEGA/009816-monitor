# ai_expert.py
import os
import requests
import json
from datetime import datetime
import time
import logging

# === 設定 logging ===
logging.basicConfig(level=logging.INFO)

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_LAST_CALL = {}
AI_COOLDOWN_MINUTES = 5  # 正式環境可改 5 分鐘

def get_ai_point(extra_data=None, target_name="標的", summary_override=None, debug=False):
    """
    核心 AI 判斷函式 (Gemini API)
    支援台股存股 / 網格策略 / 美股盤後
    """
    global AI_CACHE, AI_LAST_CALL
    now = datetime.now()

    # --- 檢查 API Key ---
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        error_msg = "❌ 未設定 GEMINI_API_KEY 環境變數"
        logging.error(error_msg)
        return {"decision": "ERROR", "confidence": 0, "reason": error_msg}

    # --- summary 補齊欄位 ---
    d = extra_data or {}
    defaults = {
        "price": 0,
        "inst": "N/A",
        "holders": "N/A",
        "order_strength": "穩定",
        "valuation": "合理",
        "day_trade": "穩定",
        "k_line": "N/A",
        "market_context": "N/A",
        "idx_5s": "N/A",
        "US_signal": "N/A",
        "rev": "N/A",
        "tech": "N/A",
        "spx": "N/A",
        "nasdaq": "N/A",
        "sox": "N/A",
        "tsm": "N/A"
    }
    for k, v in defaults.items():
        if k not in d:
            d[k] = v

    # --- summary text ---
    if summary_override:
        summary_text = summary_override
    else:
        # 簡化版本，移除 get_fm_data 依賴
        summary_text = (
            f"1. 現價: {d.get('price')}\n"
            f"2. K線/量: {d.get('k_line')}\n"
            f"3. 盤中5s力道: {d.get('order_strength')}\n"
            f"4. 價值位階: {d.get('valuation')}\n"
            f"5. 市場脈動: {d.get('market_context')}\n"
            f"6. 大盤5s脈動: {d.get('idx_5s')}\n"
            f"7. 籌碼穩定: 法人 {d.get('inst')}, 大戶 {d.get('holders')}, 日內 {d.get('day_trade')}\n"
            f"8. 美股參考: {d.get('US_signal')}\n"
            f"9. 基本面: {d.get('rev')}\n"
            f"10. 技術結構: {d.get('tech')}"
        )

    # --- Cache Key ---
    key = f"{target_name}_{summary_text[:50]}"

    # --- 冷卻檢查 ---
    last_call = AI_LAST_CALL.get(key)
    if last_call and (now - last_call).total_seconds() < AI_COOLDOWN_MINUTES * 60:
        if debug: 
            logging.info(f"🕒 冷卻中 (使用 Cache) {target_name}")
        return AI_CACHE.get(key, {"decision":"觀望","confidence":50,"reason":"使用快取結果"})

    # --- Prompt ---
    focus = "【重點監控：TSM/SOX 科技連動】" if any(x in target_name for x in ["2317", "00929", "TSM"]) else "【重點監控：趨勢脈動】"
    persona_logic = (
        f"身分：專業投資分析師。標的：{target_name}。{focus}\n"
        "請嚴守十條實戰鐵律：1.期望值 2.非加碼 3.趨勢濾網 4.動態間距 5.資金控制 "
        "6.除息還原 7.低成本 8.情緒收割 9.連動風險 10.自動化。"
    )

    prompt = f"""
{persona_logic}

技術摘要:
{summary_text}

請嚴格輸出 JSON，格式如下：
{{
  "decision": "可行 | 不可行 | 觀望",
  "confidence": 0-100,
  "reason": "80字內理由"
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {"temperature": 0.3}
    }

    # --- 呼叫 API + 重試 ---
    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 分析超時"}
    
    for attempt in range(3):
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={gemini_key}"
            
            if debug:
                logging.info(f"🔄 第 {attempt+1} 次呼叫 Gemini API...")
            
            res = requests.post(api_url, json=payload, timeout=30)

            # 處理限流
            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                logging.warning(f"⚠️ 第 {attempt+1} 次 API 限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            # 處理其他錯誤
            if res.status_code != 200:
                error_msg = f"API 錯誤 {res.status_code}: {res.text[:100]}"
                logging.error(error_msg)
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "ERROR", "confidence": 0, "reason": error_msg}

            res.raise_for_status()
            data = res.json()

            # 解析 AI 回傳文字
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_text = text.replace("```json","").replace("```","").strip()
            ai_result = json.loads(clean_text)
            
            if debug:
                logging.info(f"✅ API 呼叫成功: {ai_result}")
            
            break

        except json.JSONDecodeError as e:
            error_msg = f"JSON 解析失敗: {str(e)[:50]}"
            logging.error(error_msg)
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": error_msg}
            
        except requests.exceptions.Timeout:
            error_msg = "API 請求超時"
            logging.error(error_msg)
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": error_msg}
            
        except Exception as e:
            error_msg = f"異常: {str(e)[:80]}"
            logging.error(error_msg)
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": error_msg}

    # --- 更新 Cache ---
    AI_CACHE[key] = ai_result
    AI_LAST_CALL[key] = now

    if debug: 
        logging.info(f"🤖 AI 判斷 ({target_name}): {ai_result}")
    
    return ai_result


# === 美股專用 AI 判斷 ===
def get_us_ai_point(extra_data, debug=False):
    """
    美股盤後專用，只判斷風險模式
    """
    summary = (
        f"S&P500: {extra_data.get('spx')}\n"
        f"NASDAQ: {extra_data.get('nasdaq')}\n"
        f"SOX: {extra_data.get('sox')}\n"
        f"TSM: {extra_data.get('tsm')}\n"
        f"技術結構: {extra_data.get('tech')}"
    )

    return get_ai_point(
        extra_data=extra_data,
        target_name="US_MARKET",
        summary_override=summary,
        debug=debug
    )


# === 測試函式 ===
if __name__ == "__main__":
    """本地測試用"""
    logging.info("🧪 開始測試 AI 模組...")
    
    # 檢查 API Key
    if not os.environ.get("GEMINI_API_KEY"):
        logging.error("❌ 請先設定環境變數: export GEMINI_API_KEY='你的金鑰'")
    else:
        logging.info("✅ API Key 已設定")
        
        # 測試呼叫
        test_data = {
            "price": 15.5,
            "k_line": "上漲",
            "valuation": "50%",
            "tech": "MA20 交叉向上"
        }
        
        result = get_ai_point(extra_data=test_data, target_name="測試標的", debug=True)
        logging.info(f"📊 測試結果: {result}")
