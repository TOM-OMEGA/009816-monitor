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
        "content": f"🦅 **系統巡檢回報**\n時間: `{now_str}`\n狀態: 🟢 監控運作中"
    }

    # 嘗試發送，最多重試 2 次
    for attempt in range(3):
        try:
            res = requests.post(webhook_url, json=payload, timeout=10)
            
            # 204 是 Discord 的正常回傳代碼 (No Content)
            if res.status_code == 204:
                return "✅ Discord 發送成功！"
            
            # 處理 429 頻率限制
            if res.status_code == 429:
                # 只有當回傳內容不為空時才嘗試解析 JSON
                wait_time = 5 # 預設等待 5 秒
                if res.text:
                    try:
                        wait_time = res.json().get('retry_after', 5000) / 1000
                    except:
                        pass
                
                print(f"⚠️ 觸發頻率限制，等待 {wait_time} 秒後重試...", flush=True)
                time.sleep(wait_time + 0.1)
                continue
            
            return f"❌ Discord 拒絕 (代碼 {res.status_code}): {res.text}"
            
        except requests.exceptions.RequestException as e:
            # 處理網路超時或連線失敗
            if attempt < 2:
                time.sleep(2)
                continue
            return f"❌ 網路連線異常: {str(e)}"
            
    return "❌ 經過多次嘗試後仍失敗 (可能是頻率過高或網路問題)"
