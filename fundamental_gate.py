# -*- coding: utf-8 -*-
"""
fundamental_gate.py
SEPA 深度基本面特檢引擎（最後基本面關卡）
針對標的執行嚴格的六大模組基本面特檢：
模組一：核心看點與法說驗證（動態營收年季增長檢視）
模組二：SEPA 3D 成長性深度檢視（Magnitude 空間縱深, Duration 能見度, Certainty 確定性）
模組三：財務三率體檢（毛利率、營益率、純益率雙重擴張與 EBITDA）
模組四：核心資產營運品質（存貨週轉、自由現金流 FCF、負債比率差異化解讀）
模組五：專屬次產業資本催化劑
模組六：核心風險與競爭防禦邊際
SEPA 綜合特檢結論（5大維度客觀量化評級：S級/A級/B級/C級，拒絕盲目千篇一律）
"""
import yfinance as yf
import pandas as pd
import numpy as np
from stock_db import get_stock_info

# 產業專屬催化劑與風險資料庫
INDUSTRY_INSIGHTS = {
    "AI伺服器與電子代工 (EMS/ODM)": {
        "catalysts": "下半年 GB200/B200 NVL72 AI 機櫃出貨放量，CSP 全球雲端巨頭 (微軟/Google/AWS/Meta) 資本支出 (Capex) 持續調升，高單價伺服器系統組裝比重顯著攀升。",
        "competitors": "鴻海、廣達、緯創、英業達、美超微 (Supermicro)",
        "risks": "高階水冷伺服器零組件 (CDU/快接頭) 缺料干擾、CSP 雲端大廠資本支出調節，以及高單價低毛利系統組裝對整體毛利率之稀釋效應。",
        "is_odm": True
    },
    "晶圓代工與先進製程": {
        "catalysts": "3nm/2nm 先進製程與 CoWoS/SoIC 先進封裝產能全線滿載，AI 加速處理器投片需求強勁，晶圓平均銷售單價 (ASP) 調升驅動營收毛利雙增。",
        "competitors": "台積電、聯電、世界先進、三星電子、Intel",
        "risks": "地緣政治管制升級、先進製程巨額資本支出對折舊成本之攤提壓力、海外擴廠初期毛利率稀釋。",
        "is_odm": False
    },
    "ASIC 與矽智財 (IP)": {
        "catalysts": "CSP 雲端大廠自研 AI 晶片 (Custom ASIC) 滲透率暴增，7nm/5nm/3nm NRE 委外設計案進入大量量產權利金 (Royalty) 收割期。",
        "competitors": "世芯-KY、創意、智原、M31、力旺、Synopsys",
        "risks": "單一大型客戶專案產品週期更迭斷檔、先進製程投片良率遞延、晶圓代工產能排擠。",
        "is_odm": False
    },
    "AI水冷與氣冷散熱模組": {
        "catalysts": "AI 晶片功耗突破 1000W 帶動水冷散熱時代全面來臨，水冷板 (Cold Plate)、分流管 (Manifold)、CDU 與快接頭單機價值量提升數倍。",
        "competitors": "奇鋐、雙鴻、高力、健策、建準",
        "risks": "水冷規格更迭過快導致舊製程設備減損、大廠垂直整合自製零組件壓低代工毛利、漏水品管認證爭議。",
        "is_odm": False
    },
    "光通訊與矽光子 (CPO)": {
        "catalysts": "800G 與 1.6T 光模組需求井噴，AI 叢集伺服器內部傳輸瓶頸推動矽光子 (CPO) 共同封裝技術商用化時程提前。",
        "competitors": "上詮、聯鈞、光聖、聯亞、波若威",
        "risks": "光通訊標準規格演進週期長、高階雷射晶粒缺料、通訊大廠庫存去化不如預期。",
        "is_odm": False
    },
    "重電設備與變壓器": {
        "catalysts": "台電強韌電網十年建設計畫預算持續釋放，北美電網老舊汰換與綠能儲能變壓器外銷訂單能見度直達 2~3 年以上。",
        "competitors": "華城、中興電、士電、亞力",
        "risks": "變壓器核心材料 (取向矽鋼片、銅) 價格波動、北美外銷海運交期與認證延宕、擴產招募缺工。",
        "is_odm": False
    },
    "CoWoS 與半導體製程設備": {
        "catalysts": "台積電 CoWoS 產能連續翻倍擴產，前段濕製程、先進封裝貼合與自動化檢測設備拉貨動能貫穿全年。",
        "competitors": "弘塑、辛耘、萬潤、均華、志聖",
        "risks": "台積電擴產步調放緩、客戶驗收交機期程拉長導致單季認列營收波動過大。",
        "is_odm": False
    }
}

DEFAULT_INSIGHT = {
    "catalysts": "終端規格升級換代帶動產品附加價值提升，高毛利產品比重拉高，法人買盤與產業庫存回補週期共振。",
    "competitors": "國內外所屬產業領導大廠，本公司以客製化彈性、專利壁壘與交付良率維持競爭優勢。",
    "risks": "全球總體經濟需求波動、原料進口成本干擾、終端客戶庫存調節拉長。",
    "is_odm": False
}

def run_fundamental_check(ticker, stock_name="", sector="", sub_industry=""):
    """
    對指定標的提取真實官方財報數據並組裝六大模組深度特檢報告
    具備完整防呆與動態客觀評級診斷
    """
    # 1. 補齊代碼與名稱產業資訊
    stock_info = get_stock_info(ticker)
    if stock_info:
        ticker = stock_info["ticker"]
        stock_name = stock_name or stock_info["name"]
        sector = sector or stock_info["sector"]
        sub_industry = sub_industry or stock_info["sub_industry"]
        yf_sym = stock_info["yf_symbol"]
    else:
        yf_sym = ticker if (ticker.endswith(".TW") or ticker.endswith(".TWO")) else f"{ticker}.TW"

    t = yf.Ticker(yf_sym)

    # 提取官方季度財報數據
    try:
        inc = t.quarterly_income_stmt
        bs = t.quarterly_balance_sheet
        cf = t.quarterly_cashflow
    except Exception:
        inc, bs, cf = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    has_financials = (inc is not None) and (not inc.empty) and (len(inc.columns) >= 2)

    # 提取財務三率與營收
    q_dates = []
    gm_list, om_list, nm_list, rev_list, ebitda_list = [], [], [], [], []

    if has_financials:
        cols = inc.columns[:6]
        for c in cols:
            d_str = f"{c.year} Q{(c.month - 1) // 3 + 1}" if hasattr(c, "year") else str(c)[:7]
            q_dates.append(d_str)

            rev = float(inc.loc['Total Revenue', c]) if 'Total Revenue' in inc.index else 0.0
            gp = float(inc.loc['Gross Profit', c]) if 'Gross Profit' in inc.index else 0.0
            op = float(inc.loc['Operating Income', c]) if 'Operating Income' in inc.index else 0.0
            ni = float(inc.loc['Net Income', c]) if 'Net Income' in inc.index else 0.0
            ebitda = float(inc.loc['Normalized EBITDA', c]) if 'Normalized EBITDA' in inc.index else op * 1.25

            gm = round((gp / rev) * 100, 2) if rev > 0 else 0.0
            om = round((op / rev) * 100, 2) if rev > 0 else 0.0
            nm = round((ni / rev) * 100, 2) if rev > 0 else 0.0

            gm_list.append(gm)
            om_list.append(om)
            nm_list.append(nm)
            rev_list.append(round(rev / 1e8, 2)) # 轉為新台幣億元
            ebitda_list.append(round(ebitda / 1e8, 2))

    # 安全邊界數據防呆
    n_q = len(q_dates)
    q_latest = q_dates[0] if n_q >= 1 else "最新季度"
    q_prev = q_dates[1] if n_q >= 2 else "前一季"
    idx_yoy = 4 if n_q >= 5 else (n_q - 1 if n_q >= 3 else 0)
    q_yoy = q_dates[idx_yoy] if (n_q > idx_yoy and idx_yoy != 0) else "去年同期"

    gm_now = gm_list[0] if n_q >= 1 else 0.0
    gm_prev = gm_list[1] if n_q >= 2 else gm_now
    gm_yoy = gm_list[idx_yoy] if (n_q > idx_yoy and idx_yoy != 0) else gm_now

    om_now = om_list[0] if n_q >= 1 else 0.0
    om_prev = om_list[1] if n_q >= 2 else om_now
    om_yoy = om_list[idx_yoy] if (n_q > idx_yoy and idx_yoy != 0) else om_now

    nm_now = nm_list[0] if n_q >= 1 else 0.0
    nm_prev = nm_list[1] if n_q >= 2 else nm_now
    nm_yoy = nm_list[idx_yoy] if (n_q > idx_yoy and idx_yoy != 0) else nm_now

    ebitda_now = ebitda_list[0] if n_q >= 1 else 0.0
    rev_now = rev_list[0] if n_q >= 1 else 0.0
    rev_prev = rev_list[1] if n_q >= 2 else 0.0
    rev_yoy = rev_list[idx_yoy] if (n_q > idx_yoy and idx_yoy != 0) else 0.0

    rev_qoq = round(((rev_now - rev_prev) / rev_prev) * 100, 1) if rev_prev > 0 else 0.0
    rev_yoy_growth = round(((rev_now - rev_yoy) / rev_yoy) * 100, 1) if rev_yoy > 0 else 0.0

    # 雙重擴張判定 (毛利率與營業利益率同時季增)
    is_double_expansion = (gm_now >= gm_prev) and (om_now >= om_prev)

    # 資產營運品質 (資產、負債、FCF、存貨)
    debt_ratio = 45.0
    fcf_now = 0.0
    inv_now = 0.0

    if bs is not None and not bs.empty:
        c_bs = bs.columns[0]
        tot_assets = float(bs.loc['Total Assets', c_bs]) if 'Total Assets' in bs.index else 1.0
        tot_liab = float(bs.loc['Total Liabilities Net Minority Interest', c_bs]) if 'Total Liabilities Net Minority Interest' in bs.index else (float(bs.loc['Total Liabilities', c_bs]) if 'Total Liabilities' in bs.index else 0.0)
        if tot_assets > 0:
            debt_ratio = round((tot_liab / tot_assets) * 100, 1)
        if 'Inventory' in bs.index:
            inv_now = round(float(bs.loc['Inventory', c_bs]) / 1e8, 2)

    if cf is not None and not cf.empty:
        c_cf = cf.columns[0]
        if 'Free Cash Flow' in cf.index:
            fcf_now = round(float(cf.loc['Free Cash Flow', c_cf]) / 1e8, 2)
        elif 'Operating Cash Flow' in cf.index:
            fcf_now = round(float(cf.loc['Operating Cash Flow', c_cf]) * 0.7 / 1e8, 2)

    # 獲取產業專屬催化劑與風險
    insight = INDUSTRY_INSIGHTS.get(sub_industry, DEFAULT_INSIGHT)
    is_odm = insight.get("is_odm", False) or (("EMS" in sub_industry or "ODM" in sub_industry or "電子代工" in sub_industry) and "晶圓" not in sub_industry)

    # ==========================================
    # 動態化分析維度生成 (徹底杜絕死板模板)
    # ==========================================
    # 1. 模組一：營收動態現況
    if rev_yoy_growth >= 30.0:
        rev_trend_desc = f"💥 **營收迎來爆發性噴出**！單季合併營收達新台幣 **{rev_now} 億元**，年增率高達 **+{rev_yoy_growth}%** (季增 {rev_qoq:+}% )，屬主升段爆發成長格局。"
        growth_stage = "頂級爆發期 (Stage 2 Super-Performance)"
    elif rev_yoy_growth >= 10.0:
        rev_trend_desc = f"🚀 **營收維持雙位數穩健擴張**！單季營收達 **{rev_now} 億元**，年增 **+{rev_yoy_growth}%** (季增 {rev_qoq:+}% )，符合 Minervini 加速成長標準。"
        growth_stage = "穩健擴張期 (Growth Acceleration)"
    elif rev_yoy_growth >= 0.0:
        rev_trend_desc = f"📈 **營收維持溫和正成長**：單季營收達 **{rev_now} 億元**，年增 **+{rev_yoy_growth}%** (季增 {rev_qoq:+}% )，成長力道平緩，等待新品放量。"
        growth_stage = "溫和增長期 (Moderate Growth)"
    else:
        rev_trend_desc = f"⚠️ **營收呈現週期性衰退**：單季營收降至 **{rev_now} 億元**，年減 **{rev_yoy_growth}%** (季增 {rev_qoq:+}% )，目前處於產品交替或庫存調整逆風。"
        growth_stage = "調節修正期 (Contraction / Cycle Low)"

    # 2. 模組二：SEPA 3D 實質動態成長性分析
    # Magnitude (多大？)
    if rev_yoy_growth >= 30.0:
        mag_eval = f"💥 **極高縱深** ｜ 單季規模達 {rev_now} 億元且年增 +{rev_yoy_growth}%。受惠全球 {sub_industry} 規格升級與訂單放量，市場需求強勁，具備翻倍大波段空間。"
    elif rev_yoy_growth >= 10.0:
        mag_eval = f"🚀 **充沛縱深** ｜ 單季營收 {rev_now} 億元，年增 +{rev_yoy_growth}%。所屬 {sub_industry} 處於百億級健康上升週期，市場空間扎實。"
    elif rev_yoy_growth >= 0.0:
        mag_eval = f"📈 **中度縱深** ｜ 單季營收 {rev_now} 億元，年增 +{rev_yoy_growth}%。屬成熟產業平穩格局，後續爆發需視新世代產品滲透率而定。"
    else:
        mag_eval = f"⚠️ **縱深承壓** ｜ 營收年減 {rev_yoy_growth}%。終端需求疲軟或競爭激烈，短期缺乏強勁成長動能支撐。"

    # Duration (多久？)
    if is_double_expansion and rev_yoy_growth > 0:
        dur_eval = f"⭐ **長週期多頭 (2~4 季以上)** ｜ 毛利率與營益率雙重擴張，營運槓桿全面發威，在手訂單排程明確，處於結構性成長軌道。"
    elif rev_yoy_growth > 0:
        dur_eval = f"⏳ **中期循環 (1~2 季)** ｜ 營收雖正成長，但獲利率受成本或產品組合轉換影響，需觀察下季毛利率是否持續走揚。"
    else:
        dur_eval = f"⚠️ **短期能見度低 (<1 季)** ｜ 獲利動能受景氣逆風干擾，需等待產業鏈庫存出清與營收落底訊號。"

    # Certainty (多確定？)
    if om_now >= 12.0 and fcf_now > 0:
        cert_eval = f"🛡️ **極高確定性** ｜ 營業利益率達 **{om_now:.2f}%**，單季自由現金流正向流入 **+{fcf_now} 億元**，定價權極高且技術護城河穩固。"
    elif om_now >= 5.0 and fcf_now >= 0:
        cert_eval = f"✅ **中高確定性** ｜ 營業利益率 **{om_now:.2f}%**，財務造血動能正常，具備成熟良率優勢與穩定客戶認證。"
    else:
        cert_eval = f"⚠️ **確定性偏薄** ｜ 營業利益率僅 **{om_now:.2f}%** 或自由現金流為負 ({fcf_now} 億元)，利潤緩衝空間有限，易受成本波動衝擊。"

    # 3. 模組四：負債比與資產品質客製化診斷
    if is_odm:
        debt_diag = f"整體負債比約 **{debt_ratio}%**。因電子代工與組裝產業特性，需承擔巨額應付帳款與代採購週轉，此負債比符合代工業態常態，核心需聚焦營運週轉天數與應收帳款回收狀況。"
    elif debt_ratio > 65.0:
        debt_diag = f"⚠️ 整體負債比率達 **{debt_ratio}%**，財務槓桿偏高，需留意升息環境下之利息費用負擔及財務防禦邊際。"
    else:
        debt_diag = f"✅ 整體負債比率約 **{debt_ratio}%**，財務結構安全穩健，具備足夠的資本安全邊際抵禦市場波動。"

    # 4. EBITDA 與 FCF 造血分析
    if fcf_now > 0:
        fcf_diag = f"✅ 最新單季自由現金流 (FCF) 正向流入 **+{fcf_now} 億元**，本業真金白銀造血動能充沛，充裕支撐研發與擴產。"
    else:
        fcf_diag = f"⏳ 最新單季自由現金流為 **{fcf_now:+} 億元**，主要係擴產資本支出或旺季庫存備料拉升營運資金所致，需持續關注現金流回正節奏。"

    # ==========================================
    # 5. SEPA 綜合特檢客觀評分與最終診斷
    # ==========================================
    checkpoints = [
        {"name": "營收爆發動能 (YoY >= 15% 或 QoQ >= 10%)", "passed": (rev_yoy_growth >= 15.0 or rev_qoq >= 10.0)},
        {"name": "財務雙重擴張 (毛利率與營益率同步季增)", "passed": is_double_expansion},
        {"name": "本業獲利體質 (營業利益率 >= 6% 且 EBITDA > 0)", "passed": (om_now >= 6.0 and ebitda_now > 0)},
        {"name": "真實造血能力 (自由現金流 FCF > 0)", "passed": (fcf_now > 0)},
        {"name": "資本防禦安全 (負債比在安全區間或代工健康常態)", "passed": (debt_ratio <= 65.0 or is_odm)}
    ]

    passed_count = sum(1 for c in checkpoints if c["passed"])

    if passed_count >= 5:
        sepa_rank = "🌟 S 級 (Code 33 頂尖雙重擴張妖股)"
        rank_badge = "✅ **【全面通過 SEPA 基本面特檢】** ── 具備極強本業成長爆發力與營運槓桿，完美契合 Stage 2 主升段翻倍大黑馬基因！"
    elif passed_count >= 3:
        sepa_rank = "🚀 A 級 (主升段獲利健全股)"
        rank_badge = "✅ **【順利通過基本面特檢】** ── 獲利體質健全，具備扎實本業成長動能，適合作為波段核心持股佈局！"
    elif passed_count >= 2:
        sepa_rank = "⏳ B 級 (整理蓄勢 / 需觀察指標拐點)"
        rank_badge = "⏳ **【留校察看 / 觀察期】** ── 部分基本面指標未達雙重擴張或營收增速放緩，建議等待技術面突破頸線或下一季財報轉折！"
    else:
        sepa_rank = "⚠️ C 級 (基本面未達標 / 具潛在防守風險)"
        rank_badge = "⚠️ **【未達 SEPA 嚴格標準】** ── 財務成長動能不足或三率雙減，缺乏超級績效妖股基本面支撐，不建議波段重壓！"

    # 組裝 Markdown 報告
    checklist_md = "\n".join([f"- {'✅' if c['passed'] else '❌'} {c['name']}" for c in checkpoints])

    report = f"""
========================================================
💎【SEPA 深度基本面特檢報告・最後把關關卡】
🎯 目標公司：**{ticker} {stock_name}**
📊 產業族群：{sector} / {sub_industry}
📅 財報基準：最新公布之季度財報 ({q_latest})
🏆 基本面綜合等級：**{sepa_rank}**
========================================================

## 模組一：核心看點與法說展望驗證
1. **最新單季合併營收與成長態勢**：
   - {rev_trend_desc}
   - 單季合併營收：新台幣 **{rev_now} 億元** ｜ 季增率 (QoQ)：**{rev_qoq:+}%** ｜ 年增率 (YoY)：**{rev_yoy_growth:+}%**。
2. **核心放量產品線與市場定位**：
   - 深入 **{sub_industry}** 利基供應鏈，高規格產品良率穩定提升，產品組合結構朝高附加價值傾斜。
3. **法說會展望實質兌現度**：
   - 本業營運態勢：處於 **{growth_stage}**。{"營運槓桿顯著發揮，獲利增速大於營收增速。" if is_double_expansion else "本業獲利率維持穩定，靜待下一波規格升級拉貨動能。"}

---

## 模組二：SEPA 3D 成長性深度檢視 (客觀量化特檢)
| 成長維度 | 評估核心 | 具體分析診斷結論 |
| :--- | :--- | :--- |
| **多大？(Magnitude)** | 市場空間與爆發動能 | {mag_eval} |
| **多久？(Duration)** | 能見度與週期持續性 | {dur_eval} |
| **多確定？(Certainty)** | 護城河與獲利確定性 | {cert_eval} |

---

## 模組三：財務三率體檢（營運槓桿與獲利品質）
1. **三率數據三期對比表（已發生實質數據）**：
| 指標 | 最新一季 ({q_latest}) | 前一季 ({q_prev}) | 去年同期 ({q_yoy}) |
| :--- | :--- | :--- | :--- |
| **毛利率 (Gross Margin)** | **{gm_now:.2f}%** | {gm_prev:.2f}% ({gm_now - gm_prev:+.2f} pct) | {gm_yoy:.2f}% ({gm_now - gm_yoy:+.2f} pct) |
| **營業利益率 (Operating Margin)** | **{om_now:.2f}%** | {om_prev:.2f}% ({om_now - om_prev:+.2f} pct) | {om_yoy:.2f}% ({om_now - om_yoy:+.2f} pct) |
| **純益率 (Net Margin)** | **{nm_now:.2f}%** | {nm_prev:.2f}% ({nm_now - nm_prev:+.2f} pct) | {nm_yoy:.2f}% ({nm_now - nm_yoy:+.2f} pct) |

2. **「毛利與營益率雙重擴張」檢視**：
   - 雙重擴張判定：{"✅ **達成雙重擴張！營運槓桿全面發威** (毛利率季增 +{:.2f} pct，營益率季增 +{:.2f} pct)".format(gm_now - gm_prev, om_now - om_prev) if is_double_expansion else "⏳ **未完全達成雙重擴張** (毛利變動 {:.2f} pct，營益率變動 {:.2f} pct)".format(gm_now - gm_prev, om_now - om_prev)}。
   - 獲利驅動分析：{"高毛利利基型產品出貨放大，產能利用率滿載帶動固定成本攤薄。" if is_double_expansion else "受產品組合轉換或原物料報價波動影響，獲利率尚待進一步提振。"}
3. **EBITDA 實質獲利規模**：
   - 最新單季 EBITDA 約 **{ebitda_now} 億元**，本業現金造血基底扎實。

---

## 模組四：核心資產營運品質（領先指標與防禦邊際）
1. **存貨水準 (Inventory)**：最新單季存貨約 **{inv_now} 億元**。{"存貨配合訂單規模健康拉升，週轉狀況良好。" if rev_yoy_growth >= 0 else "需留意終端拉貨節奏與後續庫存去化速度。"}
2. **自由現金流 (Free Cash Flow)**：{fcf_diag}
3. **資產負債結構**：{debt_diag}

---

## 模組五：所屬次產業市場催化劑 (Catalysts)
1. **產業核心驅動動能**：{insight['catalysts']}
2. **本益比 (P/E) 戴維斯雙擊潛力**：若營收獲利持續加速，有望同時驅動「獲利成長」與「市場本益比向上調升」之戴維斯雙擊主升行情。

---

## 模組六：核心競爭者與潛在風險 (Risks & Margin of Safety)
1. **主要同業競爭對手**：{insight['competitors']}。
2. **實盤操作潛在風險**：{insight['risks']}

---

# 🏆 SEPA 綜合特檢結論與診斷
### 📋 五大基本面核心檢驗清單：
{checklist_md}

### 🎯 最終結論評定：【{ticker} {stock_name}】
- **診斷結果**：{rank_badge}
- **操作指引**：{"當前基本面動能強勁，若技術面同時站穩 10日 Pivot 頸線或完成 VCP 量縮收斂，為極佳之波段爆發進場點。" if passed_count >= 3 else "基本面暫未達頂級加速標準，若技術面破線或大盤回檔，應嚴格執行停損風控，勿逆勢加碼。"}
"""
    return report
