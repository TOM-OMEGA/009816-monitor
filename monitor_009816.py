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

# 導入 AI 判斷模組
try:
    from ai_expert import analyze_taiwan_stock, get_us_market_sentiment
    AI_AVAILABLE = True
except ImportError:
    AI_AVAILABLE = False
    logging.warning("⚠️ ai_expert 模組未找到，將跳過 AI 判斷")

# =====================
# 🛠️ 終極中文字體與符號解決方案
# =====================
def setup_chinese_font():
    font_filename = "NotoSansTC-Regular.ttf"
    font_path = os.path.join(os.getcwd(), font_filename)
    
    if os.path.exists(font_path):
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['font.family'] = [font_name, 'DejaVu Sans', 'sans-serif']
        plt.rcParams['axes.unicode_minus'] = False 
        logging.info(f"✅ 009816 模組：成功載入字體 {font_name} 及其符號回援機制")
    else:
        logging.error(f"❌ 009816 模組：找不到字體檔 {font_filename}")

# 初始化字體
setup_chinese_font()

def run_taiwan_stock():
    """
    009816 凱基台灣 TOP 50 存股分析模組（整合美股情緒）
    """
    symbol = "009816.TW"
    name = "凱基台灣 TOP 50"

    try:
        # 1. 抓取數據
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y", timeout=15)

        if df.empty or len(df) < 1:
            return f"# ❌ {name}\n數據尚未入庫，請待收盤後重試。", None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close = df["Close"]
        price = float(close.iloc[-1])
        
        # 2. 數據分析
        high_all = close.max()
        low_all = min(close.min(), 10.00)
        dist_from_launch = (price / 10.0 - 1) * 100
        days_active = len(df)
        
        # 3. 複利展望
        daily_ret = (price / 10.0) ** (1 / max(days_active, 1)) - 1
        annual_return = ((1 + daily_ret) ** 252 - 1) * 100
        projected_1y = price * ((1 + daily_ret) ** 252)
        
        # 4. 價格位階
        price_position = (price - low_all) / (high_all - low_all) if high_all != low_all else 0.5
        position_pct = price_position * 100

        # 5. 系統評分
        score = 65 
        if price <= 10.05: score += 10
        if dist_from_launch < 2.0: score += 5
        if price_position < 0.4: score += 10  # 低檔加分
        
        # 系統建議（僅供參考，最終以 AI 為準）
        if score >= 75:
            system_action = "🟢 積極佈局"
        elif score >= 60:
            system_action = "🟡 定期定額"
        else:
            system_action = "🔴 觀望等待"

        # =====================
        # 🤖 AI 專業判斷（結合美股情緒）
        # =====================
        ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 未啟用"}
        us_sentiment = {}
        
        if AI_AVAILABLE:
            try:
                # 取得美股情緒
                us_sentiment = get_us_market_sentiment()
                
                # 提供完整數據給 AI
                extra_data = {
                    "tech_summary": f"現價 {price:.2f}, 距發行價 {dist_from_launch:+.1f}%, 價格位階 {position_pct:.0f}%, 年化報酬 {annual_return:.1f}%",
                    "score": f"{score}/100",
                    "position": f"{position_pct:.0f}%（{price_position:.2f}）",
                    "outlook": f"2027目標 {projected_1y:.2f}, 複利年化 {annual_return:.1f}%"
                }
                
                ai_result = analyze_taiwan_stock(extra_data, name, debug=False)
                
            except Exception as e:
                logging.error(f"AI 判斷異常: {e}")
                ai_result = {"decision": "觀望", "confidence": 50, "reason": "AI 分析異常"}

        # =====================
        # 📊 繪圖邏輯
        # =====================
        plt.figure(figsize=(10, 6))
        plt.plot(df.index, close, marker='o', linestyle='-', color='#1f77b4', linewidth=2, label='每日收盤價')
        plt.axhline(y=10.0, color='#d62728', linestyle='--', alpha=0.6, label='發行價 (10.0)')
        plt.axhline(y=price, color='#2ca02c', linestyle=':', alpha=0.6, label=f'目前價格 ({price:.2f})')
        
        plt.title(f"{name} (009816) 策略趨勢分析", fontsize=16, fontweight='bold', pad=15)
        plt.xlabel("交易日期", fontsize=12)
        plt.ylabel("價格 (TWD)", fontsize=12)
        plt.legend(loc='best')
        plt.grid(True, linestyle=':', alpha=0.5)

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close()

        # =====================
        # 📖 報告組裝
        # =====================
        today = datetime.now(timezone(timedelta(hours=8)))
        
        report = [
            f"# 🦅 經理人 AI 存股決策",
            f"### 📅 巡檢日期： `{today:%Y-%m-%d %H:%M}`",
            "---",
            f"## {name} (009816) 📌",
            f"💵 **目前現價**： `{price:.2f}` (發行價: 10.00)",
            f"📈 **累計報酬**： `{dist_from_launch:+.2f}%`",
            f"📊 **價格位階**： `{position_pct:.0f}%` (全年度)",
            f"🚀 **2027 展望**： `{projected_1y:.2f}` (年化 `{annual_return:+.1f}%`)",
            "---",
        ]
        
        # 美股情緒提示（如果有）
        if us_sentiment.get("analyzed"):
            report.extend([
                f"## 🌍 美股盤後參考",
                f"📊 **市場情緒**： {us_sentiment.get('sentiment', '未知')}",
                f"💹 **台積電ADR**： {us_sentiment.get('tsm_trend', '未知')}",
                f"🔮 **明日預測**： {us_sentiment.get('next_day_prediction', '未知')}",
                "---",
            ])
        
        report.extend([
            f"## 🤖 AI 智能決策",
            f"📍 **AI 判斷**： **{ai_result['decision']}**",
            f"💯 **信心指數**： `{ai_result['confidence']}%`",
            f"💡 **決策理由**： {ai_result['reason']}",
            "",
            f"_系統評分: {score}/100 | 系統建議: {system_action}_",
            "---",
            f"📈 **{name} 策略趨勢圖已生成，請參閱下方附件**"
        ])

        return "\n".join(report).strip(), buf

    except Exception as e:
        logging.error(f"009816 執行錯誤: {e}")
        return f"# ❌ 009816 巡檢異常\n`{str(e)[:50]}`", None
