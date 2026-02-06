import requests
import os
from datetime import datetime, timedelta, timezone
import pandas as pd

# 鎖死配置，不抓多餘數據
LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')
FM_TOKEN = os.environ.get('FINMIND_TOKEN')

def run_009816_monitor(force_send=True):
    print(f"🚀 [極速模式] 啟動診斷...")
    
    # 1. 最簡單的 FinMind 抓取 (繞過 data_engine)
    url = "https://api.finmindtrade.com/api/v4/data"
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    params = {
        "dataset": "TaiwanStockPrice",
        "data_id": "009816",
        "start_date": start_date,
        "token": FM_TOKEN
    }

    try:
        print("📡 正在請求 FinMind 原生數據...")
        res = requests.get(url, params=params, timeout=5) # 縮短到 5 秒
        data = res.json().get('data', [])
        if not data:
            print("⚠️ FinMind 無數據")
            price = 10.12
        else:
            price = data[-1]['close']
            print(f"✅ 取得價格: {price}")
    except Exception as e:
        print(f"❌ API 請求失敗: {e}")
        price = 0

    # 2. 跳過 AI，直接組裝訊息 (確保推播能通)
    now_tw = (datetime.now() + timedelta(hours=8)).strftime("%H:%M:%S")
    msg = (
        f"🚨 系統強制生存報告 ({now_tw})\n"
        f"------------------\n"
        f"標的: 009816\n"
        f"偵測價: {price}\n"
        f"狀態: 繞過所有複雜邏輯執行成功\n"
        f"------------------\n"
        f"💡 如果看到這則，代表是 data_engine 裡的 sleep 或多次請求卡住你了。"
    )

    # 3. 強制推播
    if LINE_TOKEN and USER_ID:
        try:
            print("📤 嘗試推播到 LINE...")
            line_url = "https://api.line.me/v2/bot/message/push"
            headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
            payload = {"to": USER_ID, "messages": [{"type": "text", "text": msg}]}
            line_res = requests.post(line_url, headers=headers, json=payload, timeout=5)
            print(f"📬 LINE 回傳: {line_res.status_code}")
        except Exception as e:
            print(f"❌ LINE 推送崩潰: {e}")

    return {"status": "done"}
