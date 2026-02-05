import os
import requests
import json
from datetime import datetime, timedelta
import time
import pandas as pd
from data_engine import get_fm_data  # 用來抓歷史價格計算月最低

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_LAST_CALL = {}
AI_COOLDOWN_MINUTES = 5  # 測試時延長冷卻，避免 429

def get_ai_point(extra_data=None, target_name="標的", summary_override=None):
    """
    台股 AI 判斷，不改原邏輯
    extra_data 可包含 "US_signal" 作為美股參考
    """
    global AI_CACHE, AI_LAST_CALL
    now = datetime.now()

    summary_text = summary_override or ""
    key = f"{target_name}_{summary_text[:50]}"
    last_call = AI_LAST_CALL.get(key)
    if last_call and (now - last_call).total_seconds() < AI_COOLDOWN_MINUTES * 60:
        return AI_CACHE.get(key, {"decision":"觀望","confidence":0,"reason":"冷卻中"})

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "Missing API Key"}

    d = extra_data or {}

    # 計算本月最低
    month_low = None
    try:
        df_month = get_fm_data("TaiwanStockPrice", target_name.replace(".TW",""), days=30)
        if not df_month.empty:
            month_low = df_month['close'].min()
    except:
        month_low = None

    # 技術摘要
    if summary_override:
        summary = summary_override
    else:
        summary = (
            f"1. 現價: {d.get('price','N/A')}\n"
            f"2. 本月最低: {month_low if month_low else 'N/A'}\n"
            f"3. K線/量: {d.get('k_line', 'N/A')}\n"
            f"4. 盤中5s力道: {d.get('order_strength', 'N/A')}\n"
            f"5. 價值位階: {d.get('valuation', 'N/A')}\n"
            f"6. 市場脈動: {d.get('market_context', 'N/A')}\n"
            f"7. 大盤5s脈動: {d.get('idx_5s', 'N/A')}\n"
            f"8. 籌碼穩定: 法人 {d.get('inst','N/A')}, 大戶 {d.get('holders','N/A')}, 日內 {d.get('day_trade','N/A')}\n"
            f"9. 美股參考: {d.get('US_signal','N/A')}\n"
            f"10. 基本面: {d.get('rev','N/A')}"
        )

    focus = "【重點監控：TSM/SOX 科技連動】" if any(x in target_name for x in ["2317", "00929"]) else "【重點監控：台股加權指數 & 金融防禦性】"
    persona_logic = (
        f"身分：作者劉承彥。標的：{target_name}。{focus}\n"
        "請嚴守十條實戰鐵律：1.期望值 2.非加碼 3.趨勢濾網 4.動態間距 5.資金控制 "
        "6.除息還原 7.低成本 8.情緒收割 9.連動風險 10.自動化。"
    )

    prompt = f"""
{persona_logic}

技術摘要:
{summary}

請你「綜合判斷現在是否適合買入」，重點考慮當月最低點策略，並可參考美股收盤訊號，但不要只看價格。

⚠️ 嚴格輸出 JSON，禁止多餘文字：
{{
  "decision": "可行 | 不可行 | 觀望",
  "confidence": 0-100,
  "reason": "60字內理由"
}}

規則：
- confidence < 60 視為觀望
- 若大盤或產業風險高，請偏向不可行
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.4}}

    # ==== 呼叫 API + 429 重試機制 ====
    ai_result = {"decision": "ERROR", "confidence": 0, "reason": "未呼叫 API"}
    for attempt in range(2):
        try:
            # 修正 1：改用 v1 穩定版介面，並確認 gemini_key 來源
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            
            res = requests.post(api_url, json=payload, timeout=30)
            res.raise_for_status()
            data = res.json()
            
            # 修正 2：增加解析安全性，過濾 Gemini 可能帶有的 Markdown 標籤
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_text = text.replace("```json", "").replace("```", "").strip()
            ai_result = json.loads(clean_text)
            break
            
        except requests.exceptions.HTTPError as e:
            if res.status_code == 429:
                print("⚠️ AI API 限流，等待 20 秒後重試...")
                time.sleep(20)
            else:
                ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"HTTP {res.status_code}"}
                break
        except Exception as e:
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"解析失敗: {str(e)[:20]}"}
            break

    # 更新 Cache
    AI_CACHE[key] = ai_result
    AI_LAST_CALL[key] = now

    print(f"🤖 AI 判斷 ({target_name}): {ai_result}")
    return ai_result


# === 新增美股盤後 AI 判斷 ===
def get_us_ai_point(extra_data=None, target_name="US_MARKET"):
    """
    專門判斷美股收盤走勢
    target_name: SPY, QQQ, DIA, TSM
    """
    summary_override = f"美股收盤資料: {extra_data or 'N/A'}"
    # 直接呼叫台股 AI 函式，但 summary 換成美股收盤資料
    return get_ai_point(extra_data=extra_data, target_name=target_name, summary_override=summary_override)
