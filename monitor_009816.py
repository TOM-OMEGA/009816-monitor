import requests
import os
from datetime import datetime

def run_009816_monitor(force_send=True):
    # 從環境變數讀取 Discord Webhook URL
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if not webhook_url:
        return "❌ 缺失 DISCORD_WEBHOOK_URL，請檢查 Render 環境變數設定"

    # Discord 的訊息格式
    payload = {
        "username": "AI 監控助理",
        "content": f"🦅 **系統巡檢回報**\n時間: `{now_str}`\n狀態: 🟢 Discord Webhook 通道運作正常"
    }

    try:
        # Discord 成功發送會回傳 HTTP 204
        res = requests.post(webhook_url, json=payload, timeout=10)
        if res.status_code == 204:
            return "✅ Discord 發送成功！"
        else:
            return f"❌ Discord 拒絕 (代碼 {res.status_code}): {res.text}"
    except Exception as e:
        return f"❌ 網路異常: {str(e)}"
