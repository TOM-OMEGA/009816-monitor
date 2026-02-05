import os
import sys
import time
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone

# 路徑強化，確保 Render 抓到模組
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
except ImportError as e:
    print(f"❌ 導入失敗：{e}")

app = Flask(__name__)

def get_now_tw():
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    """判斷是否為交易日 9:00-13:00"""
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5:
        return False
    return 9 <= now_tw.hour <= 13

def master_monitor_loop():
    print("🤖 中央監控系統啟動：全量巡檢模式...")
    # 初始冷卻，避開 API 高峰
    time.sleep(5)

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行全面巡檢 {now_tw.strftime('%Y-%m-%d %H:%M')} ---")

                # 1️⃣ 009816 存股監控（每月一次）
                run_009816_monitor()
                time.sleep(10)  # 避免秒刷 AI

                # 2️⃣ 萬元網格模擬（可每盤中執行）
                print("📊 執行萬元網格實驗模擬...")
                run_unified_experiment()

                # 總循環 300 秒（5分鐘）
                time.sleep(300)
            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，監控暫停中...")
                # 非交易日休息 30 分鐘
                time.sleep(1800)
        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人全面監控中</h1><p>時間：{now_tw.strftime('%Y-%m-%d %H:%M:%S')}</p>"

if __name__ == "__main__":
    # 💡 防止 Flask 重複啟動執行緒
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        t = threading.Thread(target=master_monitor_loop)
        t.daemon = True
        t.start()

    port = int(os.environ.get("PORT", 10000))
    # 💡 關閉 reloader 確保只有一個執行緒在跑
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
