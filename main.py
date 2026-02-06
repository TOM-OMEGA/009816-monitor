# main.py（Render 免費 Web Service 專用）
import os
import logging
import requests
from flask import Flask
from datetime import datetime
import json

# =========================
# 導入你的 AI 模組（一次載入，避免 Render 卡死）
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

def send_discord(msg: str):
    """安全發送 Discord，訊息過長自動截斷"""
    if not WEBHOOK:
        logging.error("❌ DISCORD_WEBHOOK_URL 未設定")
        return False

    # Discord 單訊息上限 2000 字，分段處理
    max_len = 1900
    try:
        for i in range(0, len(msg), max_len):
            part = msg[i:i+max_len]
            r = requests.post(WEBHOOK, json={"content": part}, timeout=15)
            logging.info(f"Discord status {r.status_code}")
        return True
    except Exception:
        logging.exception("Discord 發送失敗")
        return False

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
# 執行任務安全包裝
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
    send_discord("📊【台股存股 AI】開始分析")
    result = safe_run(run_taiwan_stock, "台股存股 AI")
    send_discord(f"📊【台股存股 AI】結果\n{result}")
    return "OK"

# =========================
# 台股網格
# =========================
@app.route("/run/grid")
def run_grid_route():
    send_discord("🧱【台股網格 AI】開始分析")
    result = safe_run(run_grid, "台股網格 AI")
    send_discord(f"🧱【台股網格 AI】結果\n{result}")
    return "OK"

# =========================
# 美股盤後
# =========================
@app.route("/run/us")
def run_us():
    send_discord("🌎【美股盤後 AI】開始分析")
    result = safe_run(run_us_ai, "美股盤後 AI")
    send_discord(f"🌎【美股盤後 AI】結果\n{result}")
    return "OK"

# =========================
# 全部一次
# =========================
@app.route("/run/all")
def run_all():
    send_discord("🚀【AI 任務】全部執行")

    r1 = safe_run(run_taiwan_stock, "台股存股 AI")
    r2 = safe_run(run_grid, "台股網格 AI")
    r3 = safe_run(run_us_ai, "美股盤後 AI")

    send_discord(
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