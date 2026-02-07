import os
import requests
import json
import time
from datetime import datetime

# === AI 冷卻 / Cache ===
AI_CACHE = {}
AI_LAST_CALL = {}
AI_COOLDOWN_MINUTES = 1  # 測試期間 1 分鐘

def get_ai_point(target_name, strategy_type, extra_data):
    """
    通用 AI 判斷函式 (支援三種策略分流)
    Args:
        target_name: 標的名稱 (如 "009816")
        strategy_type: 策略類型 ("stock_audit", "grid_trading", "us_market")
        extra_data: 該策略專屬的數據字典或文字
    """
    global AI_CACHE, AI_LAST_CALL
    now = datetime.now()
    
    # 建立 Cache Key (含策略類型，避免混淆)
    key = f"{target_name}_{strategy_type}_{datetime.now().strftime('%H%M')}"

    # 1. 檢查冷卻與 Cache
    if key in AI_CACHE:
        return AI_CACHE[key]

    # 2. 檢查 API Key
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "尚未設定 GEMINI_API_KEY"}

    # ==========================================
    # 🧠 核心修改：三種策略的 Prompt 分流
    # ==========================================
    prompt = ""
    
    if strategy_type == "stock_audit":
        # === 情境 1: 009816 存股巡檢 ===
        # extra_data 預期是: {'price': 10.5, 'projected_1y': 11.2, 'score': 85}
        d = extra_data
        prompt = f"""
你是一位長期價值投資經理人，請評估 "{target_name}" 的存股價值。
【關鍵數據】
- 目前股價: {d.get('price')}
- 2027年投影目標價: {d.get('projected_1y')} (基於年化報酬率)
- 系統綜合評分: {d.get('score')} / 100
- 距離發行價: {d.get('dist')}%

【指令】
1. 請判斷目前的股價相對於 2027 年目標是否具有安全邊際。
2. 若評分高於 80 分，傾向「強勢佈局」；若低於 60 分，傾向「觀望」。
3. 請用繁體中文，給出一個明確的「買進/持有/觀望」建議與理由 (50字內)。
"""

    elif strategy_type == "grid_trading":
        # === 情境 2: 萬元網格交易 ===
        # extra_data 預期是: {'price': 50, 'rsi': 30, 'trend': '超跌', 'grid_buy': 48}
        d = extra_data
        prompt = f"""
你是一位高頻網格交易員，請評估 "{target_name}" 的短線波動機會。
【關鍵數據】
- 現價: {d.get('price')}
- 短線趨勢: {d.get('trend')}
- RSI (14): {d.get('rsi')}
- 布林下緣 (補倉點): {d.get('grid_buy')}

【指令】
1. 這是網格交易策略，重點在於「震盪回調買入」與「超買止盈」。
2. 若 RSI < 35 且趨勢顯示「超跌」，應建議積極補倉。
3. 若 RSI > 70，建議暫停買入。
4. 請用繁體中文，針對是否執行網格補倉給出建議 (50字內)。
"""

    elif strategy_type == "us_market":
        # === 情境 3: 美股盤後總結 ===
        # extra_data 預期是純文字 Summary
        prompt = f"""
你是一位宏觀市場分析師，請解讀以下美股盤後數據並預測明日台股開盤氣氛。
【市場摘要】
{extra_data}

【指令】
1. 重點關注科技股 (TSM/SOX/Nasdaq) 的表現對台股的連動影響。
2. 判斷整體市場情緒是「樂觀」、「悲觀」還是「中性震盪」。
3. 請用繁體中文，給出對台股投資人的操作提醒 (50字內)。
"""

if strategy_type == "stock_audit":
        role = "長期價值投資經理人"
        # 這裡決定了底部顯示的「AI 狀態」內容
        status_template = "AI 狀態：複利計算中 🤖\n💡 提醒：複利效果穩定，已納入 2027 投影計畫。"
        # ... (prompt 組裝) ...
    elif strategy_type == "grid_trading":
        role = "網格交易專家"
        status_template = "AI 狀態：網格監控中 📉\n💡 提醒：嚴守動態間距，避免情緒化手動交易。"
    else:
        role = "宏觀分析師"
        status_template = "AI 狀態：全球聯動分析中 🌏\n💡 提醒：科技股波動劇烈，注意 TSM 溢價風險。"

    # 加上統一的 JSON 輸出要求
    prompt += """
⚠️ 嚴格輸出 JSON 格式，不要有 Markdown，不要有多餘文字：
{
  "decision": "決策結果 (如: 強力買進, 暫停補倉, 市場樂觀)",
  "confidence": 0-100,
  "reason": "簡短理由"
}
"""
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}], 
        "generationConfig": {"temperature": 0.3}
    }

    # 4. 呼叫 API + 強化重試機制 (維持不變)
    ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 連線逾時"}
    
    for attempt in range(3):
        try:
            api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-2.0-flash:generateContent?key={gemini_key}"
            res = requests.post(api_url, json=payload, timeout=30)

            if res.status_code == 429:
                wait_time = 25 + (attempt * 5)
                print(f"⚠️ AI 限流 (429)，等待 {wait_time} 秒...")
                time.sleep(wait_time)
                continue

            res.raise_for_status()
            data = res.json()

            # 解析與清洗
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            clean_text = text.replace("```json", "").replace("```", "").strip()
            ai_result = json.loads(clean_text)
            break 

        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            ai_result = {"decision": "ERROR", "confidence": 0, "reason": f"異常: {str(e)[:20]}"}

    # 更新 Cache
    AI_CACHE[key] = ai_result
    return ai_result
