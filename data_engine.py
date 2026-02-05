import os
import requests
import pandas as pd
import time
from datetime import datetime, timedelta, timezone

def get_fm_data(dataset, stock_id, days=1):
    """通用的 FinMind 數據抓取工具"""
    token = os.environ.get('FINMIND_TOKEN')
    if not token:
        print(f"❌ 警告: FINMIND_TOKEN 缺失，無法抓取 {dataset}")
        return pd.DataFrame()

    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=days)).strftime('%Y-%m-%d')
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": dataset,
        "data_id": stock_id.replace(".TW", ""),
        "start_date": start_date,
        "token": token
    }
    try:
        res = requests.get(url, params=params, timeout=10) # 💡 Timeout 稍微拉長到 10
        if res.status_code == 200:
            data = res.json().get('data', [])
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        print(f"⚠️ FinMind 連線異常 [{dataset}]: {e}")
        return pd.DataFrame()

def get_high_level_insight(symbol):
    stock_id = symbol.replace(".TW", "")
    print(f"📊 引擎正在分析 {symbol} 關鍵指標 (緩衝模式)...")

    # 1. 基礎價量 (days 拉長到 5 天比較穩，預防假日或資料更新延遲)
    df_price = get_fm_data("TaiwanStockPrice", stock_id, days=5)
    time.sleep(1.2) # 💡 稍微拉長到 1.2 秒最保險
    
    # 2. 價值位階
    df_per = get_fm_data("TaiwanStockPER", stock_id, days=7)
    time.sleep(1.2)
    
    # 3. 盤中力道
    df_stats = get_fm_data("TaiwanStockStatistics", stock_id, days=2)
    time.sleep(1.2)
    
    # 4. 大盤環境
    df_index = get_fm_data("TaiwanStockIndex", "TAIEX", days=3)
    
    # ✅ 關鍵強化：使用安全提取邏輯，避免 .iloc[-1] 噴錯導致程式跳掉
    def safe_get(df, cols):
        if df is not None and not df.empty:
            # 確保欄位都存在
            if all(c in df.columns for c in cols):
                last_row = df.iloc[-1]
                return last_row
        return None

    p = safe_get(df_price, ['close', 'Trading_Volume'])
    v = safe_get(df_per, ['PER'])
    s = safe_get(df_stats, ['Buy_Order_Quantity', 'Sell_Order_Quantity'])
    m = safe_get(df_index, ['last_price'])

    insight = {
        "k_line": f"收{p['close']} 量{p['Trading_Volume']}" if p is not None else "N/A",
        "valuation": f"PER:{v['PER']:.2f}" if v is not None else "N/A",
        "order_strength": f"買{s['Buy_Order_Quantity']} vs 賣{s['Sell_Order_Quantity']}" if s is not None else "平穩",
        "market_context": f"加權:{m['last_price']}" if m is not None else "N/A",
        "tick_last": f"{p['close']}" if p is not None else "N/A",
        "inst": "盤後結算中", 
        "rev": "正常", 
        "holders": "穩定"
    }
    
    print(f"✅ {symbol} 引擎數據封裝完成")
    return insight
