import os
import sys
import time
import threading
import requests
from flask import Flask
from datetime import datetime, timedelta, timezone

# 路徑強化
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
    from us_post_market_robot import schedule_job
except ImportError as e:
    print(f"❌ 導入失敗：{e}")

app = Flask(__name__)

# LINE 設定檢查
LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def get_now_tw():
    # 雖然有設定 TZ，但使用此函式可確保萬無一失
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    # 週末不執行
    if now_tw.weekday() >= 5: return False
    # 台股交易時間
    return 9 <= now_tw.hour <= 14

def send_test_ping():
    """強制發送一則 LINE 訊息，確認 Token 與環境變數是否正確"""
    if not LINE_TOKEN or not USER_ID:
        print("❌ 無法發送測試：LINE_ACCESS_TOKEN 或 USER_ID 未設定")
        return
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": f"🔔 系統連線診斷：監控中心已上線\n⏰ 台北時間：{get_now_tw().strftime('%Y-%m-%d %H:%M:%S')}\n🚀 模式：正式部署環境"}]
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            print("✅ LINE 連線測試發送成功！")
        else:
            print(f"❌ LINE 發送失敗，狀態碼：{res.status_code}, 內容：{res.text}")
    except Exception as e:
        print(f"⚠️ 發送 LINE 時發生異常: {e}")

# === 中央巡檢線程 ===
def master_monitor_loop():
    print("🤖 中央監控系統：巡檢線程進入準備狀態...")
    time.sleep(5) 
    
    # 💡 關鍵修改：啟動後不管時間立刻發送測試訊息
    send_test_ping()

    print("🧪 啟動執行首輪初始測試 (run_009816_monitor)...")
    try:
        # 如果 monitor 內部沒有訊號就不發 LINE，這裡會造成「沒反應」的錯覺
        run_009816_monitor()
        print("✅ 初始測試流程執行完畢")
    except Exception as e:
        print(f"⚠️ 初始測試跳過或異常: {e}")

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 🚀 開始執行全面巡檢 {now_tw.strftime('%H:%M:%S')} ---")
                run_009816_monitor()
                time.sleep(15) 
                run_unified_experiment()
                print(f"✅ 本輪巡檢完成，休眠 5 分鐘。")
                time.sleep(300) 
            else:
                # 非交易時段的 Log 提示
                if now_tw.minute % 10 == 0: # 減少重複 Log
                    print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，每 10 分鐘檢查一次...")
                time.sleep(600) 
        except Exception as e:
            print(f"⚠️ 中央監控循環異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人監控中</h1><p>台北時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p><p>狀態：線程運行中</p>"

if __name__ == "__main__":
    # 1. 啟動巡檢
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    print("✅ 台股即時巡檢線程已掛載")

    # 2. 啟動美股排程
    t_us = threading.Thread(target=schedule_job, daemon=True)
    t_us.start()
    print("✅ 美股 05:05 排程線程已掛載")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
