# -*- coding: utf-8 -*-
"""
trading_calendar.py
台股開盤日智慧防護模組（遵循 Fail-Open 樂觀放行與零誤判原則）

防護原則：
1. 核心原則：Fail-Open（寧可多跑，絕不錯過），任何連線錯誤或超時一律判定為開盤。
2. 雙重核實：比對臺灣證券交易所 (TWSE) 官方全年放假行事曆 + 全市場實質成交量檢測。
3. 自動重試：遇到資料庫瞬間延遲時，自動重試避免單點連線抖動。
4. 強制開關：支援 force=True 直接略過休市檢查（手動觸發時永不阻擋）。
"""
import os
import json
import time
from datetime import datetime
import urllib.request
import urllib.error

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

def _fetch_url_json(url, timeout=8):
    """使用內建 urllib 安全抓取 JSON，避免第三方套件環境問題"""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            if res.status == 200:
                return json.loads(res.read().decode("utf-8"))
    except Exception:
        pass
    return None

def is_official_holiday(date_obj=None):
    """
    查詢證交所官方行事曆：
    僅在官方明確登記放假、補假或市場無交易時回傳 (True, 原因)。
    若未登記或連線異常，回傳 (False, 原因)，絕不因網路中斷誤判休市。
    """
    if date_obj is None:
        date_obj = datetime.now()

    roc_year = date_obj.year - 1911
    roc_date_str = f"{roc_year:03d}{date_obj.strftime('%m%d')}"

    url = "https://openapi.twse.com.tw/v1/holidaySchedule/holidaySchedule"
    schedule = _fetch_url_json(url, timeout=6)
    if not schedule or not isinstance(schedule, list):
        # 網路不通或 API 變更，採取 Fail-Open 放行
        return False, "官方日曆連線異常，採取樂觀放行"

    for item in schedule:
        if str(item.get("Date", "")).strip() == roc_date_str:
            name = str(item.get("Name", "")).strip()
            desc = str(item.get("Description", "")).strip()
            # 若為開市/最後交易，絕非休市
            if "開始交易" in name or "最後交易" in name:
                return False, f"交易日 ({name})"
            # 官方排定放假、補假或結算無交易
            if any(kw in (name + desc) for kw in ["放假", "補假", "市場無交易", "紀念日", "節"]):
                return True, f"官方排定休市 ({name})"

    return False, "官方行事曆未登記休市"

def is_market_open_today(force=False, max_retries=3, retry_delay=5):
    """
    高可靠度台股開盤判定：
    回傳: (is_open: bool, reason: str)
    """
    # 1. 手動或測試強制執行，或在 GitHub 頁面手動點擊 Run workflow
    if force or os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        return True, "手動強制執行模式（略過休市檢查）"

    now = datetime.now()

    # 2. 週末直接判定（週六週日）
    if now.weekday() >= 5:
        weekday_name = "週六" if now.weekday() == 5 else "週日"
        return False, f"例行週末休市 ({weekday_name})"

    # 3. 第一道：證交所官方行事曆比對
    is_holiday, reason = is_official_holiday(now)
    if is_holiday:
        return False, reason

    # 4. 第二道：全市場成交量撮合檢測（防突發颱風假等未排定假期）
    # 執行帶有重試的撮合檢驗，避免 16:30 證交所資料庫瞬間延遲
    url_twse = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    for attempt in range(max_retries):
        data = _fetch_url_json(url_twse, timeout=10)
        if data and isinstance(data, list) and len(data) > 500:
            has_volume = False
            for item in data[:60]:
                try:
                    vol = int(str(item.get("TradeVolume", "0")).replace(",", ""))
                    if vol > 0:
                        has_volume = True
                        break
                except Exception:
                    pass
            if has_volume:
                return True, "全市場撮合成交正常，確認為有效交易日"
            else:
                # 全市場無撮合（颱風假或突發休市）
                return False, "全市場成交量為零（確認突發休市/颱風假）"

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    # 5. Fail-Open 原則：若所有連線均未果，絕不擋開盤！
    return True, "證交所連線超時，採取樂觀放行原則（照常執行選股）"

if __name__ == "__main__":
    is_open, msg = is_market_open_today()
    print(f"今日開盤狀態: {is_open} ｜ 原因: {msg}")
