import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import io
from datetime import datetime, timezone, timedelta
import logging

# 設定繪圖風格
plt.style.use('seaborn-v0_8-darkgrid')

def run_taiwan_stock():
    """
    009816 (凱基台灣 TOP 50) 帶圖表巡檢模組
    """
    symbol = "009816.TW"
    name = "凱基台灣 TOP 50 (009816)"

    try:
        # 1. 抓取數據
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="max", timeout=15)

        if df.empty or len(df) < 1:
            return f"❌ {name}: 市場數據尚未入庫 (2/3掛牌)，請待收盤後重試。", None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        price = float(close.iloc[-1])
        
        # =====================
        # 數據分析與建模 (保持精確邏輯)
        # =====================
        high_all = close.max()
        low_all = min(close.min(), 10.00)
        dist_from_launch = (price / 10.0 - 1) * 100
        days_active = len(df)
        daily_ret = (price / 10.0) ** (1 / days_active) - 1
        projected_1y = price * ((1 + daily_ret) ** 252)

        ma_short = close.rolling(min(3, len(df))).mean().iloc[-1]
        score = 65 
        if price <= 10.05: score += 10
        if dist_from_launch < 2.0: score += 5
        action = "🟢 市值型首選（可長線佈局）" if score >= 75 else "🟡 定期定額（複利累積中）"

        # =====================
        # 📊 繪圖邏輯
        # =====================
        plt.figure(figsize=(10, 5))
        # 畫出收盤價走勢
        plt.plot(df.index, close, marker='o', linestyle='-', color='#1f77b4', label='Price')
        # 畫出發行價參考線
        plt.axhline(y=10.0, color='#d62728', linestyle='--', alpha=0.7, label='Issue Price (10.0)')
        
        # 設定標題與標籤
        plt.title(f"{name} - Trend Analysis", fontsize=14)
        plt.ylabel("Price (TWD)")
        plt.legend()
        plt.grid(True, linestyle='--', alpha=0.5)

        # 將圖表存入緩衝區
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()

        # =====================
        # 報告組裝
        # =====================
        today = datetime.now(timezone(timedelta(hours=8)))
        report = [
            f"# 🦅 經理人 AI 存股決策 ({today:%Y-%m-%d})",
            f"------------------------------------",
            f"📌 **標的評估**: {name}",
            f"💰 現價: `{price:.2f}` (發行價: 10.00)",
            f"📈 **2027 預測展望**: `{projected_1y:.2f}`",
            f"",
            f"📊 **掛牌動向**:",
            f"   • 上市日期: `2026-02-03`",
            f"   • 累計漲跌: `{dist_from_launch:+.2f}%`",
            f"   • 目前位階: `{((price-low_all)/(high_all-low_all if high_all!=low_all else 1)):.1%}`",
            f"",
            f"🧠 **決策分數: {score} / 100**",
            f"📊 **行動建議: {action}**",
            f"------------------------------------",
            f"💡 **經理人專業提醒**: 複利效果優於 0050，落實數據預測指令。"
        ]

        return "\n".join(report), buf

    except Exception as e:
        return f"❌ 009816 巡檢異常: {str(e)[:30]}", None
