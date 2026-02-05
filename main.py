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
    """獲取精準台灣時間，消除 DeprecationWarning"""
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour < 14

def master_monitor_loop():
    """主控迴圈：管理所有監控腳本"""
    print("🤖 中央監控系統啟動...")
    # 啟動時先緩衝 10 秒，確保網路完全連線
    time.sleep(10)
    
    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行例行巡檢 {now_tw.strftime('%H:%M')} ---")
                
                # 1. 每 3 分鐘跑一次核心 009816 監控
                print(run_009816_monitor())
                
                # 2. 如果是開盤 (09:15-09:20 區間) 或 收盤 (13:45-13:50 區間)
                # 稍微放寬分鐘區間，避免 time.sleep 剛好跳過觸發點
                if (now_tw.hour == 9 and 15 <= now_tw.minute <= 20) or \
                   (now_tw.hour == 13 and 45 <= now_tw.minute <= 50):
                    print("📊 執行萬元實驗室診斷...")
                    run_unified_experiment()
                
                time.sleep(180) # 休息 3 分鐘
            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，監控暫停中...")
                time.sleep(1800) 
        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人中央控制台</h1><p>運行中。目前台灣時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p>"

if __name__ == "__main__":
    # 啟動背景主控執行緒
    threading.Thread(target=master_monitor_loop, daemon=True).start()
    
    # 啟動 Flask 伺服器
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
