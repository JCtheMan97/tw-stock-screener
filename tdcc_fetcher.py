# -*- coding: utf-8 -*-
"""
tdcc_fetcher.py
台灣集中保管結算所 (TDCC) 集保戶股權分散表抓取模組
追蹤千張大戶（持股 > 1,000 張）與 400 張大戶持股比重及其變動
"""
import os
import csv
import json
import io
import requests
from datetime import datetime
from config import CACHE_DIR

TDCC_URL = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
TDCC_HISTORY_FILE = os.path.join(CACHE_DIR, "tdcc_history.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch_latest_tdcc_raw():
    """下載 TDCC 最新每週股權分散 CSV 資料"""
    try:
        res = requests.get(TDCC_URL, headers=HEADERS, timeout=25)
        if res.status_code == 200:
            res.encoding = 'utf-8-sig'
            return res.text
    except Exception as e:
        print(f"[TDCC] 下載集保資料失敗: {e}")
    return None

def parse_tdcc_csv(csv_text):
    """
    解析 TDCC CSV
    格式: 資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%
    持股分級說明:
      1: 1-999 (零股)
      ...
      12: 400,001-600,000 (400張)
      13: 600,001-800,000
      14: 800,001-1,000,000
      15: 1,000,001以上 (千張大戶)
      17: 合計
    """
    records = {}
    reader = csv.reader(io.StringIO(csv_text.strip()))
    header = next(reader, None)
    if not header:
        return "", records

    report_date = ""
    for row in reader:
        if len(row) < 6:
            continue
        date_str = row[0].strip()
        ticker = row[1].strip()
        try:
            level = int(row[2].strip())
            pct = float(row[5].strip())
        except ValueError:
            continue

        if not report_date and date_str:
            report_date = date_str

        if ticker not in records:
            records[ticker] = {
                "date": date_str,
                "pct_1000": 0.0,   # 千張大戶比例 (Level 15)
                "pct_400": 0.0,    # 400張大戶比例 (Level 12~15)
                "pct_retail": 0.0, # 散戶比例 (< 50張, Level 1~8)
            }

        if level == 15:
            records[ticker]["pct_1000"] = pct
            records[ticker]["pct_400"] += pct
        elif 12 <= level <= 14:
            records[ticker]["pct_400"] += pct
        elif 1 <= level <= 8:
            records[ticker]["pct_retail"] += pct

    # 四捨五入數值
    for ticker in records:
        records[ticker]["pct_400"] = round(records[ticker]["pct_400"], 2)
        records[ticker]["pct_1000"] = round(records[ticker]["pct_1000"], 2)
        records[ticker]["pct_retail"] = round(records[ticker]["pct_retail"], 2)

    return report_date, records

def load_tdcc_history():
    """載入歷史週記錄以計算大戶增減變化，若快取不足自動讀取 tdcc_baseline.json"""
    history = {}
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        TDCC_HISTORY_FILE,
        os.path.join(base_dir, "tdcc_history.json")
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    history = json.load(f)
                    if history:
                        break
            except Exception:
                pass

    # 若歷史記錄不足 2 週，自動合併專案基準歷史週 tdcc_baseline.json
    baseline_path = os.path.join(base_dir, "tdcc_baseline.json")
    if os.path.exists(baseline_path):
        try:
            with open(baseline_path, "r", encoding="utf-8") as bf:
                b_obj = json.load(bf)
                b_date = b_obj.get("date", "20261016")
                if b_date not in history:
                    history[b_date] = b_obj.get("data", {})
        except Exception:
            pass

    return history

def save_tdcc_history(history_data):
    """保存歷史週記錄"""
    try:
        with open(TDCC_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[TDCC] 保存歷史記錄失敗: {e}")

def get_tdcc_big_holders_summary(force_refresh=False):
    """
    獲取最新千張大戶持股比率與週增減變化
    回傳字典結構:
    {
      "2330": {
         "date": "20261022",
         "pct_1000": 87.52,
         "pct_400": 91.20,
         "pct_retail": 5.43,
         "change_1000_1w": 0.35, # 較上週增減 %
         "is_increasing": True
      }
    }
    """
    history = load_tdcc_history()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cache_daily_file = os.path.join(CACHE_DIR, "tdcc_latest.json")
    cache_daily_candidates = [
        cache_daily_file,
        os.path.join(base_dir, "tdcc_latest.json")
    ]

    # 若今天已下載過且不強制更新，直接從快取讀取 (確保快取內有非 0 之真實變動)
    if not force_refresh:
        for cdf in cache_daily_candidates:
            if os.path.exists(cdf):
                try:
                    with open(cdf, "r", encoding="utf-8") as f:
                        cached = json.load(f)
                        data_map = cached.get("data", {})
                        if data_map and len(data_map) > 1000:
                            # 檢查快取是否有計算過週增變化 (避免全部是 0.0 的未比對舊檔)
                            has_nonzero = any(float(v.get("change_1000_1w", 0.0)) != 0.0 for v in list(data_map.values())[:300])
                            if has_nonzero:
                                return data_map
                except Exception:
                    pass

    print("[TDCC] 正在下載台灣集保大戶持股分散表...")
    csv_text = fetch_latest_tdcc_raw()
    if not csv_text:
        # 下載失敗時 fallback 到舊快取
        if os.path.exists(cache_daily_file):
            with open(cache_daily_file, "r", encoding="utf-8") as f:
                return json.load(f).get("data", {})
        return {}

    report_date, latest_records = parse_tdcc_csv(csv_text)
    if not latest_records:
        return {}

    # 將最新週資料加入歷史紀錄中（最多保留 8 週）
    if report_date:
        history[report_date] = latest_records
        # 排序所有歷史週
        sorted_dates = sorted(history.keys(), reverse=True)
        # 只保留最新 8 週
        if len(sorted_dates) > 8:
            for d in sorted_dates[8:]:
                del history[d]
        save_tdcc_history(history)

    # 計算較上週與近一個月 (約4週) 之增減
    sorted_dates = sorted(history.keys(), reverse=True)
    prev_date = sorted_dates[1] if len(sorted_dates) > 1 else None
    month_date = sorted_dates[min(4, len(sorted_dates)-1)] if len(sorted_dates) > 2 else prev_date
    prev_records = history.get(prev_date, {}) if prev_date else {}
    month_records = history.get(month_date, {}) if month_date else {}

    result = {}
    for ticker, info in latest_records.items():
        pct_1000 = info["pct_1000"]
        pct_400 = info["pct_400"]
        pct_retail = info["pct_retail"]

        change_1000 = 0.0
        if prev_records and ticker in prev_records:
            prev_pct_1000 = prev_records[ticker]["pct_1000"]
            change_1000 = round(pct_1000 - prev_pct_1000, 2)

        change_1000_1m = change_1000
        if month_records and ticker in month_records:
            month_pct_1000 = month_records[ticker]["pct_1000"]
            change_1000_1m = round(pct_1000 - month_pct_1000, 2)

        is_increasing = (change_1000 > 0) or (change_1000_1m > 0)

        result[ticker] = {
            "date": report_date,
            "pct_1000": pct_1000,
            "pct_400": pct_400,
            "pct_retail": pct_retail,
            "change_1000_1w": change_1000,
            "change_1000_1m": change_1000_1m,
            "is_increasing": is_increasing
        }

    for cdf in cache_daily_candidates:
        try:
            with open(cdf, "w", encoding="utf-8") as f:
                json.dump({"date": report_date, "data": result}, f, ensure_ascii=False)
        except Exception:
            pass

    print(f"[TDCC] 成功解析 {len(result)} 檔標的之集保大戶數據 (日期: {report_date})")
    return result

def get_stock_tdcc_info(ticker):
    """
    提供自選股或特定標的查詢即時/快取的千張大戶與週增減變化
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base_dir, "tdcc_latest.json"),
        os.path.join(CACHE_DIR, "tdcc_latest.json"),
    ]
    for cdf in candidates:
        if os.path.exists(cdf):
            try:
                with open(cdf, "r", encoding="utf-8") as f:
                    d = json.load(f).get("data", {})
                    if ticker in d and float(d[ticker].get("change_1000_1w", 0.0)) != 0.0:
                        return d[ticker]
            except Exception:
                pass

    summary = get_tdcc_big_holders_summary()
    return summary.get(ticker, {
        "pct_1000": 0.0,
        "pct_400": 0.0,
        "pct_retail": 0.0,
        "change_1000_1w": 0.0,
        "change_1000_1m": 0.0,
        "is_increasing": False
    })

if __name__ == "__main__":
    res = get_tdcc_big_holders_summary(force_refresh=True)
    sample = res.get("2330", {})
    print("2330 台積電 大戶持股:", sample)
