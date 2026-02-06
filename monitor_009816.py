import requests
import os
from datetime import datetime

def run_009816_monitor(force_send=True):
    WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not WEBHOOK_URL:
        return "❌ 缺失 DISCORD_WEBHOOK_URL，請檢查 Render 設定"

    # Discord 的訊息格式
    payload = {
        "username": "AI 監控助理",
        "content": f"🦅 **系統巡檢回報**\n時間: `{now_str}`\n狀態: 🟢 Discord 通道運作正常"
    }

    try:
        # Discord 成功發送會回傳 HTTP 204
        res = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        if res.status_code == 204:
            return "✅ Discord 發送成功！"
        else:
            return f"❌ Discord 拒絕 (代碼 {res.status_code}): {res.text}"
    except Exception as e:
        return f"❌ 網路異常: {str(e)}"
"

    if not LINE_TOKEN or not USER_ID:
        return f"❌ 失敗：環境變數缺失。TOKEN: {'OK' if LINE_TOKEN else 'MISSING'}, UID: {'OK' if USER_ID else 'MISSING'}"

    try:
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {LINE_TOKEN}", 
            "Content-Type": "application/json"
        }
        payload = {
            "to": USER_ID, 
            "messages": [{"type": "text", "text": msg}]
        }
        
        # 執行請求
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        # 組合回傳報表
        status_info = {
            "http_status": response.status_code,
            "line_reason": response.text,
            "timestamp": now_str
        }
        
        print(f"📬 LINE API 回傳結果: {status_info}", flush=True)
        
        if response.status_code == 200:
            return f"✅ 發送成功！LINE 伺服器已收件。<br>回應內容: {response.text}"
        else:
            return f"❌ LINE 拒絕發送 (代碼 {response.status_code})。<br>原因: {response.text}<br>💡 小提示: 401 代表 Token 錯了，400 代表 User ID 格式錯了。"

    except Exception as e:
        return f"❌ 網路傳輸異常: {str(e)}"
