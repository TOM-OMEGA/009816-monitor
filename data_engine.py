import os
import requests
import pandas as pd
import time
from datetime import datetime, timedelta, timezone

def get_fm_data(dataset, stock_id, days=1):
    """通用的 FinMind 數據抓取工具 (極速診斷版)"""
    # 💡 關鍵修正：確保 Token 讀取且輸出診斷訊息
    token = os.environ.get('FINMIND_TOKEN')
    if not token:
        print(f"❌ 警告: FINMIND_TOKEN 缺失，無法抓取 {dataset}")
        return pd.DataFrame()

    now_utc = datetime.now(timezone.utc)
    # 💡 極速化：只抓必要天數，減少流量
    start_date = (now_utc - timedelta(days=days)).strftime('%Y-%m-%d')
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": dataset,
        "data_id": stock_id.replace(".TW", ""),
        "start_date": start_date,
        "token": token
    }
    try:
        # 加上 timeout，防止 API 伺服器遲鈍導致程式卡死
        res = requests.get(url, params=params, timeout=8)
        data = res.json().get('data', [])
        return pd.DataFrame(data)
    except Exception as e:
        print(f"⚠️ FinMind 連線異常 [{dataset}]: {e}")
        return pd.DataFrame()

def get_high_level_insight(symbol):
    stock_id = symbol.replace(".TW", "")
    print(f"📊 引擎正在分析 {symbol} 關鍵指標...")

    # 1. 基礎價量
    df_price = get_fm_data("TaiwanStockPrice", stock_id, days=3)
    time.sleep(1) # 💡 讓 FinMind 喘口氣
    
    # 2. 價值位階
    df_per = get_fm_data("TaiwanStockPER", stock_id, days=5)
    time.sleep(1) # 💡 緩衝
    
    # 3. 盤中力道
    df_stats = get_fm_data("TaiwanStockStatistics", stock_id, days=1)
    time.sleep(1) # 💡 緩衝
    
    # 4. 大盤環境
    df_index = get_fm_data("TaiwanStockIndex", "TAIEX", days=2)
    
    # 安全提取數據
    insight = {
        "k_line": f"收{df_price.iloc[-1]['close']} 量{df_price.iloc[-1]['Trading_Volume']}" if not df_price.empty else "N/A",
        "valuation": f"PER:{df_per.iloc[-1]['PER']}" if not df_per.empty else "N/A",
        "order_strength": f"買{df_stats.iloc[-1]['Buy_Order_Quantity']} vs 賣{df_stats.iloc[-1]['Sell_Order_Quantity']}" if not df_stats.empty else "平穩",
        "market_context": f"加權:{df_index.iloc[-1]['last_price']}" if not df_index.empty else "N/A",
        # 保持與其他模組兼容
        "inst": "追蹤中", "rev": "計算中", "holders": "追蹤中"
    }
    
    print(f"✅ {symbol} 引擎數據已封裝")
    return insight
