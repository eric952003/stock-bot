import os
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import io
import base64

# ==========================================
# 🔐 鑰匙與字型設定
# ==========================================
CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY')

plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'Noto Sans CJK TC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 監控清單：涵蓋大盤與高股息動能 ETF
tickers = ['0050.TW', '0056.TW', '00878.TW', '009826.TW', '00919.TW', '00929.TW','009816.TW']

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
        
        clean_ticker = ticker.replace('.TW', '').replace('.TWO', '')
        plt.title(f"{clean_ticker} - {title_tag} (近三個月)", fontsize=14)
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
    """透過 FinMind API 獲取三大法人買賣超資料 (近5日)"""
    start_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": ticker_tw,
        "start_date": start_date,
    }
    try:
        response = requests.get(url, params=parameter, timeout=5)
        data = response.json()
        if data.get("msg") == "success" and len(data.get("data", [])) > 0:
            df = pd.DataFrame(data["data"])
            df['sell_buy'] = df['buy'] - df['sell']
            daily_data = df.groupby('date').agg({'buy': 'sum', 'sell': 'sum', 'sell_buy': 'sum'}).reset_index()
            return daily_data.sort_values('date').tail(5)
    except Exception as e:
        print(f"[{ticker_tw}] 法人資料讀取發生錯誤: {e}")
    return None

def get_margin_data(ticker_tw):
    """透過 FinMind API 獲取融資融券資料 (近5日)，用於判斷散戶動向"""
    start_date = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockMarginPurchaseShortSale",
        "data_id": ticker_tw,
        "start_date": start_date,
    }
    try:
        response = requests.get(url, params=parameter, timeout=5)
        data = response.json()
        if data.get("msg") == "success" and len(data.get("data", [])) > 0:
            df = pd.DataFrame(data["data"])
            return df.sort_values('date').tail(5)
    except Exception as e:
        print(f"[{ticker_tw}] 融資資料讀取發生錯誤: {e}")
    return None

def check_systemic_risk():
    """檢查台幣匯率，作為大環境風險指標"""
    try:
        twd = yf.Ticker("TWD=X").history(period="5d")
        if not twd.empty:
            current_rate = float(twd['Close'].iloc[-1])
            if current_rate > 32.5: # 匯率警戒線
                return f"⚠️ 【系統風險警報】台幣貶至 {current_rate:.2f}，留意大盤資金外流賣壓！\n" + "=" * 20 + "\n"
    except:
        pass
    return ""

# ==========================================
# 🚀 主邏輯區
# ==========================================
def analyze_stocks(tickers):
    system_alert = check_systemic_risk()
    report_message = "📊 【股票小秘書】籌碼量化完全體\n" + "=" * 20 + "\n" + system_alert
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
                if isinstance(dividends, pd.DataFrame): dividends = dividends.iloc[:, 0]
                if isinstance(dividends, pd.Series) and not dividends.empty:
                    now = datetime.now()
                    for date, val in dividends.items():
                        clean_date = date.tz_localize(None) if hasattr(date, 'tz_localize') else date
                        if type(clean_date) in [pd.Timestamp, datetime]:
                            if (now - clean_date).days <= 365: last_year_div += float(val)
                            if (now - clean_date).days <= 30: div_status = "(近除息)"
            except: pass 
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

            # --- 4. 🌟 籌碼面強度觀測 (法人 + 融資) ---
            chip_light = ""
            pure_ticker = ticker.replace('.TW', '').replace('.TWO', '')
            inst_data = get_institutional_data(pure_ticker)
            margin_data = get_margin_data(pure_ticker)
            
            if inst_data is not None and not inst_data.empty:
                chip_score = 0
                chip_tags = []
                net_flows = inst_data['sell_buy'].tolist()
                latest_net = net_flows[-1]
                net_ratio = latest_net / (latest_vol + 0.0001)
                
                consecutive_buys, consecutive_sells = 0, 0
                for flow in reversed(net_flows):
                    if flow > 0:
                        if consecutive_sells > 0: break
                        consecutive_buys += 1
                    elif flow < 0:
                        if consecutive_buys > 0: break
                        consecutive_sells += 1

                if latest_net > 0:
                    if consecutive_buys >= 3 or net_ratio > 0.15:
                        chip_score += 2
                        chip_tags.append(f"🔥強買({consecutive_buys}連)")
                    elif consecutive_buys == 2 or net_ratio > 0.05:
                        chip_score += 1
                        chip_tags.append(f"🟢溫買")
                elif latest_net < 0:
                    if consecutive_sells >= 3 or net_ratio < -0.15:
                        chip_score -= 2
                        chip_tags.append(f"🩸強賣({consecutive_sells}連)")

                if margin_data is not None and not margin_data.empty and 'MarginPurchaseTodayBalance' in margin_data.columns:
                    margin_balances = margin_data['MarginPurchaseTodayBalance'].tolist()
                    if len(margin_balances) >= 2:
                        if margin_balances[-1] < margin_balances[-2]:
                            chip_tags.append("📉資減")
                            if latest_net > 0:
                                chip_score += 1
                                chip_tags.append("✨籌碼集中")

                score += chip_score
                if chip_tags:
                    chip_light = " | ".join(chip_tags)

            # --- 5. 判定與掛單價 ---
            data['SMA_5'] = data['Close'].rolling(window=5).mean()
            latest_SMA5 = float(data['SMA_5'].iloc[-1]) if len(data) >= 5 else latest_close
            prev_high = float(data['High'].iloc[-2]) if len(data) >= 2 else latest_close

            if score >= 3: light, suggest = "🟢強烈買進", f"買點: {min(latest_close, latest_SMA5):.2f}"
            elif score >= 1: light, suggest = "🟡逢低試單", f"買點: {min(latest_close, latest_SMA5):.2f}"
            elif score < 0: light, suggest = "🔴避險減碼", f"賣點: {max(latest_close, prev_high):.2f}"
            else: light, suggest = "⚪繼續觀望", "建議: 多看少做"

            # --- 6. 優化後的清爽版報告組合 ---
            clean_ticker = ticker.replace('.TW', '').replace('.TWO', '')
            report_message += f"{alert_header}**【{clean_ticker}】{light} {change_text}**\n"
            
            base_info = f"💰 {latest_close:.2f} | K值: {latest_K:.1f}"
            if yield_pct >= 3.0: 
                base_info += f" | 殖: {yield_pct:.1f}%{div_status}"
            report_message += f"{base_info}\n"
            
            if chip_light:
                report_message += f"🕵️ 籌碼: {chip_light}\n"
                
            report_message += f"🎯 {suggest}\n\n"

            if score >= 2 or score < 0:
                img_url = generate_chart(ticker, light)
                if img_url: triggered_charts.append(img_url)
            
        except Exception as e:
            clean_ticker = ticker.replace('.TW', '').replace('.TWO', '')
            report_message += f"⚠️【{clean_ticker}】資料讀取失敗\n\n"

    send_line_message(report_message.strip(), triggered_charts)

if __name__ == "__main__":
    if CHANNEL_ACCESS_TOKEN and IMGBB_API_KEY:
        analyze_stocks(tickers)
    else:
        print("請先設定環境變數：LINE_CHANNEL_ACCESS_TOKEN 與 IMGBB_API_KEY")
