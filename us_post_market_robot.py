# us_post_market_robot.py
import os
import requests
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

# ==== AI 模組 (確保 ai_expert.py 存在) ====
try:
    from ai_expert import get_us_ai_point
except ImportError:
    print("⚠️ 找不到 ai_expert 模組，AI 判斷功能將跳過")
    get_us_ai_point = None

# ==== 中文字體設定 (Linux/Render) ====
def setup_chinese_font():
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    font_path = os.path.join(static_dir, "NotoSansTC-Regular.otf")
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
        try:
            r = requests.get(url, timeout=30)
            with open(font_path, 'wb') as f:
                f.write(r.content)
            print("✅ 中文字體下載完成")
        except Exception as e:
            print(f"⚠️ 字體下載失敗: {e}")
            return
    try:
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['axes.unicode_minus'] = False
    except:
        print("⚠️ 字體設定失敗，可能出現中文亂碼")

setup_chinese_font()

# ==== 環境變數與設定 ====
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")
os.makedirs(STATIC_DIR, exist_ok=True)

# ==== 技術指標計算 ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-6)
    return 100 - (100 / (1 + rs))

def compute_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    dif = exp1 - exp2
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = dif - dea
    return dif, dea, hist

def compute_bollinger(series, window=20, std_dev=2):
    ma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = ma + std*std_dev
    lower = ma - std*std_dev
    return upper, ma, lower

# ==== 抓資料 ====
def fetch_data(symbol, period="30d"):
    df = yf.Ticker(symbol).history(period=period, auto_adjust=True)
    return df

# ==== 圖表生成 ====
def plot_chart(dfs):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12,14), sharex=True, gridspec_kw={'height_ratios':[5,2,2]})
    main_sym = TARGETS[0]
    colors = ['tab:blue','tab:orange','tab:green','tab:red']

    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        df = df.copy()
        color = colors[i % len(colors)]
        name = TARGETS_MAP.get(symbol, symbol)
        norm_price = (df['Close'] / df['Close'].iloc[0]) * 100
        ax1.plot(df.index, norm_price, label=name, color=color, linewidth=1.5)

        if symbol == main_sym:
            upper, ma, lower = compute_bollinger(df['Close'])
            ratio = 100 / df['Close'].iloc[0]
            ax1.plot(df.index, ma*ratio, color='gray', linestyle='--', alpha=0.5, label=f"{name} 20MA")
            ax1.fill_between(df.index, lower*ratio, upper*ratio, color='gray', alpha=0.1)
            _, _, hist = compute_macd(df['Close'])
            ax2.bar(df.index, hist, color=['red' if h>0 else 'green' for h in hist], alpha=0.7)
            ax2.set_title(f"{name} MACD 動能柱", fontsize=10)

        rsi = compute_rsi(df['Close'])
        ax3.plot(df.index, rsi, label=name, color=color, linewidth=1, linestyle='--')

    ax1.set_title("美股多維度決策儀表板", fontsize=16, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2); ax1.grid(True, alpha=0.3)
    ax2.grid(True, alpha=0.3)
    ax3.axhline(70, color='red', linestyle=':', alpha=0.6)
    ax3.axhline(30, color='green', linestyle=':', alpha=0.6)
    ax3.fill_between(df.index, 70, 100, color='red', alpha=0.05)
    ax3.fill_between(df.index, 0, 30, color='green', alpha=0.05)
    ax3.set_ylim(0,100)
    ax3.set_title("RSI 相對強弱熱度", fontsize=10)
    plt.xticks(rotation=45)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=120)
    plt.close()
    print(f"🖼 圖表已生成: {PLOT_FILE}")
    return PLOT_FILE

# ==== 報告生成 ====
def generate_report(dfs):
    report = "🦅 美股盤後快報 (含技術指標分析)\n========================\n"
    for symbol, df in dfs.items():
        last = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        pct = (last/prev-1)*100
        name = TARGETS_MAP.get(symbol, symbol)
        report += f"【{name}】 {last:,.2f} ({pct:+.2f}%)\n"
    return report

# ==== LINE 推播 ====
def push_line(report, plot_path=None):
    if not LINE_TOKEN or not USER_ID:
        print("⚠️ LINE 未設定，僅輸出報告")
        print(report)
        return

    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
    # 文字
    payload_text = {"to": USER_ID, "messages":[{"type":"text","text":report}]}
    try:
        res = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_text, timeout=15)
        if res.status_code==200: print("✅ LINE 文字推播成功")
        else: print(f"⚠️ LINE 文字推播失敗: {res.text}")
    except Exception as e:
        print(f"⚠️ LINE 推播錯誤: {e}")

    # 圖片
    if plot_path and os.path.exists(plot_path):
        base_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not base_url: return
        timestamp = int(datetime.now().timestamp())
        plot_url = f"{base_url}/static/plot.png?t={timestamp}"
        payload_img = {"to": USER_ID, "messages":[{"type":"image","originalContentUrl":plot_url,"previewImageUrl":plot_url}]}
        try:
            res = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_img, timeout=15)
            if res.status_code==200: print("✅ LINE 圖片推播成功")
            else: print(f"⚠️ LINE 圖片推播失敗: {res.text}")
        except Exception as e:
            print(f"⚠️ LINE 圖片推播錯誤: {e}")

# ==== 主程式 ====
def run_us_post_market():
    print("🚀 啟動美股盤後分析任務...")
    dfs = {}
    for s in TARGETS:
        df = fetch_data(s)
        if not df.empty:
            dfs[s] = df
    if not dfs:
        print("❌ 無法取得任何資料，任務終止")
        return

    report = generate_report(dfs)
    plot_path = plot_chart(dfs)

    # AI 判斷
    if get_us_ai_point:
        try:
            us_ai_data = {sym: {"last_close": df['Close'].iloc[-1]} for sym, df in dfs.items()}
            us_signal = get_us_ai_point(extra_data=us_ai_data, target_name="US_MARKET")
            report += f"\n🤖 AI 決策中心：{us_signal.get('decision')} (信心度 {us_signal.get('confidence')}%)"
        except Exception as e:
            print(f"⚠️ AI 判斷失敗: {e}")

    push_line(report, plot_path)
    print("✅ 美股儀表板任務完成")

# ==== 排程模式 ====
def schedule_job():
    import schedule, time
    run_time_tw = "05:05"
    schedule.every().day.at(run_time_tw).do(run_us_post_market)
    print(f"📅 排程啟動，每天 {run_time_tw} 執行")
    while True:
        schedule.run_pending()
        time.sleep(60)

# ==== 測試模式 ====
if __name__=="__main__":
    TEST_MODE = True
    if TEST_MODE:
        run_us_post_market()
    else:
        schedule_job()
