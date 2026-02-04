import os
import requests
import pandas as pd
from datetime import datetime, timedelta

# 請確保在 Render 的 Environment Variables 設定此變數
FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN')

def get_fm_data(dataset, stock_id, days=30):
    """通用的 FinMind 數據抓取工具"""
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": dataset,
        "data_id": stock_id.replace(".TW", ""),
        "start_date": start_date,
        "token": FINMIND_TOKEN
    }
    try:
        res = requests.get(url, params=params)
        return pd.DataFrame(res.json()['data'])
    except:
        return pd.DataFrame()

def get_high_level_insight(symbol):
    """
    整合法人籌碼與基本面營收
    """
    stock_id = symbol.replace(".TW", "")
    
    # 1. 法人買賣超 (近 3 日趨勢)
    df_inst = get_fm_data("TaiwanStockInstitutionalInvestorsBuySell", stock_id)
    inst_msg = "籌碼數據讀取中"
    if not df_inst.empty:
        # 篩選外資與投信
        foreign = df_inst[df_inst['name'] == 'Foreign_Investor']['diff'].tail(3).sum()
        sitc = df_inst[df_inst['name'] == 'SITC']['diff'].tail(3).sum()
        inst_msg = f"外資:{int(foreign):+}, 投信:{int(sitc):+}"

    # 2. 月營收 (YoY 基本面)
    df_rev = get_fm_data("TaiwanStockMonthRevenue", stock_id, days=120)
    rev_msg = "營收校對中"
    if not df_rev.empty:
        latest_rev_yoy = df_rev.iloc[-1]['revenue_comparison_minus_relative_percent']
        rev_msg = f"營收YoY: {latest_rev_yoy:.2f}%"

    # 3. 大戶持股 (每週更新一次)
    df_holders = get_fm_data("TaiwanStockShareholdingSpread", stock_id, days=14)
    holder_msg = "持股比例穩定"
    if not df_holders.empty:
        # 抓取 1000 股以上的大戶持股比例 (通常是 index 15)
        big_holders = df_holders[df_holders['level'] == '1000-up'].iloc[-1]['proportion']
        holder_msg = f"千張大戶: {big_holders:.1f}%"

    return {
        "inst": inst_msg,
        "rev": rev_msg,
        "holders": holder_msg
    }
