# main.py（Render 免費 Web Service，Discord 自動重試 + 限流延遲）
import os
import logging
import requests
from flask import Flask
from datetime import datetime
import json
import time

# =========================
# 導入 AI 模組
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
# Discord Webhook 安全發送（自動重試 3 次）
# =========================
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None

def send_discord_safe(msg: str, max_retries=3, delay_sec=5):
    """安全發送 Discord，訊息過長自動分段，遇 429 或失敗自動重試"""
    if not WEBHOOK:
        logging.error("❌ DISCORD_WEBHOOK_URL 未設定")
        return False

    max_len = 1900
    success = True

    for i in range(0, len(msg), max_len):
        part = msg[i:i+max_len]
        for attempt in range(1, max_retries+1):
            try:
                r = requests.post(WEBHOOK, json={"content": part}, timeout=15)
                if r.status_code == 429:
                    logging.warning(f"⚠️ Discord 限流 429，等待 {delay_sec} 秒後重試 ({attempt}/{max_retries})")
                    time.sleep(delay_sec)
                    continue
                elif r.status_code not in (200, 204):
                    logging.warning(f"⚠️ Discord 發送異常，狀態碼 {r.status_code}，重試 ({attempt}/{max_retries})")
                    time.sleep(delay_sec)
                    continue
                else:
                    logging.info(f"Discord status {r.status_code}")
                    break
            except Exception as e:
                logging.exception(f"Discord 發送失敗，重試 ({attempt}/{max_retries})")
                time.sleep(delay_sec)
        else:
            logging.error("❌ Discord 發送多次失敗，跳過")
            success = False
    return success

# =========================
# 手機測試輔助：回傳任務 URL
# =========================
def notify_mobile_run_url(route: str):
    base_url = os.environ.get("RENDER_EXTERNAL_URL")
    if not base_url:
        logging.warning("⚠️ 無法通知手機測試，RENDER_EXTERNAL_URL 未設定")
        return
    url = f"{base_url}{route}"
    send_discord_safe(f"📱 手機測試 URL：{url}")

# =========================
# 首頁
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

# =========================
# 任務安全包裝
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
# 台股存股
# =========================
@app.route("/run/tw")
def run_tw():
    notify_mobile_run_url("/run/tw")
    send_discord_safe("📊【台股存股 AI】開始分析")
    result = safe_run(run_taiwan_stock, "台股存股 AI")
    send_discord_safe(f"📊【台股存股 AI】結果\n{result}")
    return "OK"

# =========================
# 台股網格
# =========================
@app.route("/run/grid")
def run_grid_route():
    notify_mobile_run_url("/run/grid")
    send_discord_safe("🧱【台股網格 AI】開始分析")
    result = safe_run(run_grid, "台股網格 AI")
    send_discord_safe(f"🧱【台股網格 AI】結果\n{result}")
    return "OK"

# =========================
# 美股盤後
# =========================
@app.route("/run/us")
def run_us():
    notify_mobile_run_url("/run/us")
    send_discord_safe("🌎【美股盤後 AI】開始分析")
    result = safe_run(run_us_ai, "美股盤後 AI")
    send_discord_safe(f"🌎【美股盤後 AI】結果\n{result}")
    return "OK"

# =========================
# 全部一次
# =========================
@app.route("/run/all")
def run_all():
    notify_mobile_run_url("/run/all")
    send_discord_safe("🚀【AI 任務】全部執行")

    r1 = safe_run(run_taiwan_stock, "台股存股 AI")
    r2 = safe_run(run_grid, "台股網格 AI")
    r3 = safe_run(run_us_ai, "美股盤後 AI")

    send_discord_safe(
        "✅【AI 任務完成】\n"
        f"台股存股：{r1}\n\n"
        f"台股網格：{r2}\n\n"
        f"美股盤後：{r3}"
    )
    return "ALL DONE"

# =========================
# Render 啟動
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)