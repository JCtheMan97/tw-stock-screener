# -*- coding: utf-8 -*-
"""
cluster_analyzer.py
次族群聚類引擎 (Sector Clustering)
將符合「大波段蓄勢」之候選標的依照台股細分次產業進行聚合，
辨識出同族群 >= 2 檔同步吸籌之強勢共伴板塊。
"""
from collections import defaultdict
from config import MIN_CLUSTER_MEMBERS

def group_stocks_by_cluster(candidates):
    """
    將候選股票依據次族群分組，並計算族群共振強度
    參數:
      candidates: list of dict, 每個元素為通過篩選的個股完整指標
    回傳:
      clustered_groups: list of dict, 同族群 >= MIN_CLUSTER_MEMBERS 的強勢共振群組 (按強度排序)
      single_stocks: list of dict, 單一標的 (未形成 >=2 檔共振的潛力股)
    """
    sub_industry_map = defaultdict(list)

    for item in candidates:
        sub_name = item.get("sub_industry", "其他類股")
        sub_industry_map[sub_name].append(item)

    clustered_groups = []
    single_stocks = []

    for sub_name, members in sub_industry_map.items():
        if len(members) >= MIN_CLUSTER_MEMBERS:
            # 計算族群綜合統計指標
            total_foreign_buy = sum(m.get("foreign_cum_buy", 0) for m in members)
            avg_amplitude = round(sum(m.get("price_amplitude_20d", 0) for m in members) / len(members), 1)
            avg_big_holders = round(sum(m.get("pct_1000", 0) for m in members) / len(members), 1)

            # 群組內標的依照外資買超張數排序
            sorted_members = sorted(members, key=lambda x: x.get("foreign_cum_buy", 0), reverse=True)

            clustered_groups.append({
                "sub_industry": sub_name,
                "sector": members[0].get("sector", ""),
                "count": len(members),
                "total_foreign_buy": total_foreign_buy,
                "avg_amplitude": avg_amplitude,
                "avg_big_holders": avg_big_holders,
                "members": sorted_members
            })
        else:
            single_stocks.extend(members)

    # 族群共振組排序：符合檔數越多優先、其次外資波段累計買超總張數越大優先
    clustered_groups.sort(key=lambda g: (g["count"], g["total_foreign_buy"]), reverse=True)

    # 單兵股排序：按外資累計買超排序
    single_stocks.sort(key=lambda x: x.get("foreign_cum_buy", 0), reverse=True)

    return clustered_groups, single_stocks
