import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from datetime import datetime, timedelta, timezone
import logging

# 強制 Agg 後端，避免 Render 環境報錯
import matplotlib
matplotlib.use('Agg')

# ==== 設定 ====
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())

def compute_indicators(df):
    """計算趨勢、RSI與動能分值"""
    close = df['Close']
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs))
    
    # 均線
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    
    last_price = close.iloc[-1]
    last_rsi = rsi.iloc[-1]
    last_ma20 = ma20.iloc[-1]
    last_ma60 = ma60.iloc[-1]
    
    # 趨勢判斷
    if last_price > last_ma20 > last_ma60: trend = "🟢強勢多頭"
    elif last_price < last_ma20 < last_ma60: trend = "🔴強勢空頭"
    elif last_price > last_ma60: trend = "🟡多頭回檔"
    else: trend = "🟡空頭反彈"
    
    # 動能與機率 (模擬機率算法)
    up_score = 66 if last_rsi < 40 else 33 if last_rsi > 60 else 50
    down_score = 100 - up_score
    prob = 100 - last_rsi # 簡單逆向機率邏輯
    
    return {
        "price": last_price,
        "rsi": last_rsi,
        "trend": trend,
        "up": up_score,
        "down": down_score,
        "prob": prob
    }

def generate_us_dashboard(dfs):
    """繪製如圖 1000012027 的多維度儀表板"""
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 16), gridspec_kw={'height_ratios': [2, 1, 1]})
    
    for symbol, df in dfs.items():
        name = TARGETS_MAP[symbol]
        # 標準化價格
        norm_close = df['Close'] / df['Close'].iloc[0] * 100
        ax1.plot(df.index, norm_close, label=name)
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.001))))
        ax3.plot(df.index, rsi, label=f"{name} RSI", linestyle='--')

    ax1.set_title("Market Relative Performance (Base 100)", fontsize=14)
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # MACD 動能柱 (以標普500為例)
    gspc_close = dfs["^GSPC"]['Close']
    exp1 = gspc_close.ewm(span=12, adjust=False).mean()
    exp2 = gspc_close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    colors = ['red' if h > 0 else 'green' for h in hist]
    ax2.bar(dfs["^GSPC"].index, hist, color=colors, alpha=0.7)
    ax2.set_title("S&P 500 MACD Momentum")
    
    ax3.axhline(70, color='r', linestyle=':', alpha=0.5)
    ax3.axhline(30, color='g', linestyle=':', alpha=0.5)
    ax3.set_title("RSI Relative Strength")
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

def run_us_ai():
    logging.info("🚀 啟動美股盤後分析任務...")
    dfs = {}
    trade_date = "" # 用於記錄數據中真正的交易日
    
    for s in TARGETS:
        df = yf.download(s, period="3mo", interval="1d", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            dfs[s] = df
            # 修正日期：以抓取的數據最後一筆 index 作為報告日期
            if not trade_date:
                trade_date = df.index[-1].strftime("%Y-%m-%d")
            
    if not dfs: return "❌ 數據抓取失敗", None

    # 台灣目前時間
    tw_now = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
    
    # 修正：在符號與文字間補空格，確保 Discord 觸發大字體渲染
    report = [
        f"# 🦅 美股盤後快報",
        f"### 📅 交易日期： `{trade_date}`", 
        "========================"
    ]
    
    for symbol in TARGETS:
        if symbol not in dfs: continue
        df = dfs[symbol]
        last_close = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2])
        pct = (last_close / prev_close - 1) * 100
        
        info = compute_indicators(df)
        name = TARGETS_MAP[symbol]
        
        # 修正：標題符號後補空格，數據內容使用粗體與大括號高亮
        report.append(f"## 📊 【{name}】")
        report.append(f"💵 **最新收盤**： `# {last_close:,.2f} #` ({pct:+.2f}%)")
        report.append(f"🔍 **趨勢狀態**： {info['trend']}")
        report.append(f"📈 **RSI 指標**： `{info['rsi']:.1f}`")
        report.append(f"🎯 **反彈機率**： `{info['prob']:.0f}%`")
        report.append("------------------------")
        
    report.append("# 🤖 AI 狀態：觀望中")
    report.append(f"發送時間：`{tw_now}`")
    
    img_buf = generate_us_dashboard(dfs)
    
    return "\n".join(report), img_buf
