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

# --- Discord 發送邏輯 (保持你的究極修正版) ---
def dc_log(text, file_buf=None, filename="chart.png"):
    if not WEBHOOK:
        logging.warning("⚠️ Webhook URL 未設定")
        return
    try:
        clean_text = str(text)
        if len(clean_text) > 1950:
            clean_text = clean_text[:1950] + "..."
        
        if file_buf is not None:
            requests.post(WEBHOOK, json={"content": clean_text}, timeout=15)
            time.sleep(2)
            file_buf.seek(0)
            files = {"file": (filename, file_buf, "image/png")}
            res = requests.post(WEBHOOK, files=files, timeout=20)
        else:
            res = requests.post(WEBHOOK, json={"content": clean_text}, timeout=15)
    except Exception as e:
        logging.error(f"❌ 網路連線異常: {e}")

# =========================
# 核心任務邏輯 (模組化)
# =========================

def task_us_summary():
    """美股收盤總結"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dc_log(f"# 🌙 美股盤後總結報告\n時間: `{now_str}`")
    try:
        result = run_us_ai()
        if isinstance(result, tuple):
            dc_log(result[0], file_buf=result[1], filename="us_close.png")
        else:
            dc_log(result)
        return True
    except Exception as e:
        dc_log(f"⚠️ 美股分析失敗: {str(e)}")
        return False

def task_taiwan_realtime_monitor(is_manual=False):
    """台股盤中巡檢（含網格）"""
    now_str = datetime.now().strftime("%H:%M:%S")
    label = "手動點擊" if is_manual else "自動巡檢"
    logging.info(f"🚀 執行台股 3 分鐘即時監控 ({label})... {now_str}")
    
    # 1. 執行存股監控
    try:
        res_tw = run_taiwan_stock()
        if isinstance(res_tw, tuple):
            dc_log(f"🕒 台股即時快報 ({label} {now_str})\n{res_tw[0]}", file_buf=res_tw[1], filename="tw_realtime.png")
        else:
            dc_log(f"🕒 台股即時快報 ({label} {now_str})\n{res_tw}")
    except Exception as e:
        logging.error(f"台股監控異常: {e}")

    # 2. 執行網格監控
    try:
        res_grid = run_grid()
        if isinstance(res_grid, tuple):
            dc_log(res_grid[0], file_buf=res_grid[1], filename="grid_live.png")
        else:
            dc_log(res_grid)
    except Exception as e:
        logging.error(f"網格監格異常: {e}")

def run_full_inspection():
    """執行全套流程（美股+台股+網格）用於手動觸發"""
    dc_log("# 🛰️ 啟動全套手動巡檢任務...")
    task_us_summary()
    time.sleep(5)
    task_taiwan_realtime_monitor(is_manual=True)
    dc_log("✅ 手動全套巡檢完成")

# =========================
# 自動化調度中心
# =========================
def scheduler_engine():
    last_us_date = ""
    logging.info("⚙️ 自動化調度引擎已啟動")
    
    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        
        # A. 美股時段 (早上 5:30 後執行一次)
        if 5 <= now.hour < 9:
            if last_us_date != current_date:
                task_us_summary()
                last_us_date = current_date
        
        # B. 台股時段 (09:00 - 13:35) 每 3 分鐘一次
        elif (now.hour == 9) or (10 <= now.hour <= 12) or (now.hour == 13 and now.minute <= 35):
            task_taiwan_realtime_monitor(is_manual=False)
            time.sleep(180) 
            continue 
            
        time.sleep(60)

# =========================
# Flask 路由 (保留手動功能)
# =========================
@app.route("/")
def index():
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""
    <div style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1 style="color: #5865F2;">🦅 AI Manager 管理後台</h1>
        <p>當前系統時間: <code>{now_str}</code></p>
        <p>狀態: 🟢 背景自動巡檢運行中 (台股時段每 3 分鐘)</p>
        <hr style="margin: 30px 0;">
        <a href="/run" style="background: #5865F2; color: white; padding: 15px 40px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">🚀 啟動全套手動巡檢 (美+台+網格)</a>
        <p style="color: #666; font-size: 0.9em; margin-top: 10px;">點擊後將在 Discord 發送完整分析報告</p>
    </div>
    """

@app.route("/run")
def manual_trigger():
    if not WEBHOOK: return "❌ 錯誤：未設定 Webhook URL"
    # 使用 Thread 避免網頁卡住轉圈圈
    threading.Thread(target=run_full_inspection).start()
    return "<h3>✅ 手動全套巡檢已啟動！</h3><p>請檢查 Discord 頻道。</p><br><a href='/'>返回首頁</a>"

if __name__ == "__main__":
    # 啟動自動化背景引擎
    threading.Thread(target=scheduler_engine, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
