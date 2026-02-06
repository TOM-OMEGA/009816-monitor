import os, sys, time, logging, threading, requests
from flask import Flask
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# 導入子模組
from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

def send_now(msg):
    """立即發送訊息，不等待，方便偵錯"""
    if not WEBHOOK: return
    try:
        requests.post(WEBHOOK, json={"content": msg}, timeout=10)
    except:
        pass

def background_worker():
    """核心背景任務：分段執行並即時回報"""
    now = datetime.now().strftime("%H:%M:%S")
    send_now(f"🛰️ **AI 巡檢啟動** ({now})\n正在依序執行：台股 > 網格 > 美股...")

    # 1. 執行台股
    try:
        r1 = run_taiwan_stock()
        send_now(f"📈 **台股分析完成**\n{r1}")
    except Exception as e:
        send_now(f"❌ 台股模組崩潰: {e}")

    # 2. 執行網格 (最耗時，單獨發送)
    try:
        r2 = run_grid()
        send_now(f"🧱 **網格監控完成**\n{r2}")
    except Exception as e:
        send_now(f"❌ 網格模組崩潰: {e}")

    # 3. 執行美股
    try:
        r3 = run_us_ai()
        send_now(f"🌎 **美股分析完成**\n{r3}")
    except Exception as e:
        send_now(f"❌ 美股模組崩潰: {e}")

    send_now("✅ **全自動巡檢任務結束**")

@app.route("/")
def home():
    status = "✅ 準備就緒" if WEBHOOK else "❌ Webhook 未設定"
    return f"""
    <div style="font-family:sans-serif; text-align:center; padding:50px;">
        <h1 style="color:#5865F2;">🦅 AI Manager</h1>
        <p>狀態: {status}</p>
        <hr>
        <a href="/run" style="background:#5865F2; color:white; padding:15px 30px; text-decoration:none; border-radius:5px; font-weight:bold;">🚀 立即啟動全模組巡檢</a>
        <p style="color:#666; font-size:0.8em; margin-top:20px;">點擊後請檢查 Discord 頻道，訊息會分段跳出。</p>
    </div>
    """

@app.route("/run")
def manual_run():
    if not WEBHOOK:
        return "錯誤: 未設定 Webhook"
    
    # 啟動執行緒，不阻礙網頁回應
    thread = threading.Thread(target=background_worker)
    thread.start()
    
    return """
    <div style="text-align:center; padding:50px;">
        <h2>✅ 任務已在背景啟動！</h2>
        <p>請立刻前往 Discord 查看頻道。</p>
        <p>如果 1 分鐘內沒看到「🛰️ AI 巡檢啟動」，請確認 Webhook URL 是否正確。</p>
        <a href="/">返回首頁</a>
    </div>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
