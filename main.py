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

app = Flask(__name__)

# --- 2. 交易時間判斷 ---
def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5: return False  
    return 9 <= now.hour <= 14

@app.route('/')
def home():
    now = datetime.now()
    # 檢查 Discord 環境變數
    webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
    webhook_check = f"✅ 已設定 (後 5 碼: ...{webhook[-5:]})" if webhook else "❌ 缺失 (請在 Render 設定 DISCORD_WEBHOOK_URL)"
    
    return f"""
    <html>
        <head>
            <title>AI Manager DC 控制台</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6; max-width: 600px; margin: auto;">
            <h1>🦅 AI Manager 控制面板</h1>
            <p style="background: #eee; padding: 10px;">伺服器時間: <b>{now.strftime('%Y-%m-%d %H:%M:%S')}</b></p>
            <hr>
            <h3>系統診斷：</h3>
            <ul>
                <li>Discord Webhook: {webhook_check}</li>
                <li>市場狀態: {'🟢 已開盤 (執行巡檢中)' if is_market_open() else '🔴 已收盤 (待機模式)'}</li>
            </ul>
            <hr>
            <p style="font-size: 1.1em;">👉 <a href="/trigger" style="display: inline-block; color: white; background: #5865F2; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">發送 Discord 測試訊息</a></p>
            <p style="color: #666; font-size: 0.8em;">※ 點擊按鈕後將即時測試 Webhook 連線能力</p>
        </body>
    </html>
    """

@app.route('/trigger')
def manual_trigger():
    try:
        # 使用延遲導入，避免 monitor_009816.py 語法錯誤導致整個 main.py 掛掉
        from monitor_009816 import run_009816_monitor
        print("🔥 啟動手動 Discord 診斷...", flush=True)
        result = run_009816_monitor(force_send=True)
        return f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h2>診斷結果回報</h2>
            <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap;">
                {result}
            </div>
            <br><a href="/">⬅ 返回首頁</a>
        </div>
        """
    except Exception as e:
        return f"❌ 系統導入或執行異常: {str(e)}<br>可能是 monitor_009816.py 有語法錯誤，請檢查代碼。"

# --- 核心監控線程 ---
def monitor_loop():
    print("🤖 監控背景線程已啟動...", flush=True)
    time.sleep(10) # 讓 Flask 優先綁定 Port
    
    while True:
        try:
            if is_market_open():
                # 開盤期間每 5 分鐘巡檢一次
                from monitor_009816 import run_009816_monitor
                from new_ten_thousand_grid import run_unified_experiment
                
                print("🚀 執行盤中巡檢任務...", flush=True)
                run_009816_monitor()
                time.sleep(10) # 稍微間隔避免過度擠壓
                run_unified_experiment()
                
                time.sleep(300) 
            else:
                time.sleep(600) # 非交易時段每 10 分鐘檢查一次
        except Exception as e:
            print(f"⚠️ 監控循環發生錯誤: {e}", flush=True)
            time.sleep(60)

if __name__ == "__main__":
    # 1. 啟動背景線程
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    
    # 2. 啟動 Flask (Render 必須偵測到 Port)
    port = int(os.environ.get("PORT", 10000))
    print(f"✅ Flask 正在啟動，監聽 Port: {port}", flush=True)
    app.run(host='0.0.0.0', port=port, debug=False)
