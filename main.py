import os, sys, time, logging, requests, json
from flask import Flask
from datetime import datetime

# --- 1. 環境設定與導入 ---
import matplotlib
matplotlib.use('Agg')
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 延遲導入確保模組安全
from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

app = Flask(__name__)
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None

# =========================
# 核心：整合發送函式 (防 429 版本)
# =========================
def send_discord_unified(title: str, content: str):
    if not WEBHOOK:
        logging.error("❌ DISCORD_WEBHOOK_URL 未設定")
        return False

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 建立 Markdown 格式報告
    full_message = f"# 🦅 {title}\n**執行時間:** `{now_str}`\n\n{content}"

    # Discord 單則上限 2000 字，設定 1900 為安全切割線
    max_len = 1900
    success = True
    
    # 針對超長內容進行自動切割發送
    for start in range(0, len(full_message), max_len):
        part = full_message[start:start+max_len]
        # 指數型退避重試
        for attempt in range(5):
            try:
                r = requests.post(WEBHOOK, json={"content": part}, timeout=20)
                if r.status_code == 429:
                    retry_after = float(r.headers.get("Retry-After", 5))
                    logging.warning(f"⚠️ Discord 限流，等待 {retry_after} 秒...")
                    time.sleep(retry_after + 0.5)
                    continue
                elif r.status_code in (200, 204):
                    logging.info("✅ 訊息段落發送成功")
                    break
                else:
                    logging.warning(f"⚠️ 異常碼 {r.status_code}, 重試中...")
                    time.sleep(2 ** attempt)
            except Exception as e:
                logging.error(f"❌ 發送異常: {e}")
                time.sleep(2 ** attempt)
        else:
            success = False
            
    return success

# =========================
# 執行任務安全包裝
# =========================
def safe_run(func, name):
    try:
        logging.info(f"🚀 啟動任務: {name}")
        result = func()
        if isinstance(result, dict):
            return json.dumps(result, ensure_ascii=False, indent=2)
        return str(result)
    except Exception as e:
        logging.exception(f"{name} 執行崩潰")
        return f"❌ {name} 執行失敗: {str(e)[:50]}"

# =========================
# 路由 (整合測試與執行)
# =========================
@app.route("/")
def home():
    webhook_status = "✅ 已連結" if WEBHOOK else "❌ 缺失"
    return f"""
    <div style="font-family:sans-serif; padding:20px; max-width:500px; margin:auto; line-height:1.6;">
        <h1 style="color:#5865F2;">🦅 AI Manager Pro</h1>
        <p><b>Server Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><b>Webhook Status:</b> {webhook_status}</p>
        <hr>
        <div style="background:#f4f4f4; padding:15px; border-radius:10px;">
            <p>👉 <a href="/run/all" style="display:block; text-align:center; background:#5865F2; color:white; padding:12px; text-decoration:none; border-radius:5px; font-weight:bold;">🚀 執行全部任務 (整合推播)</a></p>
            <p style="font-size:0.85em; color:#666; text-align:center;">此操作將整合「台股存股+網格+美股」並發送單一報告</p>
        </div>
    </div>
    """

@app.route("/run/all")
def run_all():
    # 1. 逐一執行並收集
    res_tw = safe_run(run_taiwan_stock, "台股存股")
    res_grid = safe_run(run_grid, "台股網格")
    res_us = safe_run(run_us_ai, "美股盤後")

    # 2. 拼接 Markdown 內容 (使用 ``` 讓數據對齊)
    combined_report = (
        "### 📈 台股存股分析\n```\n" + res_tw + "\n```\n"
        "### 🧱 台股網格監控\n```\n" + res_grid + "\n```\n"
        "### 🌎 美股盤後 AI\n```\n" + res_us + "\n```"
    )

    # 3. 單一請求發送
    if send_discord_unified("AI 綜合投資報告", combined_report):
        return "<h3>✅ 任務全數執行成功</h3><p>請前往 Discord 頻道查收報告。</p><br><a href='/'>返回</a>"
    else:
        return "<h3>⚠️ 執行完成但推播異常</h3><p>請檢查 Render Logs 確認 429 狀況。</p><br><a href='/'>返回</a>"

# =========================
# Render 啟動
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
