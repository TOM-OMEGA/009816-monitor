import os, sys, requests, logging
from flask import Flask
from datetime import datetime

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# 嘗試導入模組
try:
    from monitor_009816 import run_taiwan_stock
    from new_ten_thousand_grid import run_grid
    from us_post_market_robot import run_us_ai
except ImportError as e:
    logging.error(f"導入失敗: {e}")

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

@app.route("/")
def home():
    return f"""
    <div style="padding:50px; font-family:sans-serif;">
        <h1>🧪 Webhook 強制測試儀</h1>
        <p>目前的 Webhook: <code>{WEBHOOK[:20]}...{WEBHOOK[-5:] if WEBHOOK else ""}</code></p>
        <hr>
        <a href="/force_test" style="padding:10px 20px; background:red; color:white; text-decoration:none;">1. 強制發送測試訊息</a>
        <br><br><br>
        <a href="/force_run" style="padding:10px 20px; background:green; color:white; text-decoration:none;">2. 強制執行全模組 (網頁會轉圈很久，請等它)</a>
    </div>
    """

@app.route("/force_test")
def force_test():
    if not WEBHOOK: return "錯誤：環境變數沒有 WEBHOOK"
    try:
        payload = {"content": f"✅ Webhook 通訊測試成功！時間：{datetime.now()}"}
        r = requests.post(WEBHOOK, json=payload, timeout=10)
        return f"<h3>Discord 回應碼: {r.status_code}</h3><p>回應內容: {r.text}</p><a href='/'>返回</a>"
    except Exception as e:
        return f"<h3>發送發生異常</h3><p>{str(e)}</p><a href='/'>返回</a>"

@app.route("/force_run")
def force_run():
    """
    不使用 Thread，直接在 Request 裡跑。
    這會讓網頁轉圈圈直到跑完，但在偵錯階段這最有用。
    """
    if not WEBHOOK: return "無 Webhook"
    
    logs = []
    
    def quick_send(txt):
        try:
            res = requests.post(WEBHOOK, json={"content": txt}, timeout=10)
            logs.append(f"發送「{txt[:10]}...」: 狀態 {res.status_code}")
        except Exception as e:
            logs.append(f"發送失敗: {str(e)}")

    # 開始執行
    quick_send("🚀 [診斷模式] 任務開始...")
    
    # 依序執行，並將結果存入一個 list 顯示在網頁
    try:
        r1 = run_taiwan_stock()
        quick_send(f"台股結果: {r1}")
    except Exception as e:
        logs.append(f"台股崩潰: {e}")

    # 為了測試，我們先跑這兩項就好，避免網格跑太久導致 Render 切斷連線
    
    report_html = "<br>".join(logs)
    return f"<h2>執行紀錄</h2><div>{report_html}</div><a href='/'>返回</a>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
