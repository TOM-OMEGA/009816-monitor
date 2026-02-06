# main.py
import os
import sys
import time
import threading
import requests
import logging
from flask import Flask, request
from datetime import datetime

# --- 1. 環境隔離與設定 ---
import matplotlib
matplotlib.use('Agg')
logging.getLogger('matplotlib.font_manager').disabled = True
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
app = Flask(__name__)

# --- 2. 交易時間判斷 ---
def is_market_open():
    now = datetime.now()
    # 台股交易時間：週一至週五 09:00 - 14:00
    if now.weekday() >= 5:
        return False
    return 9 <= now.hour <= 14

# --- 3. Discord webhook 發送（含簡單重試與 Retry-After 處理） ---
WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip() or None

def send_discord(content, max_retries=4):
    if not WEBHOOK:
        logging.error("DISCORD_WEBHOOK_URL 未設定，無法發送 Discord 訊息")
        return False
    payload = {"content": content}
    headers = {"Content-Type": "application/json"}
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(WEBHOOK, json=payload, headers=headers, timeout=10)
        except Exception as e:
            logging.exception("發送 Discord 時發生例外，準備重試")
            time.sleep(2 ** attempt)
            continue

        logging.info(f"Discord send status {resp.status_code} body {resp.text}")
        if resp.status_code in (200, 204):
            return True
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else (2 ** attempt)
            logging.warning(f"被限流 429，等待 {wait} 秒後重試")
            time.sleep(wait)
            continue
        if 500 <= resp.status_code < 600:
            logging.warning(f"Discord 伺服器錯誤 {resp.status_code}，稍後重試")
            time.sleep(2 ** attempt)
            continue
        # 其他 4xx 錯誤通常不可重試（例如 401/403）
        logging.error("Discord 回傳不可重試錯誤，停止重試")
        return False
    logging.error("達到最大重試次數，發送失敗")
    return False

# --- 4. Web 路由 ---
@app.route('/')
def home():
    now = datetime.now()
    webhook = os.environ.get('DISCORD_WEBHOOK_URL', '')
    webhook_check = f"✅ 已設定 (後 5 碼: ...{webhook[-5:]})" if webhook else "❌ 缺失 (請設定 DISCORD_WEBHOOK_URL)"
    return f"""
    <html>
        <head><title>AI Manager DC 控制台</title><meta charset="utf-8"></head>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6; max-width: 600px; margin: auto;">
            <h1 style="color: #5865F2;">🦅 AI Manager 控制面板</h1>
            <p style="background: #f4f4f4; padding: 10px; border-radius: 5px;">伺服器時間: <b>{now.strftime('%Y-%m-%d %H:%M:%S')}</b></p>
            <hr>
            <h3>系統狀態：</h3>
            <ul>
                <li>Discord Webhook: {webhook_check}</li>
                <li>市場監控: {'🟢 盤中巡檢中' if is_market_open() else '🔴 休市待機中'}</li>
            </ul>
            <hr>
            <p>👉 <a href="/trigger" style="display: inline-block; color: white; background: #5865F2; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">發送手動診斷測試</a></p>
            <p style="color: #d73a49; font-size: 0.85em;">⚠️ 提示：若出現 429 錯誤，請停止點擊並等待 5 分鐘。</p>
        </body>
    </html>
    """

@app.route('/trigger', methods=['GET', 'POST'])
def manual_trigger():
    try:
        # 可選擇從 query 或 header 讀取 token（若未設定 TRIGGER_SECRET，則不驗證）
        trigger_secret = os.environ.get("TRIGGER_SECRET", "").strip()
        if trigger_secret:
            token = request.args.get("token") or request.headers.get("X-Trigger-Token")
            if token != trigger_secret:
                return "❌ 未授權 (token 錯誤)", 401

        from monitor_009816 import run_009816_monitor
        logging.info("手動觸發診斷")
        result = run_009816_monitor(force_send=True)
        # 嘗試發送到 Discord（若有設定 webhook）
        send_discord(f"手動診斷結果：\n{result}")
        return f"""
        <div style="font-family: sans-serif; padding: 20px;">
            <h2>診斷結果</h2>
            <div style="background: #f0f0f0; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap;">{result}</div>
            <br><a href="/">⬅ 返回首頁</a>
        </div>
        """
    except Exception as e:
        logging.exception("手動觸發發生例外")
        return f"❌ 執行異常: {str(e)}", 500

# --- 5. 監控主迴圈（僅在 RUN_MONITOR=true 時啟動） ---
def monitor_loop():
    logging.info("背景線程已啟動，初次運行將等待 60 秒避開部署尖峰...")
    time.sleep(60)
    while True:
        try:
            if is_market_open():
                logging.info(f"執行自動巡檢任務 [{datetime.now().strftime('%H:%M:%S')}]")
                # 延遲導入以減少啟動時依賴
                from monitor_009816 import run_009816_monitor
                from new_ten_thousand_grid import run_unified_experiment

                # 執行主要網格策略
                run_unified_experiment()

                # 每 10 分鐘檢查一次（避免頻繁推播）
                time.sleep(600)
            else:
                # 非交易時段每 30 分鐘心跳檢查一次
                time.sleep(1800)
        except Exception as e:
            logging.exception("監控循環錯誤")
            time.sleep(120)

def start_monitor_thread_if_allowed():
    run_monitor = os.environ.get("RUN_MONITOR", "false").lower() == "true"
    if not run_monitor:
        logging.info("RUN_MONITOR 未啟用，未啟動背景監控")
        return

    # 嘗試避免在多 worker 環境下重複啟動：若 detect 到 gunicorn 的環境變數，仍建議在 Render 設定 workers=1
    gunicorn_present = any(k for k in os.environ.keys() if k.startswith("GUNICORN") or k == "GUNICORN_CMD_ARGS")
    if gunicorn_present:
        logging.info("偵測到 Gunicorn 相關環境變數，請確保在 Render 使用 --workers 1 以避免多重執行")
    # 啟動 daemon thread（在單 worker 或本地測試下會正常運作）
    t = threading.Thread(target=monitor_loop, daemon=True)
    t.start()
    logging.info("已啟動監控線程（daemon）")

if __name__ == "__main__":
    # 只有在直接以 python main.py 執行時才會走這段（Gunicorn 也會執行 __main__）
    start_monitor_thread_if_allowed()
    port = int(os.environ