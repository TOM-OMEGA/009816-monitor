import os
import yfinance as yf
from datetime import datetime, timedelta, timezone
import pandas as pd
import time
import logging

# 基礎日誌設定
logging.basicConfig(level=logging.INFO)

# ==== AI 模組導入 ====
try:
    from ai_expert import get_us_ai_point
except ImportError:
    get_us_ai_point = None

# ==== 設定 ====
TARGETS_MAP = {"^GSPC": "標普500", "^DJI": "道瓊工業", "^IXIC": "那斯達克", "TSM": "台積電ADR"}
TARGETS = list(TARGETS_MAP.keys())

def fetch_data_safe(symbol):
    """
    抓取美股數據並強制處理索引格式
    """
    try:
        # 下載最近一個月的數據
        df = yf.download(symbol, period="1mo", interval="1d", progress=False, timeout=15)
        
        if df.empty:
            return pd.DataFrame()
            
        # 🟢 核心修正：處理 yfinance v0.2.x 產生的 Multi-Index
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        return df
    except Exception as e:
        logging.error(f"❌ {symbol} 抓取異常: {e}")
        return pd.DataFrame()

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def generate_text_report(dfs, ai_signal):
    # 使用美國東部時間標註報告日期
    us_tz = timezone(timedelta(hours=-5))
    report_date = datetime.now(us_tz).strftime("%Y-%m-%d")
    
    report = [f"🌎 **美股盤後分析快報 [{report_date}]**"]
    
    for symbol, df in dfs.items():
        try:
            if len(df) < 10: continue
            
            close_series = df['Close']
            last_price = float(close_series.iloc[-1])
            prev_price = float(close_series.iloc[-2])
            pct_change = (last_price / prev_price - 1) * 100
            
            # 技術指標
            ma5 = close_series.rolling(5).mean().iloc[-1]
            ma20 = close_series.rolling(20).mean().iloc[-1]
            rsi = compute_rsi(close_series).iloc[-1]
            
            # 趨勢圖示
            if last_price > ma5 > ma20: trend = "🟢 強勢"
            elif last_price < ma5 < ma20: trend = "🔴 空頭"
            else: trend = "🟡 震盪"
            
            name = TARGETS_MAP.get(symbol, symbol)
            report.append(f"• {name}: `{last_price:,.1f}` ({pct_change:+.2f}%) | RSI: `{rsi:.0f}` | {trend}")
        except Exception as e:
            logging.error(f"生成 {symbol} 報告列時失敗: {e}")

    # 加入 AI 建議
    decision = ai_signal.get('decision', '分析中') if isinstance(ai_signal, dict) else "觀望"
    report.append(f"\n🤖 **AI 核心決策**: {decision}")
    
    return "\n".join(report)

# ==== ✅ 標準入口 (給 main.py 使用) ====
def run_us_ai():
    logging.info("🚀 啟動美股盤後任務...")
    
    dfs = {}
    for s in TARGETS:
        df = fetch_data_safe(s)
        if not df.empty:
            dfs[s] = df
        time.sleep(1.5) # 緩衝，避免請求過快被擋
        
    if not dfs:
        return "❌ 美股數據抓取失敗，請檢查 Render 網路連線。"

    # AI 判斷處理
    ai_signal = {"decision": "觀望"}
    if get_us_ai_point and "^GSPC" in dfs:
        try:
            # 簡單封裝最新收盤價供 AI 參考
            ai_input = {s: {"last": float(df['Close'].iloc[-1])} for s, df in dfs.items()}
            ai_signal = get_us_ai_point(extra_data=ai_input)
        except Exception as e:
            logging.error(f"AI 呼叫失敗: {e}")

    # 產出報告文字
    return generate_text_report(dfs, ai_signal)
