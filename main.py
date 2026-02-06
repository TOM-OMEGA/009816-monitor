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
    # 台股交易時間：週一至週五 09:00 - 14:00
    if now.weekday() >= 5: return False  
    return 9 <= now.hour <= 14

@app.route('/')
def home():
    now = datetime.now()
    webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
    webhook_check = f"✅ 已設定 (後 5 碼: ...{webhook[-5:]})" if webhook else "❌ 缺失 (請設定 DISCORD_WEBHOOK_URL)"
    
    return f"""
    <html>
        <head><title>AI Manager DC 控制台</title><meta charset="utf-8"></head>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6; max-width: 600px; margin: auto;">
            <h1 style="color: #5865F2;">🦅 AI Manager 控制面板</h1>
            <p style="background: #f4f4f4; padding: 10px; border-radius: 5px;">伺服器時間: <b>{now.strftime('%Y-%m-%d %H:%M:%S')}</b></p>
            <hr>
            <h3>系統狀態：</h3>
            <ul>
                <li>Discord Webhook: {webhook_check}</li>
                <li>市場監控: {'🟢 盤中巡檢中' if is_market_open() else '🔴 休市待機中'}</li>
            </ul>
            <hr>
            <p>👉 <a href="/trigger" style="display: inline-block; color: white; background: #5865F2; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">發送手動診斷測試</a></p>
            <p style="color: #d73a49; font-size: 0.85em;">⚠️ 提示：若出現 429 錯誤，請停止點擊並等待 5 分鐘。</p>
        </body>
    </html>
    """

@app.route('/trigger')
def manual_trigger():
    try:
        from monitor_009816 import run_009816_monitor
        print("🔥 手動觸發診斷...", flush=True)
        result = run_009816_monitor(force_send=True)
        return f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h2>診斷結果</h2>
            <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap;">{result}</div>
            <br><a href="/">⬅ 返回首頁</a>
        </div>
        """
    except Exception as e:
        return f"❌ 執行異常: {str(e)}"

# --- 核心監控線程 ---
def monitor_loop():
    print("🤖 背景線程已啟動，初次運行將等待 60 秒避開部署尖峰...", flush=True)
    time.sleep(60) # 避開啟動時的瞬時流量
    
    while True:
        try:
            if is_market_open():
                print(f"🚀 [{datetime.now().strftime('%H:%M:%S')}] 執行自動巡檢任務...", flush=True)
                
                # 延遲導入
                from monitor_009816 import run_009816_monitor
                from new_ten_thousand_grid import run_unified_experiment
                
                # 執行主要網格策略 (這通常包含最重要的資訊)
                run_unified_experiment()
                
                # 💡 巡檢完畢後進入長休眠，避免 Discord 429
                # 建議盤中每 10 分鐘 (600秒) 檢查一次即可
                time.sleep(600) 
            else:
                # 非交易時段每 30 分鐘心跳檢查一次即可
                time.sleep(1800)
        except Exception as e:
            print(f"⚠️ 監控循環錯誤: {e}", flush=True)
            time.sleep(120)

if __name__ == "__main__":
    # 啟動監控
    threading.Thread(target=monitor_loop, daemon=True).start()
    
    # 啟動 Web 服務
    port = int(os.environ.get("PORT", 10000))
    print(f"✅ Flask 監聽 Port: {port}", flush=True)
    app.run(host='0.0.0.0', port=port, debug=False)
