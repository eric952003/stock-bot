import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import base64
import matplotlib.font_manager as fm

# ==========================================
# 🔐 鑰匙與字型設定
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')

# 設定中文字型：優先尋找 Ubuntu 上的 Noto Sans CJK
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK TC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False # 解決負號顯示問題

tickers = ['0050.TW', '0052.TW', '009816.TW', '0056.TW', '00720B.TWO', '00725B.TWO', '00931B.TWO', '00937B.TWO', '00679B.TWO', '00761B.TWO']

def generate_chart(ticker, title_tag):
    """畫圖並上傳到 Imgbb，回傳圖片網址"""
    try:
        data = yf.Ticker(ticker).history(period='3mo')
        if data.empty: return None
        data['SMA_20'] = data['Close'].rolling(window=20).mean()
        
        plt.figure(figsize=(8, 4))
        plt.plot(data.index, data['Close'], label='收盤價', color='#1f77b4', linewidth=2)
        plt.plot(data.index, data['SMA_20'], label='20日均線', color='#ff7f0e', linestyle='--')
        
        # 🌟 標題現在可以顯示中文了！
        plt.title(f"{ticker} - {title_tag} (近三個月)", fontsize=14)
        plt.xlabel("日期")
        plt.ylabel("價格")
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        
        img_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        res = requests.post(f"https://api.imgbb.com/1/upload?key={IMGBB_API_KEY}", data={"image": img_b64}).json()
        return res['data']['url']
    except Exception:
        return None

def send_line_message(text_msg, image_urls):
    url = 'https://api.line.me/v2/bot/message/broadcast'
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'}
    
    messages = [{'type': 'text', 'text': text_msg}]
    # 🌟 依序加入觸發的圖片 (LINE 一次推播上限是 5 個訊息，所以我們只取前 4 張圖)
    for img_url in image_urls[:4]:
        messages.append({'type': 'image', 'originalContentUrl': img_url, 'previewImageUrl': img_url})
        
    requests.post(url, headers=headers, json={'messages': messages})

def analyze_stocks(tickers):
    report_message = "🚦 【股票小秘書】智能觸發報告\n" + "=" * 20 + "\n"
    triggered_charts = [] # 用來存儲需要發送的圖片網址
    
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            data = stock.history(period='1y')
            if data.empty: continue
            
            latest_close = float(data['Close'].iloc[-1])
            prev_close = float(data['Close'].iloc[-2])
            change_pct = ((latest_close - prev_close) / prev_close) * 100
            change_text = f"(🔺+{change_pct:.1f}%)" if change_pct > 0 else (f"(🟢{change_pct:.1f}%)" if change_pct < 0 else "(平盤)")

            # 智能計分與紅綠燈
            score = 0
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'] + 0.00001)
            latest_K = float(data['RSV'].ewm(com=2, adjust=False).mean().iloc[-1])
            if latest_K < 20: score += 1
            elif latest_K > 80: score -= 2
            if len(data) >= 120 and float(data['Close'].rolling(window=60).mean().iloc[-1]) > float(data['Close'].rolling(window=120).mean().iloc[-1]): score += 1
            
            # 判斷燈號
            if score >= 2: light = "🟢強烈買進"
            elif score == 1: light = "🟡逢低試單"
            elif score < 0: light = "🔴獲利避險"
            else: light = "⚪繼續觀望"

            report_message += f"【{ticker}】{light}\n收盤: {latest_close:.2f} {change_text} | K:{latest_K:.1f}\n" + "-"*17 + "\n"

            # 🌟 智能觸發畫圖：只有強烈訊號才畫圖
            if score >= 2 or score < 0:
                img_url = generate_chart(ticker, light)
                if img_url: triggered_charts.append(img_url)
            
        except Exception:
            report_message += f"【{ticker}】 錯誤\n"

    send_line_message(report_message, triggered_charts)

analyze_stocks(tickers)
