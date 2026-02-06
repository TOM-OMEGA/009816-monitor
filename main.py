import os, sys, time, threading, requests
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
run_009816_monitor = None
run_unified_experiment = None
schedule_job = None

try:
    from monitor_009816 import run_009816_monitor
except ImportError as e:
    print(f"❌ 009816 導入失敗: {e}", flush=True)

try:
    from new_ten_thousand_grid import run_unified_experiment
except ImportError as e:
    print(f"❌ 網格導入失敗: {e}", flush=True)

try:
    from us_post_market_robot import schedule_job
except ImportError as e:
    print(f"❌ 美股導入失敗: {e}", flush=True)

app = Flask(__name__)

def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5: return False  
    return 9 <= now.hour <= 14

@app.route('/')
def home():
    now = datetime.now()
    # 檢查環境變數 (隱藏部分資訊以保安全)
    token = os.environ.get('LINE_ACCESS_TOKEN', '')
    uid = os.environ.get('USER_ID', '')
    token_check = f"✅ 已讀取 (前4碼: {token[:4]}...)" if token else "❌ 缺失 (請檢查 Render 設定)"
    uid_check = f"✅ 已讀取 (開頭: {uid[:5]}...)" if uid else "❌ 缺失 (請檢查 Render 設定)"
    
    return f"""
    <html>
        <head><title>AI Manager 控制台</title></head>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6;">
            <h1>🦅 AI Manager 控制面板</h1>
            <p>伺服器時間: {now.strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <h3>系統診斷：</h3>
            <ul>
                <li>LINE Token: {token_check}</li>
                <li>User ID: {uid_check}</li>
                <li>市場狀態: {'🟢 已開盤' if is_market_open() else '🔴 已收盤'}</li>
            </ul>
            <hr>
            <p style="font-size: 1.2em;">👉 <a href="/trigger" style="color: white; background: #00b900; padding: 10px 20px; text-decoration: none; border-radius: 5px;">強制執行 LINE 深度測試</a></p>
        </body>
    </html>
    """

@app.route('/trigger')
def manual_trigger():
    if not run_009816_monitor:
        return "❌ 錯誤：monitor_009816 模組未載入"
    
    try:
        print("🔥 啟動手動深度診斷...", flush=True)
        result = run_009816_monitor(force_send=True)
        # result 現在會包含詳細的 LINE 回傳訊息
        return f"""
        <h2>診斷結果</h2>
        <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; font-family: monospace;">
            {result}
        </div>
        <br><a href="/">返回首頁</a>
        """
    except Exception as e:
        return f"❌ 系統崩潰: {str(e)}"

if __name__ == "__main__":
    if schedule_job:
        threading.Thread(target=schedule_job, daemon=True).start()
    
    def monitor_loop():
        while True:
            if is_market_open():
                if run_009816_monitor: run_009816_monitor()
                time.sleep(300)
            time.sleep(600)
            
    threading.Thread(target=monitor_loop, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
