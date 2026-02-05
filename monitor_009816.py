import requests
import os
from datetime import datetime, timedelta, timezone
from ai_expert import get_ai_point
from data_engine import get_high_level_insight, get_fm_data

LINE_TOKEN = os.environ.get('LINE_ACCESS_TOKEN')
USER_ID = os.environ.get('USER_ID')

def run_009816_monitor():
    print("\n" + "="*30)
    print("🚀 啟動 009816 最終穩定版監控 (FinMind 驅動)")
    
    # 1. 改用 FinMind 抓取即時價格 (代替 yfinance)
    print("📡 正在從 FinMind 獲取即時量價...")
    df_price = get_fm_data("TaiwanStockPrice", "009816", days=5)
    
    if df_price.empty:
        print("❌ 錯誤：FinMind 抓不到價格數據，請檢查 Token")
        return "PRICE_DATA_EMPTY"
    
    price_00 = float(df_price.iloc[-1]['close'])
    prev_close = float(df_price.iloc[-2]['close'])
    pct_00 = ((price_00 / prev_close) - 1) * 100
    print(f"✅ 009816 當前價格: {price_00} ({pct_00:+.2f}%)")

    # 2. 調閱 11 維度全籌碼數據
    print("📊 正在調閱 11 維度深度指標...")
    extra_data = get_high_level_insight("009816.TW")
    
    # 3. 獲取大盤參考數據 (同樣改由 FinMind 提供)
    df_idx = get_fm_data("TaiwanStockIndex", "TAIEX", days=2)
    market_price = df_idx.iloc[-1]['last_price'] if not df_idx.empty else "N/A"

    now_tw = datetime.now(timezone(timedelta(hours=8)))
    current_time = now_tw.strftime("%H:%M:%S")
    
    gap = round(price_00 - 10.12, 2)
    gap_msg = f"🚩 距離目標 10.12 還差 {gap} 元" if gap > 0 else "🔥 已達 10.12 進場紀律位階！"
    
    summary = f"009816價:{price_00:.2f} ({pct_00:+.2f}%)\n大盤:{market_price}\n時間:{current_time}"

    # 4. 呼叫 AI 專家
    print("🧠 正在請求 Gemini 進行 2027 深度診斷...")
    try:
        ai_msg = get_ai_point(summary, "009816 結婚基金", extra_data)
        print("✅ AI 診斷成功")
    except Exception as e:
        print(f"❌ AI 診斷報錯: {e}")
        ai_msg = "💡 AI 顧問連線中，請依紀律操作。"

    # 5. 構建戰報並發送
    full_msg = (
        f"🦅 經理人精準戰報 ({current_time})\n"
        f"------------------\n"
        f"{summary}\n"
        f"📊 籌碼指標: {extra_data.get('valuation', 'N/A')}\n"
        f"📈 盤中力道: {extra_data.get('order_strength', '穩定')}\n"
        f"------------------\n"
        f"{gap_msg}\n"
        f"------------------\n"
        f"🧠 AI 診斷：\n{ai_msg}"
    )
    
    if LINE_TOKEN and USER_ID:
        print("📤 推送訊息至 Line...")
        url = "https://api.line.me/v2/bot/message/push"
        headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}
        payload = {"to": USER_ID, "messages": [{"type": "text", "text": full_msg}]}
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=15)
            print(f"📊 Line 狀態碼: {res.status_code}")
            return f"SUCCESS_{res.status_code}"
        except Exception as e:
            print(f"❌ Line 發送崩潰: {e}")
            return "LINE_FAILED"
    return "NO_KEYS"
