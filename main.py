import os
import time
import threading
from flask import Flask
from datetime import datetime, timedelta

# 匯入你的兩個監控模組
from monitor_009816 import run_009816_monitor
from new_ten_thousand_grid import run_unified_experiment

app = Flask(__name__)

def is_market_open():
    now_tw = datetime.utcnow() + timedelta(hours=8)
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour < 14

def master_monitor_loop():
    """主控迴圈：管理所有監控腳本"""
    print("🤖 中央監控系統啟動...")
    while True:
        try:
            if is_market_open():
                # 1. 每 3 分鐘跑一次核心 009816 監控
                print(f"--- 執行例行巡檢 {datetime.now().strftime('%H:%M')} ---")
                print(run_009816_monitor())
                
                # 2. 如果是開盤 (09:15) 或 收盤 (13:45)，跑萬元實驗網格
                now_tw = datetime.utcnow() + timedelta(hours=8)
                if (now_tw.hour == 9 and 15 <= now_tw.minute <= 18) or \
                   (now_tw.hour == 13 and 45 <= now_tw.minute <= 48):
                    print("📊 執行萬元實驗室診斷...")
                    run_unified_experiment()
                
                time.sleep(180) # 休息 3 分鐘
            else:
                print("💤 非交易時段，監控暫停中...")
                time.sleep(1800) # 非交易時段每半小時檢查一次
        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    return "<h1>🦅 經理人中央控制台</h1><p>009816 與 萬元實驗室 運行中。</p>"

if __name__ == "__main__":
    # 啟動背景主控執行緒
    threading.Thread(target=master_monitor_loop, daemon=True).start()
    
    # 啟動 Flask 伺服器
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
