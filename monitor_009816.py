import requests
import os
from datetime import datetime

# ⚠️ 完全移除 pandas, yfinance, data_engine 的依賴，只留 requests
LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def run_009816_monitor(force_send=True):
    # 這是目前最安全的 Log 方式
    print("🔔 [絕對生存版] 函式開始執行...")
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 這是為了確認你的環境變數有沒有抓到
    token_status = "OK" if LINE_TOKEN else "MISSING"
    user_status = "OK" if USER_ID else "MISSING"

    msg = (
        f"✅ 伺服器終極診斷成功\n"
        f"------------------\n"
        f"時間: {now_str}\n"
        f"Token: {token_status}\n"
        f"User ID: {user_status}\n"
        f"狀態: 排除所有 API 阻塞\n"
        f"------------------\n"
        f"💡 如果看到這則，代表是數據源(FinMind/Yahoo)卡死你。"
    )

    if force_send and LINE_TOKEN and USER_ID:
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
            # 這裡縮短 timeout 到 5 秒
            res = requests.post(url, headers=headers, json=payload, timeout=5)
            print(f"📬 LINE 回傳碼: {res.status_code}")
        except Exception as e:
            print(f"❌ LINE 發送失敗: {str(e)}")
    
    return {"status": "debug_done"}
