import requests
import os
import time
from datetime import datetime


def run_009816_monitor(force_send=True):
    """
    系統巡檢 / 台股監控占位用
    目前用途：確認 Render / 排程 / Webhook 是否正常
    """
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not webhook_url:
        return "❌ 缺失 DISCORD_WEBHOOK_URL"

    payload = {
        "username": "AI 監控助理",
        "content": (
            f"🦅 **系統巡檢回報**\n"
            f"時間: `{now_str}`\n"
            f"狀態: 🟢 監控運作中"
        )
    }

    # 最多嘗試 3 次（含第一次）
    for attempt in range(3):
        try:
            res = requests.post(webhook_url, json=payload, timeout=10)

            # Discord 成功回傳
            if res.status_code == 204:
                return "✅ Discord 發送成功"

            # Discord 429 頻率限制
            if res.status_code == 429:
                wait_time = 5
                try:
                    if res.text:
                        wait_time = res.json().get("retry_after", 5000) / 1000
                except Exception:
                    pass

                print(
                    f"⚠️ Discord 限流，等待 {wait_time:.1f} 秒後重試 ({attempt+1}/3)",
                    flush=True
                )
                time.sleep(wait_time + 0.2)
                continue

            return f"❌ Discord 拒絕 ({res.status_code}): {res.text}"

        except requests.exceptions.RequestException as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return f"❌ 網路連線異常: {str(e)}"

    return "❌ 多次嘗試後仍失敗（可能頻率過高或網路問題）"


# === ✅ 標準入口（給 main.py 用）===
def run_taiwan_stock():
    """
    統一給 main.py import 的入口
    之後可在這裡串：
    - 台股盤中 AI
    - 台股收盤圖表
    """
    return run_009816_monitor()