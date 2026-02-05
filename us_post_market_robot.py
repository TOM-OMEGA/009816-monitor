# us_post_market_robot.py
import os
import requests
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as fm  # 💡 新增：字體管理器
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

# ==== 新增: 引用 AI 模組 ====
from ai_expert import get_us_ai_point

# ==== 解決 Linux/Render 中文亂碼的終極方案 ====
def setup_chinese_font():
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    os.makedirs(static_dir, exist_ok=True)
    font_path = os.path.join(static_dir, "NotoSansTC-Regular.otf")
    
    if not os.path.exists(font_path):
        print("⚠️ 檢測到缺少中文字體，正在下載 NotoSansTC...")
        url = "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Regular.otf"
        try:
            r = requests.get(url, timeout=30)
            with open(font_path, 'wb') as f:
                f.write(r.content)
            print("✅ 字體下載完成！")
        except Exception as e:
            print(f"❌ 字體下載失敗: {e} (將使用預設字體，中文可能亂碼)")
            return None

    try:
        fm.fontManager.addfont(font_path)
        font_prop = fm.FontProperties(fname=font_path)
        font_name = font_prop.get_name()
        plt.rcParams['font.family'] = font_name
        plt.rcParams['axes.unicode_minus'] = False
        print(f"✅ 已成功設定中文字體: {font_name}")
        return font_name
    except Exception as e:
        print(f"⚠️ 字體載入異常: {e}")
        return None

setup_chinese_font()

LINE_TOKEN = os.environ.get("LINE_ACCESS_TOKEN")
USER_ID = os.environ.get("USER_ID")

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
    df = ticker.history(period=period, auto_adjust=True)
    return df

# ==== RSI 計算 ====
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-6)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)

def rebound_probability(df):
    rsi = compute_rsi(df['Close'])
    latest_rsi = rsi.iloc[-1] if not rsi.empty else 50
    rebound = max(0, min(100, 100 - latest_rsi))
    drop = max(0, min(100, latest_rsi))
    return latest_rsi, rebound, drop

def recent_trend_score(df):
    if len(df) < 5:
        return 0, 0
    closes = df['Close'].iloc[-4:]
    diffs = closes.diff().dropna()
    up_days = sum(1 for d in diffs if d > 0)
    down_days = sum(1 for d in diffs if d < 0)
    return min(100, up_days*33), min(100, down_days*33)

# ==== 圖表生成 ====
def plot_chart(dfs):
    fig, (ax1, ax2) = plt.subplots(2,1,figsize=(12,10), sharex=True, gridspec_kw={'height_ratios':[2,1]})
    colors = ['tab:blue','tab:orange','tab:green','tab:red']
    for i, (symbol, df) in enumerate(dfs.items()):
        if df.empty: continue
        df = df.copy()
        df['RSI'] = compute_rsi(df['Close'])
        color = colors[i%len(colors)]
        label_name = TARGETS_MAP.get(symbol,symbol)
        normalized_price = (df['Close']/df['Close'].iloc[0])*100
        ax1.plot(df.index, normalized_price, label=label_name, color=color, linewidth=1.5)
        ax2.plot(df.index, df['RSI'], label=label_name, color=color, linewidth=1, linestyle='--')
    ax1.set_title("美股焦點走勢對比 (近30日)", fontsize=14, fontweight='bold')
    ax1.set_ylabel("標準化價格 (起始日=100)")
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle='--', alpha=0.6)
    ax2.set_title("相對強弱指標 (RSI 14日)")
    ax2.set_ylabel("RSI 數值 (0-100)")
    ax2.set_ylim(0,100)
    ax2.axhline(70,color='r',linestyle=':',alpha=0.5,label='超買區(70)')
    ax2.axhline(30,color='g',linestyle=':',alpha=0.5,label='超賣區(30)')
    ax2.axhline(50,color='gray',linestyle='-',linewidth=0.5,alpha=0.3)
    ax2.fill_between(df.index,70,100,color='red',alpha=0.1)
    ax2.fill_between(df.index,0,30,color='green',alpha=0.1)
    ax2.grid(True, linestyle='--', alpha=0.6)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(PLOT_FILE, dpi=100)
    plt.close()
    print(f"🖼 圖表已存至 {PLOT_FILE}")
    return PLOT_FILE

# ==== 文字報告 ====
def generate_report(dfs):
    us_eastern = timezone(timedelta(hours=-5))
    report_date = datetime.now(us_eastern).strftime("%Y-%m-%d")
    report = f"🦅 美股盤後快報 [{report_date}]\n"
    report += "========================\n"
    for symbol, df in dfs.items():
        if df.empty or len(df)<20:
            report += f"⚠️ {TARGETS_MAP.get(symbol,symbol)} 資料不足\n"
            continue
        last = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        pct = (last/prev-1)*100
        rsi_val, rebound_prob, drop_prob = rebound_probability(df)
        rebound_score, drop_score = recent_trend_score(df)
        ma5 = df['Close'].rolling(5).mean().iloc[-1]
        ma20 = df['Close'].rolling(20).mean().iloc[-1]
        if ma5>ma20 and last>ma5:
            trend_emoji = "🟢強勢多頭"
        elif ma5>ma20:
            trend_emoji = "🟡多頭回檔"
        elif ma5<ma20 and last<ma5:
            trend_emoji = "🔴強勢空頭"
        else:
            trend_emoji = "🟠空頭反彈"
        name = TARGETS_MAP.get(symbol,symbol)
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
    payload_text = {"to": USER_ID, "messages":[{"type":"text","text":report}]}
    try:
        print("正在發送 LINE 文字報告...")
        res_text = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_text, timeout=15)
        if res_text.status_code==200:
            print("✅ LINE 文字推播成功")
        else:
            print(f"⚠️ LINE 文字推播失敗: {res_text.text}")
    except Exception as e:
        print(f"⚠️ LINE 文字推播錯誤: {e}")
    if plot_path and os.path.exists(plot_path):
        base_url = os.environ.get("RENDER_EXTERNAL_URL")
        if not base_url:
            print("ℹ️ 本地測試模式：無法取得公開 URL，跳過圖片推播")
            return
        timestamp = int(datetime.now().timestamp())
        plot_url = f"{base_url}/static/plot.png?t={timestamp}"
        print(f"正在發送 LINE 圖片... (URL: {plot_url})")
        payload_img = {"to": USER_ID, "messages":[{"type":"image","originalContentUrl":plot_url,"previewImageUrl":plot_url}]}
        try:
            res_img = requests.post("https://api.line.me/v2/bot/message/push", headers=headers, json=payload_img, timeout=20)
            if res_img.status_code==200:
                print("✅ LINE 圖片推播成功")
            else:
                print(f"⚠️ LINE 圖片推播失敗: {res_img.text}")
        except Exception as e:
            print(f"⚠️ LINE 圖片推播錯誤: {e}")

# ==== 主程式 (已新增美股 AI 判斷) ====
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

    # ==== 新增: 美股 AI 判斷 ====
    us_ai_data = {sym: {"last_close": df['Close'].iloc[-1]} for sym, df in dfs.items()}
    try:
        us_signal = get_us_ai_point(extra_data=us_ai_data, target_name="US_MARKET")
        print(f"🤖 美股 AI 判斷結果: {us_signal}")
    except Exception as e:
        print(f"⚠️ 美股 AI 判斷失敗: {e}")
        us_signal = {"decision":"觀望","confidence":0,"reason":"AI失敗"}

    print("任務完成!")
    return us_signal  # 可回傳給台股 AI 使用

# ==== 排程設定 ====
def schedule_job():
    import schedule
    import time
    run_time_tw = "05:05"
    schedule.every().day.at(run_time_tw).do(run_us_post_market)
    print(f"📅 排程已啟動，預計每天台灣時間 {run_time_tw} 執行")
    while True:
        schedule.run_pending()
        time.sleep(60)

# ==== 測試模式 ====
if __name__ == "__main__":
    TEST_MODE = True
    if not LINE_TOKEN:
         print("⚠️ 警告: 未設定 LINE_ACCESS_TOKEN，將無法發送訊息。")
    if TEST_MODE:
        print("🚀 === 啟動測試模式 (立即執行一次) ===")
        run_us_post_market()
    else:
        print("🕒 === 啟動排程模式 (等待時間到達) ===")
        schedule_job()
