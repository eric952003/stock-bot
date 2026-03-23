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
            # 將資料拉長到 1 年，確保算得出「半年線(120日)」
            data = yf.download(ticker, period='1y', progress=False)
            
            if data.empty:
                report_message += f"\n代號: {ticker} -> 找不到資料\n"
                continue
            
            # 建立一個小工具來安全取出數字
            def get_val(df, col, idx=-1):
                try:
                    val = df[col].iloc[idx]
                    return float(val.iloc[0]) if isinstance(val, pd.Series) else float(val)
                except:
                    return 0.0

            latest_close = get_val(data, 'Close', -1)
            latest_vol = get_val(data, 'Volume', -1)
            
            # === 1. 計算 KD 指標 ===
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'])
            # 使用 EWM 計算平滑 K 值與 D 值
            data['K'] = data['RSV'].ewm(com=2, adjust=False).mean()
            data['D'] = data['K'].ewm(com=2, adjust=False).mean()
            
            latest_K = get_val(data, 'K', -1)
            latest_D = get_val(data, 'D', -1)
            
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
                prev_vol_5 = get_val(data, 'VOL_5', -2)
                
                # 如果今日成交量 > 昨天為止的 5日均量 的 2 倍
                if prev_vol_5 > 0 and latest_vol > (prev_vol_5 * 2):
                    vol_alert = f"\n🚨 突發警報：今日爆量 ({latest_vol/prev_vol_5:.1f}倍)！"

            # === 3. 長天期均線 (季線 60MA vs 半年線 120MA) ===
            signal = "⚪ 觀望"
            if len(data) >= 120:
                data['SMA_60'] = data['Close'].rolling(window=60).mean()
                data['SMA_120'] = data['Close'].rolling(window=120).mean()
                
                latest_SMA60 = get_val(data, 'SMA_60', -1)
                latest_SMA120 = get_val(data, 'SMA_120', -1)
                prev_SMA60 = get_val(data, 'SMA_60', -2)
                prev_SMA120 = get_val(data, 'SMA_120', -2)
                
                if latest_SMA60 > latest_SMA120 and prev_SMA60 <= prev_SMA120:
                    signal = "🟢 季線突破半年線"
                elif latest_SMA60 < latest_SMA120 and prev_SMA60 >= prev_SMA120:
                    signal = "🔴 季線跌破半年線"
            else:
                signal = "⚪ 上市太短，無長均線"

            # 組合最終報告文字
            report_message += f"\n代號: {ticker}\n收盤價: {latest_close:.2f}\n長線: {signal}\n指標: {kd_status}{vol_alert}\n"
            
        except Exception as e:
            report_message += f"\n代號: {ticker} -> 資料處理發生錯誤\n"

    send_line_message(report_message)

analyze_stocks(tickers)
