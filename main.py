import os
import logging
import requests
from flask import Flask
from datetime import datetime
import json
import time

# =========================
# 導入你的 AI 模組
# =========================
from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

# =========================
# 基本設定
# =========================
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# =========================
# Discord Webhook
# =========================
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None

def send_discord(msg: str = None, file_path: str = None):
    """安全發送 Discord，支援文字 + 圖片，長訊息自動分段 + 重試"""
    if not WEBHOOK:
        logging.error("❌ DISCORD_WEBHOOK_URL 未設定")
        return False

    headers = {"Content-Type": "application/json"}
    
    # 發送文字訊息
    if msg:
        max_len = 1900
        for start in range(0, len(msg), max_len):
            part = msg[start:start+max_len]
            for attempt in range(5):
                try:
                    r = requests.post(WEBHOOK, json={"content": part}, timeout=15)
                    if r.status_code == 429:
                        retry = r.json().get("retry_after", 5)
                        logging.warning(f"⚠️ Discord 限流 429，等待 {retry} 秒重試 ({attempt+1}/5)")
                        time.sleep(retry)
                        continue
                    r.raise_for_status()
                    logging.info(f"✅ Discord 發送成功，狀態碼 {r.status_code}")
                    break
                except Exception as e:
                    wait = 2 ** attempt
                    logging.warning(f"⚠️ Discord 發送失敗: {e}，等待 {wait} 秒後重試")
                    time.sleep(wait)
            else:
                logging.error("❌ Discord 發送多次失敗，跳過此段訊息")
    
    # 發送圖片附件
    if file_path and os.path.exists(file_path):
        for attempt in range(5):
            try:
                with open(file_path, "rb") as f:
                    r = requests.post(WEBHOOK, files={"file": f}, timeout=30)
                if r.status_code == 429:
                    retry = r.json().get("retry_after", 5)
                    logging.warning(f"⚠️ Discord 限流 429 圖片，等待 {retry} 秒重試 ({attempt+1}/5)")
                    time.sleep(retry)
                    continue
                r.raise_for_status()
                logging.info(f"✅ Discord 圖片發送成功，狀態碼 {r.status_code}")
                break
            except Exception as e:
                wait = 2 ** attempt
                logging.warning(f"⚠️ Discord 圖片發送失敗: {e}，等待 {wait} 秒後重試")
                time.sleep(wait)
        else:
            logging.error("❌ Discord 圖片發送多次失敗，跳過")
    
    return True

# =========================
# 安全執行任務
# =========================
def safe_run(func, name):
    try:
        result = func()
        if isinstance(result, dict):
            result = json.dumps(result, ensure_ascii=False)
        return result
    except Exception as e:
        logging.exception(f"{name} 執行失敗")
        return f"❌ {name} 執行失敗: {str(e)}"

# =========================
# 路由
# =========================
@app.route("/")
def home():
    return f"""
    <h1>🦅 AI Manager (Render Free)</h1>
    <p>Server time: {datetime.now()}</p>
    <ul>
      <li><a href="/run/tw">台股存股 AI</a></li>
      <li><a href="/run/grid">台股網格 AI</a></li>
      <li><a href="/run/us">美股盤後 AI</a></li>
      <li><a href="/run/all">全部執行</a></li>
    </ul>
    """

@app.route("/run/tw")
def run_tw():
    send_discord("📊【台股存股 AI】開始分析")
    result = safe_run(run_taiwan_stock, "台股存股 AI")
    send_discord(f"📊【台股存股 AI】結果\n{result}")
    return "OK"

@app.route("/run/grid")
def run_grid_route():
    send_discord("🧱【台股網格 AI】開始分析")
    result = safe_run(run_grid, "台股網格 AI")
    send_discord(f"🧱【台股網格 AI】結果\n{result}")
    return "OK"

@app.route("/run/us")
def run_us():
    send_discord("🌎【美股盤後 AI】開始分析")
    # 回傳值中含圖片路徑
    result = safe_run(run_us_ai, "美股盤後 AI")
    plot_file = "static/plot.png"
    send_discord(f"🌎【美股盤後 AI】結果\n{result}", file_path=plot_file)
    return "OK"

@app.route("/run/all")
def run_all():
    send_discord("🚀【AI 任務】全部執行")

    r1 = safe_run(run_taiwan_stock, "台股存股 AI")
    r2 = safe_run(run_grid, "台股網格 AI")
    r3 = safe_run(run_us_ai, "美股盤後 AI")
    plot_file = "static/plot.png"

    send_discord(
        f"✅【AI 任務完成】\n台股存股：{r1}\n台股網格：{r2}\n美股盤後：{r3}",
        file_path=plot_file
    )
    return "ALL DONE"

# =========================
# Render 啟動
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)