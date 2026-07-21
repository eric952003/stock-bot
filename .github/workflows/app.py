
import streamlit as st
from github import Github
import os

# ==========================================
# ⚙️ 設定區
# ==========================================
st.set_page_config(page_title="股票小秘書管理後台", page_icon="📈")

# 實務上部署到雲端時，這兩個變數會寫在 Streamlit Secrets 中
# 在本地測試時，可以直接把 Token 貼在這裡取代 st.secrets
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"] 
REPO_NAME = "你的GitHub帳號/stock-bot" # 請務必換成你自己的專案名稱，例如 "eric952003/stock-bot"

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