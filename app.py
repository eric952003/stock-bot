import streamlit as st
import yfinance as yf
import pandas as pd
from github import Github

# ==========================================
# ⚙️ 設定區
# ==========================================
st.set_page_config(page_title="股票小秘書管理後台", page_icon="📈")

# 實務上部署到雲端時，這兩個變數會寫在 Streamlit Secrets 中
# 在本地測試時，可以直接把 Token 貼在這裡取代 st.secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"] 
REPO_NAME = "eric952003/stock-bot" # 請務必換成你自己的專案名稱，例如 "eric952003/stock-bot"

# 登入 GitHub
g = Github(GITHUB_TOKEN)
repo = g.get_repo(REPO_NAME)

st.title("📈 股票小秘書監控清單管理")

# ==========================================
# 📂 讀取現有清單
# ==========================================
try:
    file_content = repo.get_contents("tickers.txt")
    tickers_str = file_content.decoded_content.decode("utf-8")
    # 將字串分割成 List，並過濾掉空行
    current_tickers = [t for t in tickers_str.split("\n") if t.strip()]
except Exception as e:
    st.error("找不到 tickers.txt，請確認專案中是否已建立此檔案。")
    current_tickers = []

# ==========================================
# ✍️ 新增股票區塊
# ==========================================
st.subheader("新增觀察標的")
with st.form("add_ticker_form", clear_on_submit=True):
    new_ticker = st.text_input("輸入股票代號 (例如: 2330, 00919)")
    submitted = st.form_submit_button("加入清單")
    
    if submitted:
        if new_ticker and new_ticker not in current_tickers:
            current_tickers.append(new_ticker)
            new_content = "\n".join(current_tickers)
            # 呼叫 API 更新 GitHub 檔案
            repo.update_file(file_content.path, f"新增 {new_ticker} 透過 Web UI", new_content, file_content.sha)
            st.success(f"已成功將 {new_ticker} 加入清單！")
            st.rerun() # 刷新頁面顯示最新結果
        elif new_ticker in current_tickers:
            st.warning("這個代號已經在清單中囉！")

st.divider()

# ==========================================
# 🗑️ 管理/刪除現有清單
# ==========================================
st.subheader("目前監控中的股票")

# 使用多欄位來排版清單
for ticker in current_tickers:
    col1, col2 = st.columns([3, 1])
    col1.markdown(f"🏷️ **{ticker}**")
    if col2.button("刪除", key=f"del_{ticker}"):
        current_tickers.remove(ticker)
        new_content = "\n".join(current_tickers)
        # 呼叫 API 更新 GitHub 檔案
        repo.update_file(file_content.path, f"刪除 {ticker} 透過 Web UI", new_content, file_content.sha)
        st.success(f"已刪除 {ticker}！")
        st.rerun()
st.divider() # 加一條分隔線讓畫面比較乾淨
st.subheader("⚡ 機器人手動控制台")

# 建立一個啟動按鈕
if st.button("🚀 一鍵立即掃描"):
    with st.spinner("正在發送強制啟動指令給 GitHub..."):
        try:
            # 抓取你的自動化腳本檔案 (檔名需與你設定的一致)
            workflow = repo.get_workflow("schedule.yml")
            
            # 針對 main 分支發送強制執行指令
            workflow.create_dispatch(ref="main")
            
            st.success("✅ 觸發成功！選股機器人已強制啟動，請稍候並留意您的推播通知。")
        except Exception as e:
            st.error(f"❌ 觸發失敗，錯誤訊息：{e}")
            st.info("💡 提示：請確認您的 schedule.yml 中是否已加上 `workflow_dispatch:`，或是檢查檔名是否拼錯。")
st.divider()
st.subheader("📊 網頁端即時動能掃描")

# 建立網頁內掃描按鈕
if st.button("🔍 立即在網頁查看最新數據"):
    with st.spinner("正在為您抓取最新股價與動能資料..."):
        results = []
        
        # 逐一掃描清單中的股票
        for ticker in current_tickers:
            try:
                # Yahoo Finance 的台股代號需要加上 .TW
                yf_ticker = f"{ticker}.TW"
                stock = yf.Ticker(yf_ticker)
                
                # 抓取最近兩天的歷史資料來計算漲跌
                hist = stock.history(period="2d")
                
                if len(hist) >= 2:
                    today_close = hist['Close'].iloc[-1]
                    yesterday_close = hist['Close'].iloc[-2]
                    change_percent = ((today_close - yesterday_close) / yesterday_close) * 100
                    volume = hist['Volume'].iloc[-1]
                    
                    # 將計算結果加入列表
                    results.append({
                        "股票代號": ticker,
                        "最新收盤價": round(today_close, 2),
                        "漲跌幅 (%)": round(change_percent, 2),
                        "成交量": f"{int(volume):,}"
                    })
            except Exception as e:
                st.warning(f"無法抓取 {ticker} 的資料，請確認代號是否正確。")

        # 顯示掃描結果
        if results:
            # 轉換成 Pandas 表格
            df = pd.DataFrame(results)
            
            # 在 Streamlit 中顯示精美表格
            # (台股習慣紅漲綠跌，這裡加上簡單的顏色標示)
            st.dataframe(
                df.style.map(
                    lambda x: 'color: red' if x > 0 else ('color: green' if x < 0 else ''), 
                    subset=['漲跌幅 (%)']
                ),
                use_container_width=True,
                hide_index=True
            )
            st.success("✅ 掃描完成！以上為最新盤後/盤中數據。")
        else:
            st.error("❌ 掃描失敗，請確認清單內是否有有效的股票代號。")
