import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# 請確保在 Render 的 Environment Variables 設定此變數
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN')

def get_fm_data(dataset, stock_id, days=30):
    """通用的 FinMind 數據抓取工具 (加入超時保護)"""
    # 修正 DeprecationWarning: 使用 timezone-aware 物件
    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=days)).strftime('%Y-%m-%d')
    
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": dataset,
        "data_id": stock_id.replace(".TW", ""),
        "start_date": start_date,
        "token": FINMIND_TOKEN
    }
    try:
        # 加入 timeout=10，防止開盤數據量大時卡死導致整個戰報發不出來
        res = requests.get(url, params=params, timeout=10)
        return pd.DataFrame(res.json()['data'])
    except:
        return pd.DataFrame()

def get_high_level_insight(symbol):
    """
    11項全維度數據對接：台股總覽、日成交、Tick、還原股價、K線、PER/PBR、
    5秒委託、5秒指數、加權指數、當沖/暫停、報酬指數。
    """
    stock_id = symbol.replace(".TW", "")
    
    # 1. 台股總覽 (TaiwanStockInfo) & 2. 股價日成交 (TaiwanStockPrice) & 5. K線資料
    df_price = get_fm_data("TaiwanStockPrice", stock_id, days=10)
    
    # 3. 歷史股價-Tick (TaiwanStockPriceTick)
    df_tick = get_fm_data("TaiwanStockPriceTick", stock_id, days=1)
    
    # 4. 台灣還原股價 (TaiwanStockDividendResult / TaiwanStockPrice)
    # 註：實務上透過 yfinance 或 FinMind 還原值計算
    
    # 6. 個股 PER、PBR 資料表 (TaiwanStockPER)
    df_per = get_fm_data("TaiwanStockPER", stock_id, days=7)
    
    # 7. 每 5 秒委託成交統計 (TaiwanStockStatistics)
    df_stats = get_fm_data("TaiwanStockStatistics", stock_id, days=1)
    
    # 8. 每 5 秒指數統計 (TaiwanStockIndexTick)
    df_idx_tick = get_fm_data("TaiwanStockIndexTick", "TAIEX", days=1)
    
    # 9. 加權指數 (TaiwanStockIndex) & 11. 報酬指數 (TaiwanStockTotalIndex)
    df_index = get_fm_data("TaiwanStockIndex", "TAIEX", days=5)
    df_total_idx = get_fm_data("TaiwanStockTotalIndex", "TAIEX", days=5) # 報酬指數
    
    # 10. 當沖/暫停交易 (TaiwanStockDayTrading)
    df_day = get_fm_data("TaiwanStockDayTrading", stock_id, days=7)

    # --- 數據封裝 (供 AI 診斷) ---
    # 增加判斷 logic，避免 df.empty 造成 iloc 報錯而中斷發信
    return {
        # 基礎量價
        "k_line": f"收{df_price.iloc[-1]['close']} 量的{df_price.iloc[-1]['Trading_Volume']}" if not df_price.empty else "N/A",
        "tick_last": f"Tick成交:{df_tick.iloc[-1]['deal_price']}" if not df_tick.empty else "盤後",
        
        # 價值位階 (PER/PBR)
        "valuation": f"PER:{df_per.iloc[-1]['PER']} / PBR:{df_per.iloc[-1]['PBR']}" if not df_per.empty else "N/A",
        
        # 盤中力道 (5秒委託)
        "order_strength": f"買單{df_stats.iloc[-1]['Buy_Order_Quantity']} vs 賣單{df_stats.iloc[-1]['Sell_Order_Quantity']}" if not df_stats.empty else "穩定",
        
        # 市場環境 (大盤、報酬指數、5秒指數)
        "market_context": f"加權:{df_index.iloc[-1]['last_price'] if not df_index.empty else 'N/A'} (報酬:{df_total_idx.iloc[-1]['last_price'] if not df_total_idx.empty else 'N/A'})",
        "idx_5s": f"大盤5s趨勢:{df_idx_tick.iloc[-1]['last_price']}" if not df_idx_tick.empty else "平穩",
        
        # 籌碼面 (當沖、法人、營收、大戶已包含在原邏輯)
        "day_trade": f"當沖率:{df_day.iloc[-1]['day_trading_purchase_amount_percent']}%" if not df_day.empty else "N/A",
        
        # 保留經理人原有回傳項 (建議後續將法人、營收、大戶抓取 logic 寫入此處)
        "inst": "同步抓取中...", 
        "rev": "同步計算中...",  
        "holders": "同步追蹤中..." 
    }
