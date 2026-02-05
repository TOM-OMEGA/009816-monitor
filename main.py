import os
import sys
import time
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone

# 💡 核心必要修改 1：強制將當前腳本目錄加入系統路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    # 匯入監控模組
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
except ImportError as e:
    print(f"❌ 導入失敗！請檢查檔案是否存在：{e}")

app = Flask(__name__)

def get_now_tw():
    """獲取精準台灣時間，確保 2026/2027 跨年邏輯正確"""
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour <= 13

def master_monitor_loop():
    """主控迴圈：管理所有監控腳本"""
    print("🤖 中央監控系統啟動...")
    
    time.sleep(5)
    
    try:
        if is_market_open():
            print("🚀 檢測到開盤中，啟動即時首巡...")
            run_009816_monitor()
    except Exception as e:
        print(f"⚠️ 啟動首巡失敗: {e}")

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行例行巡檢 {now_tw.strftime('%H:%M')} ---")
                
                # 1. 核心 009816 監控
                run_009816_monitor()
                
                # 💡 核心必要修改 2：強制間隔 60 秒。
                # 這是解決 Quota 報錯的關鍵，確保 009816 與萬元實驗的 AI 請求不會撞在一起。
                time.sleep(60) 
                
                # 2. 萬元實驗網格
                if (now_tw.hour == 9 and 15 <= now_tw.minute <= 25) or \
                   (now_tw.hour == 13 and 20 <= now_tw.minute <= 35):
                    print("📊 執行萬元實驗室診斷...")
                    run_unified_experiment()
                
                # 💡 核心必要修改 3：總循環間隔調整，扣除上方已 sleep 的 60 秒，維持約 5 分鐘節奏
                time.sleep(240) 
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
    t = threading.Thread(target=master_monitor_loop)
    t.daemon = True
    t.start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
