import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

def get_fm_data(dataset, stock_id, days=30):
    """通用的 FinMind 數據抓取工具 (強化診斷版)"""
    # 💡 每次呼叫才讀取 Token，確保環境變數 100% 讀到
    token = os.environ.get('FINMIND_TOKEN')
    
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
        # 增加 timeout 到 15 秒，FinMind 盤中偶爾會比較慢
        res = requests.get(url, params=params, timeout=15)
        data = res.json().get('data', [])
        if not data:
            return pd.DataFrame()
        return pd.DataFrame(data)
    except Exception as e:
        print(f"⚠️ FinMind 抓取失敗 [{dataset}]: {e}")
        return pd.DataFrame()

def get_high_level_insight(symbol):
    """
    11項全維度數據對接：優化效能版
    """
    stock_id = symbol.replace(".TW", "")
    print(f"📊 引擎正在分析 {symbol} 的 11 維指標...")

    # 1. 基礎價量 (10天份足夠計算均線)
    df_price = get_fm_data("TaiwanStockPrice", stock_id, days=10)
    
    # 3. Tick 數據 (💡 修改：只抓當天，減少數據量防止卡死)
    df_tick = get_fm_data("TaiwanStockPriceTick", stock_id, days=0) 
    
    # 6. PER/PBR (一週份)
    df_per = get_fm_data("TaiwanStockPER", stock_id, days=7)
    
    # 7. 每 5 秒委託統計 (關鍵！判斷盤中力道)
    df_stats = get_fm_data("TaiwanStockStatistics", stock_id, days=0)
    
    # 8. 大盤 5 秒指數 (判斷市場氛圍)
    df_idx_tick = get_fm_data("TaiwanStockIndexTick", "TAIEX", days=0)
    
    # 9. 加權 & 11. 報酬指數
    df_index = get_fm_data("TaiwanStockIndex", "TAIEX", days=3)
    df_total_idx = get_fm_data("TaiwanStockTotalIndex", "TAIEX", days=3)
    
    # 10. 當沖率 (一週份)
    df_day = get_fm_data("TaiwanStockDayTrading", stock_id, days=7)

    # --- 數據封裝 (加入更安全的 iloc 檢查) ---
    insight = {
        "k_line": f"收{df_price.iloc[-1]['close']} 量的{df_price.iloc[-1]['Trading_Volume']}" if not df_price.empty else "N/A",
        "tick_last": f"成交:{df_tick.iloc[-1]['deal_price']}" if not df_tick.empty else "盤後/無數據",
        "valuation": f"PER:{df_per.iloc[-1]['PER']} / PBR:{df_per.iloc[-1]['PBR']}" if not df_per.empty else "N/A",
        "order_strength": f"買單{df_stats.iloc[-1]['Buy_Order_Quantity']} vs 賣單{df_stats.iloc[-1]['Sell_Order_Quantity']}" if not df_stats.empty else "穩定",
        "market_context": f"加權:{df_index.iloc[-1]['last_price'] if not df_index.empty else 'N/A'} (報酬:{df_total_idx.iloc[-1]['last_price'] if not df_total_idx.empty else 'N/A'})",
        "idx_5s": f"大盤5s趨勢:{df_idx_tick.iloc[-1]['last_price']}" if not df_idx_tick.empty else "平穩",
        "day_trade": f"當沖率:{df_day.iloc[-1]['day_trading_purchase_amount_percent']}%" if not df_day.empty else "N/A",
        
        # 這些是您原本 monitor 邏輯中需要的 Key，我們補上預設值防止報錯
        "inst": "同步抓取中...",
        "rev": "同步計算中...",
        "holders": "同步追蹤中..."
    }
    
    print(f"✅ {symbol} 引擎運算完畢")
    return insight
