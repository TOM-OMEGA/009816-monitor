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
AI_COOLDOWN_MINUTES = 5

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

請嚴格按照以下格式輸出，不要有任何多餘文字、換行或說明：

{{"decision": "可行", "confidence": 75, "reason": "技術面偏多適合進場"}}

規則：
1. decision 只能是：可行、不可行、觀望（三選一）
2. confidence 是 0-100 的整數
3. reason 必須少於 80 字
4. 只輸出 JSON，不要有任何前後說明文字
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {
            "temperature": 0.3,
            "topK": 40,
            "topP": 0.95,
            "maxOutputTokens": 1024,
            "responseMimeType": "application/json"  # 強制 JSON 輸出
        }
    }

    # --- 呼叫 API + 重試 ---
    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 分析超時"}
    
    # 使用 Gemini 2.5 Flash（2025年6月發布的穩定版）
    # 支援 100萬 token 輸入，6.5萬 token 輸出
    api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent?key={gemini_key}"
    
    for attempt in range(3):
        try:
            if debug:
                logging.info(f"🔄 第 {attempt+1} 次呼叫 Gemini API...")
                logging.info(f"📍 使用模型: gemini-2.5-flash")
            
            res = requests.post(api_url, json=payload, timeout=30)

            # 處理限流
            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                logging.warning(f"⚠️ 第 {attempt+1} 次 API 限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            # 處理其他錯誤
            if res.status_code != 200:
                error_msg = f"API 錯誤 {res.status_code}: {res.text[:150]}"
                logging.error(error_msg)
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "ERROR", "confidence": 0, "reason": f"API錯誤 {res.status_code}"}

            data = res.json()

            # 檢查回應格式
            if "candidates" not in data or not data["candidates"]:
                error_msg = "API 回應格式錯誤"
                logging.error(f"{error_msg}: {data}")
                if attempt < 2:
                    time.sleep(5)
                    continue
                return {"decision": "ERROR", "confidence": 0, "reason": error_msg}

            # 解析 AI 回傳文字
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            
            if debug:
                logging.info(f"📥 原始回應: {text[:200]}...")
            
            # 多層清理策略
            clean_text = text.strip()
            
            # 移除 Markdown 代碼塊標記
            clean_text = clean_text.replace("```json", "").replace("```", "")
            
            # 移除前後空白和換行
            clean_text = clean_text.strip()
            
            # 嘗試找到 JSON 物件的開始和結束
            start_idx = clean_text.find("{")
            end_idx = clean_text.rfind("}") + 1
            
            if start_idx != -1 and end_idx > start_idx:
                clean_text = clean_text[start_idx:end_idx]
            
            # 修正常見的 JSON 格式問題
            clean_text = clean_text.replace("\n", " ").replace("\r", "")
            
            try:
                ai_result = json.loads(clean_text)
                
                # 驗證必要欄位
                if "decision" not in ai_result:
                    ai_result["decision"] = "觀望"
                if "confidence" not in ai_result:
                    ai_result["confidence"] = 50
                if "reason" not in ai_result:
                    ai_result["reason"] = "AI 分析完成"
                
                if debug:
                    logging.info(f"✅ API 呼叫成功: {ai_result}")
                
                break
                
            except json.JSONDecodeError as json_err:
                # JSON 解析失敗，嘗試手動提取資訊
                logging.warning(f"⚠️ JSON 解析失敗，嘗試手動提取: {str(json_err)[:50]}")
                
                # 手動解析模式（備用方案）
                decision = "觀望"
                confidence = 50
                reason = "AI 分析結果格式異常"
                
                # 簡單的關鍵字匹配
                text_lower = text.lower()
                if "可行" in text or "買入" in text or "進場" in text:
                    decision = "可行"
                    confidence = 70
                elif "不可行" in text or "賣出" in text or "離場" in text:
                    decision = "不可行"
                    confidence = 70
                
                # 提取理由（取前80字）
                if "理由" in text or "reason" in text_lower:
                    reason_start = max(text.find("理由"), text_lower.find("reason"))
                    if reason_start != -1:
                        reason = text[reason_start:reason_start+100].strip()
                
                ai_result = {
                    "decision": decision,
                    "confidence": confidence,
                    "reason": reason[:80]
                }
                
                logging.info(f"🔧 使用備用解析: {ai_result}")
                break

        except json.JSONDecodeError as e:
            error_msg = f"JSON 解析失敗"
            logging.error(f"{error_msg}: {str(e)[:50]}")
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "觀望", "confidence": 50, "reason": "格式解析異常"}
            
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
    美股盤後專用,只判斷風險模式
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
