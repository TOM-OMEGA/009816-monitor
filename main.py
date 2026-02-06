# main.py（Render 免費 Web Service 專用）
import os
import logging
import requests
from flask import Flask, request
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# =========================
# Discord Webhook
# =========================
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None

def send_discord(msg: str):
    if not WEBHOOK:
        logging.error("❌ DISCORD_WEBHOOK_URL 未設定")
        return False

    try:
        r = requests.post(
            WEBHOOK,
            json={"content": msg},
            timeout=10
        )
        logging.info(f"Discord status {r.status_code}")
        return r.status_code in (200, 204)
    except Exception as e:
        logging.exception("Discord 發送失敗")
        return False

# =========================
# 基本頁
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
# 台股存股
# =========================
@app.route("/run/tw")
def run_tw():
    from taiwan_stock_monitor import run_taiwan_stock

    send_discord("📊【台股存股 AI】開始分析")
    result = run_taiwan_stock()
    send_discord(f"📊【台股存股 AI】結果\n{result}")
    return "OK"

# =========================
# 台股網格
# =========================
@app.route("/run/grid")
def run_grid():
    from taiwan_grid_experiment import run_grid

    send_discord("🧱【台股網格 AI】開始分析")
    result = run_grid()
    send_discord(f"🧱【台股網格 AI】結果\n{result}")
    return "OK"

# =========================
# 美股盤後
# =========================
@app.route("/run/us")
def run_us():
    from us_market_ai import run_us_ai

    send_discord("🌎【美股盤後 AI】開始分析")
    result = run_us_ai()
    send_discord(f"🌎【美股盤後 AI】結果\n{result}")
    return "OK"

# =========================
# 全部一次
# =========================
@app.route("/run/all")
def run_all():
    send_discord("🚀【AI 任務】全部執行")

    from taiwan_stock_monitor import run_taiwan_stock
    from taiwan_grid_experiment import run_grid
    from us_market_ai import run_us_ai

    r1 = run_taiwan_stock()
    r2 = run_grid()
    r3 = run_us_ai()

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