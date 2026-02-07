import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import io
import os
from datetime import datetime, timezone, timedelta
import logging

# 強制 Agg 後端
import matplotlib
matplotlib.use('Agg')

# =====================
# 🛠️ 終極中文字體與符號解決方案
# =====================
def setup_chinese_font():
    # 確保 NotoSansTC-Regular.ttf 已經上傳到 GitHub 根目錄
    font_filename = "NotoSansTC-Regular.ttf"
    font_path = os.path.join(os.getcwd(), font_filename)
    
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        # 設定回援機制：優先使用 Noto Sans TC，符號（Emoji）則由 DejaVu Sans 補位顯現
        plt.rcParams['font.family'] = [font_name, 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False 
        logging.info(f"✅ 網格模組：成功載入字體 {font_name} 及其符號回援機制")
    else:
        logging.error(f"❌ 網格模組：找不到字體檔 {font_filename}")

# 初始化字體設定
setup_chinese_font()

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
    """繪製網格動態分析圖 (專業文字版 - 移除 Emoji)"""
    fig = plt.figure(figsize=(12, 12))
    
    for i, (symbol, df) in enumerate(dfs.items()):
        ax = plt.subplot(len(dfs), 1, i+1)
        name = TARGETS[symbol]['name']
        plot_df = df.tail(60) # 顯示最近 60 天細節
        
        ma20 = plot_df['Close'].rolling(20).mean()
        std20 = plot_df['Close'].rolling(20).std()
        
        # 繪製價格與布林通道
        ax.plot(plot_df.index, plot_df['Close'], label='收盤價', lw=2.5, color='#1f77b4')
        ax.fill_between(plot_df.index, ma20-2*std20, ma20+2*std20, color='gray', alpha=0.1, label='布林通道')
        ax.plot(plot_df.index, ma20, color='orange', linestyle='--', alpha=0.8, label='月線 (MA20)')
        
        # 修改點：移除圖表標題內的 📊 符號，確保 Render 環境文字渲染完全正確
        ax.set_title(f"{name} 趨勢掃描", fontsize=15, fontweight='bold', pad=10)
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
    
    report = [
        f"# 🦅 AI 萬元網格實驗報告",
        f"### 📅 報告日期： `{now:%Y-%m-%d %H:%M}`",
        f"### 💰 實驗總金： `{TEST_CAPITAL:,} TWD`",
        "---"
    ]
    
    dfs_all = {}
    for symbol, cfg in TARGETS.items():
        try:
            # 依照準則抓取一年數據判斷基準 [cite: 2026-02-02]
            df = yf.download(symbol, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            
            data = compute_advanced_grid(df)
            dfs_all[symbol] = df
            
            alloc_per_grid = (TEST_CAPITAL * cfg['weight']) / 5
            suggested_shares = int(alloc_per_grid // data['grid_buy']) if data['grid_buy'] > 0 else 0
            
# === AI 接入點 (傳入網格專屬數據) ===
            from ai_expert import get_ai_point
            grid_ai_data = {
                "price": data['price'],
                "trend": data['trend'],
                "rsi": round(data['rsi'], 1),
                "grid_buy": round(data['grid_buy'], 2)
            }
            ai = get_ai_point(target_name=cfg['name'], strategy_type="grid_trading", extra_data=grid_ai_data)

            report.append(f"## {cfg['name']} 📍")
            report.append(f"💵 **目前現價**： `{data['price']:.2f}`")
            report.append(f"🔍 **趨勢矩陣**： {data['trend']}")
            report.append(f"📈 **RSI 指標**： `{data['rsi']:.1f}`")
            report.append(f"🛡️ **補倉預計**： `{data['grid_buy']:.2f}` (約 `{suggested_shares}` 股)")
            report.append(f"🤖 **AI 建議**： `{ai.get('decision')}` - {ai.get('reason')}") # 嵌入 AI 理由
            report.append("---")
            
        except Exception as e:
            logging.error(f"網格執行錯誤 {symbol}: {e}")

    report.append(f"# AI 狀態：監控中 🤖")
    report.append("---")
    # 修改點：在報告末尾加入 Discord 專用圖表生成提示
    report.append(f"📊 **萬元網格實驗動態分析圖已生成，請參閱下方附件**")
    
    img_buf = generate_grid_chart(dfs_all)
    return "\n".join(report).strip(), img_buf
