import os
import sys
import time
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone

# 💡 核心必要修改 1：路徑強化
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
except ImportError as e:
    print(f"❌ 導入失敗！請檢查檔案是否存在：{e}")

app = Flask(__name__)

def get_now_tw():
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour <= 13

def master_monitor_loop():
    print("🤖 中央監控系統啟動...")
    # 💡 核心必要修改：啟動後先冷卻 20 秒，避開重啟後的併發高峰
    time.sleep(20)
    
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
                run_009816_monitor()
                
                # 強制間隔 60 秒解決 Quota 報錯
                time.sleep(60) 
                
                if (now_tw.hour == 9 and 15 <= now_tw.minute <= 25) or \
                   (now_tw.hour == 13 and 20 <= now_tw.minute <= 35):
                    print("📊 執行萬元實驗室診斷...")
                    run_unified_experiment()
                
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

# 💡 核心必要修改：這段 if __name__ 是防止「一次跳三個」的關鍵
if __name__ == "__main__":
    # 1. 確保在 Render/Local 都不會因為 Flask Debug 模式啟動兩次
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        t = threading.Thread(target=master_monitor_loop)
        t.daemon = True
        t.start()
    
    port = int(os.environ.get("PORT", 10000))
    # 2. 務必關閉 use_reloader
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
