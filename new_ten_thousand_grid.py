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
    from ai_expert import analyze_grid_trading, get_us_market_sentiment
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
    
    # 5. 月低計算
    month_low = close.tail(30).min() if len(close) >= 30 else close.min()

    return {
        "price": price, 
        "rsi": rsi, 
        "trend": trend, 
        "grid_buy": grid_buy,
        "month_low": month_low,
        "ma20": last_ma20,
        "ma60": last_ma60
    }

def generate_grid_chart(dfs):
    """繪製網格動態分析圖"""
    fig = plt.figure(figsize=(12, 12))
    
    for i, (symbol, df) in enumerate(dfs.items()):
        ax = plt.subplot(len(dfs), 1, i+1)
        name = TARGETS[symbol]['name']
        plot_df = df.tail(60)
        
        ma20 = plot_df['Close'].rolling(20).mean()
        std20 = plot_df['Close'].rolling(20).std()
        
        # 繪製價格與布林通道
        ax.plot(plot_df.index, plot_df['Close'], label='收盤價', lw=2.5, color='#1f77b4')
        ax.fill_between(plot_df.index, ma20-2*std20, ma20+2*std20, color='gray', alpha=0.1, label='布林通道')
        ax.plot(plot_df.index, ma20, color='orange', linestyle='--', alpha=0.8, label='月線 (MA20)')
        
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
    
    # 取得美股情緒
    us_sentiment = {}
    if AI_AVAILABLE:
        us_sentiment = get_us_market_sentiment()
    
    report = [
        f"# 🦅 AI 萬元網格實驗報告",
        f"### 📅 報告日期： `{now:%Y-%m-%d %H:%M}`",
        f"### 💰 實驗總金： `{TEST_CAPITAL:,} TWD`",
        "---"
    ]
    
    # 美股情緒提示
    if us_sentiment.get("analyzed"):
        report.extend([
            f"## 🌍 美股盤後參考",
            f"📊 **市場情緒**： {us_sentiment.get('sentiment', '未知')}",
            f"🔮 **明日預測**： {us_sentiment.get('next_day_prediction', '未知')}",
            f"💹 **台積電ADR**： {us_sentiment.get('tsm_trend', '未知')}",
            "---"
        ])
    
    dfs_all = {}
    ai_results = {}
    
    for symbol, cfg in TARGETS.items():
        try:
            # 抓取一年數據
            df = yf.download(symbol, period="1y", interval="1d", progress=False)
            if df.empty: continue
            if isinstance(df.columns, pd.MultiIndex): 
                df.columns = df.columns.get_level_values(0)
            
            data = compute_advanced_grid(df)
            dfs_all[symbol] = df
            
            alloc_per_grid = (TEST_CAPITAL * cfg['weight']) / 5
            suggested_shares = int(alloc_per_grid // data['grid_buy']) if data['grid_buy'] > 0 else 0
            
            # =====================
            # 🤖 AI 判斷整合（結合美股情緒）
            # =====================
            ai_result = {"decision": "觀望", "confidence": 0, "reason": "AI 未啟用"}
            
            if AI_AVAILABLE:
                try:
                    extra_data = {
                        "price": data['price'],
                        "trend": data['trend'],
                        "rsi": f"{data['rsi']:.1f}",
                        "grid_buy": f"{data['grid_buy']:.2f}"
                    }
                    ai_result = analyze_grid_trading(extra_data, cfg['name'], debug=False)
                    ai_results[symbol] = ai_result
                except Exception as e:
                    logging.error(f"AI 判斷異常 {symbol}: {e}")
                    ai_result = {"decision": "觀望", "confidence": 50, "reason": "AI 分析異常"}
            
            # =====================
            # 📝 個股報告
            # =====================
            report.append(f"## {cfg['name']} 📍")
            report.append(f"💵 **目前現價**： `{data['price']:.2f}`")
            report.append(f"🔍 **趨勢矩陣**： {data['trend']}")
            report.append(f"📈 **RSI 指標**： `{data['rsi']:.1f}`")
            report.append(f"🛡️ **補倉預計**： `{data['grid_buy']:.2f}`")
            report.append(f"⚡ **下單指令**： `買入 {suggested_shares} 股`")
            report.append(f"### 🤖 AI 策略判斷")
            report.append(f"📍 **決策**： **{ai_result['decision']}** (信心度: {ai_result['confidence']}%)")
            report.append(f"💡 **理由**： {ai_result['reason']}")
            report.append("-" * 20)
            
        except Exception as e:
            logging.error(f"網格執行錯誤 {symbol}: {e}")

    # =====================
    # 🧠 綜合 AI 建議
    # =====================
    if ai_results:
        can_buy = [k for k, v in ai_results.items() if "買進" in v['decision'] or "立即" in v['decision']]
        wait_buy = [k for k, v in ai_results.items() if "回檔" in v['decision'] or "等待" in v['decision']]
        
        report.append(f"## 🧠 綜合 AI 建議（結合美股影響）")
        if can_buy:
            report.append(f"✅ **立即進場**： {', '.join([TARGETS[s]['name'] for s in can_buy])}")
        if wait_buy:
            report.append(f"⏳ **等待回檔**： {', '.join([TARGETS[s]['name'] for s in wait_buy])}")
        if not can_buy and not wait_buy:
            report.append(f"⚠️ **建議觀望**： 等待更明確訊號或持續定期定額")
        report.append("-" * 20)

    report.append(f"📊 **萬元網格實驗動態分析圖已生成，請參閱下方附件**")
    
    img_buf = generate_grid_chart(dfs_all)
    return "\n".join(report).strip(), img_buf
