import os
import yfinance as yf
import pandas as pd
import requests

# ==========================================
# 🔐 讓程式自動去 GitHub 保險箱拿鑰匙
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

# 設定你想觀察的股票代號 (包含剛上市的 009816 和上櫃的 00720B)
tickers = [‘0050.TW’, ‘0052.TW’, ‘009816.TW’, ‘0056.TW’, ‘00720B.TWO’, ‘00725B.TWO’, ‘00931B.TWO’, ‘00937B.TWO’, ‘00722B.TWO’, ‘00761B.TWO’]

def send_line_message(msg):
    url = 'https://api.line.me/v2/bot/message/push'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
    }
    data = {
        'to': USER_ID,
        'messages': [{'type': 'text', 'text': msg}]
    }
    requests.post(url, headers=headers, json=data)

def analyze_stocks(tickers):
    report_message = "📈 【股票小秘書】今日買賣點掃描報告\n" + "-" * 20 + "\n"
    
    for ticker in tickers:
        try:
            data = yf.download(ticker, period='6mo', progress=False)
            
            if data.empty:
                report_message += f"\n代號: {ticker} -> 找不到資料\n"
                continue
            
            latest_close = float(data['Close'].iloc[-1].iloc[0]) if isinstance(data['Close'].iloc[-1], pd.Series) else float(data['Close'].iloc[-1])

            if len(data) < 50:
                report_message += f"\n代號: {ticker}\n收盤價: {latest_close:.2f}\n狀態: ⚪ 上市太短，尚無長均線\n"
                continue
            
            data['SMA_20'] = data['Close'].rolling(window=20).mean()
            data['SMA_50'] = data['Close'].rolling(window=50).mean()
            
            latest = data.iloc[-1]
            prev = data.iloc[-2]
            
            latest_SMA20 = float(latest['SMA_20'].iloc[0]) if isinstance(latest['SMA_20'], pd.Series) else float(latest['SMA_20'])
            latest_SMA50 = float(latest['SMA_50'].iloc[0]) if isinstance(latest['SMA_50'], pd.Series) else float(latest['SMA_50'])
            prev_SMA20 = float(prev['SMA_20'].iloc[0]) if isinstance(prev['SMA_20'], pd.Series) else float(prev['SMA_20'])
            prev_SMA50 = float(prev['SMA_50'].iloc[0]) if isinstance(prev['SMA_50'], pd.Series) else float(prev['SMA_50'])

            signal = "⚪ 觀望"
            if latest_SMA20 > latest_SMA50 and prev_SMA20 <= prev_SMA50:
                signal = "🟢 買入訊號 (黃金交叉)"
            elif latest_SMA20 < latest_SMA50 and prev_SMA20 >= prev_SMA50:
                signal = "🔴 賣出訊號 (死亡交叉)"
            
            report_message += f"\n代號: {ticker}\n收盤價: {latest_close:.2f}\n狀態: {signal}\n"
            
        except Exception as e:
            report_message += f"\n代號: {ticker} -> 發生錯誤跳過\n"

    send_line_message(report_message)

analyze_stocks(tickers)
