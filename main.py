import os
import sys
import time
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone

# 路徑強化
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
    from us_post_market_robot import run_us_post_market, schedule_job
except ImportError as e:
    print(f"❌ 導入失敗：{e}")

app = Flask(__name__)

def get_now_tw():
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5: return False
    # 稍微放寬到 14 點，確保收盤數據也能抓到
    return 9 <= now_tw.hour <= 14

# === 中央巡檢線程 ===
def master_monitor_loop():
    print("🤖 中央監控系統：巡檢線程啟動...")
    time.sleep(3) 
    
    # 💡 測試點：在 while 之前先強制跑一次，不管是不是開盤時間
    print("🧪 啟動初期強制測試巡檢...")
    try:
        run_009816_monitor()
        print("✅ 初始測試完成")
    except Exception as e:
        print(f"❌ 初始測試失敗: {e}")

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 🚀 開始執行全面巡檢 {now_tw.strftime('%H:%M:%S')} ---")

                # === 1️⃣ 存股009816 AI判斷 ===
                print("🦅 執行 009816 監控任務...")
                run_009816_monitor()
                
                # 💡 關鍵 2：縮短任務間隔，原本 60 秒太久了，改 10 秒
                print("⏳ 等待 10 秒切換下一個任務...")
                time.sleep(10) 

                # === 2️⃣ 一萬元網格實驗 ===
                print("📊 執行萬元網格 AI 實驗...")
                run_unified_experiment()
                
                print(f"✅ 本輪巡檢完成，進入休眠。")
                time.sleep(300) # 5 分鐘後再跑下一輪
            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，每 10 分鐘檢查一次...")
                time.sleep(600) 

        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人監控中</h1><p>台北時間：{now_tw.strftime('%H:%M:%S')}</p>"

if __name__ == "__main__":
    # 1. 啟動台股巡檢 (daemon=True 確保 Flask 關閉時它也會關閉)
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    print("✅ 台股即時巡檢線程已掛載")

    # 2. 啟動美股排程
    t_us = threading.Thread(target=schedule_job, daemon=True)
    t_us.start()
    print("✅ 美股 05:05 排程線程已掛載")
    
    # 3. 啟動 Flask (正式環境建議 debug=False)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
