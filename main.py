import os, sys, time, logging, json
from flask import Flask
from datetime import datetime

# --- 1. 環境設定與導入 ---
import matplotlib
matplotlib.use('Agg')
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 確保路徑正確
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from monitor_009816 import run_taiwan_stock
from new_ten_thousand_grid import run_grid
from us_post_market_robot import run_us_ai

app = Flask(__name__)

# =========================
# 執行任務安全包裝 (回傳原始字串)
# =========================
def safe_run(func, name):
    try:
        logging.info(f"🧪 偵錯模式啟動任務: {name}")
        start_time = time.time()
        result = func()
        duration = time.time() - start_time
        
        if isinstance(result, dict):
            result_str = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            result_str = str(result)
            
        return {
            "name": name,
            "content": result_str,
            "length": len(result_str),
            "time": round(duration, 2)
        }
    except Exception as e:
        err_msg = f"❌ {name} 執行崩潰: {str(e)}"
        return {"name": name, "content": err_msg, "length": len(err_msg), "time": 0}

# =========================
# 路由設定
# =========================
@app.route("/")
def home():
    return f"""
    <div style="font-family:sans-serif; padding:20px; max-width:600px; margin:auto;">
        <h1 style="color:#5865F2;">🦅 AI Manager 診斷後台</h1>
        <p><b>伺服器時間:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <hr>
        <div style="background:#eef; padding:15px; border-radius:10px; border:1px solid #ccd;">
            <h3>🔍 數據量測工具</h3>
            <p>點擊下方連結，將「只在網頁顯示數據」，不觸發 Discord，用於檢查字數：</p>
            <a href="/debug/all" style="display:inline-block; background:#5865F2; color:white; padding:10px 20px; text-decoration:none; border-radius:5px;">📊 檢視所有 AI 數據量</a>
        </div>
        <br>
        <p>👉 <a href="/run/all">🚀 正式執行 (發送 Discord)</a></p>
    </div>
    """

@app.route("/debug/all")
def debug_all():
    # 執行所有模組
    reports = [
        safe_run(run_taiwan_stock, "台股存股"),
        safe_run(run_grid, "台股網格"),
        safe_run(run_us_ai, "美股盤後")
    ]
    
    total_len = sum(r['length'] for r in reports)
    
    # 建立偵錯網頁
    html = f"""
    <body style="font-family:monospace; background:#1e1e1e; color:#d4d4d4; padding:20px;">
        <h1 style="color:#4ec9b0;">📊 AI 數據量分析報告</h1>
        <p>總計字數: <span style="color:#ce9178; font-size:1.5em;">{total_len}</span> / 2000 (Discord 單則上限)</p>
        <a href="/" style="color:#569cd6;">⬅ 返回首頁</a>
        <hr style="border-color:#333;">
    """
    
    for r in reports:
        color = "#9cdcfe" if r['length'] < 1000 else "#d16969"
        html += f"""
        <div style="margin-bottom:30px; border:1px solid #333; padding:15px;">
            <h2 style="color:#dcdcaa;">📍 {r['name']}</h2>
            <p>耗時: {r['time']}s | 字數: <span style="color:{color};">{r['length']}</span></p>
            <pre style="background:#000; padding:10px; border-radius:5px; overflow-x:auto; white-space:pre-wrap;">{r['content']}</pre>
        </div>
        """
    
    html += "</body>"
    return html

# =========================
# 正式執行路由保留
# =========================
@app.route("/run/all")
def run_all():
    # ... 這裡保持你原本的 Discord 發送邏輯 ...
    return "已觸發正式推播"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
