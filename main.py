import os
import logging
import requests
from flask import Flask, jsonify
from datetime import datetime
import json
import time

# =========================
# 導入你的 AI 模組
# =========================
from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai  # 已修改為 Discord 版本

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
    """安全發送 Discord，訊息過長自動分段 + 支援附件"""
    if not WEBHOOK:
        logging.error("❌ DISCORD_WEBHOOK_URL 未設定")
        return False

    success = True

    # 發送文字
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
                    logging.info(f"Discord 發送成功，狀態碼 {r.status_code}")
                    break
                except Exception as e:
                    wait = 2 ** attempt
                    logging.warning(f"⚠️ Discord 發送失敗: {e}，等待 {wait} 秒後重試")
                    time.sleep(wait)
            else:
                logging.error("❌ Discord 發送多次失敗，跳過此段訊息")
                success = False

    # 發送附件
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
                logging.info(f"Discord 圖片發送成功，狀態碼 {r.status_code}")
                break
            except Exception as e:
                wait = 2 ** attempt
                logging.warning(f"⚠️ Discord 圖片發送失敗: {e}，等待 {wait} 秒後重試")
                time.sleep(wait)
        else:
            logging.error("❌ Discord 圖片發送多次失敗，跳過")
            success = False

    return success

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
# 路由函式生成器（統一 JSON 回傳）
# =========================
def create_route(func, name, send_file=False):
    def route():
        message = f"🚀【{name}】開始分析"
        discord_ok = send_discord(message)

        result = safe_run(func, name)
        # 如果是 US AI，可能有圖片
        file_path = None
        if send_file and hasattr(func, "PLOT_FILE"):
            file_path = func.PLOT_FILE

        discord_ok &= send_discord(result, file_path=file_path)

        status = "success" if discord_ok else "fail"
        return jsonify({
            "status": status,
            "message": result,
            "discord_sent": discord_ok
        })
    return route

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
# 註冊路由
# =========================
app.add_url_rule("/run/tw", "run_tw", create_route(run_taiwan_stock, "台股存股 AI"))
app.add_url_rule("/run/grid", "run_grid", create_route(run_grid, "台股網格 AI"))
app.add_url_rule("/run/us", "run_us", create_route(run_us_ai, "美股盤後 AI", send_file=True))

@app.route("/run/all")
def run_all():
    results = {}
    discord_ok = send_discord("🚀【AI 任務】全部執行")

    r1 = safe_run(run_taiwan_stock, "台股存股 AI")
    results["台股存股 AI"] = r1
    r2 = safe_run(run_grid, "台股網格 AI")
    results["台股網格 AI"] = r2
    r3 = safe_run(run_us_ai, "美股盤後 AI")
    results["美股盤後 AI"] = r3

    # 對 US AI 加入附件
    file_path = getattr(run_us_ai, "PLOT_FILE", None)
    if file_path:
        discord_ok &= send_discord(r3, file_path=file_path)
    else:
        discord_ok &= send_discord(r3)

    status = "success" if discord_ok else "fail"
    return jsonify({
        "status": status,
        "message": results,
        "discord_sent": discord_ok
    })

# =========================
# Render 啟動
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)