# -*- coding: utf-8 -*-
"""
sepa_engine.py
Mark Minervini SEPA 趨勢模板、0050 Alpha RS 雙軌動能、
VCP 量價收縮 (Dead Quiet) 與 20日橫盤震盪 (股價不太動) 計算核心
"""
import pandas as pd
import numpy as np
import yfinance as yf
from config import (
    MAX_PRICE_AMPLITUDE_PCT,
    VOLUME_CONTRACTION_RATIO,
    DEAD_QUIET_RATIO,
    MIN_ALPHA_RS,
    MAX_MA50_BIAS_PCT
)

def evaluate_stock_sepa(ticker_symbol, df_stock, df_0050):
    """
    對單一個股進行完整的 SEPA + 橫盤壓縮評估
    參數:
      ticker_symbol: 股票代碼 (例: '2330.TW')
      df_stock: 該股票歷史日 K DataFrame (包含 Open, High, Low, Close, Volume)
      df_0050: 0050 (元大台灣50) 歷史日 K (用於計算 Alpha RS)
    回傳字典:
      {
         "is_qualified": True/False,
         "fail_reasons": [...],
         "trend_template_ok": True/False,
         "price_amplitude_20d": 8.5,       # 近20日高低震盪幅度 (%)
         "is_tight_range": True/False,     # 橫盤不太動
         "v_ratio_20": 0.68,               # 5日量/20日量
         "vcp_status": "💎 極致壓縮(80%+CV)",
         "is_dead_quiet": True/False,
         "alpha_rs": 112.5,
         "alpha_status": "🌟 雙軌領先",
         "bias_50": 3.2,                   # 50MA 乖離率 (%)
         "close": 1080.0
      }
    """
    if df_stock is None or len(df_stock) < 150:
        return {"is_qualified": False, "fail_reasons": ["歷史交易資料不足 (需至少150天)"]}

    if isinstance(df_stock.columns, pd.MultiIndex):
        df_stock = df_stock.copy()
        df_stock.columns = df_stock.columns.get_level_values(0)

    close = df_stock['Close'].iloc[:, 0] if isinstance(df_stock['Close'], pd.DataFrame) else df_stock['Close']
    high = df_stock['High'].iloc[:, 0] if isinstance(df_stock['High'], pd.DataFrame) else df_stock['High']
    low = df_stock['Low'].iloc[:, 0] if isinstance(df_stock['Low'], pd.DataFrame) else df_stock['Low']
    volume = df_stock['Volume'].iloc[:, 0] if isinstance(df_stock['Volume'], pd.DataFrame) else df_stock['Volume']

    p_now = float(close.iloc[-1])
    if p_now <= 0:
        return {"is_qualified": False, "fail_reasons": ["現價異常"]}

    # --- 1. Minervini 趨勢模板 7 大條件 (Trend Template) ---
    sma50 = close.rolling(50).mean()
    sma150 = close.rolling(150).mean()
    # 支援 150~200 天以上數據
    has_200 = len(close) >= 200
    sma200 = close.rolling(200).mean() if has_200 else sma150

    m50 = float(sma50.iloc[-1])
    m150 = float(sma150.iloc[-1])
    m200 = float(sma200.iloc[-1])

    # 200MA 是否向上彎曲 (與 22 天前相比)
    m200_22 = float(sma200.iloc[-23]) if has_200 and len(sma200) >= 23 else m200
    is_m200_up = (m200 >= m200_22 * 0.995)

    # 52週 (約252日) 高低點
    lookback_len = min(len(close), 252)
    h_52w = float(high.iloc[-lookback_len:].max())
    l_52w = float(low.iloc[-lookback_len:].min())

    cond1 = (p_now > m150) and (p_now > m200)
    cond2 = (m150 > m200 * 0.98) # 150MA 高於或即將金叉 200MA
    cond3 = is_m200_up
    cond4 = (m50 > m150) and (m50 > m200)
    cond5 = (p_now >= m50 * 0.98) # 站上 50MA (容許微幅回測)
    cond6 = ((p_now / l_52w) - 1) * 100 >= 20.0 if l_52w > 0 else False # 距波段低點反彈 20% 以上
    cond7 = (1 - (p_now / h_52w)) * 100 <= 25.0 if h_52w > 0 else False # 距波段高點在 25% 以內

    trend_template_ok = (cond1 and cond4 and cond5 and cond6 and cond7)

    # 50MA 乖離率
    bias_50 = round(((p_now - m50) / m50) * 100, 1) if m50 > 0 else 0.0

    # --- 2. 股價狹幅橫盤不動 (近 20 日振幅 <= MAX_PRICE_AMPLITUDE_PCT) ---
    win_20 = min(len(close), 20)
    h_20 = float(high.iloc[-win_20:].max())
    l_20 = float(low.iloc[-win_20:].min())
    price_amp_20d = round(((h_20 - l_20) / l_20) * 100, 1) if l_20 > 0 else 999.0
    is_tight_range = (price_amp_20d <= MAX_PRICE_AMPLITUDE_PCT)

    # --- 3. VCP 量價萎縮與波動緊縮 (Pine Script 同步演算法) ---
    vol_5 = float(volume.rolling(5).mean().iloc[-1])
    vol_10 = float(volume.rolling(10).mean().iloc[-1])
    vol_20 = float(volume.rolling(20).mean().iloc[-1]) if len(volume) >= 20 else vol_5
    vol_3 = float(volume.rolling(3).mean().iloc[-1])

    v_ratio_20 = round(vol_5 / vol_20, 2) if vol_20 > 0 else 1.0
    v_ratio_10 = round(vol_5 / vol_10, 2) if vol_10 > 0 else 1.0

    # True Range & ATR
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)

    atr_5 = float(tr.rolling(5).mean().iloc[-1])
    atr_20 = float(tr.rolling(20).mean().iloc[-1]) if len(tr) >= 20 else atr_5
    a_ratio_20 = round(atr_5 / atr_20, 2) if atr_20 > 0 else 1.0

    # 價格緊縮標準差 (Tight CV)
    roll_std5 = close.rolling(5).std(ddof=0)
    roll_mean5 = close.rolling(5).mean()
    cv_5 = roll_std5 / roll_mean5
    cv_5_ma20 = float(cv_5.rolling(20).mean().iloc[-1]) if len(cv_5) >= 20 else float(cv_5.iloc[-1])
    is_tight_cv = (float(cv_5.iloc[-1]) < cv_5_ma20 * 1.05)

    is_dead_quiet = (vol_3 < vol_20 * DEAD_QUIET_RATIO) and is_tight_cv
    is_vcp_80 = (a_ratio_20 < 0.85 or v_ratio_20 < VOLUME_CONTRACTION_RATIO) and is_tight_cv
    is_vcp_90 = (a_ratio_20 < 0.95 or v_ratio_20 < 0.95) and is_tight_cv

    if is_vcp_80:
        vcp_status = "💎 極致壓縮(80%+CV)"
    elif is_dead_quiet:
        vcp_status = "💤 Dead Quiet (靜止平台)"
    elif is_vcp_90:
        vcp_status = "🔥 相對壓縮(90%+CV)"
    else:
        vcp_status = "⏳ 區間量縮整理"

    # --- 4. Alpha RS vs 0050 (領頭羊相對強度) ---
    alpha_rs = 100.0
    is_alpha_ok = True
    alpha_status = "標準"

    if df_0050 is not None and len(df_0050) >= 60:
        c_0050 = df_0050['Close'].iloc[:, 0] if isinstance(df_0050['Close'], pd.DataFrame) else df_0050['Close']
        
        # 統一剝除時區，確保個股與 0050 日期精確對齊無 NaN
        c_0050_s = c_0050.tz_localize(None) if (hasattr(c_0050.index, 'tz') and c_0050.index.tz is not None) else c_0050
        close_s = close.tz_localize(None) if (hasattr(close.index, 'tz') and close.index.tz is not None) else close

        b_c = c_0050_s.reindex(close_s.index).ffill().bfill()
        rel_val = close_s / b_c
        
        d_3m = min(len(rel_val)-1, 63)
        d_6m = min(len(rel_val)-1, 126)
        d_9m = min(len(rel_val)-1, 189)
        d_1y = min(len(rel_val)-1, 252)

        rel_3m = rel_val.shift(d_3m)
        rel_6m = rel_val.shift(d_6m)
        rel_9m = rel_val.shift(d_9m)
        rel_1y = rel_val.shift(d_1y)

        rel_alpha_series = ((rel_val / rel_3m * 2) + (rel_val / rel_6m) + (rel_val / rel_9m) + (rel_val / rel_1y)) / 5 * 100
        rel_alpha_now = float(rel_alpha_series.iloc[-1]) if not pd.isna(rel_alpha_series.iloc[-1]) else 100.0
        alpha_rs = round(rel_alpha_now, 1)

        alpha_sma5 = float(rel_alpha_series.rolling(5).mean().iloc[-1]) if len(rel_alpha_series) >= 5 else rel_alpha_now
        is_rs_recovering = (rel_alpha_now > float(rel_alpha_series.iloc[-2])) and (rel_alpha_now > alpha_sma5)
        
        hist_30_max = float(rel_alpha_series.iloc[-31:-1].max()) if len(rel_alpha_series) >= 32 else rel_alpha_now
        is_alpha_new_high = (rel_alpha_now >= hist_30_max)
        is_price_new_high = (p_now >= float(close.iloc[-31:-1].max())) if len(close) >= 32 else False
        is_alpha_leading = (not is_price_new_high) and is_alpha_new_high

        if is_alpha_leading:
            alpha_status = "🌟 Alpha領先"
        elif is_alpha_new_high:
            alpha_status = "🔥 Alpha新高"
        elif alpha_rs >= 115.0:
            alpha_status = "🚀 超越大盤"
        elif alpha_rs >= 100.0:
            alpha_status = "✅ 強於大盤"
        elif is_rs_recovering:
            alpha_status = "📈 動能回溫中"
        elif alpha_rs >= 90.0:
            alpha_status = "⚖️ 與大盤持平"
        else:
            alpha_status = "⏳ 蓄勢整理中"

        is_alpha_ok = (alpha_rs >= MIN_ALPHA_RS or is_alpha_leading or is_rs_recovering or alpha_rs >= 80.0)

    # --- 5. 突破判定與成交量放量 (Pine Script 同步) ---
    win_10 = min(len(high), 11)
    pivot_10d = float(high.iloc[-win_10:-1].max()) if win_10 > 1 else float(high.iloc[-1])
    breakout_10d = (p_now >= pivot_10d)
    
    today_vol = float(volume.iloc[-1])
    vol_spike_ratio = round(today_vol / vol_20, 2) if vol_20 > 0 else 1.0
    is_vol_spike = (today_vol >= vol_20 * 1.5)

    # 過去 10 日內是否曾出現量縮壓縮 (VCP Memo)
    past_10_vol_min = float(volume.iloc[-min(len(volume), 10):].min())
    is_short_term_dry = (past_10_vol_min < vol_20 * 0.85)
    is_vcp_memo = (is_vcp_80 or is_dead_quiet or is_vcp_90 or is_short_term_dry)

    # 乖離是否過熱
    dynamic_bias_limit = 40.0 if alpha_rs > 150 else MAX_MA50_BIAS_PCT
    is_extended = (bias_50 > dynamic_bias_limit)

    # --- 6. 核心訊號決策：爆發建倉 (BREAKOUT) vs 潛伏蓄勢 (STEALTH) ---
    is_all_set = trend_template_ok and is_alpha_ok and not is_extended
    signal_type = "NONE"
    action_title = "未達建倉標準"
    is_qualified = False

    if is_all_set and breakout_10d and is_vol_spike:
        # 模式一：【爆發當天 / 建議建倉】
        signal_type = "BREAKOUT"
        action_title = "🚀 建議建倉 (VCP突破)" if is_vcp_memo else "⚡ 考慮建倉 (放量強勢突破)"
        is_qualified = True
    elif is_all_set and is_tight_range and (is_vcp_memo or v_ratio_20 < 1.0):
        # 模式二：【爆發前夕 / 潛伏蓄勢】
        signal_type = "STEALTH"
        action_title = "🏹 潛伏蓄勢 (爆發前夕 / 橫盤量縮)"
        is_qualified = True

    return {
        "is_qualified": is_qualified,
        "signal_type": signal_type,
        "action_title": action_title,
        "breakout_10d": breakout_10d,
        "is_vol_spike": is_vol_spike,
        "vol_spike_ratio": vol_spike_ratio,
        "pivot_10d": pivot_10d,
        "trend_template_ok": trend_template_ok,
        "price_amplitude_20d": price_amp_20d,
        "is_tight_range": is_tight_range,
        "v_ratio_20": v_ratio_20,
        "vcp_status": vcp_status,
        "is_dead_quiet": is_dead_quiet,
        "alpha_rs": alpha_rs,
        "alpha_status": alpha_status,
        "bias_50": bias_50,
        "close": p_now
    }
