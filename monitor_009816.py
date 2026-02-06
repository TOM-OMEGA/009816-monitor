import requests
import os
from datetime import datetime

def run_009816_monitor(force_send=True):
    LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
    USER_ID = os.environ.get('USER_ID')
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"🔔 系統連線測試\n時間: {now_str}\n狀態: 正在診斷 LINE 推播通路"

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
