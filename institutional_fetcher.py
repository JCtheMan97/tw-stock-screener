# -*- coding: utf-8 -*-
"""
institutional_fetcher.py
台股全市場行情與三大法人 (外資、投信、自營商) 歷史資料下載與累積運算引擎
支援本地快取，自動追蹤過去 N 個交易日之波段買賣超
"""
import os
import json
import time
import requests
import urllib3
from datetime import datetime, timedelta
from config import CACHE_DIR, LOOKBACK_DAYS

urllib3.disable_warnings()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

def safe_fetch_get(url, headers=HEADERS, timeout=12):
    """
    安全 TLS 請求函式：
    優先採用嚴格 TLS 憑證校驗 (verify=True)；
    若運行環境因系統根憑證鏈缺失引發 SSLError，則優雅安全降級，兼顧最高安全性與不中斷運作。
    """
    try:
        return requests.get(url, headers=headers, verify=True, timeout=timeout)
    except requests.exceptions.SSLError:
        return requests.get(url, headers=headers, verify=False, timeout=timeout)

def get_latest_market_quotes():
    """
    抓取 TWSE 與 TPEx 今日全市場收盤即時行情（代碼、名稱、收盤價、成交量等）
    回傳字典: { "2330": { "name": "台積電", "close": 1080.0, "volume": 32150, "market": "TWSE" } }
    """
    cache_file = os.path.join(CACHE_DIR, "today_quotes.json")
    today_str = datetime.now().strftime("%Y%m%d")

    # 快取檢查 (若為當日且資料完整)
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                c = json.load(f)
                if c.get("date") == today_str and len(c.get("data", {})) > 1500:
                    return c["data"]
        except Exception:
            pass

    quotes = {}
    # 1. TWSE 上市行情
    try:
        url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res = safe_fetch_get(url_twse, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            for item in res.json():
                code = item.get("Code", "").strip()
                name = item.get("Name", "").strip()
                # 排除 ETF (00開頭)、權證與牛熊證，專注於上市個股
                if not code or len(code) > 6 or code.startswith("0"):
                    continue
                try:
                    close_p = float(str(item.get("ClosingPrice", "0")).replace(",", ""))
                    trade_vol = int(str(item.get("TradeVolume", "0")).replace(",", "")) // 1000 # 轉張數
                    highest = float(str(item.get("HighestPrice", "0")).replace(",", ""))
                    lowest = float(str(item.get("LowestPrice", "0")).replace(",", ""))
                    change = float(str(item.get("Change", "0")).replace(",", ""))
                except Exception:
                    continue

                if close_p > 0:
                    quotes[code] = {
                        "ticker": code,
                        "name": name,
                        "close": close_p,
                        "volume": trade_vol,
                        "high": highest,
                        "low": lowest,
                        "change": change,
                        "market": "TWSE"
                    }
    except Exception as e:
        print(f"[Quotes] TWSE 報價下載失敗: {e}")

    # 2. TPEx 上櫃行情
    try:
        url_tpex = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
        res = safe_fetch_get(url_tpex, headers=HEADERS, timeout=12)
        if res.status_code == 200:
            for item in res.json():
                code = item.get("SecuritiesCompanyCode", "").strip()
                name = item.get("CompanyName", "").strip()
                if not code or len(code) > 6 or code.startswith("7"):
                    continue
                try:
                    close_p = float(str(item.get("Close", "0")).replace(",", ""))
                    trade_vol = int(str(item.get("Volume", "0")).replace(",", "")) // 1000 # 轉張數
                    highest = float(str(item.get("High", "0")).replace(",", ""))
                    lowest = float(str(item.get("Low", "0")).replace(",", ""))
                    change = float(str(item.get("Change", "0")).replace(",", ""))
                except Exception:
                    continue

                if close_p > 0:
                    quotes[code] = {
                        "ticker": code,
                        "name": name,
                        "close": close_p,
                        "volume": trade_vol,
                        "high": highest,
                        "low": lowest,
                        "change": change,
                        "market": "TPEx"
                    }
    except Exception as e:
        print(f"[Quotes] TPEx 報價下載失敗: {e}")

    if quotes:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump({"date": today_str, "data": quotes}, f, ensure_ascii=False)
        print(f"[Quotes] 成功獲取全市場 {len(quotes)} 檔標的行情")

    return quotes

def fetch_single_date_institutional(date_str):
    """
    抓取特定日期 (YYYYMMDD) 之 TWSE (T86) 與 TPEx (dailyTrade) 三大法人買賣超資料
    """
    cache_path = os.path.join(CACHE_DIR, f"inst_{date_str}.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                c = json.load(f)
                if c.get("data") and len(c["data"]) > 1000:
                    return c["data"]
        except Exception:
            pass

    combined = {}

    # 1. TWSE T86
    url_twse = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
    try:
        res = safe_fetch_get(url_twse, headers=HEADERS, timeout=10)
        data = res.json()
        if data.get("stat") == "OK" and "data" in data:
            for row in data["data"]:
                ticker = row[0].strip()
                def parse_num(v):
                    try: return int(str(v).replace(",", ""))
                    except: return 0
                # 外資買賣超股數 -> 張數
                foreign_net = parse_num(row[4]) // 1000
                trust_net = parse_num(row[10]) // 1000
                dealer_net = parse_num(row[11]) // 1000
                combined[ticker] = {
                    "foreign": foreign_net,
                    "trust": trust_net,
                    "dealer": dealer_net,
                    "total": foreign_net + trust_net + dealer_net
                }
    except Exception:
        pass

    # 2. TPEx dailyTrade
    try:
        roc_year = int(date_str[:4]) - 1911
        roc_date = f"{roc_year}/{date_str[4:6]}/{date_str[6:]}"
        url_tpex = f"https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?date={roc_date}&type=Daily&response=json"
        res = safe_fetch_get(url_tpex, headers=HEADERS, timeout=10)
        data = res.json()
        tables = data.get("tables", [])
        if tables and len(tables) > 0 and tables[0].get("data"):
            for row in tables[0]["data"]:
                ticker = row[0].strip()
                def parse_num(v):
                    try: return int(str(v).replace(",", ""))
                    except: return 0
                foreign_net = parse_num(row[4]) // 1000 if len(row) > 4 else 0
                trust_net = parse_num(row[7]) // 1000 if len(row) > 7 else 0
                dealer_net = parse_num(row[10]) // 1000 if len(row) > 10 else 0
                combined[ticker] = {
                    "foreign": foreign_net,
                    "trust": trust_net,
                    "dealer": dealer_net,
                    "total": foreign_net + trust_net + dealer_net
                }
    except Exception:
        pass

    if combined:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"date": date_str, "data": combined}, f, ensure_ascii=False)
        print(f"[Inst] 已儲存 {date_str} 三大法人資料 ({len(combined)} 檔)")

    return combined

def get_recent_trading_dates(count=LOOKBACK_DAYS):
    """
    推算最近的有效交易日清單（排除週末）
    若今日小於 15:30，以昨日為最新日期
    """
    now = datetime.now()
    if now.hour < 16: # 台股約 15:30~16:00 法人日報完整發布
        current = now - timedelta(days=1)
    else:
        current = now

    trading_dates = []
    while len(trading_dates) < count:
        if current.weekday() < 5: # 週一至週五
            trading_dates.append(current.strftime("%Y%m%d"))
        current -= timedelta(days=1)

    return sorted(trading_dates) # 從舊到新排列

def get_accumulated_institutional_data(days=LOOKBACK_DAYS):
    """
    計算過去 N 個交易日內之波段外資/投信/三大法人累積數據
    回傳字典結構:
    {
      "2330": {
         "foreign_cum_buy": 15420,       # 20日累計外資買超 (張)
         "foreign_buy_days": 14,         # 20日中外資買超天數
         "foreign_buy_ratio": 0.70,      # 買超天數佔比
         "consecutive_foreign_days": 3,  # 最近連續買超天數
         "trust_cum_buy": 2100,          # 20日累計投信買超 (張)
         "total_cum_buy": 18200,         # 20日三大法人合計買超 (張)
         "today_foreign": 3200           # 最新一日外資買賣超
      }
    }
    """
    dates = get_recent_trading_dates(days)
    print(f"[Inst] 計算過去 {len(dates)} 個交易日法人籌碼: {dates[0]} ~ {dates[-1]}")

    daily_maps = []
    for d in dates:
        d_map = fetch_single_date_institutional(d)
        if d_map:
            daily_maps.append((d, d_map))
        time.sleep(0.1)

    if not daily_maps:
        return {}

    all_tickers = set()
    for _, d_map in daily_maps:
        all_tickers.update(d_map.keys())

    stats = {}
    for ticker in all_tickers:
        foreign_cum = 0
        trust_cum = 0
        total_cum = 0
        foreign_buy_days = 0
        consecutive_foreign = 0

        # 從最新一天往前看以計算連續買超天數
        consecutive_streak = True

        for _, d_map in reversed(daily_maps):
            info = d_map.get(ticker, {"foreign": 0, "trust": 0, "dealer": 0, "total": 0})
            f_net = info["foreign"]
            if f_net > 0 and consecutive_streak:
                consecutive_foreign += 1
            else:
                consecutive_streak = False

        for _, d_map in daily_maps:
            info = d_map.get(ticker, {"foreign": 0, "trust": 0, "dealer": 0, "total": 0})
            f_net = info["foreign"]
            t_net = info["trust"]
            tot = info["total"]

            foreign_cum += f_net
            trust_cum += t_net
            total_cum += tot
            if f_net > 0:
                foreign_buy_days += 1

        total_days = len(daily_maps)
        ratio = round(foreign_buy_days / total_days, 2) if total_days > 0 else 0.0
        latest_d_map = daily_maps[-1][1]
        today_foreign = latest_d_map.get(ticker, {}).get("foreign", 0)

        stats[ticker] = {
            "foreign_cum_buy": foreign_cum,
            "foreign_buy_days": foreign_buy_days,
            "foreign_buy_ratio": ratio,
            "consecutive_foreign_days": consecutive_foreign,
            "trust_cum_buy": trust_cum,
            "total_cum_buy": total_cum,
            "today_foreign": today_foreign,
            "total_days": total_days
        }

    print(f"[Inst] 成功彙整 {len(stats)} 檔標的之波段法人統計")
    return stats

if __name__ == "__main__":
    quotes = get_latest_market_quotes()
    inst = get_accumulated_institutional_data(days=5)
    print("Sample 2330 quotes:", quotes.get("2330"))
    print("Sample 2330 inst:", inst.get("2330"))
