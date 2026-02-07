import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import os
from datetime import datetime, timedelta, timezone
import logging

# 強制 Agg 後端
import matplotlib
matplotlib.use('Agg')

# =====================
# 🛠️ 終極中文字體與符號解決方案
# =====================
def setup_chinese_font():
    # 確保名稱與你上傳到 GitHub 的 NotoSansTC-Regular.ttf 完全一致
    font_filename = "NotoSansTC-Regular.ttf"
    font_path = os.path.join(os.getcwd(), font_filename)
    
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        # 設定回援機制：優先使用 Noto Sans TC，符號則由 DejaVu Sans 補位
        plt.rcParams['font.family'] = [font_name, 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False 
        logging.info(f"✅ 美股模組：成功載入本地字體 {font_name}")
    else:
        logging.error(f"❌ 美股模組：找不到字體檔 {font_filename}")

# 初始化字體
setup_chinese_font()

# ==== 設定 ====
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())

def compute_indicators(df):
    """計算趨勢、RSI與波動預期"""
    close = df['Close']
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs))
    
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    last_price = float(close.iloc[-1])
    
    # 趨勢燈號校正
    if last_price > ma20.iloc[-1] > ma60.iloc[-1]: 
        trend = "🔴 強勢多頭"
    elif last_price < ma20.iloc[-1] < ma60.iloc[-1]: 
        trend = "🟢 強勢空頭"
    elif last_price > ma60.iloc[-1]: 
        trend = "🟡 多頭回檔"
    else: 
        trend = "🟡 空頭反彈"
    
    # 計算波動區間
    returns = np.log(close / close.shift(1))
    volatility = returns.std() * np.sqrt(5)
    range_up = last_price * (1 + volatility)
    range_down = last_price * (1 - volatility)
    
    return {
        "price": last_price,
        "rsi": float(rsi.iloc[-1]),
        "trend": trend,
        "prob": 100 - float(rsi.iloc[-1]),
        "range": (range_down, range_up)
    }

def generate_us_dashboard(dfs):
    """繪製美股多維度決策儀表板 (純淨文字版 - 移除 Emoji)"""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 16), gridspec_kw={'height_ratios': [2, 1, 1]})
    
    for symbol, df in dfs.items():
        name = TARGETS_MAP[symbol]
        norm_close = df['Close'] / df['Close'].iloc[0] * 100
        ax1.plot(df.index, norm_close, label=name, linewidth=2.5)
        
        # RSI 曲線
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
        ax3.plot(df.index, rsi, label=f"{name}", alpha=0.8)

    # 修改點：移除圖表標題內的 📊, 📈, 🔥 符號，確保 Render 環境文字渲染完全正確
    ax1.set_title("市場指數相對表現 (基準 100)", fontsize=18, fontweight='bold', pad=20)
    ax1.legend(loc='upper left', fontsize=12)
    ax1.grid(True, linestyle='--', alpha=0.5)
    
    # S&P 500 MACD
    gspc_close = dfs["^GSPC"]['Close']
    exp1 = gspc_close.ewm(span=12, adjust=False).mean()
    exp2 = gspc_close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    colors = ['#ff4d4d' if h > 0 else '#2ecc71' for h in hist]
    ax2.bar(dfs["^GSPC"].index, hist, color=colors, alpha=0.8, width=0.8)
    ax2.set_title("標普 500 市場動能 (MACD)", fontsize=16, fontweight='bold')
    ax2.grid(True, axis='y', alpha=0.3)
    
    # RSI 熱力
    ax3.axhline(70, color='#ff4d4d', linestyle='--', linewidth=1.5)
    ax3.axhline(30, color='#2ecc71', linestyle='--', linewidth=1.5)
    ax3.set_title("RSI 強弱熱度掃描", fontsize=16, fontweight='bold')
    ax3.set_ylim(0, 100)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=180, bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

def run_us_ai():
    dfs = {}
    trade_date = "" 
    
    for s in TARGETS:
        try:
            # 抓取數據 (往前看一年以利精確分析)
            df = yf.download(s, period="1y", interval="1d", progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                dfs[s] = df
                if not trade_date:
                    trade_date = df.index[-1].strftime("%Y-%m-%d")
        except Exception as e:
            logging.error(f"抓取 {s} 失敗: {e}")
            
    if not dfs: return "❌ 數據抓取失敗", None

    tw_now = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
    
    report = [
        "# 美股盤後快報 🦅",
        f"### 📅 交易日期： `{trade_date}`",
        "---"
    ]
    
    for symbol in TARGETS:
        if symbol not in dfs: continue
        df = dfs[symbol]
        info = compute_indicators(df)
        name = TARGETS_MAP[symbol]
        last_close = info['price']
        prev_close = float(df['Close'].iloc[-2])
        pct = (last_close / prev_close - 1) * 100
        
        report.append(f"## {name} 📊")
        report.append(f"💵 **最新收盤**： `{last_close:,.2f}` (**{pct:+.2f}%**)")
        report.append(f"🔍 **趨勢狀態**： {info['trend']}")
        report.append(f"📈 **RSI 指標**： `{info['rsi']:.1f}`")
        
        if symbol == "TSM":
            low, high = info['range']
            report.append(f"🎯 **反彈機率**： `{info['prob']:.0f}%`")
            report.append(f"🛡️ **下週預期**： `${low:.1f}` ~ `${high:.1f}`")
        else:
            report.append(f"🎯 **反彈機率**： `{info['prob']:.0f}%`")
            
        report.append("-" * 15)
        
    report.append(f"# AI 狀態：系統運行中 🤖")
    report.append(f"發送時間：`{tw_now} (UTC+8)`")
    report.append("---")
    # 修改點：在報告末尾加入 Discord 專用圖表生成提示，讓文字與圖案各司其職
    report.append(f"📈 **美股多維度決策儀表板已生成，請參閱下方附件**")
    
    img_buf = generate_us_dashboard(dfs)
    return "\n".join(report).strip(), img_buf
