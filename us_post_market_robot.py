import os
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import matplotlib
import time  # ✅ 補上原本缺失的導入
matplotlib.use('Agg')
import logging
logging.getLogger('matplotlib.font_manager').disabled = True

# ==== AI 模組 ====
try:
    from ai_expert import get_us_ai_point
except ImportError:
    get_us_ai_point = None

# ==== 中文字體設定 (保持不變) ====
def setup_chinese_font():
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    font_path = os.path.join(static_dir, "NotoSansTC-Regular.otf")
    if not os.path.exists(font_path):
        url = "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
        try:
            r = requests.get(url, timeout=45)
            r.raise_for_status()
            with open(font_path, 'wb') as f:
                f.write(r.content)
        except: return None
    try:
        fe = fm.FontEntry(fname=font_path, name='NotoSansTC')
        fm.fontManager.ttflist.append(fe)
        plt.rcParams['font.family'] = fe.name
        plt.rcParams['axes.unicode_minus'] = False
        return fm.FontProperties(fname=font_path)
    except: return None

# ==== 設定與技術指標 (保持不變) ====
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/period, adjust=False).mean()
    loss = -delta.where(delta < 0, 0).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, 1e-6)
    return 100 - (100 / (1 + rs))

def compute_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    return (exp1 - exp2) - (exp1 - exp2).ewm(span=9, adjust=False).mean()

def compute_bollinger(series, window=20, std_dev=2):
    ma = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    return ma + std*std_dev, ma, ma - std*std_dev

def fetch_data(symbol, period="30d"):
    try:
        return yf.Ticker(symbol).history(period=period, auto_adjust=True, timeout=10)
    except: return pd.DataFrame()

# ==== 圖表生成 ====
def plot_chart(dfs):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    font_prop = setup_chinese_font()
    if not font_prop: return None
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12,14), sharex=True, gridspec_kw={'height_ratios':[5,2,2]})
    main_sym = "^GSPC"
    colors = ['tab:blue','tab:orange','tab:green','tab:red']

    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        color = colors[i % len(colors)]
        name = TARGETS_MAP.get(symbol, symbol)
        norm = 100 / df['Close'].iloc[0]
        ax1.plot(df.index, df['Close']*norm, label=name, color=color)
        if symbol == main_sym:
            upper, ma, lower = compute_bollinger(df['Close'])
            ax1.fill_between(df.index, lower*norm, upper*norm, color='gray', alpha=0.1)
            hist = compute_macd(df['Close'])
            ax2.bar(df.index, hist, color=['red' if h>0 else 'green' for h in hist], alpha=0.7)
        rsi = compute_rsi(df['Close'])
        ax3.plot(df.index, rsi, label=name, color=color, linestyle='--')

    ax1.set_title("美股多維度決策儀表板", fontproperties=font_prop, fontsize=16)
    ax1.legend(loc='upper left', prop=font_prop)
    ax3.axhline(70, color='red', linestyle=':')
    ax3.axhline(30, color='green', linestyle=':')
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=120)
    plt.close()
    return PLOT_FILE

# ==== 報告生成 ====
def generate_report(dfs, ai_signal):
    us_eastern = timezone(timedelta(hours=-5))
    report_date = datetime.now(us_eastern).strftime("%Y-%m-%d")
    report = f"🌎 **美股盤後快報 [{report_date}]**\n"

    for symbol, df in dfs.items():
        if len(df) < 20: continue
        last = df['Close'].iloc[-1]; prev = df['Close'].iloc[-2]
        pct = (last/prev-1)*100
        rsi_val = compute_rsi(df['Close']).iloc[-1]
        
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        if ma5>ma20 and last>ma5: trend = "🟢 強勢"
        elif ma5<ma20 and last<ma5: trend = "🔴 空頭"
        else: trend = "🟡 震盪"
        
        name = TARGETS_MAP.get(symbol, symbol)
        report += f"• {name}: `{last:,.1f}` ({pct:+.2f}%) | RSI: `{rsi_val:.0f}` | {trend}\n"
    
    report += f"🤖 **AI 決策**: {ai_signal.get('decision', '分析中')}\n"
    return report

# ==== ✅ 標準入口（給 main.py 用）====
def run_us_ai():
    logging.info("🚀 開始美股分析任務...")
    dfs = {s: fetch_data(s) for s in TARGETS}
    dfs = {s: df for s, df in dfs.items() if not df.empty}
    
    if not dfs: 
        return "❌ 美股數據抓取失敗"

    ai_signal = {"decision": "觀望"}
    if get_us_ai_point:
        try:
            us_ai_data = {sym: {"last_close": df['Close'].iloc[-1]} for sym, df in dfs.items()}
            ai_signal = get_us_ai_point(extra_data=us_ai_data)
        except Exception as e:
            logging.error(f"AI 判斷異常: {e}")

    report = generate_report(dfs, ai_signal)
    
    # 僅生成圖片不發送，若需要發送圖片，需在 main.py 另行處理
    try:
        plot_chart(dfs)
        logging.info(f"✅ 圖表已生成於 {PLOT_FILE}")
    except Exception as e:
        logging.error(f"圖表生成失敗: {e}")

    return report
