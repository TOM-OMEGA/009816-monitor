import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
import json
import os
from datetime import datetime, timezone, timedelta
import logging

# --- 強制修復：防止伺服器環境卡死並支援無 GUI 環境 ---
import matplotlib
matplotlib.use('Agg')

# ================= 設定 =================
LEDGER_FILE = "/tmp/ledger.json"
GRID_LEVELS = 5
GRID_GAP_PCT = 0.03

TARGETS = {
    "00929.TW": {"cap": 3333, "name": "00929 (High Div)"},
    "2317.TW": {"cap": 3334, "name": "2317 (Hon Hai)"},
    "00878.TW": {"cap": 3333, "name": "00878 (Sustainable)"}
}

# ================= 工具與繪圖 =================
def load_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def generate_grid_plot(dfs_dict):
    """
    繪製多標的對比趨勢圖
    """
    plt.figure(figsize=(12, 6))
    for symbol, df in dfs_dict.items():
        if df.empty: continue
        name = TARGETS[symbol]['name']
        # 標準化價格 (以第一天為 100) 以便觀察相對動能
        norm_price = df['Close'] / df['Close'].iloc[0] * 100
        plt.plot(df.index, norm_price, label=f"{name}", lw=2)
    
    plt.title("Portfolio Relative Performance (Base 100)", fontsize=14)
    plt.ylabel("Relative Growth (%)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    return buf

# ================= 主程式 =================
def run_grid():
    ledger = load_ledger()
    tw_tz = timezone(timedelta(hours=8))
    now = datetime.now(tw_tz)
    
    report = [
        f"# 🦅 AI 存股網格報告 ({now:%Y-%m-%d})", 
        "-"*30
    ]
    
    dfs_for_plot = {}

    for symbol, cfg in TARGETS.items():
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="6mo", timeout=15)
            
            if df.empty: continue
            
            # 處理 MultiIndex 索引
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            dfs_for_plot[symbol] = df
            price = float(df['Close'].iloc[-1])
            
            # 趨勢分析
            ma20 = df['Close'].rolling(20).mean().iloc[-1]
            ma60 = df['Close'].rolling(60).mean().iloc[-1]
            trend_icon = "🟢 多頭" if price > ma20 > ma60 else "🔴 空頭" if price < ma20 < ma60 else "🟡 盤整"

            report.append(
                f"### 📍 {cfg['name']}\n"
                f"💰 現價: `{price:.2f}` | 📈 趨勢: {trend_icon}\n"
                f"📒 **網格水位**: `{price*(1-GRID_GAP_PCT):.2f}` (預計補倉點)"
            )

        except Exception as e:
            report.append(f"❌ {symbol} 異常: `{str(e)[:20]}`")

    # 產出圖表
    img_buf = None
    if dfs_for_plot:
        try:
            img_buf = generate_grid_plot(dfs_for_plot)
        except Exception as e:
            logging.error(f"繪圖失敗: {e}")

    report.append("-" * 30)
    report.append("💡 *註：網格數據每 24 小時校準一次。*")
    
    return "\n".join(report), img_buf
