import os, sys, time, logging, json, threading, requests
from flask import Flask
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = Flask(__name__)

# 延遲導入，避免啟動時卡死
from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

def send_to_discord(content):
    if not WEBHOOK:
        logging.error("❌ 未設定 DISCORD_WEBHOOK_URL")
        return
    
    # 檢查內容是否包含 Cloudflare 錯誤訊息 (預防發送垃圾訊息)
    if "<!DOCTYPE html>" in content or "Cloudflare" in content:
        content = "⚠️ 數據抓取失敗：受到 Cloudflare 防火牆阻擋，請稍後再試。"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {"content": f"## 🦅 AI 巡檢報告 [{now_str}]\n{content}"[:1990]}
    
    try:
        r = requests.post(WEBHOOK, json=payload, timeout=15)
        logging.info(f"📡 Discord 回應狀態: {r.status_code}")
        if r.status_code != 204:
            logging.error(f"❌ Discord 錯誤回應: {r.text}")
    except Exception as e:
        logging.error(f"❌ Discord 連線異常: {e}")

def run_all_tasks_and_send():
    logging.info("🚀 開始全自動巡檢...")
    
    # 執行任務並收集文字
    r1 = str(run_taiwan_stock())
    r2 = str(run_grid())
    r3 = str(run_us_ai())
    
    # 整合並修剪過長的 HTML (如果有的話)
    full_report = f"### 📈 台股存股\n{r1}\n\n### 🧱 台股網格\n{r2}\n\n### 🌎 美股分析\n{r3}"
    
    send_to_discord(full_report)

@app.route("/")
def home():
    return f"<h1>🦅 AI Manager</h1><p>Webhook: {'✅ OK' if WEBHOOK else '❌ Missing'}</p><a href='/run'>🚀 執行並推播</a>"

@app.route("/run")
def manual_run():
    threading.Thread(target=run_all_tasks_and_send).start()
    return "<h3>🚀 已啟動背景計算</h3><p>請於 2-3 分鐘後檢查 Discord。</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
