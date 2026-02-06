import os, sys, time, logging, threading, requests
from flask import Flask
from datetime import datetime

# --- 基礎設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

try:
    from monitor_009816 import run_taiwan_stock
    from new_ten_thousand_grid import run_grid
    from us_post_market_robot import run_us_ai
except ImportError as e:
    logging.error(f"❌ 模組導入失敗: {e}")

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

def dc_log(text, file_buf=None, filename="chart.png"):
    """
    升級版公用發送函式：支援發送文字與單張圖片
    """
    if not WEBHOOK:
        logging.warning("⚠️ Webhook URL 未設定")
        return
    try:
        # 處理文字長度限制
        content = text[:1950] + "..." if len(text) > 1950 else text
        
        # 如果有圖片文件流
        if file_buf:
            file_buf.seek(0) # 確保讀取位置在開頭
            files = {"file": (filename, file_buf, "image/png")}
            payload = {"content": content}
            res = requests.post(WEBHOOK, data=payload, files=files, timeout=20)
        else:
            # 僅發送文字
            res = requests.post(WEBHOOK, json={"content": content}, timeout=15)
            
        if res.status_code not in [200, 204]:
            logging.error(f"❌ Discord 發送失敗: {res.status_code}, {res.text}")
    except Exception as e:
        logging.error(f"❌ 網路連線異常: {e}")

# =========================
# 核心背景任務邏輯
# =========================
def background_inspection():
    start_time = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    dc_log(f"# 🛰️ **AI 投資監控系統：巡檢啟動**\n時間: `{now_str}`\n進度: [ 0% ]")

    # 1. 執行台股監控 (支援圖表)
    try:
        # 解構回傳值：文字與圖片流
        report1, img_buf1 = run_taiwan_stock()
        dc_log(report1, file_buf=img_buf1, filename="009816_trend.png")
    except Exception as e:
        dc_log(f"⚠️ **台股模組異常**: `{str(e)}`")

    # 2. 執行網格監控 (目前僅文字，保留預留)
    try:
        time.sleep(2)
        # 網格模組若尚未修改回傳圖片，這裏先處理文字
        result2 = run_grid()
        if isinstance(result2, tuple):
            dc_log(result2[0], file_buf=result2[1], filename="grid_report.png")
        else:
            dc_log(result2)
    except Exception as e:
        dc_log(f"⚠️ **網格模組異常**: `{str(e)}`")

    # 3. 執行美股監控 (準備對接圖片)
    try:
        time.sleep(2)
        result3 = run_us_ai()
        if isinstance(result3, tuple):
            dc_log(result3[0], file_buf=result3[1], filename="us_market.png")
        else:
            dc_log(result3)
    except Exception as e:
        dc_log(f"⚠️ **美股模組異常**: `{str(e)}`")

    duration = time.time() - start_time
    dc_log(f"✅ **巡檢完成**\n總耗時: `{duration:.1f} 秒`\n系統狀態: 🟢 正常運行中")

# ... 網頁路由 (Flask Routes) 保持不變 ...
@app.route("/")
def index():
    webhook_status = "✅ 已連線" if WEBHOOK else "❌ 未設定"
    return f"""
    <div style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #5865F2;">🦅 AI Manager 管理後台</h1>
        <div style="background: #f4f4f4; padding: 20px; border-radius: 10px; display: inline-block;">
            <p><b>Webhook 狀態:</b> {webhook_status}</p>
        </div>
        <hr style="width: 300px; margin: 30px auto;">
        <a href="/run" style="background: #5865F2; color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold;">🚀 啟動全自動巡檢</a>
    </div>
    """

@app.route("/run")
def trigger():
    if not WEBHOOK: return "❌ 錯誤：請先設定 DISCORD_WEBHOOK_URL"
    threading.Thread(target=background_inspection).start()
    return """<div style="text-align: center; padding: 50px;"><h2>✅ 背景任務已啟動！</h2><a href="/">⬅ 返回首頁</a></div>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
