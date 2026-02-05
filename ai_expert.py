import os
import requests
import json

def get_ai_point(summary, target_name, extra_data=None):
    gemini_key = os.environ.get('GEMINI_API_KEY')
    if not gemini_key: return "❌ Secret 錯誤"

    # ✅ 使用您帳號清單中明確支援的 2.0 版本
    model_name = "gemini-2.0-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
    
    d = extra_data if extra_data else {}
    ext_msg = (
        f"1.價量K線: {d.get('k_line', 'N/A')}\n"
        f"2.即時Tick: {d.get('tick_last', 'N/A')}\n"
        f"3.價值位階: {d.get('valuation', 'N/A')}\n"
        f"4.盤中5s力道: {d.get('order_strength', 'N/A')}\n"
        f"5.市場/報酬指數: {d.get('market_context', 'N/A')}\n"
        f"6.大盤5s脈動: {d.get('idx_5s', 'N/A')}\n"
        f"7.籌碼穩定: {d.get('day_trade', 'N/A')}, 法人:{d.get('inst', 'N/A')}, 大戶:{d.get('holders', 'N/A')}\n"
        f"8.基本面: {d.get('rev', 'N/A')}"
    )
    
    if "009816" in target_name:
        persona_logic = (
            "身分：基金經理人 (守護 2027 結婚基金)。\n"
            "監控：台積電(TSM)溢價、費半(SOX)補跌壓力、10.12 目標價執行。\n"
            "準則：長線期望值為重，嚴禁頻繁交易，重點在於風險回測與溢價收斂。"
        )
    else:
        focus = "【重點監控：TSM/SOX 科技連動】" if any(x in target_name for x in ["2317", "00929"]) else "【重點監控：台股加權指數 & 金融防禦性】"
        persona_logic = (
            f"身分：作者劉承彥。標的：{target_name}。{focus}\n"
            "請嚴守十條實戰鐵律：1.期望值 2.非加碼 3.趨勢濾網 4.動態間距 5.資金控制 6.除息還原 7.低成本 8.情緒收割 9.連動風險 10.自動化。"
        )

    task_description = (
        f"【角色身分】: {persona_logic}\n"
        f"【技術指標摘要】: {summary}\n"
        f"【全維度 11 項實戰數據】:\n{ext_msg}\n"
        f"【任務】: 結合上述鐵律與全維度數據，針對 {target_name} 給予 150 字內診斷。\n"
        f"【要求】: 必須明確給出『執行建議：可行/不可行/觀望』。2027 年視告，數據導向。"
    )

    payload = {
        "contents": [{"parts": [{"text": task_description}]}], # ✅ 確保傳入完整指令
        "generationConfig": {"temperature": 0.7, "topP": 0.95}
    }

    try:
        res = requests.post(url, json=payload, timeout=30)
        result = res.json()
        if 'error' in result:
            return f"❌ AI 報報錯: {result['error'].get('message', '未知錯誤')[:20]}"
        if 'candidates' in result:
            return result['candidates'][0]['content']['parts'][0]['text']
        return "💡 系統校對中，請維持紀律。"
    except Exception as e:
        return f"❌ AI 顧問連線中：({str(e)[:15]})"
