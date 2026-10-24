# -*- coding: utf-8 -*-
"""
config.py
台股「翻倍大波段」蓄勢模型與自動化推播設定檔
"""
import os

# 載入 .env 環境變數 (優先使用 dotenv，若無則手動解析)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip("'\"")
                    if k and not os.getenv(k):
                        os.environ[k] = v
    except Exception:
        pass

# --- 🎯 策略核心參數 (翻倍大波段蓄勢模型) ---
# 1. 籌碼面：外資/法人波段狂買
LOOKBACK_DAYS = 20            # 追蹤過去交易日數 (通常為 15~20 天)
MIN_FOREIGN_BUY_RATIO = 0.50  # 過去 20 日中，外資買超天數比例 (例如 >= 50% 或 60%)
MIN_CUMULATIVE_BUY_AMOUNT = 50_000_000  # 過去 20 日外資累計淨買超金額下限 (元，預設 5,000 萬元，兼顧高價飆股與中小型股)
MIN_CUMULATIVE_BUY_SHARES = 500  # 過去 20 日外資累計淨買超張數下限 (張，參考/雙軌備用)
MIN_TODAY_VOLUME = 500        # 當日最低成交量 (張，排除無量殭屍股)

# 2. 價格型態：橫盤不動 (壓盤吃貨箱型)
MAX_PRICE_AMPLITUDE_PCT = 12.0  # 近 20 日高低價震盪幅度上限 (例如 <= 10% ~ 12%)

# 3. 籌碼集中度：集保千張大戶持股 (持續增加為主，排除本身過高牛皮股)
MIN_BIG_HOLDERS_WEEK_CHANGE = 0.01  # 大戶週增長門檻 (持續增加)
MAX_STATIC_BIG_HOLDERS_PCT = 75.0   # 千張大戶持股上限 (若未增加，超過此比例視為漲幅有限之牛皮股予以排除)
MIN_ACTIVE_BIG_HOLDERS_PCT = 20.0   # 基本大戶門檻 (排除完全無主力的大型散戶雜牌股)

# 4. 量能與波動萎縮 (VCP / Dead Quiet)
VOLUME_CONTRACTION_RATIO = 0.85   # 5日均量 / 20日均量門檻 (例如 < 0.85)
DEAD_QUIET_RATIO = 0.70           # 3日均量 / 20日均量門檻 (靜止平台)

# 5. 族群共振門檻
MIN_CLUSTER_MEMBERS = 2           # 同細分次族群至少需符合之個股檔數

# 6. Minervini 趨勢模板與 Alpha RS
MIN_ALPHA_RS = 100.0              # 相對於 0050 的 Alpha RS 得分門檻
MAX_MA50_BIAS_PCT = 25.0          # 50MA 乖離率上限 (避免過熱追高)

# --- 📲 LINE Messaging API 推播設定 ---
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.getenv("LINE_USER_ID", "")

# 支援 Streamlit Cloud st.secrets (若存在)
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if not LINE_CHANNEL_ACCESS_TOKEN and "LINE_CHANNEL_ACCESS_TOKEN" in st.secrets:
                LINE_CHANNEL_ACCESS_TOKEN = st.secrets["LINE_CHANNEL_ACCESS_TOKEN"]
            if not LINE_USER_ID and "LINE_USER_ID" in st.secrets:
                LINE_USER_ID = st.secrets["LINE_USER_ID"]
    except Exception:
        pass

# --- 📁 資料快取目錄 ---
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
