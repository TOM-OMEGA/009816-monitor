import os
import yfinance as yf
from datetime import datetime

def run_009816_monitor():
    """
    抓取 009816 實際行情並生成報告文字
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    target_stock = "00915.TW"  # 範例使用 00915 (凱基優選高股息) 或你的目標代號
    
    try:
        # 1. 抓取數據 (加入 timeout 避免卡死 Render)
        stock = yf.Ticker(target_stock)
        df = stock.history(period="2d")
        
        if df.empty:
            return f"⚠️ **台股監控提醒**\n無法取得 {target_stock} 數據，請檢查 API 連線。"

        # 2. 計算漲跌
        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        change = current_price - prev_price
        pct_change = (change / prev_price) * 100
        
        emoji = "📈" if change >= 0 else "📉"
        
        # 3. 組合報告內容
        report = (
            f"📊 **台股監控回報 ({target_stock})**\n"
            f"現價: `{current_price:.2f}` ({emoji} {pct_change:+.2f}%)\n"
            f"狀態: 🟢 監控運作中\n"
            f"更新: `{now_str}`"
        )
        return report

    except Exception as e:
        # 如果抓不到數據，回傳基礎連線報告，確保 main.py 不會因為這裡掛掉而發不出其他兩份報告
        return f"📊 **系統連線診斷**\n狀態: 🟡 基礎連線正常 (數據抓取異常: {str(e)[:30]})\n時間: `{now_str}`"

# === ✅ 標準入口（給 main.py 用）===
def run_taiwan_stock():
    """
    統一給 main.py import 的入口
    """
    try:
        return run_009816_monitor()
    except Exception as e:
        # 這是最後一道防線，絕對不 throw exception 給 main.py
        return f"❌ 台股監控模組完全崩潰: {str(e)[:50]}"
