import os, sys, time, logging, threading, requests
from flask import Flask
from datetime import datetime

# --- 基礎設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# 延遲導入子模組，避免啟動時因單一檔案報錯而導致整台機器啟動失敗
try:
    from monitor_009816 import run_taiwan_stock
    from new_ten_thousand_grid import run_grid
    from us_post_market_robot import run_us_ai
except ImportError as e:
    logging.error(f"❌ 模組導入失敗: {e}")

# 從環境變數讀取 Webhook
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

def dc_log(text):
    """公用發送函式，確保訊息長度不超過 Discord 限制"""
    if not WEBHOOK:
        logging.warning("⚠️ Webhook URL 未設定")
        return
    try:
        # 簡單切分訊息以防萬一
        if len(text) > 1950:
            text = text[:1950] + "..."
        
        res = requests.post(WEBHOOK, json={"content": text}, timeout=15)
        if res.status_code != 204:
            logging.error(f"❌ Discord 發送失敗: {res.status_code}, {res.text}")
    except Exception as e:
        logging.error(f"❌ 網路連線異常: {e}")

# =========================
# 核心背景任務邏輯
# =========================
def background_inspection():
    """
    分段執行所有 AI 監控任務
    """
    start_time = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 0. 啟動通知
    dc_log(f"🛰️ **AI 投資監控系統：巡檢啟動**\n時間: `{now_str}`\n進度: [ 0% ] 正在初始化...")

    # 1. 執行台股監控
    try:
        report1 = run_taiwan_stock()
        dc_log(report1)
    except Exception as e:
        dc_log(f"⚠️ **台股模組異常**: `{str(e)}`")

    # 2. 執行網格監控 (耗時較長)
    try:
        # 加入小延遲，避免 Webhook 頻率過高被限流
        time.sleep(2)
        report2 = run_grid()
        dc_log(report2)
    except Exception as e:
        dc_log(f"⚠️ **網格模組異常**: `{str(e)}`")

    # 3. 執行美股監控
    try:
        time.sleep(2)
        report3 = run_us_ai()
        dc_log(report3)
    except Exception as e:
        dc_log(f"⚠️ **美股模組異常**: `{str(e)}`")

    # 4. 結束通知
    duration = time.time() - start_time
    dc_log(f"✅ **巡檢完成**\n總耗時: `{duration:.1f} 秒`\n系統狀態: 🟢 正常運行中")

# =========================
# 網頁路由 (Flask Routes)
# =========================
@app.route("/")
def index():
    webhook_status = "✅ 已連線" if WEBHOOK else "❌ 未設定"
    return f"""
    <div style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #5865F2;">🦅 AI Manager 管理後台</h1>
        <div style="background: #f4f4f4; padding: 20px; border-radius: 10px; display: inline-block;">
            <p><b>Webhook 狀態:</b> {webhook_status}</p>
            <p><b>伺服器地區:</b> {os.environ.get('RENDER_REGION', '預設')}</p>
        </div>
        <hr style="width: 300px; margin: 30px auto;">
        <a href="/run" style="background: #5865F2; color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold;">🚀 啟動全自動巡檢</a>
        <p style="color: gray; margin-top: 15px;">點擊後請前往 Discord 查看頻道進度。</p>
    </div>
    """

@app.route("/run")
def trigger():
    if not WEBHOOK:
        return "❌ 錯誤：請先在 Render 後台設定 DISCORD_WEBHOOK_URL"
    
    # 建立一個背景執行緒跑任務，避免網頁 30 秒自動超時
    task_thread = threading.Thread(target=background_inspection)
    task_thread.start()
    
    return """
    <div style="text-align: center; padding: 50px; font-family: sans-serif;">
        <h2 style="color: green;">✅ 背景任務已啟動！</h2>
        <p>巡檢大約需要 3-5 分鐘，請檢查 Discord 頻道。</p>
        <a href="/">⬅ 返回首頁</a>
    </div>
    """

if __name__ == "__main__":
    # Render 會自動分配 PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
