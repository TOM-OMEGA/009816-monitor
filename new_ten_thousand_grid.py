import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from datetime import datetime, timezone, timedelta
import logging

# 強制 Agg 後端，確保在 Render 等伺服器環境運行穩定
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
    upper = ma20 + (std * 2)
    lower = ma20 - (std * 2)
    
    last_ma20 = ma20.iloc[-1]
    last_ma60 = ma60.iloc[-1]
    last_lower = lower.iloc[-1]
    last_upper = upper.iloc[-1]
    
    # 2. RSI (強弱指標)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + (gain / loss.replace(0, 0.001)))).iloc[-1]
    
    # 3. 六維度趨勢引擎
    if price > last_ma20 > last_ma60 and price > (last_ma20 * 1.02):
        trend = "🟢 強勢多頭 (利潤奔跑)"
    elif last_ma20 > price > last_ma60:
        trend = "🍀 多頭回檔 (分批佈局點)"
    elif price < last_ma20 < last_ma60 and price < last_lower:
        trend = "🔥 極度超跌 (左側機會)"
    elif price < last_ma20 < last_ma60:
        trend = "🔴 強勢空頭 (觀望避險)"
    elif price > last_ma60 and price < last_ma20:
        trend = "🟡 弱勢整理 (網格震盪)"
    else:
        trend = "🟠 空頭反彈 (謹慎試單)"
    
    # 4. ATR 動態網格間距 (計算最近 14 天波動)
    tr = pd.concat([
        (df['High'] - df['Low']), 
        (df['High'] - df['Close'].shift()).abs(), 
        (df['Low'] - df['Close'].shift()).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    
    # 動態補倉建議：若處於超跌或回檔區，補倉位設在布林下軌附近或現價減去 0.8 倍 ATR
    grid_buy = min(price - (atr * 0.8), last_lower)

    return {
        "price": price,
        "rsi": rsi,
        "trend": trend,
        "bb_lower": last_lower,
        "bb_upper": last_upper,
        "atr": atr,
        "grid_buy": grid_buy
    }

def generate_grid_chart(dfs):
    """繪製網格動態分析圖：包含價格、布林通道與成交量指標"""
    plt.figure(figsize=(12, 10))
    
    for i, (symbol, df) in enumerate(dfs.items()):
        ax = plt.subplot(3, 1, i+1)
        name = TARGETS[symbol]['name']
        
        plot_df = df.tail(40)
        ma20 = plot_df['Close'].rolling(20).mean()
        std20 = plot_df['Close'].rolling(20).std()
        
        # 繪製主線
        ax.plot(plot_df.index, plot_df['Close'], label='Price', lw=2, color='#1f77b4')
        ax.fill_between(plot_df.index, ma20-2*std20, ma20+2*std20, color='gray', alpha=0.15, label='BB Band')
        ax.plot(plot_df.index, ma20, color='orange', linestyle='--', alpha=0.7, label='MA20')
        
        ax.set_title(f"{name} Analysis (6-Wave Trend)", fontsize=11, fontweight='bold')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.2, linestyle=':')

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
    buf.seek(0)
    plt.close()
    return buf

def run_grid():
    tw_tz = timezone(timedelta(hours=8))
    now = datetime.now(tw_tz)
    
    report = [
        f"# 🦅 AI 萬元網格實驗報告 [{now:%Y-%m-%d}]",
        f"**實驗資金總額:** `{TEST_CAPITAL:,} TWD`",
        "=========================="
    ]
    
    dfs_all = {}
    for symbol, cfg in TARGETS.items():
        try:
            # 增加抓取長度以確保 MA60 計算準確
            df = yf.download(symbol, period="8mo", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            data = compute_advanced_grid(df)
            dfs_all[symbol] = df
            
            # 計算一萬元分配到該標的的預計每格買入金額
            alloc_total = TEST_CAPITAL * cfg['weight']
            per_grid = alloc_total / 5 # 假設分五層網格
            
            report.append(f"### 📍 {cfg['name']}")
            report.append(f"💰 現價: `{data['price']:.2f}` | **趨勢: {data['trend']}**")
            report.append(f"📊 RSI: `{data['rsi']:.1f}` | ATR(14): `{data['atr']:.2f}`")
            report.append(f"🛡️ 布林區間: `{data['bb_lower']:.2f}` - `{data['bb_upper']:.2f}`")
            report.append(f"📥 **動態補倉建議**: `{data['grid_buy']:.2f}` (預計投入: {per_grid:.0f}元)")
            report.append("-" * 25)
            
        except Exception as e:
            report.append(f"❌ {symbol} 分析失敗: {str(e)[:50]}")

    report.append(f"🤖 **經理人決策**: 六維度矩陣已完成掃描。")
    report.append(f"\n(台灣時間 {now:%H:%M} 即時分析)")
    
    img_buf = generate_grid_chart(dfs_all)
    return "\n".join(report), img_buf
