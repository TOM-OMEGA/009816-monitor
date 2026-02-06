# us_post_market_robot.py
import os
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

# ==== 強制設定：防止伺服器環境卡死 ====
# 1. 先設定後端為 Agg (無介面模式)
import matplotlib
matplotlib.use('Agg') 
# 2. 禁用字體管理員的囉唆日誌
import logging
logging.getLogger('matplotlib.font_manager').disabled = True
# ===================================

# ==== AI 模組 (確保 ai_expert.py 存在) ====
try:
    from ai_expert import get_us_ai_point
except ImportError:
    print("⚠️ 找不到 ai_expert 模組，AI 判斷功能將跳過")
    get_us_ai_point = None

# ==== 中文字體設定 (優化：延遲載入並明確指定路徑) ====
def setup_chinese_font():
    # 💡 關鍵修改：將重量級引用移入函式內 (Lazy Import)
    # 避免在 main.py 啟動時就佔用大量記憶體
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt

    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    font_path = os.path.join(static_dir, "NotoSansTC-Regular.otf")
    
    # 1. 檢查並下載字體 (加上 Timeout 防止卡死)
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
        try:
            print("📥 正在下載中文字體以解決亂碼問題...")
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            with open(font_path, 'wb') as f:
                f.write(r.content)
            print("✅ 中文字體下載完成")
        except Exception as e:
            print(f"⚠️ 字體下載失敗: {e}")
            return None

    # 2. 註冊字體
    try:
        fe = fm.FontEntry(fname=font_path, name='NotoSansTC')
        fm.fontManager.ttflist.append(fe)
        plt.rcParams['font.family'] = fe.name
        plt.rcParams['axes.unicode_minus'] = False # 解決負號亂碼
        return fm.FontProperties(fname=font_path)
    except Exception as e:
        print(f"⚠️ 字體設定異常: {e}")
        return None

# ==== 環境變數與設定 ====
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")
os.makedirs(STATIC_DIR, exist_ok=True)

# ==== 技術指標計算 (不變) ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-6)
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    dif = exp1 - exp2
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif - dea

def compute_bollinger(series, window=20, std_dev=2):
    ma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    return ma + std*std_dev, ma, ma - std*std_dev

def fetch_data(symbol, period="30d"):
    # 增加 timeout 防止 yfinance 卡死
    try:
        return yf.Ticker(symbol).history(period=period, auto_adjust=True, timeout=10)
    except Exception as e:
        print(f"⚠️ 無法抓取 {symbol}: {e}")
        return pd.DataFrame()

# ==== 圖表生成 (修正：傳入 font_prop 解決亂碼) ====
def plot_chart(dfs):
    # 💡 關鍵修改：將繪圖引用移入函式內
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    
    # 取得字體屬性
    font_prop = setup_chinese_font()
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12,14), sharex=True, gridspec_kw={'height_ratios':[5,2,2]})
    main_sym = "^GSPC"
    colors = ['tab:blue','tab:orange','tab:green','tab:red']

    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        color = colors[i % len(colors)]
        name = TARGETS_MAP.get(symbol, symbol)
        
        norm_ratio = 100 / df['Close'].iloc[0]
        ax1.plot(df.index, df['Close'] * norm_ratio, label=name, color=color, linewidth=1.5)

        if symbol == main_sym:
            upper, ma, lower = compute_bollinger(df['Close'])
            ax1.plot(df.index, ma*norm_ratio, color='gray', linestyle='--', alpha=0.5, label=f"{name} 20MA")
            ax1.fill_between(df.index, lower*norm_ratio, upper*norm_ratio, color='gray', alpha=0.1)
            
            hist = compute_macd(df['Close'])
            ax2.bar(df.index, hist, color=['red' if h>0 else 'green' for h in hist], alpha=0.7)
            ax2.set_title(f"{name} MACD 動能柱", fontproperties=font_prop, fontsize=10)

        rsi = compute_rsi(df['Close'])
        ax3.plot(df.index, rsi, label=name, color=color, linewidth=1, linestyle='--')

    # 設定標題與標籤 (明確傳入字體屬性)
    ax1.set_title("美股多維度決策儀表板", fontproperties=font_prop, fontsize=16, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2, prop=font_prop)
    ax1.grid(True, alpha=0.3)
    
    ax3.axhline(70, color='red', linestyle=':', alpha=0.6)
    ax3.axhline(30, color='green', linestyle=':', alpha=0.6)
    ax3.set_ylim(0,100)
    ax3.set_title("RSI 相對強弱熱度", fontproperties=font_prop, fontsize=10)
    
    plt.xticks(rotation=45)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=120)
    plt.close()
    return PLOT_FILE

# ==== 報告生成 (不變) ====
def generate_report(dfs, ai_signal):
    us_eastern = timezone(timedelta(hours=-5))
    report_date = datetime.now(us_eastern).strftime("%Y-%m-%d")
    report = f"🦅 美股盤後快報 [{report_date}]\n"
    report += "========================\n"
    
    for symbol, df in dfs.items():
        if len(df) < 20: continue
        last = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        pct = (last/prev-1)*100
        
        rsi_series = compute_rsi(df['Close'])
        rsi_val = rsi_series.iloc[-1]
        rebound_prob = max(0, min(100, 100 - rsi_val))
        
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        if ma5>ma20 and last>ma5: trend = "🟢強勢多頭"
        elif ma5>ma20: trend = "🟡多頭回檔"
        elif ma5<ma20 and last<ma5: trend = "🔴強勢空頭"
        else: trend = "🟠空頭反彈"

        name = TARGETS_MAP.get(symbol, symbol)
        report += (f"【{name}】 {last:,.2f} ({pct:+.2f}%)\n"
                   f"趨勢: {trend} | RSI: {rsi_val:.1f}\n"
                   f"機率試算: 反彈機率{rebound_prob:.0f}%\n"
                   "------------------------\n")
    
    report += f"🤖 AI 決策：{ai_signal.get('decision', '分析中')}\n"
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
    report += f"(台灣時間 {now_tw} 發送)"
    return report

# ==== LINE 推播 (優化渲染 URL) ====
def push_line(report, plot_path=None):
    if not LINE_TOKEN or not USER_ID: 
        print("⚠️ 無法推播：LINE_TOKEN 或 USER_ID 未設定")
        return

    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    
    # 傳送文字
    try:
        requests.post("https://api.line.me/v2/bot/message/push", 
                      headers=headers, 
                      json={"to": USER_ID, "messages":[{"type":"text","text":report}]}, 
                      timeout=15)
    except Exception as e:
        print(f"❌ LINE 文字推播失敗: {e}")

    # 傳送圖片 (Render 專用)
    if plot_path and os.path.exists(plot_path):
        base_url = os.environ.get("RENDER_EXTERNAL_URL")
        if base_url:
            plot_url = f"{base_url}/static/plot.png?t={int(datetime.now().timestamp())}"
            try:
                requests.post("https://api.line.me/v2/bot/message/push", 
                              headers=headers, 
                              json={"to": USER_ID, "messages":[{"type":"image","originalContentUrl":plot_url,"previewImageUrl":plot_url}]}, 
                              timeout=15)
            except Exception as e:
                print(f"❌ LINE 圖片推播失敗: {e}")

# ==== 主任務 ====
def run_us_post_market():
    print("🚀 啟動美股盤後分析任務...")
    # 確保字體環境
    setup_chinese_font()
    
    dfs = {s: fetch_data(s) for s in TARGETS}
    dfs = {s: df for s, df in dfs.items() if not df.empty}
    if not dfs: 
        print("⚠️ 無法取得美股數據，任務結束")
        return

    ai_signal = {"decision": "觀望", "confidence": 0}
    if get_us_ai_point:
        try:
            us_ai_data = {sym: {"last_close": df['Close'].iloc[-1]} for sym, df in dfs.items()}
            ai_signal = get_us_ai_point(extra_data=us_ai_data, target_name="US_MARKET")
        except Exception as e: print(f"⚠️ AI 判斷失敗: {e}")

    report = generate_report(dfs, ai_signal)
    plot_path = plot_chart(dfs)
    push_line(report, plot_path)
    print("✅ 美股分析任務完成")

def schedule_job():
    import schedule, time
    run_time = "05:05" 
    schedule.every().day.at(run_time).do(run_us_post_market)
    print(f"📅 [美股排程] 已掛載，基準時間: {run_time}")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ================= 標準入口（給 main.py 用） =================
def run_us_ai():
    """
    統一給主控程式呼叫的入口（美股收盤 AI）
    """
    return run_unified_experiment()


# 允許單獨執行（本地或 Render 測試用）
if __name__ == "__main__":
    print(run_us_ai())