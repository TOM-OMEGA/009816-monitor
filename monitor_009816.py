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
# 🛠️ 中文字體配置 (讀取 GitHub 本地檔案)
# =====================
def setup_chinese_font():
    # 確保名稱與你上傳的檔案一模一樣
    font_filename = "NotoSansTC-Regular.ttf"
    font_path = os.path.join(os.getcwd(), font_filename)
    
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['font.family'] = font_name
        plt.rcParams['axes.unicode_minus'] = False 
        logging.info(f"✅ 成功啟用本地字體: {font_name}")
    else:
        logging.error(f"❌ 找不到字體檔: {font_filename}，請確認已上傳至 GitHub 根目錄")

# 初始化字體
setup_chinese_font()

def run_taiwan_stock():
    """
    009816 凱基台灣 TOP 50 巡檢模組 - 終極中文版
    """
    symbol = "009816.TW"
    name = "凱基台灣 TOP 50"

    try:
        # 1. 抓取數據 (往前看一年以利判斷)
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", timeout=15)

        if df.empty or len(df) < 1:
            return f"# ❌ {name}\n數據尚未入庫，請待收盤後重試。", None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        price = float(close.iloc[-1])
        
        # 數據分析
        high_all = close.max()
        low_all = min(close.min(), 10.00)
        dist_from_launch = (price / 10.0 - 1) * 100
        days_active = len(df)
        
        # 2027 展望投影 [cite: 2026-02-02]
        daily_ret = (price / 10.0) ** (1 / max(days_active, 1)) - 1
        projected_1y = price * ((1 + daily_ret) ** 252)

        score = 65 
        if price <= 10.05: score += 10
        if dist_from_launch < 2.0: score += 5
        action = "🟢 強勢佈局" if score >= 75 else "🟡 定期定額"

        # =====================
        # 📊 繪圖邏輯 (使用本地字體)
        # =====================
        plt.figure(figsize=(10, 6))
        plt.plot(df.index, close, marker='o', linestyle='-', color='#1f77b4', linewidth=2, label='每日收盤價')
        plt.axhline(y=10.0, color='#d62728', linestyle='--', alpha=0.6, label='發行價 (10.0)')
        
        # 這裡的標題會完美顯示中文
        plt.title(f"📈 {name} (009816) 策略趨勢分析", fontsize=16, fontweight='bold', pad=15)
        plt.xlabel("交易日期", fontsize=12)
        plt.ylabel("價格 (TWD)", fontsize=12)
        plt.legend(loc='best')
        plt.grid(True, linestyle=':', alpha=0.5)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()

        # =====================
        # 📖 報告組裝 (大標題格式)
        # =====================
        today = datetime.now(timezone(timedelta(hours=8)))
        report = [
            f"# 🦅 經理人 AI 存股決策",
            f"### 📅 巡檢日期： `{today:%Y-%m-%d %H:%M}`",
            "---",
            f"## {name} (009816) 📌",
            f"💵 **目前現價**： `{price:.2f}` (發行價: 10.00)",
            f"🚀 **2027 展望**： `{projected_1y:.2f}`",
            f"📈 **累計漲跌**： `{dist_from_launch:+.2f}%`",
            f"📊 **目前位階**： `{((price-low_all)/(high_all-low_all if high_all!=low_all else 1)):.1%}`",
            "---",
            f"## 🧠 決策分析",
            f"⚖️ **系統評分**： `{score} / 100`",
            f"🎯 **行動建議**： **{action}**",
            "---",
            f"# AI 狀態：複利計算中 🤖",
            f"💡 **提醒**：複利效果穩定，已納入 2027 投影計畫。"
        ]

        return "\n".join(report).strip(), buf

    except Exception as e:
        logging.error(f"009816 執行錯誤: {e}")
        return f"# ❌ 009816 巡檢異常\n`{str(e)[:50]}`", None
