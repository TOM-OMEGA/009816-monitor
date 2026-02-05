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
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return pd.DataFrame(res.json().get('data', []))
        return pd.DataFrame()

    except Exception as e:
        print(f"⚠️ FinMind 例外 [{dataset}]: {e}")
        return pd.DataFrame()


def _safe_last(df, cols):
    """安全取最後一筆"""
    if df is not None and not df.empty:
        if all(c in df.columns for c in cols):
            return df.iloc[-1]
    return None


def _order_strength(buy, sell):
    """買賣力道轉成 AI 友善等級"""
    if buy == 0 and sell == 0:
        return "未知", 0

    ratio = buy / max(sell, 1)

    if ratio >= 1.3:
        return "強勢", ratio
    elif ratio >= 0.8:
        return "中性", ratio
    else:
        return "偏弱", ratio


def _valuation_level(per):
    if per <= 0:
        return "未知"
    if per < 15:
        return "低位階"
    elif per < 25:
        return "合理"
    else:
        return "偏高"


def get_high_level_insight(symbol):
    stock_id = symbol.replace(".TW", "")
    print(f"📊 分析 {symbol} 關鍵指標（AI 決策用）")

    # === 1. 價量 ===
    df_price = get_fm_data("TaiwanStockPrice", stock_id, days=5)
    time.sleep(1.2)

    # === 2. PER ===
    df_per = get_fm_data("TaiwanStockPER", stock_id, days=7)
    time.sleep(1.2)

    # === 3. 盤中買賣 ===
    df_stats = get_fm_data("TaiwanStockStatistics", stock_id, days=2)
    time.sleep(1.2)

    # === 4. 大盤 ===
    df_index = get_fm_data("TaiwanStockIndex", "TAIEX", days=3)

    p = _safe_last(df_price, ['close', 'Trading_Volume'])
    v = _safe_last(df_per, ['PER'])
    s = _safe_last(df_stats, ['Buy_Order_Quantity', 'Sell_Order_Quantity'])
    m = _safe_last(df_index, ['last_price'])

    # === 數值抽取 ===
    close_price = float(p['close']) if p is not None else 0
    volume = int(p['Trading_Volume']) if p is not None else 0
    per = float(v['PER']) if v is not None else 0

    buy_q = int(s['Buy_Order_Quantity']) if s is not None else 0
    sell_q = int(s['Sell_Order_Quantity']) if s is not None else 0

    order_label, order_ratio = _order_strength(buy_q, sell_q)
    valuation_label = _valuation_level(per)

    insight = {
        # === 給人看的 ===
        "k_line": f"收 {close_price} / 量 {volume}",
        "valuation": f"PER {per:.2f} ({valuation_label})" if per > 0 else "N/A",
        "order_strength": f"{order_label} ({order_ratio:.2f})",
        "market_context": f"加權 {m['last_price']}" if m is not None else "N/A",

        # === 給 AI / 風控用的 ===
        "price": close_price,
        "volume": volume,
        "per": per,
        "valuation_level": valuation_label,
        "buy_sell_ratio": order_ratio,
        "order_level": order_label,

        # === 保留欄位（未來擴充）===
        "inst": "normal",
        "rev": "normal",
        "holders": "stable"
    }

    print(f"✅ {symbol} 高階指標完成")
    return insight
