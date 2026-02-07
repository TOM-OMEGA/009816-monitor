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
    升級版公用發送函式：支援發送文字與單張圖片
    """
    if not WEBHOOK:
        logging.warning("⚠️ Webhook URL 未設定")
        return
    
    try:
        # 確保 text 一定是字串，防止 BytesIO 物件混入
        clean_text = str(text)
        if len(clean_text) > 1950:
            clean_text = clean_text[:1950] + "..."
        
        # 情況 A: 有圖片附件
        if file_buf is not None:
            file_buf.seek(0)  # 移至起始位置
            files = {"file": (filename, file_buf, "image/png")}
            payload = {"content": clean_text}
            # 注意：發送檔案時使用 data= 而非 json=
            res = requests.post(WEBHOOK, data=payload, files=files, timeout=20)
        
        # 情況 B: 純文字
        else:
            res = requests.post(WEBHOOK, json={"content": clean_text}, timeout=15)
            
        if res.status_code not in [200, 204]:
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
    
    # 啟動通知
    dc_log(f"# 🛰️ AI 投資監控系統：巡檢啟動\n時間: `{now_str}`")
    # 強制等待，確保啟動通知與第一份報告分開
    time.sleep(3) 

    # 1. 執行 009816 監控
    try:
        result1 = run_taiwan_stock()
        if isinstance(result1, tuple) and len(result1) == 2:
            msg, img = result1
            dc_log(msg, file_buf=img, filename="009816_analysis.png")
        else:
            dc_log(result1)
        # 【關鍵修正】增加等待時間至 5 秒，徹底切斷 Discord 的訊息合併（Grouping）
        time.sleep(5) 
    except Exception as e:
        dc_log(f"⚠️ **009816 模組異常**: `{str(e)}`")

    # 2. 執行網格監控
    try:
        result2 = run_grid()
        if isinstance(result2, tuple) and len(result2) == 2:
            msg, img = result2
            dc_log(msg, file_buf=img, filename="grid_report.png")
        else:
            dc_log(result2)
        # 【關鍵修正】再次強制冷卻
        time.sleep(5) 
    except Exception as e:
        dc_log(f"⚠️ **網格模組異常**: `{str(e)}`")

    # 3. 執行美股監控
    try:
        # 【關鍵修正 A】發送一個獨立的物理分隔線，強迫 Discord 結算上一個訊息氣泡
        dc_log("-------------------------------------------") 
        
        # 【關鍵修正 B】拉長等待時間至 8 秒，確保伺服器將其判定為新事件
        time.sleep(8) 
        
        result3 = run_us_ai()
        if isinstance(result3, tuple) and len(result3) == 2:
            msg, img = result3
            # 這裡的 msg 第一行必須是 # 標題
            dc_log(msg, file_buf=img, filename="us_market.png")
        else:
            dc_log(result3)
    except Exception as e:
        dc_log(f"⚠️ **美股模組異常**: `{str(e)}`")
    time.sleep(2)
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
        </div>
        <hr style="width: 300px; margin: 30px auto;">
        <a href="/run" style="background: #5865F2; color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold;">🚀 啟動全自動巡檢</a>
    </div>
    """

@app.route("/run")
def trigger():
    if not WEBHOOK:
        return "❌ 錯誤：請先在 Render 後台設定 DISCORD_WEBHOOK_URL"
    
    threading.Thread(target=background_inspection).start()
    
    return """
    <div style="text-align: center; padding: 50px; font-family: sans-serif;">
        <h2 style="color: green;">✅ 背景任務已啟動！</h2>
        <p>請檢查 Discord 頻道。</p>
        <a href="/">⬅ 返回首頁</a>
    </div>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
