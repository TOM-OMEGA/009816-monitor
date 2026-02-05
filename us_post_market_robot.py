# us_post_market_robot.py
import os
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
import requests
import pandas as pd

LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")

# ===== 目標股票/指數 =====
TARGETS = ["^GSPC", "^DJI", "^IXIC", "TSM"]

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
PLOT_FILE = os.path.join(STATIC_DIR, "plot.png")

os.makedirs(STATIC_DIR, exist_ok=True)

# ==== 資料抓取 ====
def fetch_data(symbol, period="30d"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period)
    return df

# ==== 計算 RSI ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta>0, 0)
    loss = -delta.where(delta<0, 0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean().replace(0, 1e-6)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

# ==== 反彈/下跌機率 ====
def rebound_probability(df):
    rsi = compute_rsi(df['Close'])
    latest_rsi = rsi.iloc[-1] if not rsi.empty else 50
    rebound = max(0, min(100, 100 - latest_rsi))
    drop = max(0, min(100, latest_rsi))
    return latest_rsi, rebound, drop

# ==== 前 3 日趨勢分數 ====
def recent_trend_score(df):
    if len(df) < 4:
        return 0,0
    closes = df['Close'].iloc[-4:]
    scores = [closes.iloc[i] - closes.iloc[i-1] for i in range(1,len(closes))]
    up_days = sum(1 for s in scores if s>0)
    down_days = sum(1 for s in scores if s<0)
    rebound_score = min(100, up_days*33)
    drop_score = min(100, down_days*33)
    return rebound_score, drop_score

# ==== 圖表生成 ====
def plot_chart(dfs):
    plt.figure(figsize=(12,6))
    for symbol, df in dfs.items():
        df = df.copy()
        df['pct_change'] = df['Close'].pct_change()*100
        df['RSI'] = compute_rsi(df['Close'])
        plt.plot(df.index, df['Close'], label=f"{symbol} 收盤價")
        plt.plot(df.index[-4:], df['pct_change'].iloc[-4:], linestyle='--', marker='o', label=f"{symbol} 連續3日漲跌%")
        plt.plot(df.index, df['RSI'], linestyle=':', label=f"{symbol} RSI")
    plt.title("美股盤後分析")
    plt.xlabel("日期")
    plt.ylabel("價格 / 漲跌% / RSI")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT_FILE)
    plt.close()
    print(f"🖼 圖表已存至 {PLOT_FILE}")
    return PLOT_FILE

# ==== 文字報告 ====
def generate_report(dfs):
    report = f"🦅 美股盤後分析報告 ({datetime.now(timezone(timedelta(hours=0))):%Y-%m-%d %H:%M})\n"
    report += "----------------------\n"
    for symbol, df in dfs.items():
        if df.empty: continue
        last = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2] if len(df)>=2 else last
        pct = round((last/prev-1)*100,2)
        rsi_val, rebound_prob, drop_prob = rebound_probability(df)
        rebound_score, drop_score = recent_trend_score(df)
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1] if len(df)>=20 else df['Close'].iloc[-1]
        trend = "多頭" if ma5>ma20 else "空頭" if ma5<ma20 else "盤整"
        report += (
            f"{symbol}: {last:.2f} ({pct:+.2f}%)\n"
            f"趨勢: {trend}, RSI: {rsi_val:.1f}\n"
            f"反彈機率: {rebound_prob:.0f}%, 下跌機率: {drop_prob:.0f}%\n"
            f"連續反彈動能分數: {rebound_score:.0f}, 連續下跌動能分數: {drop_score:.0f}\n"
            "----------------------\n"
        )
    return report

# ==== LINE 推播 ====
def push_line(report, plot_path=None):
    if not LINE_TOKEN or not USER_ID:
        print("⚠️ LINE TOKEN 或 USER ID 未設定")
        return

    headers = {"Authorization": f"Bearer {LINE_TOKEN}", "Content-Type": "application/json"}

    # 文字推播
    payload_text = {"to": USER_ID, "messages":[{"type":"text","text":report}]}
    try:
        res_text = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_text, timeout=10)
        print(f"📊 LINE 文字推播結果: {res_text.status_code}")
    except Exception as e:
        print(f"⚠️ LINE 文字推播失敗: {e}")

    # 圖片推播
    if plot_path:
        base_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not base_url:
            print("⚠️ 無法取得公開 URL，圖片無法推播")
            return
        plot_url = f"{base_url}/static/plot.png"
        payload_img = {"to": USER_ID, "messages":[{"type":"image","originalContentUrl":plot_url,"previewImageUrl":plot_url}]}
        try:
            res_img = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_img, timeout=10)
            print(f"📊 LINE 圖片推播結果: {res_img.status_code}")
        except Exception as e:
            print(f"⚠️ LINE 圖片推播失敗: {e}")

# ==== 主程式 ====
def run_us_post_market():
    dfs = {symbol: fetch_data(symbol) for symbol in TARGETS}
    report = generate_report(dfs)
    plot_path = plot_chart(dfs)
    push_line(report, plot_path)

# ==== 排程設定 ====
def schedule_job():
    import schedule, time
    schedule.every().day.at("21:05").do(run_us_post_market)
    print("📅 美股盤後分析排程已啟動，每天美東時間16:05自動執行")
    while True:
        schedule.run_pending()
        time.sleep(30)

# ==== 測試模式 ====
if __name__ == "__main__":
    TEST_MODE = True
    if TEST_MODE:
        print("🚀 測試模式，立即抓取資料與推播 LINE")
        run_us_post_market()
    else:
        schedule_job()
