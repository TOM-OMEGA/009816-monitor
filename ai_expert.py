import os
import requests

def get_ai_point(summary):
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_key: return "❌ Secret 錯誤"

    # 鎖定 Gemini 3 穩定路徑
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash-preview:generateContent?key={gemini_key}"
    
    # 保持你成功的單一字串結構，但注入核心數據規則
    task_description = (
        f"你是專業基金經理人。數據：{summary}。目前 009816 持股台積電達 40%，"
        f"請針對 RSI 超過 70 的過熱風險、美股費半大跌 2% 的補跌壓力，"
        f"以及 10.12 目標價的執行紀律，為一年後的結婚基金需求給予 120 字內冷靜且具前瞻性的觀察建議，"
        f"參考 RSI 數值：超過 70 為極端過熱，低於 30 為超跌，"
        f"必須考慮美股 (費半/TSM) 與台股 ETF 之間的連動延遲與溢價風險，"
        f"重視 RSI < 35 或 5日乖離率 < -1.5% 的超跌機會，"
        f"語氣專業沈穩，數據導向，比對大盤財報前與預測一年後的長線情況，"
        f". 數據要準確，要提供當下最準確的數據，避免不實推測。"
    )

    payload = {
        "contents": [{"parts": [{"text": task_description}]}]
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        result = res.json()
        
        if 'candidates' in result:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            # 備援：2.5 穩定版
            alt_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
            res_alt = requests.post(alt_url, json=payload, timeout=20)
            res_json = res_alt.json()
            return res_json['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in res_json else "💡 現象：溢價偏高且數據連動風險大，嚴守 10.12 紀律。"
    except Exception as e:
        return f"❌ 連線異常: {str(e)[:20]}"
