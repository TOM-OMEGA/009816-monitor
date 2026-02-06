import os, sys, time, logging, json, threading
from flask import Flask
from datetime import datetime

# --- 1. 環境設定 ---
import matplotlib
matplotlib.use('Agg')
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 加入當前路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

app = Flask(__name__)
DEBUG_FILE = "debug_result.json"

# =========================
# 背景執行任務
# =========================
def background_task():
    results = []
    tasks = [
        (run_taiwan_stock, "台股存股"),
        (run_grid, "台股網格"),
        (run_us_ai, "美股盤後")
    ]
    
    for func, name in tasks:
        try:
            logging.info(f"⏳ 背景執行中: {name}")
            start = time.time()
            res = func()
            duration = time.time() - start
            results.append({
                "name": name, 
                "content": str(res), 
                "len": len(str(res)), 
                "time": f"{duration:.1f}s"
            })
        except Exception as e:
            results.append({"name": name, "content": f"出錯: {e}", "len": 0, "time": "0s"})
    
    # 存檔供網頁讀取
    with open(DEBUG_FILE, "w", encoding="utf-8") as f:
        json.dump({"updated": datetime.now().strftime("%H:%M:%S"), "data": results}, f, ensure_ascii=False)
    logging.info("✅ 所有任務背景執行完畢")

# =========================
# 路由設定
# =========================
@app.route("/")
def home():
    last_update = "尚未執行"
    if os.path.exists(DEBUG_FILE):
        with open(DEBUG_FILE, "r") as f:
            last_update = json.load(f).get("updated", "未知")

    return f"""
    <div style="font-family:sans-serif; padding:20px; max-width:600px; margin:auto;">
        <h1>🦅 AI Manager 診斷後台</h1>
        <p>最後更新時間: <b>{last_update}</b></p>
        <hr>
        <div style="background:#f9f9f9; padding:15px; border-radius:10px; border:1px solid #ddd;">
            <h3>第一步：觸發計算</h3>
            <p>點擊後會立即返回，程式會在背景跑（約需 1-2 分鐘）。</p>
            <a href="/trigger_debug" style="display:inline-block; background:#5865F2; color:white; padding:10px; text-decoration:none; border-radius:5px;">🚀 開始背景計算</a>
        </div>
        <br>
        <div style="background:#eef; padding:15px; border-radius:10px; border:1px solid #ccd;">
            <h3>第二步：檢視結果</h3>
            <p>若背景跑完，點擊此處可看內容與字數。</p>
            <a href="/view_debug" style="display:inline-block; background:#2ecc71; color:white; padding:10px; text-decoration:none; border-radius:5px;">📊 查看最新數據量</a>
        </div>
    </div>
    """

@app.route("/trigger_debug")
def trigger():
    threading.Thread(target=background_task).start()
    return "<h3>🚀 已啟動背景計算</h3><p>請等待約 1-2 分鐘後，回到首頁點擊「查看最新數據量」。</p><a href='/'>返回首頁</a>"

@app.route("/view_debug")
def view():
    if not os.path.exists(DEBUG_FILE):
        return "<h3>❌ 尚未有數據</h3><p>請先點擊觸發計算並稍等。</p><a href='/'>返回</a>"
    
    with open(DEBUG_FILE, "r", encoding="utf-8") as f:
        report = json.load(f)
    
    html = f"<body style='background:#1e1e1e; color:#ccc; padding:20px; font-family:monospace;'>"
    html += f"<h1>📊 數據診斷 (更新於: {report['updated']})</h1><a href='/'>⬅ 返回</a><hr>"
    
    total_len = sum(d['len'] for d in report['data'])
    html += f"<h3>總計字數: <span style='color:orange;'>{total_len}</span> / 2000</h3>"

    for d in report['data']:
        html += f"""
        <div style="border:1px solid #444; padding:10px; margin:20px 0;">
            <h3 style="color:#569cd6;">📍 {d['name']} ({d['time']})</h3>
            <p>字數: {d['len']}</p>
            <pre style="background:#000; padding:10px; white-space:pre-wrap;">{d['content']}</pre>
        </div>
        """
    return html + "</body>"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
