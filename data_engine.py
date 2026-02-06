import os
import requests
import pandas as pd
import time
from datetime import datetime, timedelta, timezone

def get_fm_data(dataset, stock_id, days=1):
    """FinMind 通用抓取（強化 timeout + 防呆）"""
    token = os.environ.get('FINMIND_TOKEN')
    if not token:
        print(f"❌ FINMIND_TOKEN 缺失，略過 {dataset}")
        return pd.DataFrame()

    # 考量到 FinMind 資料更新延遲，建議將回溯天數稍微放寬
    now_utc = datetime.now(timezone.utc)
    start_date = (now_utc - timedelta(days=days + 2)).strftime('%Y-%m-%d')

    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": dataset,
        "data_id": stock_id.replace(".TW", ""),
        "start_date": start_date,
        "token": token
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            data = res.json().get('data', [])
            return pd.DataFrame(data)
        return pd.DataFrame()

    except Exception as e:
        print(f"⚠️ FinMind 例外 [{dataset}]: {e}")
        return pd.DataFrame()

def _safe_last(df, cols):
    """安全取最後一筆資料，並檢查必要欄位是否存在"""
    if df is not None and not df.empty:
        # 確保所有要求的欄位都在 dataframe 中
        available_cols = [c for c in cols if c in df.columns]
        if available_cols:
            return df.iloc[-1]
    return None

def _order_strength(buy, sell):
    """買賣力道轉成 AI 友善等級"""
    if buy == 0 and sell == 0:
        return "未知", 0.0
    
    # 避免除以零
    ratio = buy / max(sell, 1)
    if ratio >= 1.3: return "強勢", ratio
    elif ratio >= 0.8: return "中性", ratio
    else: return "偏弱", ratio

def _valuation_level(per):
    if per <= 0: return "未知"
    if per < 15: return "低位階"
    elif per < 25: return "合理"
    else: return "偏高"

def get_high_level_insight(symbol):
    stock_id = symbol.replace(".TW", "")
    print(f"📊 分析 {symbol} 關鍵指標（AI 決策用）")

    # === 數據抓取 (保持間隔避免 429) ===
    df_price = get_fm_data("TaiwanStockPrice", stock_id, days=5)
    time.sleep(1.0)
    df_per = get_fm_data("TaiwanStockPER", stock_id, days=7)
    time.sleep(1.0)
    df_stats = get_fm_data("TaiwanStockStatistics", stock_id, days=2)
    time.sleep(1.0)
    df_index = get_fm_data("TaiwanStockIndex", "TAIEX", days=3)

    # === 安全提取 (關鍵：防止 None 崩潰) ===
    p = _safe_last(df_price, ['close', 'Trading_Volume'])
    v = _safe_last(df_per, ['PER'])
    s = _safe_last(df_stats, ['Buy_Order_Quantity', 'Sell_Order_Quantity'])
    m = _safe_last(df_index, ['last_price'])

    # === 數值抽取（加入強烈防護邏輯） ===
    # 如果抓不到當前價格，預設為 0，後續由 monitor_009816 的 yfinance 補位
    close_price = float(p['close']) if (p is not None and 'close' in p) else 0.0
    volume = int(p['Trading_Volume']) if (p is not None and 'Trading_Volume' in p) else 0
    per = float(v['PER']) if (v is not None and 'PER' in v) else 0.0

    buy_q = int(s['Buy_Order_Quantity']) if (s is not None and 'Buy_Order_Quantity' in s) else 0
    sell_q = int(s['Sell_Order_Quantity']) if (s is not None and 'Sell_Order_Quantity' in s) else 0

    order_label, order_ratio = _order_strength(buy_q, sell_q)
    valuation_label = _valuation_level(per)

    market_price = m['last_price'] if (m is not None and 'last_price' in m) else "N/A"

    insight = {
        # === 顯示用文字 ===
        "k_line": f"收 {close_price} / 量 {volume}",
        "valuation": f"PER {per:.2f} ({valuation_label})" if per > 0 else "N/A",
        "order_strength": f"{order_label} ({order_ratio:.2f})",
        "market_context": f"加權 {market_price}",

        # === 機器/風控數值 ===
        "price": close_price,
        "volume": volume,
        "per": per,
        "valuation_level": valuation_label,
        "buy_sell_ratio": round(order_ratio, 2),
        "order_level": order_label,

        # === 擴充欄位 ===
        "inst": "normal",
        "rev": "normal",
        "holders": "stable"
    }

    print(f"✅ {symbol} 高階指標處理完成 (價格: {close_price})")
    return insight
