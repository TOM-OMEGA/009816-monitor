# us_post_market_robot.py
import os
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates # 新增：用於優化圖表日期顯示
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd
import numpy as np # 新增 numpy 處理可能的計算問題

# 解決 matplotlib 中文顯示問題 (如果你的環境無法顯示中文，請註解掉這兩行)
plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei'] # windows 適用
plt.rcParams['axes.unicode_minus'] = False

LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")

# ===== 目標股票/指數 =====
# 建議加入一個對照字典，讓圖表顯示更直覺
TARGETS_MAP = {
    "^GSPC": "標普500",
    "^DJI": "道瓊工業",
    "^IXIC": "那斯達克",
    "TSM": "台積電ADR"
}
TARGETS = list(TARGETS_MAP.keys())

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")

os.makedirs(STATIC_DIR, exist_ok=True)

# ==== 資料抓取 ====
def fetch_data(symbol, period="30d"):
    print(f"抓取 {symbol} 資料中...")
    ticker = yf.Ticker(symbol)
    # 增加 auto_adjust=True 以獲取還原權值股價，分析較準確
    df = ticker.history(period=period, auto_adjust=True)
    return df

# ==== 計算 RSI ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    # 使用指數移動平均 (EMA) 計算 RSI 會更平滑標準
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, 1e-6) # 避免除以零
    rsi = 100 - (100 / (1 + rs))
    
    # 填補前期的 NaN 值
    rsi = rsi.fillna(50)
    return rsi

# ==== 反彈/下跌機率 ====
def rebound_probability(df):
    rsi = compute_rsi(df['Close'])
    latest_rsi = rsi.iloc[-1] if not rsi.empty else 50
    # 簡單的線性映射，RSI越低反彈機率越高
    rebound = max(0, min(100, 100 - latest_rsi))
    drop = max(0, min(100, latest_rsi))
    return latest_rsi, rebound, drop

# ==== 前 3 日趨勢分數 ====
def recent_trend_score(df):
    if len(df) < 5: # 至少需要 5 天資料來計算近 4 天的變化
        return 0, 0
    # 這裡邏輯稍微修正，取最後 4 天的收盤價，計算 3 次漲跌變化
    closes = df['Close'].iloc[-4:]
    diffs = closes.diff().dropna()
    
    up_days = sum(1 for d in diffs if d > 0)
    down_days = sum(1 for d in diffs if d < 0)
    
    rebound_score = min(100, up_days * 33)
    drop_score = min(100, down_days * 33)
    return rebound_score, drop_score

# ==== (重點修改) 圖表生成 ====
def plot_chart(dfs):
    # 創建一個包含 2 個子圖的畫布，共享 X 軸，高度比為 2:1
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
    
    colors = ['tab:blue', 'tab:orange', 'tab:green', 'tab:red']
    
    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        df = df.copy()
        df['RSI'] = compute_rsi(df['Close'])
        color = colors[i % len(colors)]
        label_name = TARGETS_MAP.get(symbol, symbol)
        
        # --- 上圖：收盤價 ---
        # 如果是不同量級的商品(如道瓊和台積電)，畫在一起其實看不清楚台積電的波動
        # 這裡示範將它們標準化(以第一天為基準100)來比較走勢幅度，如果你想看絕對價格，請註解掉下面那行並取消註解再下一行
        normalized_price = (df['Close'] / df['Close'].iloc[0]) * 100
        ax1.plot(df.index, normalized_price, label=label_name, color=color, linewidth=1.5)
        # ax1.plot(df.index, df['Close'], label=label_name, color=color, linewidth=1.5) # 畫絕對價格
        
        # --- 下圖：RSI ---
        ax2.plot(df.index, df['RSI'], label=label_name, color=color, linewidth=1, linestyle='--')

    # --- 設定上圖 (價格) ---
    ax1.set_title("美股焦點走勢對比 (近30日)", fontsize=14, fontweight='bold')
    ax1.set_ylabel("標準化價格 (起始日=100)")
    # ax1.set_ylabel("收盤價 (美元/點數)") # 如果畫絕對價格，請改用這個 Y 軸標籤
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.6)
    
    # --- 設定下圖 (RSI) ---
    ax2.set_title("相對強弱指標 (RSI 14日)")
    ax2.set_ylabel("RSI 數值 (0-100)")
    ax2.set_ylim(0, 100) # RSI 固定在 0-100 之間
    # 加入 RSI 參考線
    ax2.axhline(70, color='r', linestyle=':', alpha=0.5, label='超買區(70)')
    ax2.axhline(30, color='g', linestyle=':', alpha=0.5, label='超賣區(30)')
    ax2.axhline(50, color='gray', linestyle='-', linewidth=0.5, alpha=0.3)
    ax2.fill_between(df.index, 70, 100, color='red', alpha=0.1) # 填充超買區顏色
    ax2.fill_between(df.index, 0, 30, color='green', alpha=0.1) # 填充超賣區顏色
    ax2.grid(True, linestyle='--', alpha=0.6)
    
    # --- 設定 X 軸日期格式 ---
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45) # 日期轉向避免重疊

    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=100) # 提高一點解析度
    plt.close()
    print(f"🖼 圖表已存至 {PLOT_FILE}")
    return PLOT_FILE

# ==== 文字報告 ====
def generate_report(dfs):
    # 獲取美東時間的昨天日期 (因為是盤後分析)
    us_eastern = timezone(timedelta(hours=-5)) # 標準時間是 -5, 日光節約是 -4，這裡簡化處理
    report_date = datetime.now(us_eastern).strftime("%Y-%m-%d")
    
    report = f"🦅 美股盤後快報 [{report_date}]\n"
    report += "========================\n"
    
    for symbol, df in dfs.items():
        if df.empty or len(df) < 20: 
            report += f"⚠️ {TARGETS_MAP.get(symbol, symbol)} 資料不足\n"
            continue
            
        last = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        pct = (last / prev - 1) * 100
        
        rsi_val, rebound_prob, drop_prob = rebound_probability(df)
        rebound_score, drop_score = recent_trend_score(df)
        
        # 計算均線趨勢
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        
        # 判斷趨勢燈號
        if ma5 > ma20 and last > ma5:
            trend_emoji = "🟢強勢多頭"
        elif ma5 > ma20:
            trend_emoji = "🟡多頭回檔"
        elif ma5 < ma20 and last < ma5:
            trend_emoji = "🔴強勢空頭"
        else:
            trend_emoji = "🟠空頭反彈"

        name = TARGETS_MAP.get(symbol, symbol)
        report += (
            f"【{name}】 {last:,.2f} ({pct:+.2f}%)\n"
            f"趨勢: {trend_emoji} | RSI: {rsi_val:.1f}\n"
            f"短線動能: 📈反彈{rebound_score:.0f}分 vs 📉下跌{drop_score:.0f}分\n"
            f"機率試算: 反彈機率{rebound_prob:.0f}%\n"
            "------------------------\n"
        )
    
    now_tw = datetime.now(timezone(timedelta(hours=8))).strftime("%H:%M")
    report += f"(台灣時間 {now_tw} 發送)"
    return report

# ==== LINE 推播 ====
def push_line(report, plot_path=None):
    if not LINE_TOKEN or not USER_ID:
        print("⚠️ LINE TOKEN 或 USER ID 未設定，跳過推播")
        print("----- 報告內容 -----")
        print(report)
        return

    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}

    # 文字推播
    payload_text = {"to": USER_ID, "messages":[{"type":"text","text":report}]}
    try:
        print("正在發送 LINE 文字報告...")
        res_text = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_text, timeout=15)
        if res_text.status_code == 200:
            print(f"✅ LINE 文字推播成功")
        else:
            print(f"⚠️ LINE 文字推播失敗: {res_text.text}")
    except Exception as e:
        print(f"⚠️ LINE 文字推播錯誤: {e}")

    # 圖片推播
    if plot_path and os.path.exists(plot_path):
        # 注意：如果不是在 Render 等伺服器環境，這裡需要一個公開可訪問的 URL
        base_url = os.environ.get("RENDER_EXTERNAL_URL") 
        if not base_url:
            print("ℹ️ 本地測試模式：無法取得公開 URL，跳過圖片推播 (僅儲存圖片)")
            # 如果你在本地測試，可以考慮用 imgur API 上傳圖片獲取連結，這裡暫不實作
            return
            
        # 在 URL 後面加上時間戳記，強制 LINE 重新讀取圖片，避免快取舊圖
        timestamp = int(datetime.now().timestamp())
        plot_url = f"{base_url}/static/plot.png?t={timestamp}"
        
        print(f"正在發送 LINE 圖片... (URL: {plot_url})")
        payload_img = {"to": USER_ID, "messages":[{"type":"image","originalContentUrl":plot_url,"previewImageUrl":plot_url}]}
        try:
            res_img = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_img, timeout=20)
            if res_img.status_code == 200:
                print(f"✅ LINE 圖片推播成功")
            else:
                # 常見錯誤是 URL 無法公開訪問或圖片太大
                print(f"⚠️ LINE 圖片推播失敗 (請檢查 URL 是否公開): {res_img.text}")
        except Exception as e:
            print(f"⚠️ LINE 圖片推播錯誤: {e}")

# ==== 主程式 ====
def run_us_post_market():
    print("開始執行美股盤後分析任務...")
    dfs = {}
    for symbol in TARGETS:
        try:
            df = fetch_data(symbol)
            if not df.empty:
                dfs[symbol] = df
        except Exception as e:
            print(f"⚠️ 抓取 {symbol} 失敗: {e}")
            
    if not dfs:
        print("❌ 無法獲取任何數據，任務終止")
        return

    report = generate_report(dfs)
    plot_path = plot_chart(dfs)
    push_line(report, plot_path)
    print("任務完成!")

# ==== 排程設定 ====
def schedule_job():
    import schedule
    import time
    # 設定美東時間下午 4:05 (收盤後)執行。
    # 需注意你的伺服器時區設定，如果伺服器是 UTC，美東 16:05 大約是 UTC 20:05 或 21:05
    # 這裡暫定為台灣時間早上 5:05 (夏令) 或 6:05 (冬令) 比較保險
    run_time_tw = "05:05" 
    schedule.every().day.at(run_time_tw).do(run_us_post_market)
    print(f"📅 排程已啟動，預計每天台灣時間 {run_time_tw} 執行")
    print("(請確保你的執行環境會持續運行，否則排程將失效)")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# ==== 測試模式 ====
if __name__ == "__main__":
    # 將此設為 False 以啟用排程模式
    TEST_MODE = True
    
    # 檢查是否有必要的環境變數
    if not LINE_TOKEN:
         print("⚠️ 警告: 未設定 LINE_ACCESS_TOKEN，將無法發送訊息。")
         # TEST_MODE = False # 強制不執行測試

    if TEST_MODE:
        print("🚀 === 啟動測試模式 (立即執行一次) ===")
        run_us_post_market()
    else:
        print("🕒 === 啟動排程模式 (等待時間到達) ===")
        schedule_job()
