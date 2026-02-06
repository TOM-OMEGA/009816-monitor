import requests
import os
import time
from datetime import datetime

def run_009816_monitor(force_send=True):
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not webhook_url:
        return "❌ 缺失 DISCORD_WEBHOOK_URL"

    payload = {
        "username": "AI 監控助理",
        "content": f"🦅 **系統巡檢回報**\n時間: `{now_str}`\n狀態: 🟢 監控中"
    }

    # 💡 增加重試邏輯處理 429
    for i in range(3): # 最多嘗試 3 次
        res = requests.post(webhook_url, json=payload, timeout=10)
        
        if res.status_code == 204:
            return "✅ Discord 發送成功！"
        
        elif res.status_code == 429:
            # 取得 Discord 建議的等待時間（秒）
            retry_after = res.json().get('retry_after', 5) / 1000
            print(f"⚠️ 觸發頻率限制，等待 {retry_after} 秒...", flush=True)
            time.sleep(retry_after + 0.5)
            continue
            
        else:
            return f"❌ Discord 拒絕 (代碼 {res.status_code}): {res.text}"
            
    return "❌ 經過多次嘗試後仍失敗 (429 Rate Limit)"
