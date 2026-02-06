import os, sys, time, logging, json, threading, requests
from flask import Flask
from datetime import datetime

# --- 1. 基本設定 ---
import matplotlib
matplotlib.use('Agg')
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

app = Flask(__name__)
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None

def send_to_discord(content):
    if not WEBHOOK or not content: return
    # 切割訊息以防萬一
    for i in range(0, len(content), 1900):
        requests.post(WEBHOOK, json={"content": content[i:i+1900]}, timeout=15)

# =========================
# 核心背景任務
# =========================
def run_all_tasks_and_send():
    logging.info("🚀 開始背景全自動巡檢...")
    
    # 執行三個模組
    r1 = str(run_taiwan_stock())
    time.sleep(5) # 間隔避免 CPU 過載
    r2 = str(run_grid())
    time.sleep(5)
    r3 = str(run_us_ai())
    
    # 整合報告
    full_report = (
        f"## 🦅 AI 投資綜合報告 ({datetime.now().strftime('%m/%d %H:%M')})\n"
        f"### 📈 存股分析\n{r1}\n\n"
        f"### 🧱 網格監控\n{r2}\n\n"
        f"### 🌎 美股分析\n{r3}"
    )
    
    send_to_discord(full_report)
    logging.info("✅ 報告已推播至 Discord")

# =========================
# 路由設定
# =========================
@app.route("/")
def home():
    return "<h1>🦅 AI Manager Active</h1><p>點擊 <a href='/run'>/run</a> 啟動背景任務並推播至 Discord。</p>"

@app.route("/run")
def manual_run():
    threading.Thread(target=run_all_tasks_and_send).start()
    return "<h3>🚀 任務已啟動</h3><p>程式正在背景跑，預計 5 分鐘後 Discord 會收到報告。</p>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
