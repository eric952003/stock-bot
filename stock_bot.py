import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 🔐 讓程式自動去 GitHub 保險箱拿鑰匙
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')

# 設定你想觀察的股票代號
tickers = ['0050.TW', '0052.TW', '009816.TW', '0056.TW', '00720B.TWO', '00725B.TWO', '00931B.TWO', '00937B.TWO', '00679B.TWO', '00761B.TWO']

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
    report_message = "💰 【股票小秘書】紅綠燈與配息偵測\n" + "=" * 20 + "\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1y')
            if data.empty: continue
            
            latest_close = float(data['Close'].iloc[-1])
            prev_close = float(data['Close'].iloc[-2])
            latest_vol = float(data['Volume'].iloc[-1])
            
            # --- 1. 計算漲跌幅 ---
            change_pct = ((latest_close - prev_close) / prev_close) * 100
            change_text = f"(🔺+{change_pct:.1f}%)" if change_pct > 0 else (f"(🔻{change_pct:.1f}%)" if change_pct < 0 else "(平盤)")
            alert_header = "🚨【劇烈波動】\n" if abs(change_pct) >= 5.0 else ""

            # --- 2. 獲取配息資訊 (TTM 過去一年總和) ---
            dividends = stock.dividends
            last_year_div = 0.0
            div_status = ""
            if not dividends.empty:
                # 篩選過去 365 天的配息
                one_year_ago = datetime.now() - timedelta(days=365)
                # 處理時區問題，統一轉為無時區比較
                last_year_divs = dividends[dividends.index.tz_localize(None) > one_year_ago]
                last_year_div = last_year_divs.sum()
                
                # 檢查最近 30 天是否有除息
                recent_divs = dividends[dividends.index.tz_localize(None) > (datetime.now() - timedelta(days=30))]
                if not recent_divs.empty:
                    div_status = " 🎁近期除息"

            # 計算殖利率
            yield_pct = (last_year_div / latest_close) * 100 if last_year_div > 0 else 0

            # --- 3. 智能計分與紅綠燈 ---
            score = 0
            # KD 指標
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'] + 0.00001)
            data['K'] = data['RSV'].ewm(com=2, adjust=False).mean()
            latest_K = float(data['K'].iloc[-1])
            if latest_K < 20: score += 1
            elif latest_K > 80: score -= 2
            
            # 均線趨勢
            if len(data) >= 120:
                sma60 = data['Close'].rolling(window=60).mean().iloc[-1]
                sma120 = data['Close'].rolling(window=120).mean().iloc[-1]
                if sma60 > sma120: score += 1
            
            # 爆量加分
            if len(data) >= 6:
                avg_vol = data['Volume'].rolling(window=5).mean().iloc[-2]
                if latest_vol > (avg_vol * 2) and latest_K < 50: score += 1
            
            # 🌟 殖利率加分：如果預估殖利率 > 5%，額外加 1 分
            if yield_pct >= 5.0: score += 1

            # --- 4. 判定與掛單價 ---
            data['SMA_5'] = data['Close'].rolling(window=5).mean()
            latest_SMA5 = float(data['SMA_5'].iloc[-1]) if len(data) >= 5 else latest_close
            prev_high = float(data['High'].iloc[-2]) if len(data) >= 2 else latest_close

            if score >= 2:
                light, suggest = "🟢 強烈買進", f"🎯 建議買價: {min(latest_close, latest_SMA5):.2f}"
            elif score == 1:
                light, suggest = "🟡 逢低試單", f"🎯 建議買價: {min(latest_close, latest_SMA5):.2f}"
            elif score < 0:
                light, suggest = "🔴 獲利/避險", f"🎯 建議賣價: {max(latest_close, prev_high):.2f}"
            else:
                light, suggest = "⚪ 繼續觀望", "🎯 建議動作: 多看少做"

            # --- 5. 組合報告 ---
            report_message += f"{alert_header}【{ticker}】 {light}\n"
            report_message += f"💸 收盤: {latest_close:.2f} {change_text}\n"
            report_message += f"💰 殖利率: {yield_pct:.1f}%{div_status}\n"
            report_message += f"📊 指標: K:{latest_K:.1f} | {suggest}\n"
            report_message += "-" * 17 + "\n"
            
        except Exception as e:
            report_message += f"\n【{ticker}】 -> 錯誤: {str(e)[:15]}\n"

    send_line_message(report_message)

analyze_stocks(tickers)
