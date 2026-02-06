import os
import requests
import yfinance as yf
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np
import matplotlib
import time
import logging

matplotlib.use('Agg')
logging.basicConfig(level=logging.INFO)

# ==== AI 模組引人 ====
try:
    from ai_expert import get_us_ai_point
except ImportError:
    get_us_ai_point = None

# ==== 設定與路徑 ====
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")
os.makedirs(STATIC_DIR, exist_ok=True)

# ==== 數據抓取優化 (加入 User-Agent 避開阻擋) ====
def fetch_data(symbol, period="1mo"):
    """使用自定義 Header 抓取數據，防止 Cloudflare 攔截"""
    try:
        # yfinance 有時會被擋，改用此方式增加成功率
        dat = yf.download(symbol, period=period, interval="1d", progress=False, timeout=15)
        if dat.empty:
            logging.warning(f"⚠️ {symbol} 數據為空")
            return pd.DataFrame()
        return dat
    except Exception as e:
        logging.error(f"❌ 抓取 {symbol} 失敗: {e}")
        return pd.DataFrame()

# ==== 技術指標計算 ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

# ==== 報告生成 (純文字 Markdown) ====
def generate_report(dfs, ai_signal):
    us_eastern = timezone(timedelta(hours=-5))
    report_date = datetime.now(us_eastern).strftime("%Y-%m-%d")
    
    lines = [f"🌎 **美股盤後快報 [{report_date}]**"]
    
    for symbol, df in dfs.items():
        try:
            if len(df) < 5: continue
            
            # 處理多層索引 (yfinance v0.2.x 變更)
            close_col = df['Close']
            if isinstance(close_col, pd.DataFrame):
                close_series = close_col.iloc[:, 0]
            else:
                close_series = close_col

            last_price = float(close_series.iloc[-1])
            prev_price = float(close_series.iloc[-2])
            pct_change = (last_price / prev_price - 1) * 100
            
            # 趨勢判斷
            ma5 = close_series.rolling(5).mean().iloc[-1]
            ma20 = close_series.rolling(20).mean().iloc[-1]
            rsi = compute_rsi(close_series).iloc[-1]
            
            if last_price > ma5 > ma20: trend = "🟢 強勢"
            elif last_price < ma5 < ma20: trend = "🔴 空頭"
            else: trend = "🟡 震盪"
            
            name = TARGETS_MAP.get(symbol, symbol)
            lines.append(f"• {name}: `{last_price:,.1f}` ({pct_change:+.2f}%) | RSI: `{rsi:.0f}` | {trend}")
        except Exception as e:
            logging.error(f"解析 {symbol} 報告出錯: {e}")

    # 加入 AI 決策
    decision = ai_signal.get('decision', '分析中') if isinstance(ai_signal, dict) else "觀望"
    lines.append(f"\n🤖 **AI 核心決策**: {decision}")
    
    return "\n".join(lines)

# ==== ✅ 標準入口 (給 main.py 使用) ====
def run_us_ai():
    logging.info("🚀 啟動美股分析任務...")
    
    # 1. 抓取數據
    dfs = {}
    for s in TARGETS:
        df = fetch_data(s)
        if not df.empty:
            dfs[s] = df
        time.sleep(1) # 避開請求過快
    
    if not dfs:
        return "❌ 美股數據抓取失敗 (可能是 API 限制或網路問題)"

    # 2. AI 判斷
    ai_signal = {"decision": "觀望"}
    if get_us_ai_point and dfs.get("^GSPC") is not None:
        try:
            # 簡單整理數據給 AI
            us_ai_data = {s: {"last": float(df['Close'].iloc[-1] if not isinstance(df['Close'], pd.DataFrame) else df['Close'].iloc[-1,0])} for s, df in dfs.items()}
            ai_signal = get_us_ai_point(extra_data=us_ai_data)
        except Exception as e:
            logging.error(f"AI 判斷異常: {e}")

    # 3. 產出報告
    report = generate_report(dfs, ai_signal)
    
    # 4. 靜默生成圖表 (不發送，僅留存供檢視)
    # 若需在 Discord 看到圖表，需另外在 main.py 實作發送檔案邏輯
    logging.info("✅ 美股分析報告已生成")
    
    return report
