# -*- coding: utf-8 -*-
"""
main.py
台股「翻倍大波段」蓄勢模型主程式
整合：TWSE/TPEx 盤後行情 -> 法人 20 日波段吸籌 -> 集保千張大戶 -> SEPA 趨勢模板與 VCP 橫盤縮量 -> 次族群共振 -> LINE 推播
"""
import sys
import os
import argparse
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf

from config import (
    LOOKBACK_DAYS,
    MIN_FOREIGN_BUY_RATIO,
    MIN_CUMULATIVE_BUY_AMOUNT,
    MIN_CUMULATIVE_BUY_SHARES,
    MIN_TODAY_VOLUME,
    MAX_PRICE_AMPLITUDE_PCT,
    MIN_BIG_HOLDERS_WEEK_CHANGE,
    MAX_STATIC_BIG_HOLDERS_PCT,
    MIN_ACTIVE_BIG_HOLDERS_PCT
)
from industry_mapping import get_stock_industry
from tdcc_fetcher import get_tdcc_big_holders_summary
from institutional_fetcher import get_latest_market_quotes, get_accumulated_institutional_data
from sepa_engine import evaluate_stock_sepa
from cluster_analyzer import group_stocks_by_cluster
from notifier import format_screener_report, send_line_message
from fundamental_gate import run_fundamental_check
from config import CACHE_DIR

def fetch_history_batch(tickers, start_date, end_date):
    """
    併發下載候選標的之歷史日 K 線資料
    """
    results = {}
    def _fetch_one(t):
        try:
            symbol = t if (t.endswith(".TW") or t.endswith(".TWO")) else f"{t}.TW"
            ticker_obj = yf.Ticker(symbol)
            df = ticker_obj.history(start=start_date, end=end_date, auto_adjust=True)
            if df.empty and symbol.endswith(".TW"):
                symbol = f"{t}.TWO"
                ticker_obj = yf.Ticker(symbol)
                df = ticker_obj.history(start=start_date, end=end_date, auto_adjust=True)
            if not df.empty and len(df) > 30:
                return t, df
        except Exception:
            pass
        return t, None

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(_fetch_one, t) for t in tickers]
        for f in futures:
            t, df = f.result()
            if df is not None and len(df) > 30:
                results[t] = df

    return results

def run_screener_pipeline(dry_run=False, notify=True, test_limit=None):
    start_time = time.time()
    today_str = datetime.now().strftime("%Y-%m-%d")
    print(f"\n========================================================")
    print(f"🚀 開始執行台股【大波段蓄勢模型】選股引擎 ({today_str})")
    print(f"========================================================")

    # 1. 抓取今日全市場報價行情
    print("\n[步驟 1/5] 抓取全市場盤後報價行情與流動性初篩...")
    quotes = get_latest_market_quotes()
    if not quotes:
        print("❌ 無法取得盤後即時報價，請確認網路連線或非交易日。")
        return

    # 流動性初篩：成交量 >= MIN_TODAY_VOLUME (500張)，股價 > 10元
    pool_1 = {}
    for ticker, q in quotes.items():
        if q["volume"] >= MIN_TODAY_VOLUME and q["close"] >= 10.0:
            pool_1[ticker] = q

    print(f"  -> 全市場 {len(quotes)} 檔標的，流動性初篩符合 (量>={MIN_TODAY_VOLUME}張): {len(pool_1)} 檔")

    # 2. 抓取法人 20 日波段累積買賣超
    print(f"\n[步驟 2/5] 分析過去 {LOOKBACK_DAYS} 個交易日三大法人/外資波段吸籌數據...")
    inst_data = get_accumulated_institutional_data(days=LOOKBACK_DAYS)
    
    # 籌碼面初篩：外資波段累計買超金額 >= MIN_CUMULATIVE_BUY_AMOUNT (5,000萬元) 且 買超天數比率 >= MIN_FOREIGN_BUY_RATIO (50%)
    pool_2 = {}
    for ticker, q in pool_1.items():
        inst = inst_data.get(ticker, {})
        f_cum = inst.get("foreign_cum_buy", 0)
        f_ratio = inst.get("foreign_buy_ratio", 0.0)
        consecutive_f = inst.get("consecutive_foreign_days", 0)

        # 計算外資 20 日累計買超金額 (元) = 張數 * 現價 * 1000
        close_price = float(q.get("close", 0.0))
        f_cum_amount = f_cum * close_price * 1000
        inst["foreign_cum_amount"] = f_cum_amount
        inst["foreign_cum_amount_yi"] = round(f_cum_amount / 100_000_000, 2)

        # 核心籌碼條件：外資波段真金白銀大買 (累計金額達標 且 (天數過半 或 連續大買))
        if f_cum_amount >= MIN_CUMULATIVE_BUY_AMOUNT and (f_ratio >= MIN_FOREIGN_BUY_RATIO or consecutive_f >= 3):
            pool_2[ticker] = {
                **q,
                **inst
            }

    min_amt_yi = MIN_CUMULATIVE_BUY_AMOUNT / 100_000_000
    print(f"  -> 符合「外資波段真金白銀大買」(累計買超金額>={min_amt_yi:.2f}億元 & 買超天數比>={int(MIN_FOREIGN_BUY_RATIO*100)}%): 共 {len(pool_2)} 檔")

    if test_limit and len(pool_2) > test_limit:
        print(f"  ⚠️ 啟用測試限制，僅分析前 {test_limit} 檔標的...")
        pool_2 = dict(list(pool_2.items())[:test_limit])

    if not pool_2:
        print("今日無符合籌碼波段狂買之標的。")
        report = format_screener_report([], [], trade_date_str=today_str)
        if notify and not dry_run:
            send_line_message(report)
        return

    # 3. 整合台灣集保 (TDCC) 千張大戶持股
    print("\n[步驟 3/5] 整合 TDCC 集保千張大戶籌碼集中度...")
    tdcc_data = get_tdcc_big_holders_summary()

    for ticker, info in pool_2.items():
        tdcc_item = tdcc_data.get(ticker, {})
        info["pct_1000"] = tdcc_item.get("pct_1000", 0.0)
        info["pct_400"] = tdcc_item.get("pct_400", 0.0)
        info["change_1000_1w"] = tdcc_item.get("change_1000_1w", 0.0)
        info["is_increasing_tdcc"] = tdcc_item.get("is_increasing", False)

    # 4. 下載歷史日 K 並計算 Minervini SEPA 趨勢模板、Alpha RS、橫盤振幅與 VCP 縮量
    print(f"\n[步驟 4/5] 執行 Minervini SEPA 趨勢模板、0050 Alpha RS 與 20日橫盤量縮計算...")
    
    # 下載 0050 基準
    start_date = (datetime.now() - pd.Timedelta(days=400)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        df_0050 = yf.Ticker("0050.TW").history(start=start_date, end=end_date, auto_adjust=True)
    except Exception:
        df_0050 = yf.download("0050.TW", start=start_date, end=end_date, progress=False, auto_adjust=True)
    if isinstance(df_0050.columns, pd.MultiIndex):
        df_0050.columns = df_0050.columns.get_level_values(0)

    # 批次下載候選標的歷史 K 線
    candidate_tickers = list(pool_2.keys())
    print(f"  -> 正在併發下載 {len(candidate_tickers)} 檔候選股日 K 資料...")
    history_dfs = fetch_history_batch(candidate_tickers, start_date, end_date)

    qualified_stocks = []
    for ticker, stock_info in pool_2.items():
        df_stock = history_dfs.get(ticker)
        if df_stock is None or len(df_stock) < 100:
            continue

        sepa_result = evaluate_stock_sepa(ticker, df_stock, df_0050)
        
        # 匹配產業與細分次族群
        stock_name = stock_info["name"]
        sector, sub_industry = get_stock_industry(stock_name)

        # 檢驗是否符合所有嚴格大波段標準
        if sepa_result["is_qualified"]:
            pct_1000 = stock_info.get("pct_1000", 0.0)
            chg_1000 = stock_info.get("change_1000_1w", 0.0)
            f_ratio = stock_info.get("foreign_buy_ratio", 0.0)

            # 核心心法：大戶「持續增加（動能）」才是翻倍關鍵！
            # 若本身持股太高 (> 75%) 且未持續增加，多屬牛皮成熟股，漲幅有限，予以排除！
            is_big_holders_valid = False
            if chg_1000 >= MIN_BIG_HOLDERS_WEEK_CHANGE:
                is_big_holders_valid = True
            elif pct_1000 <= MAX_STATIC_BIG_HOLDERS_PCT and pct_1000 >= MIN_ACTIVE_BIG_HOLDERS_PCT and f_ratio >= 0.55:
                # 處於成長型爆發區間 (20% ~ 75%)，且外資近 20 天超過 55% 天數都在狂買吸籌
                is_big_holders_valid = True

            if is_big_holders_valid:
                full_info = {
                    **stock_info,
                    **sepa_result,
                    "close": stock_info["close"],
                    "sector": sector,
                    "sub_industry": sub_industry
                }
                qualified_stocks.append(full_info)
        else:
            # 記錄被排除的原因 (提供 debug 觀測)
            pass

    print(f"  -> 嚴格通過「Trend Template + 20日振幅<={MAX_PRICE_AMPLITUDE_PCT}% + VCP量縮 + 千張大戶集中」: 共 {len(qualified_stocks)} 檔")

    # 5. 次族群聚類分析 (Sector Clustering)
    print("\n[步驟 5/5] 執行次族群共振聚類分析 (Sector Clustering)...")
    clustered_groups, single_stocks = group_stocks_by_cluster(qualified_stocks)

    print(f"  -> 辨識出【族群共振板塊 (>=2檔)】: {len(clustered_groups)} 組")
    for g in clustered_groups:
        print(f"     🔥 【{g['sub_industry']}】({g['count']} 檔符合 | 外資累計 +{g['total_foreign_buy']:,}張)")
        for m in g['members']:
            print(f"        • {m['ticker']} {m['name']} ${m['close']} | 20日振幅 {m['price_amplitude_20d']}% | 大戶 {m['pct_1000']}%")

    print(f"  -> 單兵潛力股: {len(single_stocks)} 檔")

    # 6. 最後基本面關卡：多因子動態綜合評分，挑選今日爆發潛力第一名作為首選標的
    print("\n[步驟 6/6] 執行最後基本面關卡：SEPA 多因子動態評分與首選特檢...")
    def calculate_sepa_rank_score(s):
        score = 0.0
        # 1. 突破爆發信號權重大加分
        if s.get("signal_type") == "BREAKOUT":
            score += 200.0
            vol_spike = s.get("vol_spike_ratio", 1.0)
            score += min(vol_spike * 15, 60.0) # 放量倍數加分
        else:
            # 潛伏蓄勢：振幅越緊密、壓縮越極致加分越高
            amp = s.get("price_amplitude_20d", 15.0)
            score += max(0, (15.0 - amp) * 5)
            if "極致壓縮" in s.get("vcp_status", ""):
                score += 35.0
            elif "Dead Quiet" in s.get("vcp_status", ""):
                score += 30.0

        # 2. Alpha RS 動能強度
        alpha = s.get("alpha_rs", 100.0)
        score += (alpha - 100.0) * 1.5

        # 3. 外資波段吸籌強度 (買超天數比例與連續度)
        f_ratio = s.get("foreign_buy_ratio", 0.0)
        score += f_ratio * 50.0

        # 4. 集保千張大戶動態增減 (大戶增量是飆股靈魂)
        chg_1000 = s.get("change_1000_1w", 0.0)
        if chg_1000 > 0:
            score += min(chg_1000 * 30, 60.0)
        pct_1000 = s.get("pct_1000", 0.0)
        if 35.0 <= pct_1000 <= 75.0:
            score += 20.0 # 處於黃金大戶成長區間

        return round(score, 1)

    top_target = None
    if qualified_stocks:
        top_target = max(qualified_stocks, key=calculate_sepa_rank_score)
        top_score = calculate_sepa_rank_score(top_target)
        print(f"  -> 今日綜合評分最高焦點標的：{top_target['ticker']} {top_target['name']} (綜合得分: {top_score}分)")

    fundamental_report = ""
    if top_target:
        print(f"  -> 今日首選焦點標的：{top_target['ticker']} {top_target['name']}，正在生成六大模組基本面特檢報告...")
        fundamental_report = run_fundamental_check(
            top_target['ticker'],
            top_target['name'],
            top_target.get('sector', ''),
            top_target.get('sub_industry', '')
        )
        report_file = os.path.join(CACHE_DIR, f"sepa_deep_check_{top_target['ticker']}.md")
        with open(report_file, "w", encoding="utf-8") as f_rep:
            f_rep.write(fundamental_report)
        print(f"  -> 深度基本面特檢完成，已存檔至 {report_file}")

    # 7. 組裝完整報告與發送推播 (蓄勢族群總表 + 首選標的 SEPA 特檢)
    report_text = format_screener_report(clustered_groups, single_stocks, trade_date_str=today_str)
    if fundamental_report:
        report_text += "\n\n" + fundamental_report
    
    # 自動存檔至 reports/ 目錄永久歸檔
    reports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    daily_report_path = os.path.join(reports_dir, f"report_{today_str}.md")
    with open(daily_report_path, "w", encoding="utf-8") as f_out:
        f_out.write(report_text)
    print(f"  -> 當日報告已自動存檔至: {daily_report_path}")

    # 儲存結構化 JSON 供 Web 儀表板秒級讀取 (同步存於 cache/ 與根目錄)
    import json
    json_path = os.path.join(CACHE_DIR, "latest_screen_data.json")
    root_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_screen_data.json")
    payload = {
        "trade_date": today_str,
        "clusters": clustered_groups,
        "singles": single_stocks,
        "top_target": top_target,
        "fundamental_report": fundamental_report
    }
    for p in [json_path, root_json_path]:
        try:
            with open(p, "w", encoding="utf-8") as f_json:
                json.dump(payload, f_json, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            pass

    elapsed = round(time.time() - start_time, 2)
    print(f"\n========================================================")
    print(f"🏁 全流程完成！總耗時: {elapsed} 秒")
    print(f"========================================================")

    if dry_run or not notify:
        print("\n[Dry Run 模式] 完整報告預覽（包含大波段清單與最後基本面特檢）：")
        print("--------------------------------------------------------")
        print(report_text)
        print("--------------------------------------------------------")
    else:
        print("\n[LINE 推播] 正在發送至 LINE...")
        send_line_message(report_text)

    return clustered_groups, single_stocks

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台股大波段蓄勢選股與推播工作流")
    parser.add_argument("--dry-run", action="store_true", help="僅在終端機輸出報告，不發送 LINE 訊息")
    parser.add_argument("--no-notify", action="store_true", help="不觸發 LINE 通知")
    parser.add_argument("--limit", type=int, default=None, help="限制測試分析的股票數量")
    args = parser.parse_args()

    run_screener_pipeline(dry_run=args.dry_run, notify=not args.no_notify, test_limit=args.limit)
