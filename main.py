import os
import sys
import time
import threading
import requests
from flask import Flask
from datetime import datetime

# --- 1. 環境隔離 ---
import matplotlib
matplotlib.use('Agg')
import logging
logging.getLogger('matplotlib.font_manager').disabled = True

# 路徑強化
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# --- 2. 安全導入模組 ---
# 定義全域變數，避免 NameError
run_009816_monitor = None
run_unified_experiment = None
schedule_job = None

try:
    from monitor_009816 import run_009816_monitor
except ImportError as e:
    print(f"❌ 009816 模組導入失敗: {e}", flush=True)

try:
    from new_ten_thousand_grid import run_unified_experiment
except ImportError as e:
    print(f"❌ 網格模組導入失敗: {e}", flush=True)

try:
    from us_post_market_robot import schedule_job
except ImportError as e:
    print(f"❌ 美股模組導入失敗: {e}", flush=True)

app = Flask(__name__)

# --- 3. 交易時間判斷 ---
def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5: return False  
    return 9 <= now.hour <= 14

# --- 4. 核心監控循環 ---
def master_monitor_loop():
    print("🤖 監控線程已進入 master_monitor_loop", flush=True)
    time.sleep(5) # 讓 Flask 先啟動

    # 💡 啟動即時診斷測試
    print("🧪 執行啟動診斷測試...", flush=True)
    if run_009816_monitor:
        try:
            # 強制發送測試訊息
            run_009816_monitor(force_send=True)
            print("✅ 啟動診斷任務已觸發", flush=True)
        except Exception as e:
            print(f"❌ 診斷執行期間崩潰: {e}", flush=True)
    else:
        print("⚠️ 無法執行診斷：run_009816_monitor 未正確載入", flush=True)

    last_heartbeat_hour = -1

    while True:
        try:
            now = datetime.now()
            
            if is_market_open():
                print(f"🚀 [{now.strftime('%H:%M:%S')}] 盤中巡檢...", flush=True)
                if run_009816_monitor: run_009816_monitor()
                time.sleep(15)
                if run_unified_experiment: run_unified_experiment()
                print("✅ 巡檢完畢，休眠 5 分鐘", flush=True)
                time.sleep(300)
            else:
                if now.hour != last_heartbeat_hour:
                    print(f"💤 [非交易時段] 系統待機中 ({now.strftime('%H:%M')})", flush=True)
                    last_heartbeat_hour = now.hour
                time.sleep(600) 

        except Exception as e:
            print(f"⚠️ 監控循環異常: {e}", flush=True)
            time.sleep(60)

@app.route('/')
def home():
    now = datetime.now()
    return f"""
    <h1>🦅 AI Manager Active</h1>
    <p>Server Time: {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Market Open: {is_market_open()}</p>
    <hr>
    <h3>模組狀態：</h3>
    <ul>
        <li>009816 監控: {'✅' if run_009816_monitor else '❌'}</li>
        <li>網格策略: {'✅' if run_unified_experiment else '❌'}</li>
        <li>美股機器人: {'✅' if schedule_job else '❌'}</li>
    </ul>
    <hr>
    <p>👉 <a href="/trigger">點擊這裡強制測試 LINE 推播</a></p>
    """

# 💡 新增：手動板機，直接在瀏覽器觸發測試
@app.route('/trigger')
def manual_trigger():
    if not run_009816_monitor:
        return "❌ 錯誤：monitor_009816 模組未載入"
    
    try:
        # 執行並回傳結果到網頁
        print("🔥 收到手動觸發請求...", flush=True)
        result = run_009816_monitor(force_send=True)
        return f"✅ 執行成功！回傳結果: {result}"
    except Exception as e:
        return f"❌ 執行失敗: {str(e)}"

if __name__ == "__main__":
    # 1. 掛載美股排程
    if schedule_job:
        t_us = threading.Thread(target=schedule_job, daemon=True)
        t_us.start()
    
    # 2. 掛載台股巡檢
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    
    print("✅ 線程指令已發出", flush=True)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
