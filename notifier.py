# -*- coding: utf-8 -*-
"""
notifier.py
LINE Messaging API 推播模組
產出排版清晰、分族群整理之「大波段蓄勢強勢股」精選報告
"""
import json
import requests
from datetime import datetime
from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_USER_ID

def format_screener_report(clustered_groups, single_stocks, trade_date_str=None):
    """
    將篩選與聚類結果格式化為高可讀性的 LINE 訊息文字
    """
    if not trade_date_str:
        trade_date_str = datetime.now().strftime("%Y-%m-%d")

    total_matches = sum(g["count"] for g in clustered_groups) + len(single_stocks)

    lines = [
        "🚀【台股大波段蓄勢・族群共振報告】",
        f"📅 交易日期：{trade_date_str}",
        f"🎯 嚴選標的：共 {total_matches} 檔符合所有大波段蓄勢模板",
        "━━━━━━━━━━━━━━━━━━━━"
    ]

    if not clustered_groups and not single_stocks:
        lines.append("😴 今日市場無同時符合『波段外資狂買 + 橫盤不漲 + 千張大戶增加 + VCP縮量』之標的。")
        lines.append("💡 大師心法：真正翻倍的大波段需要耐心等待完美買點，保護資金、耐心等待下一次完美收斂！")
        return "\n".join(lines)

    # 1. 族群共振區
    if clustered_groups:
        lines.append("🔥 族群共振區（同產業 ≥ 2 檔同步蓄勢）：\n")
        for g in clustered_groups:
            sub_name = g["sub_industry"]
            count = g["count"]
            tot_buy = g["total_foreign_buy"]
            lines.append(f"【{sub_name}】({count} 檔符合 | 外資波段大買 +{tot_buy:,}張)")

            for m in g["members"]:
                ticker = m["ticker"]
                name = m["name"]
                close = m["close"]
                change_sign = "+" if m.get("change", 0) > 0 else ""
                change_str = f"{change_sign}{m.get('change', 0):.2f}" if "change" in m else ""
                amp = m["price_amplitude_20d"]
                vcp_st = m["vcp_status"]
                f_cum = m["foreign_cum_buy"]
                f_ratio = int(m.get("foreign_buy_ratio", 0) * 100)
                pct_1000 = m.get("pct_1000", 0.0)
                chg_1000 = m.get("change_1000_1w", 0.0)
                chg_1000_str = f"+{chg_1000}%" if chg_1000 > 0 else f"{chg_1000}%"
                alpha_st = m.get("alpha_status", "強於大盤")

                price_str = f"${float(close):.2f}"
                sig_type = m.get("signal_type", "STEALTH")
                action_title = m.get("action_title", "🏹 潛伏蓄勢")
                
                lines.append(f"• {ticker} {name}  {price_str} ({change_str})")
                lines.append(f"  💡 訊號決策：{action_title}")
                if sig_type == "BREAKOUT":
                    vol_spike = m.get("vol_spike_ratio", 1.5)
                    pivot_p = m.get("pivot_10d", 0.0)
                    lines.append(f"  ⚡ 突破爆發：今日放量 {vol_spike} 倍突破 10日 Pivot 壓力 (${pivot_p:.2f})！")
                else:
                    lines.append(f"  📦 橫盤狀態：20日振幅僅 {amp}% | {vcp_st}")

                lines.append(f"  🏛️ 外資吸籌：20日累計買超 +{f_cum:,}張 (買超天數比 {f_ratio}%)")
                lines.append(f"  👥 千張大戶：{pct_1000}% (週增 {chg_1000_str})")
                lines.append(f"  📈 動能指標：Minervini 7 條件全符 | {alpha_st}")
                lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")

    # 2. 單兵突進區 (獨立強勢股 / 新切入該產業潛力黑馬，保留完整指標不剔除)
    if single_stocks:
        lines.append("⭐ 獨立潛力標的（單兵突進 / 新切入轉型黑馬，非必要排除）：\n")
        for m in single_stocks:
            ticker = m["ticker"]
            name = m["name"]
            close = m["close"]
            change_sign = "+" if m.get("change", 0) > 0 else ""
            change_str = f"{change_sign}{m.get('change', 0):.2f}" if "change" in m else ""
            price_str = f"${float(close):.2f}"
            sub_name = m.get("sub_industry", "一般類股")
            f_cum = m["foreign_cum_buy"]
            f_ratio = int(m.get("foreign_buy_ratio", 0) * 100)
            pct_1000 = m.get("pct_1000", 0.0)
            chg_1000 = m.get("change_1000_1w", 0.0)
            chg_1000_str = f"+{chg_1000}%" if chg_1000 > 0 else f"{chg_1000}%"
            amp = m["price_amplitude_20d"]
            vcp_st = m["vcp_status"]
            sig_type = m.get("signal_type", "STEALTH")
            action_title = m.get("action_title", "🏹 潛伏蓄勢")
            alpha_st = m.get("alpha_status", "強於大盤")

            lines.append(f"• {ticker} {name}  {price_str} ({change_str}) | 【{sub_name}】")
            lines.append(f"  💡 訊號決策：{action_title}")
            if sig_type == "BREAKOUT":
                vol_spike = m.get("vol_spike_ratio", 1.5)
                pivot_p = m.get("pivot_10d", 0.0)
                lines.append(f"  ⚡ 突破爆發：今日放量 {vol_spike} 倍突破 10日 Pivot 壓力 (${pivot_p:.2f})！")
            else:
                lines.append(f"  📦 橫盤狀態：20日振幅僅 {amp}% | {vcp_st}")

            lines.append(f"  🏛️ 外資吸籌：20日累計買超 +{f_cum:,}張 (買超天數比 {f_ratio}%)")
            lines.append(f"  👥 千張大戶：{pct_1000}% (週增 {chg_1000_str})")
            lines.append(f"  📈 動能指標：Minervini 7 條件全符 | {alpha_st}\n")

    lines.append("⚠️ 本報告由量化演算法自動產生，僅供策略研究參考，非投資建議。")
    return "\n".join(lines)

def send_line_message(message_text):
    """
    呼叫 LINE Messaging API 推播訊息給指定 User (自動處理分段，單則最長 4500 字)
    """
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_USER_ID:
        print("[LINE] ⚠️ 未偵測到 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_USER_ID，將輸出於終端機：")
        print("--------------------------------------------------")
        print(message_text)
        print("--------------------------------------------------")
        return False

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

    # 自動分割過長文字為多則訊息 (LINE 單次 push 最多 5 則訊息，每則 < 5000 字)
    max_chunk = 4200
    chunks = []
    if len(message_text) <= max_chunk:
        chunks.append(message_text)
    else:
        current_chunk = []
        current_len = 0
        for block in message_text.split("\n\n"):
            if current_len + len(block) + 2 > max_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [block]
                current_len = len(block)
            else:
                current_chunk.append(block)
                current_len += len(block) + 2
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

    messages_payload = [{"type": "text", "text": c} for c in chunks[:5]]

    payload = {
        "to": LINE_USER_ID,
        "messages": messages_payload
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            print("[LINE] ✅ 訊息已成功推播至 LINE！")
            return True
        else:
            print(f"[LINE] ❌ 推播失敗 (HTTP {res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"[LINE] ❌ 連線錯誤: {e}")
        return False

if __name__ == "__main__":
    dummy_groups = [
        {
            "sub_industry": "光通訊與矽光子 (CPO)",
            "count": 2,
            "total_foreign_buy": 4570,
            "members": [
                {
                    "ticker": "3450",
                    "name": "聯鈞",
                    "close": 218.0,
                    "change": 2.5,
                    "price_amplitude_20d": 7.4,
                    "vcp_status": "💎 極致壓縮(80%+CV)",
                    "foreign_cum_buy": 3420,
                    "foreign_buy_ratio": 0.75,
                    "pct_1000": 68.5,
                    "change_1000_1w": 1.25,
                    "alpha_status": "🌟 Alpha領先"
                },
                {
                    "ticker": "4979",
                    "name": "華星光",
                    "close": 152.0,
                    "change": 0.5,
                    "price_amplitude_20d": 8.1,
                    "vcp_status": "💤 Dead Quiet (靜止平台)",
                    "foreign_cum_buy": 1150,
                    "foreign_buy_ratio": 0.65,
                    "pct_1000": 62.1,
                    "change_1000_1w": 0.45,
                    "alpha_status": "📈 動能回復中"
                }
            ]
        }
    ]
    report = format_screener_report(dummy_groups, [])
    send_line_message(report)
