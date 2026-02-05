import os
import sys
import time
import threading
from flask import Flask
from datetime import datetime, timedelta, timezone

# 路徑強化，確保模組能抓到
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from monitor_009816 import run_009816_monitor
    from new_ten_thousand_grid import run_unified_experiment
    from us_post_market_robot import run_us_post_market, schedule_job
except ImportError as e:
    print(f"❌ 導入失敗：{e}")

app = Flask(__name__)

def get_now_tw():
    return datetime.now(timezone(timedelta(hours=8)))

def is_market_open():
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5:
        return False
    return 9 <= now_tw.hour <= 13

# === 中央巡檢線程 ===
def master_monitor_loop():
    """中央監控線程：存股 + 網格 AI 判斷"""
    print("🤖 中央監控系統啟動：全量巡檢模式...")
    time.sleep(20)  # 啟動冷卻，避開 API 巔峰

    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行全面巡檢 {now_tw.strftime('%H:%M')} ---")

                # === 1️⃣ 存股009816 AI判斷 ===
                print("🦅 執行 009816 存股判斷...")
                run_009816_monitor()
                time.sleep(60)  # 確保 AI 配額安全

                # === 2️⃣ 一萬元網格實驗 ===
                print("📊 執行萬元網格 AI 實驗...")
                run_unified_experiment()
                time.sleep(240)  # 總循環 5 分鐘，扣除上方等待

            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，監控暫停中...")
                time.sleep(1800)  # 非交易日/時段休眠 30 分鐘

        except Exception as e:
            print(f"⚠️ 中央監控異常: {e}")
            time.sleep(60)

# === Flask 路由 ===
@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人全面監控中</h1><p>時間：{now_tw.strftime('%H:%M:%S')}</p>"

@app.route('/us_post_market')
def trigger_us_post_market():
    """手動觸發美股盤後分析"""
    try:
        print("🚀 手動觸發美股盤後分析...")
        run_us_post_market()
        return "美股盤後分析已執行 ✅"
    except Exception as e:
        return f"❌ 執行失敗: {e}"

if __name__ == "__main__":
    # 💡 防止 Flask 重複啟動執行緒
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        # 啟動中央巡檢
        t = threading.Thread(target=master_monitor_loop, daemon=True)
        t.start()

        # 啟動美股盤後分析排程
        t2 = threading.Thread(target=schedule_job, daemon=True)
        t2.start()

        # 測試模式：啟動時立即推播一次
        TEST_MODE = True
        if TEST_MODE:
            print("🚀 測試模式啟動：立即執行美股盤後分析並推播 LINE")
            run_us_post_market()

    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
