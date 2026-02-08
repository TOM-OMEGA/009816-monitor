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
# 核心任務：美股盤後總結
# =========================
def task_us_summary():
    """美股收盤後執行一次：建立今日情緒基調"""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dc_log(f"# 🌙 美股盤後總結報告\n時間: `{now_str}`")
    try:
        result = run_us_ai()
        if isinstance(result, tuple):
            dc_log(result[0], file_buf=result[1], filename="us_close.png")
        else:
            dc_log(result)
    except Exception as e:
        dc_log(f"⚠️ 美股分析失敗: {str(e)}")

# =========================
# 核心任務：台股盤中每3分鐘巡檢
# =========================
def task_taiwan_realtime_monitor():
    """台股開盤期間執行：每3分鐘告知點位與動作"""
    now_str = datetime.now().strftime("%H:%M:%S")
    logging.info(f"🚀 執行台股 3 分鐘即時監控... {now_str}")
    
    # 執行存股監控 (009816 等)
    try:
        res_tw = run_taiwan_stock()
        if isinstance(res_tw, tuple):
            # 只有當 AI 建議「買進」或點位到達時才發圖，否則發文字簡報節省流量
            dc_log(f"🕒 台股即時快報 ({now_str})\n{res_tw[0]}", file_buf=res_tw[1], filename="tw_realtime.png")
        else:
            dc_log(f"🕒 台股即時快報 ({now_str})\n{res_tw}")
    except Exception as e:
        logging.error(f"台股監控異常: {e}")

    # 執行網格監控 (點位提醒)
    try:
        res_grid = run_grid()
        if isinstance(res_grid, tuple):
            dc_log(res_grid[0], file_buf=res_grid[1], filename="grid_live.png")
        else:
            dc_log(res_grid)
    except Exception as e:
        logging.error(f"網格監控異常: {e}")

# =========================
# 自動化調度中心 (Background Engine)
# =========================
def scheduler_engine():
    """
    負責判斷現在該做什麼：
    1. 05:30 - 08:00 -> 執行美股總結 (每日一次)
    2. 09:00 - 13:35 -> 每三分鐘巡檢台股
    """
    last_us_date = ""
    logging.info("⚙️ 自動化調度引擎已啟動")
    
    while True:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        
        # A. 美股時段 (早上 5:30 後執行一次)
        if now.hour >= 5 and now.hour < 9:
            if last_us_date != current_date:
                task_us_summary()
                last_us_date = current_date
        
        # B. 台股時段 (09:00 - 13:35)
        elif (now.hour == 9) or (10 <= now.hour <= 12) or (now.hour == 13 and now.minute <= 35):
            # 只有週一到週五執行 (這部分可視需求加上 now.weekday() < 5)
            task_taiwan_realtime_monitor()
            time.sleep(180) # 核心：每 3 分鐘 (180秒) 執行一次
            continue # 跳過下方的 60 秒等待
            
        # C. 非交易時段 (每 10 分鐘檢查一次即可)
        else:
            if now.minute % 10 == 0:
                logging.info(f"💤 非交易時段待命中... ({now.strftime('%H:%M')})")
        
        time.sleep(60) # 每分鐘檢查一次時間狀態

# --- Flask 路由 ---
@app.route("/")
def index():
    return "<h1>🦅 AI Manager 24H 監控中</h1><p>自動化引擎運行中，台股時段每 3 分鐘巡檢。</p>"

@app.route("/run")
def manual_trigger():
    threading.Thread(target=task_taiwan_realtime_monitor).start()
    return "手動即時巡檢已觸發！"

if __name__ == "__main__":
    # 啟動自動化背景引擎
    threading.Thread(target=scheduler_engine, daemon=True).start()
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
