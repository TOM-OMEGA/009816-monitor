import os
from datetime import datetime

def run_009816_monitor():
    """
    系統巡檢 / 台股監控內容生成
    不再直接發送 Discord，改為 return 文字內容
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 這裡未來可以加入 yfinance 的數據分析
    # 目前作為系統連線狀態的占位報告
    report = (
        f"📊 **系統連線診斷**\n"
        f"狀態: 🟢 監控運作中\n"
        f"時間: `{now_str}`\n"
        f"附註: 台股存股模組待命執行中。"
    )
    
    return report

# === ✅ 標準入口（給 main.py 用）===
def run_taiwan_stock():
    """
    統一給 main.py import 的入口
    """
    try:
        # 直接調用生成報告的函式
        return run_009816_monitor()
    except Exception as e:
        return f"❌ 台股監控模組執行異常: {str(e)}"
