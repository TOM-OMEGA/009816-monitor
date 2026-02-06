import os
import requests
import json
from datetime import datetime, timedelta
import time
import pandas as pd
from data_engine import get_fm_data

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_LAST_CALL = {}
AI_COOLDOWN_MINUTES = 1  # 測試期間縮短冷卻，正式環境可改回 5

def get_ai_point(extra_data=None, target_name="標的", summary_override=None):
    """
    核心 AI 判斷函式
    """
    global AI_CACHE, AI_LAST_CALL
    now = datetime.now()

    summary_text = summary_override or ""
    key = f"{target_name}_{summary_text[:50]}"
    
    # 檢查冷卻
    last_call = AI_LAST_CALL.get(key)
    if last_call and (now - last_call).total_seconds() < AI_COOLDOWN_MINUTES * 60:
        return AI_CACHE.get(key, {"decision":"觀望","confidence":0,"reason":"冷卻中"})

    # 取得 Key (優先從環境變數抓取)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "Missing API Key"}

    d = extra_data or {}

    # 技術摘要處理
    if summary_override:
        summary = summary_override
    else:
        # 計算本月最低 (台股邏輯)
        month_low = None
        try:
            df_month = get_fm_data("TaiwanStockPrice", target_name.replace(".TW",""), days=30)
            if not df_month.empty:
                month_low = df_month['close'].min()
        except:
            month_low = None

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

    # 提示詞邏輯
    focus = "【重點監控：TSM/SOX 科技連動】" if any(x in target_name for x in ["2317", "00929", "TSM"]) else "【重點監控：趨勢脈動】"
    persona_logic = (
        f"身分：作者劉承彥。標的：{target_name}。{focus}\n"
        "請嚴守十條實戰鐵律：1.期望值 2.非加碼 3.趨勢濾網 4.動態間距 5.資金控制 "
        "6.除息還原 7.低成本 8.情緒收割 9.連動風險 10.自動化 11.圖表。"
    )

    prompt = f"""
{persona_logic}

技術摘要:
{summary}

請綜合判斷是否適合操作。
⚠️ 嚴格輸出 JSON，禁止多餘文字：
{{
  "decision": "可行 | 不可行 | 觀望",
  "confidence": 0-100,
  "reason": "80字內理由"
}}
"""

    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.3}}

    # ==== 呼叫 API + 429 強化重試機制 ====
    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 分析超時"}
    
    # 重試次數增加到 3 次，應對 Render 啟動時的突發請求
    for attempt in range(3):
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            res = requests.post(api_url, json=payload, timeout=30)
            
            # 處理 429 限流
            if res.status_code == 429:
                wait_time = 25 + (attempt * 5) # 遞增等待時間
                print(f"⚠️ 第 {attempt+1} 次 API 限流，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue
                
            res.raise_for_status()
            data = res.json()
            
            # 解析並清理文字
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_text = text.replace("```json", "").replace("```", "").strip()
            ai_result = json.loads(clean_text)
            break # 成功則跳出迴圈
            
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"異常: {str(e)[:20]}"}

    # 更新 Cache
    AI_CACHE[key] = ai_result
    AI_LAST_CALL[key] = now
    print(f"🤖 AI 判斷 ({target_name}): {ai_result}")
    return ai_result

# === 新增美股盤後 AI 判斷 (優化 Prompt 邏輯) ===
def get_us_ai_point(extra_data=None, target_name="US_MARKET"):
    """
    針對美股收盤數據優化的判斷入口
    """
    summary_override = (
        f"【美股盤後多維度數據】\n"
        f"各指數現況: {extra_data}\n"
        f"請結合 MACD 動能柱(紅綠縮長)與布林通道位置判斷趨勢。"
    )
    return get_ai_point(extra_data=extra_data, target_name=target_name, summary_override=summary_override)
