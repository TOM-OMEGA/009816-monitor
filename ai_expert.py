# ai_expert.py
import os
import requests
import json
from datetime import datetime
import time
from data_engine import get_fm_data

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
        "tech": "N/A",  # 網格或美股
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
        month_low = None
        try:
            if ".TW" in target_name:
                df_month = get_fm_data("TaiwanStockPrice", target_name.replace(".TW",""), days=30)
                if df_month is not None and not df_month.empty:
                    month_low = df_month['close'].min()
        except:
            month_low = None

        summary_text = (
            f"1. 現價: {d.get('price')}\n"
            f"2. 本月最低: {month_low if month_low else 'N/A'}\n"
            f"3. K線/量: {d.get('k_line')}\n"
            f"4. 盤中5s力道: {d.get('order_strength')}\n"
            f"5. 價值位階: {d.get('valuation')}\n"
            f"6. 市場脈動: {d.get('market_context')}\n"
            f"7. 大盤5s脈動: {d.get('idx_5s')}\n"
            f"8. 籌碼穩定: 法人 {d.get('inst')}, 大戶 {d.get('holders')}, 日內 {d.get('day_trade')}\n"
            f"9. 美股參考: {d.get('US_signal')}\n"
            f"10. 基本面: {d.get('rev')}\n"
            f"11. 技術結構: {d.get('tech')}"
        )

    # --- Cache Key ---
    key = f"{target_name}_{summary_text[:50]}"

    # --- 冷卻檢查 ---
    last_call = AI_LAST_CALL.get(key)
    if last_call and (now - last_call).total_seconds() < AI_COOLDOWN_MINUTES * 60:
        if debug: print(f"🕒 冷卻中 (使用 Cache) {target_name}")
        return AI_CACHE.get(key, {"decision":"觀望","confidence":0,"reason":"冷卻中"})

    # --- 取得 API Key ---
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "Missing API Key"}

    # --- Prompt ---
    focus = "【重點監控：TSM/SOX 科技連動】" if any(x in target_name for x in ["2317", "00929", "TSM"]) else "【重點監控：趨勢脈動】"
    persona_logic = (
        f"身分：作者劉承彥。標的：{target_name}。{focus}\n"
        "請嚴守十條實戰鐵律：1.期望值 2.非加碼 3.趨勢濾網 4.動態間距 5.資金控制 "
        "6.除息還原 7.低成本 8.情緒收割 9.連動風險 10.自動化 11.圖表。"
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

    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3}}

    # --- 呼叫 API + 重試 ---
    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 分析超時"}
    for attempt in range(3):
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            res = requests.post(api_url, json=payload, timeout=30)

            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                if debug: print(f"⚠️ 第 {attempt+1} 次 API 限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            res.raise_for_status()
            data = res.json()

            # 解析 AI 回傳文字
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_text = text.replace("```json","").replace("```","").strip()
            ai_result = json.loads(clean_text)
            break

        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"異常: {str(e)[:50]}"}

    # --- 更新 Cache ---
    AI_CACHE[key] = ai_result
    AI_LAST_CALL[key] = now

    if debug: print(f"🤖 AI 判斷 ({target_name}): {ai_result}")
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
