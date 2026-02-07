import os, sys, time, logging, threading, requests
from flask import Flask
from datetime import datetime

# --- 基礎設定 ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# 延遲導入子模組
try:
    from monitor_009816 import run_taiwan_stock
    from new_ten_thousand_grid import run_grid
    from us_post_market_robot import run_us_ai
except ImportError as e:
    logging.error(f"❌ 模組導入失敗: {e}")

# 從環境變數讀取 Webhook
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

def dc_log(text, file_buf=None, filename="chart.png"):
    """
    【究極修正版】
    強制將文字與圖片剝離為兩個獨立請求，徹底破解 Discord 標題縮小問題。
    """
    if not WEBHOOK:
        logging.warning("⚠️ Webhook URL 未設定")
        return
    
    try:
        clean_text = str(text)
        if len(clean_text) > 1950:
            clean_text = clean_text[:1950] + "..."
        
        # 情況 A: 有圖片附件 -> 執行兩階段發送
        if file_buf is not None:
            # 第一階段：單獨發送純文字 (Payload 只有內容)
            # 這是標題變大的唯一關鍵：不能跟圖片一起發送
            requests.post(WEBHOOK, json={"content": clean_text}, timeout=15)
            
            # 物理延遲：確保 Discord 伺服器判定為兩則不同訊息
            time.sleep(2)
            
            # 第二階段：單獨發送圖片檔案 (Content 為空)
            file_buf.seek(0)
            files = {"file": (filename, file_buf, "image/png")}
            res = requests.post(WEBHOOK, files=files, timeout=20)
        
        # 情況 B: 純文字
        else:
            res = requests.post(WEBHOOK, json={"content": clean_text}, timeout=15)
            
        if 'res' in locals() and res.status_code not in [200, 204]:
            logging.error(f"❌ Discord 發送失敗: {res.status_code}")
            
    except Exception as e:
        logging.error(f"❌ 網路連線異常: {e}")

# =========================
# 核心背景任務邏輯
# =========================
def background_inspection():
    """
    巡檢任務：確保三份報告之間有足夠的冷卻時間防止氣泡合併
    """
    start_time = time.time()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 0. 啟動通知
    dc_log(f"# 🛰️ AI 投資監控系統：巡檢啟動\n時間: `{now_str}`")
    time.sleep(3) 

    # 1. 執行台股監控
    try:
        result1 = run_taiwan_stock()
        if isinstance(result1, tuple) and len(result1) == 2:
            msg, img = result1
            dc_log(msg, file_buf=img, filename="taiwan_stock.png")
        else:
            dc_log(result1)
        time.sleep(5) # 加長間隔
    except Exception as e:
        dc_log(f"⚠️ **台股模組異常**: `{str(e)}`")

    # 2. 執行網格監控
    try:
        result2 = run_grid()
        if isinstance(result2, tuple) and len(result2) == 2:
            msg, img = result2
            dc_log(msg, file_buf=img, filename="grid_report.png")
        else:
            dc_log(result2)
        time.sleep(6) 
    except Exception as e:
        dc_log(f"⚠️ **網格模組異常**: `{str(e)}`")

    # 3. 執行美股監控
    try:
        # dc_log 現在會先噴發文字報告(標題變大)，隨後才貼上圖表
        result3 = run_us_ai()
        if isinstance(result3, tuple) and len(result3) == 2:
            msg, img = result3
            dc_log(msg, file_buf=img, filename="us_market.png")
        else:
            dc_log(result3)
    except Exception as e:
        dc_log(f"⚠️ **美股模組異常**: `{str(e)}`")

    time.sleep(5)
    duration = time.time() - start_time
    dc_log(f"✅ **巡檢完成**\n耗時: `{duration:.1f} 秒`\n系統狀態: 🟢 正常運行")

# =========================
# Flask 路由維持現狀
# =========================
@app.route("/")
def index():
    return f"""
    <div style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #5865F2;">🦅 AI Manager 管理後台</h1>
        <a href="/run" style="background: #5865F2; color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold;">🚀 啟動全自動巡檢</a>
    </div>
    """

@app.route("/run")
def trigger():
    if not WEBHOOK: return "❌ 錯誤：未設定 Webhook URL"
    threading.Thread(target=background_inspection).start()
    return "背景任務已啟動！請檢查 Discord。"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
