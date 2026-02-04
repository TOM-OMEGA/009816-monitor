import os
import requests
import pandas as pd
from datetime import datetime, timedelta

FINMIND_TOKEN = os.environ.get('FINMIND_TOKEN')

def get_accurate_data(symbol):
    """從 FinMind 獲取法人籌碼與基本面精準數據"""
    # 移除 .TW 尾綴符合 API 格式
    stock_id = symbol.replace(".TW", "")
    today = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    payload = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": stock_id,
        "start_date": start_date,
        "token": FINMIND_TOKEN,
    }

    try:
        # 1. 抓取法人買賣超
        res = requests.get("https://api.finmindtrade.com/api/v4/data", params=payload)
        data = res.json()['data']
        df = pd.DataFrame(data)
        
        # 計算近三日外資合計買賣超
        foreign_buy = df[df['name'] == 'Foreign_Investor']['diff'].tail(3).sum()
        
        # 2. 抓取最新月營收 (基本面健檢)
        payload["dataset"] = "TaiwanStockMonthRevenue"
        res_rev = requests.get("https://api.finmindtrade.com/api/v4/data", params=payload)
        rev_data = res_rev.json()['data']
        rev_yoy = rev_data[-1]['revenue_comparison_minus_relative_percent'] if rev_data else 0

        return {
            "foreign_3d_sum": int(foreign_buy),
            "rev_yoy": float(rev_yoy),
            "status": "Success"
        }
    except Exception as e:
        return {"status": "Error", "msg": str(e)}
