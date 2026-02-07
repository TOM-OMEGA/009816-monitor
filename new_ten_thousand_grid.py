import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from datetime import datetime, timezone, timedelta
import logging

# 強制 Agg 後端
import matplotlib
matplotlib.use('Agg')

# ================= 實驗參數 =================
TEST_CAPITAL = 10000  # 一萬元實驗資金
TARGETS = {
    "00929.TW": {"name": "00929 科技優息", "weight": 0.33},
    "2317.TW": {"name": "2317 鴻海", "weight": 0.34},
    "00878.TW": {"name": "00878 永續高股息", "weight": 0.33}
}

def compute_advanced_grid(df):
    """強化版：六維度趨勢矩陣與高精準指標計算"""
    close = df['Close']
    price = float(close.iloc[-1])
    
    # 1. 均線與布林通道
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    std = close.rolling(20).std()
    lower = ma20 - (std * 2)
    
    last_ma20 = ma20.iloc[-1]
    last_ma60 = ma60.iloc[-1]
    last_lower = lower.iloc[-1]
    
    # 2. RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.001)))).iloc[-1]
    
    # 3. 六維度趨勢引擎
    if price > last_ma20 > last_ma60:
        trend = "🔴 強勢多頭"
    elif last_ma20 > price > last_ma60:
        trend = "🍀 多頭回檔"
    elif price < last_ma20 < last_ma60 and price < last_lower:
        trend = "🔥 極度超跌"
    elif price < last_ma20 < last_ma60:
        trend = "🟢 強勢空頭"
    else:
        trend = "🟡 橫盤整理"
    
    # 4. ATR 動態間距
    tr = pd.concat([(df['High']-df['Low']), (df['High']-close.shift()).abs(), (df['Low']-close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    grid_buy = min(price - (atr * 0.8), last_lower)

    return {"price": price, "rsi": rsi, "trend": trend, "grid_buy": grid_buy}

def generate_grid_chart(dfs):
    """繪製網格動態分析圖 (漢化版)"""
    # 1. 解決中文亂碼關鍵設定
    plt.rcParams['font.sans-serif'] = ['Noto Sans CJK TC', 'Microsoft JhengHei', 'PingFang TC', 'Arial Unicode MS', 'DejaVu Sans', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False 
    
    fig = plt.figure(figsize=(12, 12))
    
    for i, (symbol, df) in enumerate(dfs.items()):
        ax = plt.subplot(len(dfs), 1, i+1)
        name = TARGETS[symbol]['name']
        plot_df = df.tail(60) # 顯示最近 60 天
        
        ma20 = plot_df['Close'].rolling(20).mean()
        std20 = plot_df['Close'].rolling(20).std()
        
        # 繪製布林通道與價格
        ax.plot(plot_df.index, plot_df['Close'], label='收盤價', lw=2.5, color='#1f77b4')
        ax.fill_between(plot_df.index, ma20-2*std20, ma20+2*std20, color='gray', alpha=0.1, label='布林通道')
        ax.plot(plot_df.index, ma20, color='orange', linestyle='--', alpha=0.8, label='月線 (MA20)')
        
        ax.set_title(f"📊 {name} 趨勢掃描", fontsize=14, fontweight='bold')
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3, linestyle=':')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    buf.seek(0)
    plt.close()
    return buf

def run_grid():
    tw_tz = timezone(timedelta(hours=8))
    now = datetime.now(tw_tz)
    
    # 標準化大標題格式
    report = [
        f"# 🦅 AI 萬元網格實驗報告",
        f"### 📅 報告日期： `{now:%Y-%m-%d %H:%M}`",
        f"### 💰 實驗總金： `{TEST_CAPITAL:,} TWD`",
        "---"
    ]
    
    dfs_all = {}
    for symbol, cfg in TARGETS.items():
        try:
            df = yf.download(symbol, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            data = compute_advanced_grid(df)
            dfs_all[symbol] = df
            
            alloc_per_grid = (TEST_CAPITAL * cfg['weight']) / 5
            suggested_shares = int(alloc_per_grid // data['grid_buy']) if data['grid_buy'] > 0 else 0
            
            report.append(f"## {cfg['name']} 📍")
            report.append(f"💵 **目前現價**： `{data['price']:.2f}`")
            report.append(f"🔍 **趨勢矩陣**： {data['trend']}")
            report.append(f"📈 **RSI 指標**： `{data['rsi']:.1f}`")
            report.append(f"🛡️ **補倉預計**： `{data['grid_buy']:.2f}`")
            report.append(f"⚡ **下單指令**： `買入 {suggested_shares} 股`")
            report.append("-" * 20)
            
        except Exception as e:
            logging.error(f"網格執行錯誤 {symbol}: {e}")

    report.append(f"# AI 狀態：監控中 🤖")
    
    img_buf = generate_grid_chart(dfs_all)
    # 使用 .strip() 確保訊息乾淨，觸發 Discord 大標題
    return "\n".join(report).strip(), img_buf
