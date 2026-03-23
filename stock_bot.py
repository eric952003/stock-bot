import os
import yfinance as yf
import pandas as pd
import requests

# ==========================================
# 🔐 讓程式自動去 GitHub 保險箱拿鑰匙
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
USER_ID = os.environ.get('LINE_USER_ID')

# 設定你想觀察的股票代號
tickers = ['0050.TW', '0052.TW', '009816.TW', '0056.TW', '00720B.TWO', '00725B.TWO', '00931B.TWO', '00937B.TWO', '00722B.TWO', '00761B.TWO']

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
    report_message = "📈 【股票小秘書】ETF進階掃描報告\n" + "=" * 20 + "\n"
    
    for ticker in tickers:
        try:
            # 🌟 修復核心：改用 yf.Ticker().history()，確保資料格式最乾淨單純
            stock = yf.Ticker(ticker)
            data = stock.history(period='1y')
            
            if data.empty:
                report_message += f"\n代號: {ticker} -> 找不到資料\n"
                continue
            
            # 直接取最後一筆資料
            latest_close = float(data['Close'].iloc[-1])
            latest_vol = float(data['Volume'].iloc[-1])
            
            # === 1. 計算 KD 指標 ===
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            
            # 🌟 修復核心：分母加上 0.00001，防止債券 ETF 價格不動導致「除以零」當機
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
                
                # 如果今日成交量 > 昨天為止的 5日均量 的 2 倍
                if prev_vol_5 > 0 and latest_vol > (prev_vol_5 * 2):
                    vol_alert = f"\n🚨 突發警報：今日爆量 ({latest_vol/prev_vol_5:.1f}倍)！"

            # === 3. 長天期均線 (季線 60MA vs 半年線 120MA) ===
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

            # 組合最終報告文字
            report_message += f"\n代號: {ticker}\n收盤價: {latest_close:.2f}\n長線: {signal}\n指標: {kd_status}{vol_alert}\n"
            
        except Exception as e:
            # 🌟 修復核心：萬一還有錯，把真正的「錯誤原因」抓出來傳到 LINE！
            report_message += f"\n代號: {ticker} -> 發生錯誤 (原因: {str(e)[:15]})\n"

    send_line_message(report_message)

analyze_stocks(tickers)

