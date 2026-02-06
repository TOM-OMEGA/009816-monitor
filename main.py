import os
import sys
import time
import threading
import requests
from flask import Flask
from datetime import datetime

# --- 1. 環境隔離：防止字體或繪圖庫卡死 ---
import matplotlib
matplotlib.use('Agg')
import logging
logging.getLogger('matplotlib.font_manager').disabled = True

# 路徑強化
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
    from us_post_market_robot import schedule_job
except ImportError as e:
    print(f"❌ 模組導入失敗：{e}")

app = Flask(__name__)

# --- 2. 時間判斷：直接依賴 TZ=Asia/Taipei ---
def is_market_open():
    # 因為你環境變數設定了 TZ，這裡直接拿到的就是台北時間
    now = datetime.now()
    if now.weekday() >= 5: return False  # 週末不跑
    return 9 <= now.hour <= 14

def master_monitor_loop():
    print("🤖 監控線程已進入 master_monitor_loop")
    
    # 💡 診斷：啟動時強迫發一則訊息，確認線程真的有在跑
    try:
        print("🧪 執行啟動即時測試...")
        # 這裡加一個參數讓它一定會發送 LINE
        run_009816_monitor(force_send=True)
        print("✅ 啟動測試已送出")
    except Exception as e:
        print(f"❌ 啟動測試失敗: {e}")

    while True:
        try:
            now = datetime.now()
            if is_market_open():
                print(f"🚀 [{now.strftime('%H:%M:%S')}] 市場開放中，執行巡檢...")
                run_009816_monitor()
                time.sleep(15)
                run_unified_experiment()
                print("✅ 巡檢完畢，休眠 5 分鐘")
                time.sleep(300)
            else:
                # 即使沒開盤也印一行，證明線程還活著
                if now.minute % 10 == 0:
                    print(f"💤 [{now.strftime('%H:%M:%S')}] 非交易時段，監理中...")
                time.sleep(600)
        except Exception as e:
            print(f"⚠️ 循環發生異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    return f"Status: Active - Server Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

if __name__ == "__main__":
    # 啟動線程
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    
    # 美股排程
    t_us = threading.Thread(target=schedule_job, daemon=True)
    t_us.start()
    
    print("✅ 所有線程啟動指令已發出")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
