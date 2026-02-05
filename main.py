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
    now_tw = get_now_tw()
    if now_tw.weekday() >= 5: return False
    return 9 <= now_tw.hour <= 13

def master_monitor_loop():
    print("🤖 中央監控系統啟動：全量巡檢模式...")
    # 啟動先冷卻，避開 API 巔峰
    time.sleep(20)
    
    while True:
        try:
            now_tw = get_now_tw()
            if is_market_open():
                print(f"--- 執行全面巡檢 {now_tw.strftime('%H:%M')} ---")
                
                # 1. 009816 監控 (優先執行)
                run_009816_monitor()
                
                # 💡 關鍵修正：拉開 60 秒間隔，確保 AI 配額計數器重置
                time.sleep(60)
                
                # 2. 萬元實驗網格 (現在改為每次巡檢都執行)
                print("📊 執行萬元實驗室診斷...")
                run_unified_experiment()
                
                # 總循環 300 秒 (5分鐘)，扣除上方已等待的 60 秒
                time.sleep(240) 
            else:
                print(f"💤 非交易時段 ({now_tw.strftime('%H:%M')})，監控暫停中...")
                time.sleep(1800) 
        except Exception as e:
            print(f"⚠️ 異常: {e}")
            time.sleep(60)

@app.route('/')
def home():
    now_tw = get_now_tw()
    return f"<h1>🦅 經理人全面監控中</h1><p>時間：{now_tw.strftime('%H:%M:%S')}</p>"

if __name__ == "__main__":
    # 💡 防止 Flask 重複啟動執行緒
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        t = threading.Thread(target=master_monitor_loop)
        t.daemon = True
        t.start()
    
    port = int(os.environ.get("PORT", 10000))
    # 💡 關閉 reloader 確保只有一個執行緒在跑
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
