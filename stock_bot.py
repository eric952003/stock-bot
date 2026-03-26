import os
import yfinance as yf
import pandas as pd
import requests

# ==========================================
# 🔐 讓程式自動去 GitHub 保險箱拿鑰匙
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
# (廣播模式下其實不需要 USER_ID 了，但保留著以免未來想改回來)
USER_ID = os.environ.get('LINE_USER_ID')

# 設定你想觀察的股票代號
tickers = ['0050.TW', '0052.TW', '00692.TW', '009816.TW', '0056.TW', '00720B.TWO', '00725B.TWO', '00931B.TWO', '00937B.TWO', '00722B.TWO', '00761B.TWO']

# 🌟 升級核心：將發送模式從 push(私訊) 改為 broadcast(廣播)
def send_line_message(msg):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
    }
    data = {
        'messages': [{'type': 'text', 'text': msg}]
    }
    requests.post(url, headers=headers, json=data)

def analyze_stocks(tickers):
    report_message = "📈 【股票小秘書】ETF進階掃描報告\n" + "=" * 20 + "\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1y')
            
            if data.empty:
                report_message += f"\n代號: {ticker} -> 找不到資料\n"
                continue
            
            latest_close = float(data['Close'].iloc[-1])
            latest_vol = float(data['Volume'].iloc[-1])
            
            # === 1. 計算 KD 指標 ===
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'] + 0.00001)
            data['K'] = data['RSV'].ewm(com=2, adjust=False).mean()
            data['D'] = data['K'].ewm(com=2, adjust=False).mean()
            
            latest_K = float(data['K'].iloc[-1])
            latest_D = float(data['D'].iloc[-1])
            
            if pd.isna(latest_K) or latest_K == 0.0:
                kd_status = "計算中"
            else:
                kd_status = f"K:{latest_K:.1f} D:{latest_D:.1f}"
                if latest_K < 20:
                    kd_status += " 🌟超跌便宜"
                elif latest_K > 80:
                    kd_status += " ⚠️漲多過熱"

            # === 2. 突發爆量警報 ===
            vol_alert = ""
            if len(data) >= 6:
                data['VOL_5'] = data['Volume'].rolling(window=5).mean()
                prev_vol_5 = float(data['VOL_5'].iloc[-2])
                
                if prev_vol_5 > 0 and latest_vol > (prev_vol_5 * 2):
                    vol_alert = f"\n🚨 突發警報：今日爆量 ({latest_vol/prev_vol_5:.1f}倍)！"

            # === 3. 長天期均線 ===
            signal = "⚪ 觀望"
            if len(data) >= 120:
                data['SMA_60'] = data['Close'].rolling(window=60).mean()
                data['SMA_120'] = data['Close'].rolling(window=120).mean()
                
                latest_SMA60 = float(data['SMA_60'].iloc[-1])
                latest_SMA120 = float(data['SMA_120'].iloc[-1])
                prev_SMA60 = float(data['SMA_60'].iloc[-2])
                prev_SMA120 = float(data['SMA_120'].iloc[-2])
                
                if latest_SMA60 > latest_SMA120 and prev_SMA60 <= prev_SMA120:
                    signal = "🟢 季線突破半年線"
                elif latest_SMA60 < latest_SMA120 and prev_SMA60 >= prev_SMA120:
                    signal = "🔴 季線跌破半年線"
            else:
                signal = "⚪ 上市太短，無長均線"

            report_message += f"\n代號: {ticker}\n收盤價: {latest_close:.2f}\n長線: {signal}\n指標: {kd_status}{vol_alert}\n"
            
        except Exception as e:
            report_message += f"\n代號: {ticker} -> 發生錯誤 (原因: {str(e)[:15]})\n"

    send_line_message(report_message)

analyze_stocks(tickers)
