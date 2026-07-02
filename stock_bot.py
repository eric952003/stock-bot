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

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK TC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

tickers = ['0050.TW', '0052.TW', '009816.TW', '0056.TW', '00878.TW', '00919.TW', '00403A.TW']

# ==========================================
# 📊 功能函式區
# ==========================================
def generate_chart(ticker, title_tag):
    try:
        data = yf.Ticker(ticker).history(period='3mo')
        if data.empty: return None
        data['SMA_20'] = data['Close'].rolling(window=20).mean()
        
        plt.figure(figsize=(8, 4))
        plt.plot(data.index, data['Close'], label='收盤價', color='#1f77b4', linewidth=2)
        plt.plot(data.index, data['SMA_20'], label='20日均線', color='#ff7f0e', linestyle='--')
        
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
    for img_url in image_urls[:4]:
        messages.append({'type': 'image', 'originalContentUrl': img_url, 'previewImageUrl': img_url})
        
    requests.post(url, headers=headers, json={'messages': messages})

def get_institutional_data(ticker_tw):
    """透過 FinMind API 獲取三大法人買賣超資料"""
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": ticker_tw,
        "start_date": start_date,
    }
    
    try:
        response = requests.get(url, params=parameter)
        data = response.json()
        if data.get("msg") == "success" and len(data.get("data", [])) > 0:
            df = pd.DataFrame(data["data"])
            # 將三大法人的買進、賣出、淨買賣超按日期加總
            daily_data = df.groupby('date').agg({
                'buy': 'sum',
                'sell': 'sum',
                'sell_buy': 'sum'
            }).reset_index()
            return daily_data.sort_values('date').tail(2) # 回傳近兩日資料
    except Exception as e:
        pass # 抓不到就略過，不影響主程式運行
    return None

# ==========================================
# 🚀 主邏輯區
# ==========================================
def analyze_stocks(tickers):
    report_message = "📊 【股票小秘書】籌碼旗艦完全體\n" + "=" * 20 + "\n"
    triggered_charts = []
    
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
            change_text = f"(🔺+{change_pct:.1f}%)" if change_pct > 0 else (f"(🟢{change_pct:.1f}%)" if change_pct < 0 else "(平盤)")
            alert_header = "🚨【劇烈波動】\n" if abs(change_pct) >= 5.0 else ""

            # --- 2. 獲取配息資訊 ---
            dividends = stock.dividends
            last_year_div = 0.0
            div_status = ""
            
            try:
                if isinstance(dividends, pd.DataFrame):
                    dividends = dividends.iloc[:, 0]
                if isinstance(dividends, pd.Series) and not dividends.empty:
                    now = datetime.now()
                    for date, val in dividends.items():
                        try:
                            clean_date = date.tz_localize(None)
                        except Exception:
                            clean_date = date
                            
                        if type(clean_date) is pd.Timestamp or type(clean_date) is datetime:
                            if (now - clean_date).days <= 365:
                                last_year_div += float(val)
                            if (now - clean_date).days <= 30:
                                div_status = " (近除息)"
            except Exception:
                pass 

            yield_pct = (last_year_div / latest_close) * 100 if last_year_div > 0 else 0

            # --- 3. 智能計分與 KD ---
            score = 0
            data['L9'] = data['Low'].rolling(window=9).min()
            data['H9'] = data['High'].rolling(window=9).max()
            data['RSV'] = 100 * (data['Close'] - data['L9']) / (data['H9'] - data['L9'] + 0.00001)
            data['K'] = data['RSV'].ewm(com=2, adjust=False).mean()
            latest_K = float(data['K'].iloc[-1])
            
            if latest_K < 20: score += 1
            elif latest_K > 80: score -= 2
            
            if len(data) >= 120 and float(data['Close'].rolling(window=60).mean().iloc[-1]) > float(data['Close'].rolling(window=120).mean().iloc[-1]): score += 1
            if len(data) >= 6 and latest_vol > (float(data['Volume'].rolling(window=5).mean().iloc[-2]) * 2) and latest_K < 50: score += 1
            if yield_pct >= 5.0: score += 1

            # --- 4. 🌟 籌碼面分析 (FinMind) ---
            chip_light = ""
            pure_ticker = ticker.replace('.TW', '').replace('.TWO', '')
            inst_data = get_institutional_data(pure_ticker)
            
            if inst_data is not None and len(inst_data) >= 2:
                day_minus_1_net = inst_data['sell_buy'].iloc[-2]
                day_latest_net = inst_data['sell_buy'].iloc[-1]
                latest_inst_buy_vol = inst_data['buy'].iloc[-1]
                latest_inst_sell_vol = inst_data['sell'].iloc[-1]
                
                # 【買盤邏輯】
                if day_minus_1_net > 0 and day_latest_net > 0:
                    score += 1
                    chip_light += "🟢連買 "
                
                inst_buy_ratio = latest_inst_buy_vol / (latest_vol + 0.0001) 
                if inst_buy_ratio > 0.15: # 法人買超佔比 > 15%
                    score += 1
                    chip_light += f"🟢買佔({inst_buy_ratio*100:.0f}%) "
                    
                # 【賣盤邏輯】
                if day_minus_1_net < 0 and day_latest_net < 0:
                    score -= 1
                    chip_light += "🔴連賣 "
                    
                inst_sell_ratio = latest_inst_sell_vol / (latest_vol + 0.0001)
                if inst_sell_ratio > 0.15: # 法人賣超佔比 > 15%
                    score -= 1
                    chip_light += f"🔴賣佔({inst_sell_ratio*100:.0f}%) "

            # --- 5. 判定與掛單價 ---
            data['SMA_5'] = data['Close'].rolling(window=5).mean()
            latest_SMA5 = float(data['SMA_5'].iloc[-1]) if len(data) >= 5 else latest_close
            prev_high = float(data['High'].iloc[-2]) if len(data) >= 2 else latest_close

            if score >= 2: light, suggest = "🟢強烈買進", f"買點: {min(latest_close, latest_SMA5):.2f}"
            elif score == 1: light, suggest = "🟡逢低試單", f"買點: {min(latest_close, latest_SMA5):.2f}"
            elif score < 0: light, suggest = "🔴避險/減碼", f"賣點: {max(latest_close, prev_high):.2f}"
            else: light, suggest = "⚪繼續觀望", "建議: 多看少做"

            # --- 6. 組合報告 ---
            report_message += f"{alert_header}【{ticker}】{light}\n"
            report_message += f"收盤: {latest_close:.2f} {change_text}\n"
            report_message += f"殖利: {yield_pct:.1f}%{div_status} | K值: {latest_K:.1f}\n"
            if chip_light:
                report_message += f"籌碼: {chip_light}\n"
            report_message += f"🎯 {suggest}\n"
            report_message += "-" * 17 + "\n"

            # 觸發繪圖條件 (分數夠高或夠低)
            if score >= 2 or score < 0:
                img_url = generate_chart(ticker, light)
                if img_url: triggered_charts.append(img_url)
            
        except Exception as e:
            report_message += f"【{ticker}】 錯誤: {str(e)[:15]}\n" + "-" * 17 + "\n"

    send_line_message(report_message, triggered_charts)

# 執行程式
if __name__ == "__main__":
    if CHANNEL_ACCESS_TOKEN and IMGBB_API_KEY:
        analyze_stocks(tickers)
    else:
        print("請先設定環境變數：LINE_CHANNEL_ACCESS_TOKEN 與 IMGBB_API_KEY")
