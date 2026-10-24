# -*- coding: utf-8 -*-
"""
analyze_stock.py
依據頂級證券法人分析師 + Mark Minervini SEPA 體系
針對指定標的輸出六大模組「深度基本面特檢報告」之輔助腳本與範本生成器
"""
import sys
import argparse
from datetime import datetime
import yfinance as yf
from industry_mapping import get_stock_industry
from institutional_fetcher import get_latest_market_quotes, get_accumulated_institutional_data
from tdcc_fetcher import get_tdcc_big_holders_summary

SEPA_ANALYSIS_PROMPT_TEMPLATE = """
# Role & Expertise
你是一位頂級的證券研究法人分析師，同時精通 Mark Minervini 的 SEPA (Specific Entry Point Analysis) 交易體系。你的任務是針對使用者指定的上市/上櫃公司進行「深度基本面特檢」，篩選出具備 Stage 2 主升段超級績效 (Superperformance) 基因的標的。

# Execution Constraints (極重要執行限制)
1. 必須啟動聯網功能，搜尋並引用最新（當前年份為2026年）的財報數據、法說會簡報、法人研究報告與市場共識。
2. 嚴格禁止偷懶。所有表格中的數據（最新一季/前一季/去年同期）必須完整查出並填寫，不得出現「略」、「請自行查詢」或空白。
3. 如果遇到數據尚未公布或查無資料，請明確說明原因，並以最接近的歷史數據或法人預估值替代。

【嚴格數據防護指令（防止 AI 幻覺）】
1. 所有財務數據（營收、三率、EPS）必須嚴格以「公開資訊觀測站」或「公司官方自結/財報」已發生的數字為準。
2. 若最新季度數據尚未公布，請直接標示「未公布」，絕不可為了填滿表格而拿法人預估值或歷史高點數字湊數。
3. 必須將「已發生實質數據」與「未來預估數據」分開呈現，不可混淆。

---
# Input Target
目標公司：{ticker} {name}
產業分類：{sector} / {sub_industry}
分析基準時點：最新已公布之季度財報與最新法說會
---
"""

def generate_stock_context(ticker):
    quotes = get_latest_market_quotes()
    stock_info = quotes.get(ticker, {})
    name = stock_info.get("name", ticker)
    sector, sub_industry = get_stock_industry(name)
    inst = get_accumulated_institutional_data(days=20).get(ticker, {})
    tdcc = get_tdcc_big_holders_summary().get(ticker, {})

    f_cum = inst.get("foreign_cum_buy", 0)
    close_p = stock_info.get("close", 0.0)
    f_amt_yi = round(f_cum * float(close_p) * 1000 / 100_000_000, 2)

    summary = {
        "ticker": ticker,
        "name": name,
        "close": close_p,
        "sector": sector,
        "sub_industry": sub_industry,
        "foreign_cum_20d": f_cum,
        "foreign_cum_amount_yi": f_amt_yi,
        "pct_1000": tdcc.get("pct_1000", 0.0),
        "change_1000_1w": tdcc.get("change_1000_1w", 0.0)
    }
    return summary

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEPA 深度基本面特檢模板產生器")
    parser.add_argument("ticker", help="台股股票代號 (例: 3450, 3017, 6781)")
    args = parser.parse_args()

    info = generate_stock_context(args.ticker)
    print(f"✅ 已成功抓取 {info['ticker']} {info['name']} 基礎盤面與籌碼資訊：")
    print(f"   主產業: {info['sector']} | 次族群: {info['sub_industry']}")
    print(f"   收盤價: ${info['close']} | 20日外資累計: +{info['foreign_cum_amount_yi']}億元 (+{info['foreign_cum_20d']:,}張) | 千張大戶: {info['pct_1000']}%")
