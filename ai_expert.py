import os
import requests

def get_ai_point(summary):
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_key: return "❌ Secret 錯誤"

    # 使用你清單中最頂級的 Gemini 3 Pro 預覽版
    # 注意：API URL 中的模型名稱通常不需要 "models/" 前綴，但要確保字串完全正確
    model_name = "gemini-3-pro-preview" 
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
    
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
        "contents": [{"parts": [{"text": task_description}]}],
        "generationConfig": {
            "temperature": 0.7, # 稍微增加一點創造力，讓點評更具前瞻性
            "topP": 0.95
        }
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        result = res.json()
        
        if 'candidates' in result:
            # 成功獲取 Gemini 3 Pro 的深度點評
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            # 備援 1：使用你清單中的穩定版 Gemini 2.5 Flash
            alt_model = "gemini-2.5-flash"
            alt_url = f"https://generativelanguage.googleapis.com/v1beta/models/{alt_model}:generateContent?key={gemini_key}"
            res_alt = requests.post(alt_url, json=payload, timeout=20)
            res_json = res_alt.json()
            
            if 'candidates' in res_json:
                return res_json['candidates'][0]['content']['parts'][0]['text']
            else:
                # 最終保險，輸出 API 原始錯誤，方便我們除錯
                error_msg = result.get('error', {}).get('message', '未知錯誤')
                return f"💡 系統校對中：{error_msg[:30]}"
                
    except Exception as e:
        return f"❌ 連線異常: {str(e)[:20]}"
