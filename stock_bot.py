import os
import yfinance as yf
import pandas as pd
import requests

# ==========================================
# 🔐 讓程式自動去 GitHub 保險箱拿鑰匙
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

# 設定你想觀察的股票代號
tickers = ['0050.TW', '0052.TW', '009816.TW', '0056.TW', '00720B.TWO', '00725B.TWO', '00931B.TWO', '00937B.TWO', '00722B.TWO', '00761B.TWO']

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
    report_message = "🚦 【股票小秘書】買賣紅綠燈報告\n" + "=" * 20 + "\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1y')
            
            if data.empty:
                continue
            
            latest_close = float(data['Close'].iloc[-1])
            latest_vol = float(data['Volume'].iloc[-1])
            
            # 準備計算掛單價需要的數據 (5日均線、昨日最高價)
            data['SMA_5'] = data['Close'].rolling(window=5).mean()
            latest_SMA5 = float(data['SMA_5'].iloc[-1]) if len(data) >= 5 else latest_close
            prev_high = float(data['High'].iloc[-2]) if len(data) >= 2 else latest_close

            # 🌟 智能計分系統 (初始為0分)
            score = 0
            
            # === 1. 計算 KD 指標 ===
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'] + 0.00001)
            data['K'] = data['RSV'].ewm(com=2, adjust=False).mean()
            data['D'] = data['K'].ewm(com=2, adjust=False).mean()
            
            latest_K = float(data['K'].iloc[-1])
            
            kd_status = f"K:{latest_K:.1f}"
            if not pd.isna(latest_K) and latest_K > 0:
                if latest_K < 20:
                    kd_status += " (超跌)"
                    score += 1  # 便宜加分
                elif latest_K > 80:
                    kd_status += " (過熱)"
                    score -= 2  # 危險扣分

            # === 2. 突發爆量警報 ===
            vol_alert = ""
            if len(data) >= 6:
                data['VOL_5'] = data['Volume'].rolling(window=5).mean()
                prev_vol_5 = float(data['VOL_5'].iloc[-2])
                
                if prev_vol_5 > 0 and latest_vol > (prev_vol_5 * 2):
                    vol_alert = " 💥爆量"
                    if latest_K < 50: 
                        score += 1  # 低檔爆量加分

            # === 3. 長天期均線 (季線 vs 半年線) ===
            trend_status = "無長均線"
            if len(data) >= 120:
                data['SMA_60'] = data['Close'].rolling(window=60).mean()
                data['SMA_120'] = data['Close'].rolling(window=120).mean()
                
                latest_SMA60 = float(data['SMA_60'].iloc[-1])
                latest_SMA120 = float(data['SMA_120'].iloc[-1])
                
                if latest_SMA60 > latest_SMA120:
                    trend_status = "多頭排列"
                    score += 1  # 趨勢向上加分
                else:
                    trend_status = "空頭排列"

            # === 4. 綜合判定紅綠燈與掛單價 ===
            suggest_price_text = ""
            
            if score >= 2:
                light = "🟢 強烈買進"
                buy_price = min(latest_close, latest_SMA5)
                suggest_price_text = f"🎯 建議買價: {buy_price:.2f} 左右 (參考5日線)"
            elif score == 1:
                light = "🟡 逢低試單"
                buy_price = min(latest_close, latest_SMA5)
                suggest_price_text = f"🎯 建議買價: {buy_price:.2f} 左右 (參考5日線)"
            elif score < 0:
                light = "🔴 獲利/避險"
                sell_price = max(latest_close, prev_high)
                suggest_price_text = f"🎯 建議賣價: {sell_price:.2f} 左右 (參考昨高)"
            else:
                light = "⚪ 繼續觀望"
                suggest_price_text = "🎯 建議動作: 多看少做，保留資金"
                
            # 組合最終報告文字
            report_message += f"\n【{ticker}】 {light}\n"
            report_message += f"💸 收盤: {latest_close:.2f}\n"
            report_message += f"📊 狀態: {trend_status} | {kd_status}{vol_alert}\n"
            report_message += f"{suggest_price_text}\n"
            report_message += "-" * 17 + "\n"
            
        except Exception as e:
            report_message += f"\n【{ticker}】 -> 發生錯誤\n"

    send_line_message(report_message)

analyze_stocks(tickers)
