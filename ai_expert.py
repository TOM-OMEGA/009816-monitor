import os
import requests
import json

def get_ai_point(summary, target_name, extra_data=None):
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_key:
        return {"decision": "ERROR", "confidence": 0, "reason": "Missing API Key"}

    model_name = "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"

    d = extra_data or {}
    ext_data = {
        "valuation": d.get("valuation"),
        "order_strength": d.get("order_strength"),
        "market_context": d.get("market_context"),
        "idx_5s": d.get("idx_5s"),
        "k_line": d.get("k_line"),
        "tick": d.get("tick_last"),
        "chip": {
            "inst": d.get("inst"),
            "holders": d.get("holders"),
            "day_trade": d.get("day_trade")
        },
        "fundamental": d.get("rev")
    }

    prompt = f"""
你是台股基金經理人，你的判斷會被程式直接用來決定是否買入。

【標的】:{target_name}
【技術摘要】:{summary}
【市場數據】:{json.dumps(ext_data, ensure_ascii=False)}

請你「綜合判斷現在是否適合買入」，而不是只看價格。

⚠️ 嚴格輸出 JSON，禁止多餘文字：

{{
  "decision": "可行 | 不可行 | 觀望",
  "confidence": 0-100,
  "reason": "50字內理由"
}}

規則：
- confidence < 60 視為觀望
- 若大盤或產業風險高，請偏向不可行
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4}
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        data = res.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        return {"decision": "ERROR", "confidence": 0, "reason": str(e)[:30]}
