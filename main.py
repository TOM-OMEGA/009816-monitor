import os
import sys
import time
import threading
import requests
from flask import Flask
from datetime import datetime

# --- 1. 環境隔離：防止繪圖庫在 Linux 無介面環境卡死 ---
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

# --- 2. 交易時間判斷 (假設 TZ=Asia/Taipei 已設定) ---
def is_market_open():
    now = datetime.now()
    # 0=週一, 4=週五。週末 (5,6) 直接回傳 False
    if now.weekday() >= 5: return False  
    # 台北時間 09:00 ~ 14:00 (含收盤清算)
    return 9 <= now.hour <= 14

# --- 3. 核心監控循環 ---
def master_monitor_loop():
    print("🤖 監控線程已進入 master_monitor_loop")
    
    # 💡 啟動即時診斷測試 (強迫發送，確認 LINE 連結)
    # 增加一個 10 秒緩衝，確保 Flask 已經跑起來
    time.sleep(10)
    print("🧪 執行啟動診斷測試 (force_send=True)...")
    try:
        # 如果 monitor 內部 API 卡死，這裡會擋住。
        # 建議搭配我之前給你的「暴力診斷版」monitor 使用
        run_009816_monitor(force_send=True)
        print("✅ 啟動診斷任務已觸發過")
    except Exception as e:
        print(f"❌ 診斷失敗: {e}")

    last_heartbeat_hour = -1

    while True:
        try:
            now = datetime.now()
            
            if is_market_open():
                print(f"🚀 [{now.strftime('%H:%M:%S')}] 市場開放，執行 009816 巡檢...")
                run_009816_monitor()
                time.sleep(15)
                run_unified_experiment()
                print("✅ 巡檢完畢，休眠 5 分鐘")
                time.sleep(300)
            else:
                # --- 非交易時段邏輯 ---
                # 每小時的第 0 分鐘發送一次 Survival Log 到 Render 
                if now.hour != last_heartbeat_hour:
                    print(f"💤 [生存回報] 目前為非交易時段 ({now.strftime('%Y-%m-%d %H:%M')})，系統監理中...")
                    last_heartbeat_hour = now.hour
                
                # 即使沒開盤，每 10 分鐘在 Log 留個腳印
                time.sleep(600) 

        except Exception as e:
            print(f"⚠️ 監控循環異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now = datetime.now()
    return f"🦅 AI Manager Active<br>Server Time: {now.strftime('%Y-%m-%d %H:%M:%S')}<br>Market Open: {is_market_open()}"

if __name__ == "__main__":
    # 1. 優先掛載美股排程 (通常在 05:05 跑)
    t_us = threading.Thread(target=schedule_job, daemon=True)
    t_us.start()
    
    # 2. 掛載台股巡檢
    t_tw = threading.Thread(target=master_monitor_loop, daemon=True)
    t_tw.start()
    
    print("✅ 監控線程啟動指令已發出")
    
    # 3. 啟動 Flask (Render 必須偵測到這個 Port 起來才算部署成功)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
