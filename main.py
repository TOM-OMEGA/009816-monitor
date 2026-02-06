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
    from us_post_market_robot import schedule_job
except ImportError as e:
    print(f"❌ 導入失敗：{e}")

app = Flask(__name__)

def get_now_tw():
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    # 週末不跑
    if now_tw.weekday() >= 5: return False
    # 台股交易時間 09:00 - 13:35 (多給一點 buffer)
    return 9 <= now_tw.hour < 14

# === 中央巡檢線程 ===
def master_monitor_loop():
    """中央監控線程：確保啟動後能快速執行第一次，之後再進循環"""
    print("🤖 中央監控系統啟動：全量巡檢模式...")
    
    # 💡 關鍵 1：啟動後先睡 5 秒就好，不要睡 20 秒，讓推播快點出來
    time.sleep(5) 

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行全面巡檢 {now_tw.strftime('%H:%M')} ---")
                
                # 💡 關鍵 2：給 009816 獨立的 try-except，避免它掛了影響後面的網格
                try:
                    print("🦅 執行 009816 監控...")
                    run_009816_monitor()
                except Exception as e:
                    print(f"❌ 009816 監控失敗: {e}")

                # 💡 關鍵 3：API 緩衝時間縮短
                time.sleep(15) 

                try:
                    print("📊 執行萬元網格實驗...")
                    run_unified_experiment()
                except Exception as e:
                    print(f"❌ 網格實驗失敗: {e}")
                
                # 每輪巡檢完睡 5 分鐘 (300秒)，扣除上方已經睡掉的時間
                print(f"✅ 本輪巡檢結束，下次巡檢約為 {(get_now_tw() + timedelta(seconds=285)).strftime('%H:%M')}")
                time.sleep(285) 
            else:
                # 💡 關鍵 4：非交易時段顯示倒數，並稍微縮短檢查間隔
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，巡檢暫停中...")
                time.sleep(600) # 10 分鐘檢查一次
        except Exception as e:
            print(f"⚠️ 中央監控總循環異常: {e}")
            time.sleep(30)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人全面監控中</h1><p>台北時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p>"

if __name__ == "__main__":
    # 1. 啟動美股排程 (它內部通常會有自己的 while loop 或 schedule)
    t_us = threading.Thread(target=schedule_job, daemon=True)
    t_us.start()
    print("✅ 美股 05:05 排程線程已掛載")

    # 2. 啟動台股巡檢 (確保它在 Flask 啟動前就已經在背景跑)
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    print("✅ 台股即時巡檢線程已掛載")
    
    # 3. 啟動 Flask
    port = int(os.environ.get("PORT", 10000))
    # 關閉 debug 模式避免 Thread 被執行兩次
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
