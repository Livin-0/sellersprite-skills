"""
sp_score.py
===========
SOP V3.1 STEP 7 · 六维综合评分与判档（全自动，零人工）
读取 raw/{mp}/* 数据 → 归一化 → 6 维自动打分 → 加权汇总 → 否决判定 → 写入 score/scoring.json

scoring.json 结构：
{
  "uk": {
    "direction": "D2",
    "raw_scores": { 6 个维度 1-5 },
    "weighted_breakdown": [(dim, score, weight, sub), ...],
    "weighted_total": 3.4,
    "tier": "T2",
    "veto_records": [...],
    "skill_25_breakout": {...},
    "summary_zh": "...",
    "raw_kpis": {...}
  },
  "fr": {...}
}

V3.1.1 调整：移除 supply_demand_median 中位数要求（用 data/config.json::directions 显式配置）。
"""
from __future__ import annotations
import os
import sys
import json
import statistics
from typing import Any
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)


# V3.1.1 · 移除 median_supply_demand 计算（供需比不再作为方向强判定输入）
# 方向判定直接读取 data/config.json::directions[mp]，避免 keyword_mine 数据缺失时返 0 错判。


def _extract_kw_trend_series(d: Any) -> list:
    """V3.1.1：从 keyword_research_trends.json 抽取"按月搜索量"序列。

    兼容 2 种 SellerSprite 格式：
    1. 聚合格式：items=[{keyword, searches:[...]}]
    2. 按月展开：items=[{time:"2025年09月", keywrod/keyword, search, ...}]

    返回按时间升序的整数列表（月搜索量）。
    """
    import re
    if not isinstance(d, dict) or d.get("_error"):
        return []
    # 兼容 _list_wrapped
    if isinstance(d, dict) and d.get("_list_wrapped"):
        items = d.get("items")
    else:
        items = d.get("items") if isinstance(d, dict) else d
    if not isinstance(items, list) or not items:
        return []
    first = items[0] if items and isinstance(items[0], dict) else {}
    # 聚合格式
    if isinstance(first.get("searches"), list):
        series = first.get("searches") or []
        return [v if isinstance(v, (int, float)) else 0 for v in series]
    # 按月展开格式
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        time_str = it.get("time") or it.get("month") or ""
        m = re.search(r"(\d{4})年(\d{1,2})月", str(time_str))
        if not m:
            continue
        y, mo = m.groups()
        key = (int(y), int(mo))
        v = it.get("search")
        out.append((key, v if isinstance(v, (int, float)) else 0))
    out.sort(key=lambda x: x[0])
    return [v for _, v in out]


def median_yoy_trend(mp: str) -> tuple:
    """用 keyword_research_trends 计算同比（中位月增长率）。"""
    d = sp.load_json(ROOT, f"raw/{mp}/keyword_research_trends.json")
    series = _extract_kw_trend_series(d)
    if len(series) < 2:
        return 0.0, 0.0
    # V3.1.1：分母为 0 时按 0 处理，避免 ZeroDivisionError
    if len(series) >= 13 and series[-13] > 0:
        yoy = (series[-1] - series[-13]) / series[-13] * 100
    else:
        yoy = 0
    if len(series) >= 2 and series[-2] > 0:
        mom = (series[-1] - series[-2]) / series[-2] * 100
    else:
        mom = 0
    return round(yoy, 2), round(mom, 2)


def skill_25_breakout(mp: str, keyword: str = "yoga mats") -> dict:
    """评估 Skill 25 季节破格：(下月-当月)/当月 > 100% 且 淡季同比 > 10%"""
    out = {"next_month_growth_pct": 0.0, "off_season_yoy_pct": 0.0, "applied": False}
    d = sp.load_json(ROOT, f"raw/{mp}/keyword_research_trends.json")
    series = _extract_kw_trend_series(d)
    if len(series) < 13:
        return out
    cur = series[-1] or 0
    nxt = series[-1] * 1.1  # 缺下月数据时按 1.1× 估算
    growth = ((nxt - cur) / cur * 100) if cur > 0 else 0
    yoy = (series[-1] - series[-13]) / series[-13] * 100 if series[-13] > 0 else 0
    out["next_month_growth_pct"] = round(growth, 2)
    out["off_season_yoy_pct"] = round(yoy, 2)
    out["applied"] = growth > 100 and yoy > 10
    return out


def compute_marketplace(mp: str) -> dict:
    print(f"\n=== Scoring {mp.upper()} ===")
    stats = sp.load_normalized(ROOT, mp, "market_research")
    brand = sp.load_normalized(ROOT, mp, "market_brand")
    product = sp.load_normalized(ROOT, mp, "market_product")
    price = sp.load_normalized(ROOT, mp, "market_price")
    listing = sp.load_normalized(ROOT, mp, "market_listing-date")
    rating = sp.load_normalized(ROOT, mp, "market_rating")
    demand = sp.load_normalized(ROOT, mp, "market_demand")

    # 从 market_research 抓同比/环比（如果有）
    raw_research = sp.load_json(ROOT, f"raw/{mp}/market_research.json")
    items = (raw_research.get("items") if isinstance(raw_research, dict)
             and raw_research.get("_list_wrapped") else raw_research)
    if isinstance(items, list) and items:
        first = items[0]
        # 用 l6NewRatio 推新品占比（如果 listing 没数据）
        if listing.get("newReleaseRatio", 0) == 0:
            listing["newReleaseRatio"] = first.get("l6NewRatio", 0) or 0

    # V3.1.1：方向判定直接读 data/config.json::directions[mp]，
    # 不再用 supply_demand_median 中位数（用户已移除该要求）。
    cfg = sp.load_config(ROOT)
    direction = (cfg.get("directions") or {}).get(mp) or "D2"

    # 同比 / 环比
    yoy_mom = median_yoy_trend(mp)
    yoy, mom = (yoy_mom if isinstance(yoy_mom, tuple) else (0.0, 0.0))
    stats["yoyTrendPct"] = yoy
    stats["monthlyTrendPct"] = mom
    stats["sampleSizeListings"] = stats.get("sampleSizeListings") or stats.get("activeAsinCount", 0)

    # 6 维自动打分
    raw_scores = sp.auto_score(stats, brand, product, price, listing, demand, rating)
    # 维度 6 = 4（无强制认证/专利，瑜伽垫为常见品类，假设 4 分）
    raw_scores["brand_compliance"] = {"score": 4, "reason": "瑜伽垫无强制认证，外观专利风险低", "label": "品牌与合规 / Compliance"}

    # 加权汇总
    total = sp.auto_total(raw_scores, direction, brand_compliance=4)

    # Skill 25 破格
    s25 = skill_25_breakout(mp)
    if s25["applied"] and total["tier"] != "T3":
        # 维度5 升 1 级
        old = raw_scores["demand_strength"]["score"]
        if old < 5:
            raw_scores["demand_strength"]["score"] = old + 1
            raw_scores["demand_strength"]["reason"] += f" · Skill25 破格升 1 级（原 {old}→{old+1}）"
            total = sp.auto_total(raw_scores, direction, brand_compliance=4)

    summary = _summary_zh(mp, direction, total, raw_scores, s25)

    result = {
        "direction": direction,
        "raw_scores": {k: v["score"] for k, v in raw_scores.items()},
        "raw_score_reasons": {k: v["reason"] for k, v in raw_scores.items()},
        "weighted_breakdown": total["weighted_breakdown"],
        "weighted_total": total["weighted_total"],
        "tier": total["tier"],
        "veto_records": total["veto_records"],
        "skill_25_breakout": s25,
        "summary_zh": summary,
        "raw_kpis": {
            "monthlyGmvUsd": stats.get("monthlyGmvUsd", 0),
            "activeAsinCount": stats.get("activeAsinCount", 0),
            "supplyDemandRatio": stats.get("supplyDemandRatio", 0),
            "averagePriceUsd": stats.get("averagePriceUsd", 0),
            "sampleSizeListings": stats.get("sampleSizeListings", 0),
            "yoyTrendPct": yoy,
            "monthlyTrendPct": mom,
        },
    }
    print(f"   direction={direction}, total={total['weighted_total']}, tier={total['tier']}")
    return result


def _summary_zh(mp: str, direction: str, total: dict,
                raw_scores: dict, s25: dict) -> str:
    tier_zh = {"T1": "必做", "T2": "可做（复议）", "T3": "放弃"}[total["tier"]]
    d1 = raw_scores["market_demand"]["score"]
    d2 = raw_scores["dispersion"]["score"]
    d3 = raw_scores["price"]["score"]
    d4 = raw_scores["new_opportunity"]["score"]
    d5 = raw_scores["demand_strength"]["score"]
    s25_str = " · 季节破格已应用" if s25.get("applied") else ""
    veto_str = " · " + " · ".join(total["veto_records"]) if total["veto_records"] else ""
    return (f"{mp.upper()} 站 {direction} 方向 · "
            f"六维 {d1}/{d2}/{d3}/{d4}/{d5} · 加权 {total['weighted_total']:.1f} → {total['tier']} {tier_zh}"
            f"{s25_str}{veto_str}")


def main() -> None:
    cfg = sp.load_config(ROOT)
    out = {}
    for mp in cfg["marketplaces"]:
        try:
            out[mp] = compute_marketplace(mp)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERROR] {mp}: {e}")
            out[mp] = {"direction": "D2", "tier": "T3", "weighted_total": 0,
                       "summary_zh": f"评分失败: {e}", "raw_scores": {},
                       "veto_records": [],
                       "skill_25_breakout": {}}
    p = os.path.join(ROOT, "score", "scoring.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[ok] {p}")


if __name__ == "__main__":
    main()
