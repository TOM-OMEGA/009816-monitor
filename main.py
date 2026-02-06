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
    # 修正交易時間邏輯
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour <= 14

def master_monitor_loop():
    print("🤖 中央監控系統：巡檢線程進入準備狀態...")
    # 給環境一點緩衝時間
    time.sleep(10) 
    
    # 💡 修正：首輪測試改為「非同步嘗試」，失敗也不會停掉整個 while 迴圈
    print("🧪 啟動執行首輪初始測試...")
    try:
        run_009816_monitor()
        print("✅ 初始測試流程觸發成功")
    except Exception as e:
        print(f"⚠️ 初始測試跳過 (數據源可能暫時無回應): {e}")

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
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，每 10 分鐘檢查一次...")
                time.sleep(600) 
        except Exception as e:
            print(f"⚠️ 中央監控循環異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人監控中</h1><p>台北時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p>"

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
