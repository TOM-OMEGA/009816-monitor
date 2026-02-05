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

# ==== 引用 AI 模組 ====
from ai_expert import get_us_ai_point

# ==== 解決 Linux/Render 中文亂碼 ====
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
        except: return None
    try:
        fm.fontManager.addfont(font_path)
        plt.rcParams['font.family'] = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['axes.unicode_minus'] = False
        return True
    except: return None

setup_chinese_font()

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

def compute_macd(series):
    exp1 = series.ewm(span=12, adjust=False).mean()
    exp2 = series.ewm(span=26, adjust=False).mean()
    dif = exp1 - exp2
    dea = dif.ewm(span=9, adjust=False).mean()
    return dif - dea  # 回傳柱狀圖數值

def compute_bollinger(series):
    ma = series.rolling(window=20).mean()
    std = series.rolling(window=20).std()
    return ma + (std * 2), ma, ma - (std * 2)

# ==== 圖表生成 (三層儀表板) ====
def plot_chart(dfs):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 14), sharex=True, 
                                        gridspec_kw={'height_ratios': [5, 2, 2]})
    main_sym = "^GSPC" # 以標普500作為主要趨勢參考
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
    
    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        color = colors[i % len(colors)]
        name = TARGETS_MAP.get(symbol, symbol)
        
        # 1. 主圖：標準化價格 + 布林通道 (僅針對主標的)
        norm_ratio = 100 / df['Close'].iloc[0]
        ax1.plot(df.index, df['Close'] * norm_ratio, label=name, color=color, linewidth=1.5)
        
        if symbol == main_sym:
            upper, ma, lower = compute_bollinger(df['Close'])
            ax1.plot(df.index, ma * norm_ratio, color='gray', linestyle='--', alpha=0.4)
            ax1.fill_between(df.index, lower * norm_ratio, upper * norm_ratio, color='gray', alpha=0.1)

        # 2. 中圖：MACD (僅顯示主要標的動能)
        if symbol == main_sym:
            hist = compute_macd(df['Close'])
            ax2.bar(df.index, hist, color=['red' if h > 0 else 'green' for h in hist], alpha=0.7)
            ax2.set_title(f"{name} MACD 動能柱", fontsize=10)

        # 3. 下圖：RSI 
        rsi = compute_rsi(df['Close'])
        ax3.plot(df.index, rsi, label=name, color=color, linewidth=1, linestyle='--')

    ax1.set_title("美股多維度決策儀表板 (近30日)", fontsize=16, fontweight='bold')
    ax1.legend(loc='upper left', ncol=2)
    ax1.grid(True, alpha=0.3)
    ax3.axhline(70, color='red', linestyle=':', alpha=0.6)
    ax3.axhline(30, color='green', linestyle=':', alpha=0.6)
    ax3.set_ylim(0, 100)
    plt.xticks(rotation=45)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=120)
    plt.close()
    return PLOT_FILE

# ==== 文字報告 (詳細版) ====
def generate_report(dfs, ai_signal):
    us_eastern = timezone(timedelta(hours=-5))
    report_date = datetime.now(us_eastern).strftime("%Y-%m-%d")
    report = f"🦅 美股盤後快報 [{report_date}]\n"
    report += "========================\n"
    
    for symbol, df in dfs.items():
        if df.empty or len(df) < 20: continue
        last = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        pct = (last / prev - 1) * 100
        
        # 指標計算
        rsi_series = compute_rsi(df['Close'])
        rsi_val = rsi_series.iloc[-1]
        rebound_prob = max(0, min(100, 100 - rsi_val))
        
        # 動能分數
        closes = df['Close'].iloc[-4:]
        diffs = closes.diff().dropna()
        up_days = sum(1 for d in diffs if d > 0)
        down_days = sum(1 for d in diffs if d < 0)
        
        # 趨勢判斷
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        if ma5 > ma20 and last > ma5: trend_emoji = "🟢強勢多頭"
        elif ma5 > ma20: trend_emoji = "🟡多頭回檔"
        elif ma5 < ma20 and last < ma5: trend_emoji = "🔴強勢空頭"
        else: trend_emoji = "🟠空頭反彈"

        name = TARGETS_MAP.get(symbol, symbol)
        report += (
            f"【{name}】 {last:,.2f} ({pct:+.2f}%)\n"
            f"趨勢: {trend_emoji} | RSI: {rsi_val:.1f}\n"
            f"短線動能: 📈反彈{up_days*33:.0f}分 vs 📉下跌{down_days*33:.0f}分\n"
            f"機率試算: 反彈機率{rebound_prob:.0f}%\n"
            "------------------------\n"
        )
    
    # 整合 AI 決策
    report += f"🤖 AI 決策中心：{ai_signal.get('decision', '分析中')} "
    report += f"(信心度 {ai_signal.get('confidence', 0)}%)\n"
    report += f"原因: {ai_signal.get('reason', '無')}\n"
    
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
    report += f"\n(台灣時間 {now_tw} 發送)"
    return report

# ==== 執行與推播 ====
def run_us_post_market():
    print("🚀 啟動美股多維度分析任務...")
    dfs = {}
    for symbol in TARGETS:
        df = yf.Ticker(symbol).history(period="30d", auto_adjust=True)
        if not df.empty: dfs[symbol] = df
    
    if not dfs: return

    # 1. 取得 AI 訊號
    us_ai_data = {sym: {"last_close": df['Close'].iloc[-1]} for sym, df in dfs.items()}
    try:
        us_signal = get_us_ai_point(extra_data=us_ai_data, target_name="US_MARKET")
    except Exception as e:
        us_signal = {"decision": "觀望", "confidence": 0, "reason": f"AI模組異常: {e}"}

    # 2. 生成詳細報告與圖表
    report = generate_report(dfs, us_signal)
    plot_path = plot_chart(dfs)
    
    # 3. LINE 推播
    if LINE_TOKEN and USER_ID:
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        # 文字
        requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json={"to": USER_ID, "messages":[{"type":"text","text":report}]})
        # 圖片
        base_url = os.environ.get("RENDER_EXTERNAL_URL")
        if base_url:
            plot_url = f"{base_url}/static/plot.png?t={int(datetime.now().timestamp())}"
            requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json={"to": USER_ID, "messages":[{"type":"image","originalContentUrl":plot_url,"previewImageUrl":plot_url}]})
    
    print("✅ 任務完成")
    return us_signal

if __name__ == "__main__":
    run_us_post_market()
