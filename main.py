# main.py（Render 免費 Web Service 專用）
import os
import logging
import requests
from flask import Flask
from datetime import datetime
import json
import time

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

def send_discord(msg: str = None, file_path: str = None):
    """安全發送 Discord，支援文字 + 附件 + 限流重試"""
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
                        retry = float(r.headers.get("Retry-After", 5))
                        logging.warning(f"⚠️ Discord 限流 429，等待 {retry} 秒重試 ({attempt+1}/5)")
                        time.sleep(retry)
                        continue
                    elif r.status_code not in (200, 204):
                        logging.warning(f"⚠️ Discord 發送異常，狀態碼 {r.status_code}")
                        time.sleep(2 ** attempt)
                        continue
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
                    retry = float(r.headers.get("Retry-After", 5))
                    logging.warning(f"⚠️ Discord 限流 429 圖片/檔案，等待 {retry} 秒重試 ({attempt+1}/5)")
                    time.sleep(retry)
                    continue
                elif r.status_code not in (200, 204):
                    logging.warning(f"⚠️ Discord 附件發送異常，狀態碼 {r.status_code}")
                    time.sleep(2 ** attempt)
                    continue
                logging.info(f"Discord 附件發送成功，狀態碼 {r.status_code}")
                break
            except Exception as e:
                wait = 2 ** attempt
                logging.warning(f"⚠️ Discord 附件發送失敗: {e}，等待 {wait} 秒後重試")
                time.sleep(wait)
        else:
            logging.error("❌ Discord 附件發送多次失敗，跳過")
            success = False

    return success

def save_and_send_file(content: str, prefix: str):
    """將內容存成文字檔，附上時間戳，然後透過 Discord 附件發送"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    logging.info(f"✅ 已將結果存成檔案 {filename}")
    send_discord(file_path=filename)
    os.remove(filename)
    logging.info(f"🗑 已刪除暫存檔 {filename}")

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
            result = json.dumps(result, ensure_ascii=False, indent=2)
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
    save_and_send_file(result, "tw_result")
    return "OK"

# =========================
# 台股網格
# =========================
@app.route("/run/grid")
def run_grid_route():
    send_discord("🧱【台股網格 AI】開始分析")
    result = safe_run(run_grid, "台股網格 AI")
    save_and_send_file(result, "grid_result")
    return "OK"

# =========================
# 美股盤後
# =========================
@app.route("/run/us")
def run_us():
    send_discord("🌎【美股盤後 AI】開始分析")
    result = safe_run(run_us_ai, "美股盤後 AI")
    save_and_send_file(result, "us_result")
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

    combined = f"台股存股：\n{r1}\n\n台股網格：\n{r2}\n\n美股盤後：\n{r3}"
    save_and_send_file(combined, "all_result")

    return "ALL DONE"

# =========================
# Render 啟動
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)