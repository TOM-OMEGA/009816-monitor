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

# ==== 引用 AI 模組 (請確保檔案存在) ====
try:
    from ai_expert import get_us_ai_point
except ImportError:
    print("⚠️ 找不到 ai_expert 模組，將跳過 AI 判斷功能")

# ==== 解決 Linux/Render 中文亂碼 ====
def setup_chinese_font():
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    font_path = os.path.join(static_dir, "NotoSansTC-Regular.otf")
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
        try:
            r = requests.get(url, timeout=30); f = open(font_path, 'wb'); f.write(r.content); f.close()
        except: return None
    try:
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['axes.unicode_minus'] = False
        return True
    except: return None

setup_chinese_font()

# ==== 環境變數與設定 ====
LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")
os.makedirs(STATIC_DIR, exist_ok=True)

# ==== 技術指標計算函數 ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
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
    upper = ma + (std * std_dev)
    lower = ma - (std * std_dev)
    return upper, ma, lower

# ==== 圖表生成 (三層儀表板) ====
def plot_chart(dfs):
    # 創建三層圖表：主圖(5)、MACD(2)、RSI(2)
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14), sharex=True, 
                                        gridspec_kw={'height_ratios': [5, 2, 2]})
    
    # 這裡選取第一個標的 (通常是大盤) 來畫布林通道與 MACD，避免線條太亂
    # 其他標的則畫在同一圖層對比
    main_sym = TARGETS[0] 
    
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
    
    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        df = df.copy()
        color = colors[i % len(colors)]
        name = TARGETS_MAP.get(symbol, symbol)
        
        # 1. 主圖：標準化價格
        norm_price = (df['Close'] / df['Close'].iloc[0]) * 100
        ax1.plot(df.index, norm_price, label=f"{name}", color=color, linewidth=1.5)
        
        # 如果是主要標的 (例如 S&P 500)，畫上布林通道趨勢 (以100為基準轉化)
        if symbol == main_sym:
            upper, ma, lower = compute_bollinger(df['Close'])
            # 轉化為標準化數值以匹配主圖比例
            ratio = 100 / df['Close'].iloc[0]
            ax1.plot(df.index, ma * ratio, color='gray', linestyle='--', alpha=0.5, label=f"{name} 20MA")
            ax1.fill_between(df.index, lower * ratio, upper * ratio, color='gray', alpha=0.1)

        # 2. 中圖：MACD 柱狀圖 (僅顯示主要標的動能)
        if symbol == main_sym:
            _, _, hist = compute_macd(df['Close'])
            ax2.bar(df.index, hist, color=['red' if h > 0 else 'green' for h in hist], alpha=0.7)
            ax2.set_title(f"{name} MACD 動能柱", fontsize=10)

        # 3. 下圖：RSI 對比
        rsi = compute_rsi(df['Close'])
        ax3.plot(df.index, rsi, label=name, color=color, linewidth=1, linestyle='--')

    # 介面裝飾
    ax1.set_title("美股多維度決策儀表板", fontsize=16, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2)
    ax1.grid(True, alpha=0.3)
    
    ax2.grid(True, alpha=0.3)
    
    ax3.axhline(70, color='red', linestyle=':', alpha=0.6)
    ax3.axhline(30, color='green', linestyle=':', alpha=0.6)
    ax3.fill_between(df.index, 70, 100, color='red', alpha=0.05)
    ax3.fill_between(df.index, 0, 30, color='green', alpha=0.05)
    ax3.set_ylim(0, 100)
    ax3.set_title("RSI 相對強弱熱度", fontsize=10)

    plt.xticks(rotation=45)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=120)
    plt.close()
    return PLOT_FILE

# ==== 其餘功能保持原樣 (省略部分重複邏輯以節省空間) ====
def fetch_data(symbol, period="30d"):
    return yf.Ticker(symbol).history(period=period, auto_adjust=True)

def generate_report(dfs):
    # ... (此處保留原本的 generate_report 邏輯)
    # [註：內容與您上傳的版本一致]
    report = "🦅 美股盤後快報 (含技術指標分析)\n========================\n"
    for symbol, df in dfs.items():
        last = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        pct = (last/prev-1)*100
        name = TARGETS_MAP.get(symbol, symbol)
        report += f"【{name}】 {last:,.2f} ({pct:+.2f}%)\n"
    return report

def push_line(report, plot_path):
    # ... (此處保留原本的 push_line 邏輯)
    pass

def run_us_post_market():
    print("🚀 啟動美股多維度分析任務...")
    dfs = {s: fetch_data(s) for s in TARGETS if not fetch_data(s).empty}
    if not dfs: return
    
    report = generate_report(dfs)
    plot_path = plot_chart(dfs)
    
    # 執行 AI 判斷 (傳入最新數據)
    us_ai_data = {sym: {"last_close": df['Close'].iloc[-1]} for sym, df in dfs.items()}
    try:
        us_signal = get_us_ai_point(extra_data=us_ai_data, target_name="US_MARKET")
        report += f"\n🤖 AI 決策中心：{us_signal.get('decision')} (信心度 {us_signal.get('confidence')}%)"
    except: pass
    
    push_line(report, plot_path)
    print("✅ 儀表板發送完成")

if __name__ == "__main__":
    run_us_post_market()
