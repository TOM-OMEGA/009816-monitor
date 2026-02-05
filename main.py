import os
import time
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone

# 匯入你的兩個監控模組
from monitor_009816 import run_009816_monitor
from new_ten_thousand_grid import run_unified_experiment

app = Flask(__name__)

def get_now_tw():
    """獲取精準台灣時間，確保 2026/2027 跨年邏輯正確"""
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour < 14

def master_monitor_loop():
    """主控迴圈：管理所有監控腳本"""
    print("🤖 中央監控系統啟動...")
    
    # 💡 關鍵修改：部署後「立即執行一次」，不要等 sleep
    try:
        if is_market_open():
            print("🚀 檢測到開盤中，啟動即時首巡...")
            run_009816_monitor()
            # 強制補發萬元實驗戰報
            run_unified_experiment()
    except Exception as e:
        print(f"⚠️ 啟動首巡失敗: {e}")

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行例行巡檢 {now_tw.strftime('%H:%M')} ---")
                
                # 1. 核心 009816 監控
                run_009816_monitor()
                
                # 2. 萬元實驗網格 (放寬時間判定，確保 3 分鐘一輪不會漏掉)
                if (now_tw.hour == 9 and 15 <= now_tw.minute <= 25) or \
                   (now_tw.hour == 13 and 45 <= now_tw.minute <= 55):
                    print("📊 執行萬元實驗室診斷...")
                    run_unified_experiment()
                
                time.sleep(180) 
            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，監控暫停中...")
                time.sleep(1800) 
        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人中央控制台</h1><p>系統即時時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p>"

if __name__ == "__main__":
    # 啟動背景執行緒
    t = threading.Thread(target=master_monitor_loop)
    t.daemon = True
    t.start()
    
    # 啟動 Flask
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
