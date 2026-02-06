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
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour <= 13

def master_monitor_loop():
    print("🤖 中央監控系統：全量巡檢線程啟動...")
    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行全面巡檢 {now_tw.strftime('%H:%M')} ---")
                
                # 1️⃣ 執行台股 009816 監控 (含圖表與 AI)
                run_009816_monitor()
                
                # 💡 防止 API 碰撞：錯開 60 秒再執行下一個 AI 任務
                time.sleep(60) 

                # 2️⃣ 執行一萬元網格實驗
                run_unified_experiment()
                
                # 每輪巡檢完睡 5 分鐘
                time.sleep(240) 
            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，巡檢暫停中...")
                time.sleep(300) # 5 分鐘檢查一次
        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人全面監控中</h1><p>台北時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p>"

if __name__ == "__main__":
    # 啟動台股監控線程
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    print("✅ 台股即時巡檢線程已掛載")

    # 啟動美股 05:05 排程線程
    t_us = threading.Thread(target=schedule_job, daemon=True)
    t_us.start()
    print("✅ 美股 05:05 排程線程已掛載")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
