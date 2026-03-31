import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import base64

# ==========================================
# 🔐 鑰匙區
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')

tickers = ['0050.TW', '0052.TW', '009816.TW', '0056.TW', '00720B.TWO', '00725B.TWO', '00931B.TWO', '00937B.TWO', '00679B.TWO', '00761B.TWO']

def generate_chart(ticker):
    """畫圖並上傳到 Imgbb，回傳圖片網址"""
    try:
        data = yf.Ticker(ticker).history(period='3mo') # 抓近3個月畫圖
        if data.empty: return None
        
        data['SMA_20'] = data['Close'].rolling(window=20).mean()
        
        # 設定畫布
        plt.figure(figsize=(8, 4))
        plt.plot(data.index, data['Close'], label='Close Price', color='#1f77b4', linewidth=2)
        plt.plot(data.index, data['SMA_20'], label='20MA (Monthly)', color='#ff7f0e', linestyle='--')
        plt.title(f"{ticker} - Last 3 Months", fontsize=14)
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend()
        
        # 把圖存在記憶體中
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        
        # 將圖片轉碼並上傳到 Imgbb
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        res = requests.post(
            f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}",
            data={"image": img_b64}
        ).json()
        
        return res['data']['url'] # 回傳公開網址
    except Exception as e:
        print(f"畫圖失敗: {e}")
        return None

def send_line_message(text_msg, image_url=None):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
    }
    
    # 🌟 組合訊息：包含文字，如果有圖就加上圖！
    messages = [{'type': 'text', 'text': text_msg}]
    if image_url:
        messages.append({
            'type': 'image',
            'originalContentUrl': image_url,
            'previewImageUrl': image_url
        })
        
    data = {'messages': messages}
    requests.post(url, headers=headers, json=data)

def analyze_stocks(tickers):
    report_message = "📊 【股票小秘書】極簡掃描報告\n" + "=" * 20 + "\n"
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1y')
            if data.empty: continue
            
            latest_close = float(data['Close'].iloc[-1])
            prev_close = float(data['Close'].iloc[-2])
            
            change_pct = ((latest_close - prev_close) / prev_close) * 100
            change_text = f"(🔺+{change_pct:.1f}%)" if change_pct > 0 else (f"(🟢{change_pct:.1f}%)" if change_pct < 0 else "(平盤)")
            alert_header = "🚨【劇烈波動】\n" if abs(change_pct) >= 5.0 else ""

            # 智能計分
            score = 0
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'] + 0.00001)
            latest_K = float(data['RSV'].ewm(com=2, adjust=False).mean().iloc[-1])
            
            if latest_K < 20: score += 1
            elif latest_K > 80: score -= 2
            if len(data) >= 120 and float(data['Close'].rolling(window=60).mean().iloc[-1]) > float(data['Close'].rolling(window=120).mean().iloc[-1]): score += 1

            if score >= 2: light = "🟢強烈買進"
            elif score == 1: light = "🟡逢低試單"
            elif score < 0: light = "🔴獲利避險"
            else: light = "⚪繼續觀望"

            report_message += f"{alert_header}【{ticker}】{light}\n"
            report_message += f"收盤: {latest_close:.2f} {change_text} | K:{latest_K:.1f}\n"
            report_message += "-" * 17 + "\n"
            
        except Exception:
            report_message += f"【{ticker}】 讀取錯誤\n" + "-" * 17 + "\n"

    # 🌟 報告算完後，專門幫 0050 畫一張大盤走勢圖！
    chart_url = generate_chart('0050.TW')
    
    # 傳送文字報告 + 圖片
    send_line_message(report_message, chart_url)

analyze_stocks(tickers)
    
