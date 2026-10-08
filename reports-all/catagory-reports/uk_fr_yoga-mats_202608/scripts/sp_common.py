"""
sp_common.py
============
SOP V3.0 共享渲染工具：被 4 个主脚本 + 3 个后处理脚本共同引用。
约束：仅使用 Python 标准库（json / html / statistics / datetime）。
"""
from __future__ import annotations
import json
import html
import os
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional


# V3.1 · 站点白名单（防路径穿越 + 防错 marketplace code）
ALLOWED_MARKETPLACES = {"us", "jp", "uk", "de", "fr", "it", "es", "ca", "in", "mx"}


def _esc(s: Any) -> str:
    """V3.1 安全：HTML escape raw JSON 字段（niche/keyword/title/asin 等），防 XSS。"""
    if s is None:
        return "—"
    if not isinstance(s, str):
        s = str(s)
    return html.escape(s, quote=True)


def _validate_marketplace(mp: Any) -> str:
    """V3.1 安全：白名单校验 marketplace code，非法直接抛错（防止路径穿越/错码）。"""
    if not isinstance(mp, str):
        raise ValueError(f"marketplace must be string, got {type(mp).__name__}: {mp!r}")
    s = mp.strip().lower()
    if s not in ALLOWED_MARKETPLACES:
        raise ValueError(f"marketplace {mp!r} not in whitelist {sorted(ALLOWED_MARKETPLACES)}")
    return s


# ---------------------------------------------------------------------------
# 路径 / 配置
# ---------------------------------------------------------------------------
def load_config(project_root: str) -> Dict[str, Any]:
    with open(os.path.join(project_root, "data", "config.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_json(project_root: str, rel_path: str) -> Any:
    # V3.1 安全：防 rel_path 含 ../ 跳出项目根
    abs_path = os.path.abspath(os.path.join(project_root, rel_path))
    abs_root = os.path.abspath(project_root)
    if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
        raise ValueError(f"path traversal blocked: {rel_path!r} → {abs_path!r}")
    with open(abs_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _unwrap(d: Any) -> Any:
    """如果 d 是 {"items": [...], "_list_wrapped": True} 形式则解开为列表。"""
    if isinstance(d, dict) and d.get("_list_wrapped") and "items" in d:
        return d["items"]
    return d


# ---------------------------------------------------------------------------
# V3.1 · 数据归一化（把 SellerSprite CLI 实际响应映射到标准 schema）
# ---------------------------------------------------------------------------
STD_SCHEMA_DOC = {
    "stats":  ["monthlyGmvUsd", "monthlySearchVolume", "activeAsinCount",
               "supplyDemandRatio", "averagePriceUsd", "medianPriceUsd",
               "sampleSizeListings", "yoyTrendPct", "monthlyTrendPct"],
    "brand":  ["brandCr10", "brandCr5", "topBrands"],
    "product": ["productCr10", "productCr5", "topProducts"],
    "price":  ["medianPrice", "averagePrice", "buckets"],
    "listing": ["newReleaseRatio", "buckets"],
    "ebc":    ["ebcCoverage", "withEbc", "withoutEbc"],
    "rating": ["averageRating", "buckets"],
    "demand": ["monthlyGmvTrend"],
    "seller": ["chinaSellerRatio", "usSellerRatio", "otherSellerRatio"],
    "kw_research": ["keywords"],
    "kw_mine":  ["mined"],
}


def normalize_stats(d: Any) -> dict:
    d = d if isinstance(d, dict) else {}
    # 兼容 items[] 包装结构（market_research 返回 {items:[{...}]}）
    if isinstance(d.get("items"), list) and d.get("items"):
        src = d["items"][0]
    else:
        src = d
    products = (src.get("totalProducts") or src.get("products")
                or src.get("activeAsinCount") or 0)
    avg_revenue = (src.get("avgRevenue") or 0)
    avg_price = (src.get("avgPrice") or 0)
    total_monthly = (src.get("totalRevenue") or 0)
    return {
        "monthlyGmvUsd":       total_monthly if total_monthly else avg_revenue * products,
        "monthlySearchVolume": 0,  # SellerSprite 不直接返回站内搜索量
        "activeAsinCount":     products,
        "supplyDemandRatio":   (src.get("supplyDemandRatio") or 0),
        "averagePriceUsd":     avg_price,
        "medianPriceUsd":      (src.get("medianPrice") or avg_price),
        "sampleSizeListings":  (src.get("sampleSizeListings") or products),
        "yoyTrendPct":         (src.get("yoyTrendPct") or src.get("yoyGrowthPct") or 0),
        "monthlyTrendPct":     (src.get("monthlyTrendPct") or src.get("momGrowthPct") or 0),
        "_raw": d,
    }


def normalize_brand(d: Any) -> dict:
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    cr10 = sum(min(b.get("totalUnitsRatio") or b.get("totalRevenueRatio") or 0, 1.0)
               for b in items[:10]) if items else 0
    top = []
    for b in items[:10]:
        top.append({"brand": b.get("brand", "—"),
                    "share": b.get("totalRevenueRatio") or b.get("totalUnitsRatio") or 0,
                    "products": b.get("products", 0),
                    "totalUnits": b.get("totalUnits", 0),
                    "totalRevenue": b.get("totalRevenue", 0)})
    return {"brandCr10": round(cr10, 4), "brandCr5": round(sum((t["share"] for t in top[:5])), 4),
            "topBrands": top, "_raw": d}


def normalize_product(d: Any) -> dict:
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    cr10 = sum(min(p.get("totalUnitsRatio") or p.get("totalRevenueRatio") or 0, 1.0)
               for p in items[:10]) if items else 0
    top = []
    for p in items[:10]:
        top.append({"asin": p.get("asin", "—"),
                    "brand": p.get("brand", "—"),
                    "monthlySales": p.get("totalUnits", 0),
                    "share": p.get("totalUnitsRatio") or p.get("totalRevenueRatio") or 0,
                    "rating": p.get("rating", 0),
                    "price": p.get("price", 0),
                    "shelfDate": p.get("shelfDate", "")})
    return {"productCr10": round(cr10, 4), "topProducts": top, "_raw": d}


def normalize_price(d: Any) -> dict:
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    if not items:
        return {"medianPrice": 0, "averagePrice": 0, "buckets": []}
    avg = sum(((int(b["label"].split("-")[0]) if b["label"].split("-")[0].isdigit()
                else 5) + (int(b["label"].split("-")[1]) if "-" in b["label"] and b["label"].split("-")[1].isdigit() else 0)) / 2
              * (b.get("unitsRatio", 0)) for b in items)
    avg_price = sum((b.get("avgPrice", 0) or 0) for b in items) / len(items)
    buckets = [{"range": f"${b.get('label', '?')}" + (
                  "+" if "以上" in b.get("label", "") else ""),
                "share": b.get("unitsRatio", 0),
                "asinCount": b.get("products", 0)} for b in items]
    return {"medianPrice": round(avg, 2), "averagePrice": round(avg_price, 2),
            "buckets": buckets, "_raw": d}


def normalize_listing(d: Any) -> dict:
    """上架时间分布 → 估算 newReleaseRatio（近 6 月新品占比）"""
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    new_ratio = 0
    for b in items[:3]:  # 前 3 个 bucket 一般是 < 3m / 3-6m / 6-12m
        new_ratio += b.get("unitsRatio", b.get("products", 0) /
                           max(1, sum(x.get("products", 0) for x in items)))
    return {"newReleaseRatio": round(new_ratio, 4),
            "buckets": [{"range": b.get("label", "?"),
                         "share": b.get("unitsRatio", 0),
                         "asinCount": b.get("products", 0)} for b in items],
            "_raw": d}


def normalize_ebc(d: Any) -> dict:
    d = d if isinstance(d, dict) else {}
    if "ebcCoverage" in d or "withEbc" in d:
        return d
    # 兼容：某些响应是 boolean 字段
    return {"ebcCoverage": d.get("ebcCoverage", 0.6), "withEbc": d.get("withEbc", 0),
            "withoutEbc": d.get("withoutEbc", 0), "_raw": d}


def normalize_rating(d: Any) -> dict:
    d = d if isinstance(d, dict) else {}  # V3.1 安全：NoneType 防御
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    avg = sum(b.get("avgRating", 0) * (b.get("unitsRatio", 0)) for b in items) if items else 0
    return {"averageRating": round(d.get("avgRating", 0) or avg, 2),
            "buckets": [{"range": b.get("label", "?"),
                         "share": b.get("unitsRatio", 0),
                         "asinCount": b.get("products", 0)} for b in items],
            "_raw": d}


def normalize_seller_country(d: Any) -> dict:
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    china = us = other = 0
    for s in items:
        c = (s.get("country") or s.get("countryCode") or "").upper()
        share = s.get("unitsRatio", s.get("productsRatio", 0)) or 0
        if c in ("CN", "中国"):
            china += share
        elif c in ("US", "USA", "GB", "UK", "FR", "DE", "JP"):
            us += share
        else:
            other += share
    s = max(1.0, china + us + other)
    return {"chinaSellerRatio": round(china/s, 4), "usSellerRatio": round(us/s, 4),
            "otherSellerRatio": round(other/s, 4), "_raw": d}


def normalize_demand(d: Any) -> dict:
    d = d if isinstance(d, dict) else {}
    return {"monthlyGmvTrend": d.get("monthlyGmvTrend", []), "_raw": d}


def normalize_keyword_research(d: Any) -> dict:
    items = _unwrap(d) or []
    items = items if isinstance(items, list) else []
    out = []
    for k in items:
        # V3.1 fix: 实际响应里 keyword 字段叫 "keywords"（复数，因为接口支持一次查多词）
        kw = (k.get("keywords") or k.get("keyword") or k.get("phrase") or "—")
        if isinstance(kw, list):
            kw = kw[0] if kw else "—"
        # 搜索量：searches > searchVolume > search > monthlySearch
        search = (k.get("searches") or k.get("searchVolume")
                  or k.get("search") or k.get("monthlySearch") or 0)
        products = (k.get("products") or k.get("asinCount") or 0)
        # supplyDemandRatio：优先取接口返回值，否则按"月搜索量/月活跃ASIN"计算
        sdr = k.get("supplyDemandRatio")
        if sdr is None or sdr == 0:
            sdr = search / max(1, products) if search else 0
        # V3.1 fix: 字段实际是 titleDensityExact，titleDensity 是泛指
        title_density = (k.get("titleDensityExact") or k.get("titleDensity") or 0)
        out.append({"keyword": kw,
                    "keywordCn": k.get("keywordCn", ""),
                    "search": search,
                    "purchases": (k.get("purchases") or k.get("purchaseVolume") or 0),
                    "asinCount": products,
                    "supplyDemandRatio": round(sdr, 2),
                    "titleDensity": title_density,
                    "purchasesRate": (k.get("purchaseRate") or k.get("purchasesRate") or 0),
                    "monthlyTrend": k.get("growth", 0),
                    "hasBrandWord": k.get("hasBrandWord", False),
                    "marketplace": k.get("marketplace", "")})
    return {"keywords": out, "_raw": d}


def normalize_keyword_mine(d: Any) -> dict:
    items = d.get("items") if isinstance(d, dict) else d
    items = items if isinstance(items, list) else []
    out = []
    for k in items:
        search = (k.get("searches") or k.get("searchVolume")
                  or k.get("search") or 0)
        asin_count = (k.get("products") or k.get("asinCount") or 0)
        out.append({"keyword": k.get("keyword") or k.get("phrase", "—"),
                    "keywordCn": k.get("keywordCn") or "",
                    "search": search,
                    "purchases": k.get("purchases") or k.get("purchaseVolume") or 0,
                    "asinCount": asin_count,
                    "supplyDemandRatio": (k.get("supplyDemandRatio") or
                                          (search / max(1, asin_count))),
                    "titleDensity": k.get("titleDensity", 0),
                    "monopolyClickRate": k.get("monopolyClickRate", 0),
                    "purchasesRate": k.get("purchaseRate") or k.get("purchasesRate") or 0})
    return {"mined": out, "_raw": d}


def normalize_review(d: dict) -> dict:
    """trend_review 返回结构可能是 {"reviews":[...]} 或直接列表。"""
    if isinstance(d, dict) and "reviews" in d:
        return d
    if isinstance(d, list):
        return {"reviews": d}
    return {"reviews": []}


def normalize_competitor(d: Any) -> dict:
    items = d.get("items") or d.get("competitors") if isinstance(d, dict) else d
    items = items if isinstance(items, list) else []
    out = []
    seen_asins = set()  # V3.1 fix: 同一父体变体 (B09339/B0B9Y/B0FY2ZPB3D = 同一产品) 去重
    for c in items:
        asin = c.get("asin", "—")
        # V3.1 fix: 数据真实性校验 — 价格<=0 或标题为空的视为无效 ASIN
        price = c.get("price") or c.get("priceUsd") or 0
        title = c.get("title", "—") or "—"
        valid = bool(asin and asin != "—" and price > 0 and title != "—")
        # V3.1 fix: 月销字段实际是 amzUnit（amzUnit 才是有效月销）
        monthly_sales = c.get("amzUnit") or c.get("monthlySold") or c.get("units") or 0
        # V3.1 fix: 毛利率实际由 profit 字段反推（profit=净利润），若 profit<0则毛利很低
        profit = c.get("profit") or 0
        est_margin = (c.get("estimatedMarginPct")
                      or (profit / price if price > 0 else 0))
        out.append({"asin": asin,
                    "title": title,
                    "brand": c.get("brand", "—"),
                    "priceUsd": price,
                    "estimatedCostUsd": c.get("estimatedCostUsd") or max(0, price - profit),
                    "estimatedMarginPct": max(0, min(1, est_margin)),
                    "fbaFeeUsd": c.get("fbaFeeUsd") or c.get("fba") or 0,
                    "monthlySales": monthly_sales if valid else 0,
                    "rating": c.get("rating", 0),
                    "lqs": c.get("lqs", 0),
                    "valid": valid,
                    "invalidReason": (None if valid else
                                      ("价格缺失" if price <= 0 else
                                       "标题缺失" if not title or title == "—" else "ASIN 缺失")),
                    "dedupSkip": asin in seen_asins})
        if valid:
            seen_asins.add(asin)
    return {"competitors": out}


def normalize_google_trend(d: Any) -> dict:
    if isinstance(d, dict) and "trends" in d:
        return d
    if isinstance(d, list):
        return {"trends": d, "_list_wrapped": True}
    return {"trends": []}


# 工具名 → 归一化函数
NORMALIZERS = {
    "market_research":  normalize_stats,
    "market_stats":     normalize_stats,
    "market_brand":     normalize_brand,
    "market_product":   normalize_product,
    "market_price":     normalize_price,
    "market_listing-date": normalize_listing,
    "market_ebc":       normalize_ebc,
    "market_rating":    normalize_rating,
    "market_seller-country": normalize_seller_country,
    "market_demand":    normalize_demand,
    "keyword_research": normalize_keyword_research,
    "keyword_mine":     normalize_keyword_mine,
    "google_trend":     normalize_google_trend,
    "competitor_lookup": normalize_competitor,
    "review":           normalize_review,
}


def load_normalized(project_root: str, mp: str, tool_key: str) -> Any:
    """读取并归一化 SellerSprite 响应。V3.1 加了 marketplace 白名单。"""
    safe_mp = _validate_marketplace(mp)
    p = os.path.join(project_root, "raw", safe_mp, f"{tool_key}.json")
    if not os.path.exists(p):
        return {}
    d = load_json(project_root, os.path.relpath(p, project_root))
    fn = NORMALIZERS.get(tool_key)
    return fn(d) if fn else d


def write_html(project_root: str, rel_path: str, html_text: str) -> str:
    abs_path = os.path.join(project_root, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(html_text)
    return abs_path


# ---------------------------------------------------------------------------
# 通用 HTML 片段
# ---------------------------------------------------------------------------
MARKETPLACE_NAME = {"US": "美国站", "JP": "日本站", "UK": "英国站", "DE": "德国站",
                    "FR": "法国站", "IT": "意大利站", "ES": "西班牙站", "CA": "加拿大站",
                    "IN": "印度站", "MX": "墨西哥站"}

# V3.1 调色板（10 国站点 palette + 中性色）
SITE_PALETTE = {
    "US": "#4F46E5",  # Indigo
    "JP": "#EC4899",  # Blossom
    "UK": "#2E7D32",  # Forest
    "DE": "#E11D48",  # Coral
    "FR": "#1D4ED8",  # French Blue
    "IT": "#CA8A04",  # Mustard
    "ES": "#7C3AED",  # Mauve
    "CA": "#B45309",  # Maple
    "IN": "#F59E0B",  # Saffron
    "MX": "#15803D",  # Cactus
}

FLAG_EMOJI = {
    "US": "🇺🇸", "JP": "🇯🇵", "UK": "🇬🇧", "DE": "🇩🇪", "FR": "🇫🇷",
    "IT": "🇮🇹", "ES": "🇪🇸", "CA": "🇨🇦", "IN": "🇮🇳", "MX": "🇲🇽",
}


def flag_emoji(mp: str) -> str:
    return FLAG_EMOJI.get(mp.upper(), "🌐")


def site_color(mp: str) -> str:
    return SITE_PALETTE.get(mp.upper(), "#565959")


def topbar(active: str = "", niche: str = "Yoga Mats", brand: str = "LIVIN.COM",
           marketplaces: list = None, current_mp: str = "") -> str:
    """V3.1 顶栏 · 按 marketplaces 动态生成所有子页链接。

    强制约束（README v3.1 STEP 8）：
      - 「季节性 / 用户需求 / 关键词机会」3 个二级入口的链接必须按 marketplaces
        列表动态生成，禁止硬编码 us_*.html。
      - 站级页（season / needs / kw）按当前站 mp 渲染，下拉里展示其他站。
      - overview 模式（总览页）下「用户需求 / 关键词机会」必须展开为多站下拉，
        保证 fr_needs.html / fr_kwneeds.html 等所有子页链接出现在 index.html 顶栏。
    """
    mps = marketplaces or []
    # 默认主站 = 第一个站点（占位时为 US）
    primary = (mps[0] if mps else "US").lower()
    # 站级页使用的目标站
    target = (current_mp or primary).lower() if active != "overview" else primary

    # 站点下拉：把全部站点列出来，悬停展开
    site_dropdown = ""
    if mps:
        items = "".join(
            f'<a href="{m.lower()}.html">{flag_emoji(m)} {m.upper()} {MARKETPLACE_NAME.get(m.upper(),"")}</a>'
            for m in mps
        )
        site_dropdown = (
            '<span class="sp-topbar-dropdown">'
            f'<a class="sp-topbar-mp" href="{primary}.html">站点分析 ▾</a>'
            f'<span class="sp-topbar-dropdown-menu">{items}</span>'
            '</span>'
        )

    # V3.1 强制：所有二级页链接按当前站动态生成，不再硬编码 us_*.html
    if active == "overview":
        # 总览页：季节性锚点；用户需求 / 关键词机会 → 多站下拉
        season_href = "index.html#gtrend"
        season_active = ""
        if mps and len(mps) > 1:
            # 多站：把"用户需求""关键词机会"做成 dropdown，包含所有站子页
            needs_items = "".join(
                f'<a href="{m.lower()}_needs.html">{flag_emoji(m)} {m.upper()} 用户需求</a>'
                for m in mps
            )
            kw_items = "".join(
                f'<a href="{m.lower()}_kwneeds.html">{flag_emoji(m)} {m.upper()} 关键词</a>'
                for m in mps
            )
            needs_dd = (
                '<span class="sp-topbar-dropdown">'
                f'<a class="sp-topbar-mp" href="{primary}_needs.html">用户需求 ▾</a>'
                f'<span class="sp-topbar-dropdown-menu">{needs_items}</span>'
                '</span>'
            )
            kw_dd = (
                '<span class="sp-topbar-dropdown">'
                f'<a class="sp-topbar-mp" href="{primary}_kwneeds.html">关键词机会 ▾</a>'
                f'<span class="sp-topbar-dropdown-menu">{kw_items}</span>'
                '</span>'
            )
        else:
            # 单站：直接跳
            needs_dd = f'<a href="{primary}_needs.html">用户需求</a>'
            kw_dd = f'<a href="{primary}_kwneeds.html">关键词机会</a>'
    else:
        season_href = f"{target}_seasonality.html"
        season_active = "is-active" if active == "season" else ""
        needs_dd = f"<a href='{target}_needs.html' class='{('is-active' if active=='needs' else '')}'>用户需求</a>"
        kw_dd = f"<a href='{target}_kwneeds.html' class='{('is-active' if active=='kw' else '')}'>关键词机会</a>"

    overview_active = "is-active" if active == "overview" else ""
    report_active = "is-active" if active == "report" else ""
    # V3.1.1：选品报告链接（站级，非 overview）
    report_link = ""
    if active != "overview" and active != "report":
        report_link = f"<a href='{target}_report.html' class='{('is-active' if active=='report' else '')}'>选品报告</a>"
    elif active == "report":
        report_link = f"<a href='{target}_report.html' class='{report_active}'>选品报告</a>"
    return f"""
    <header class="sp-topbar">
      <div class="sp-topbar-inner">
        <a class="sp-brand" href="index.html">
          <span class="sp-brand-mark"></span>
          <span class="sp-brand-name">{html.escape(brand)}</span>
        </a>
        <span class="sp-topbar-divider">|</span>
        <span class="sp-topbar-niche">选品报告 · {html.escape(niche)}</span>
        <nav class="sp-topbar-nav">
          <a href="index.html" class="{overview_active}">总览</a>
          {site_dropdown}
          <a href="{season_href}" class="{season_active}">季节性</a>
          {needs_dd}
          {kw_dd}
          {report_link}
        </nav>
        <span class="sp-topbar-meta">SOP V3.1 · {datetime.now().strftime('%Y-%m-%d')}</span>
      </div>
    </header>
    """


def style_block() -> str:
    return """
    <style>
      :root{
        /* V3.1 调色板：README 强制规范 */
        --topbar-bg:#0A1A2F;
        --brand-yellow:#FCD34D;
        --link:#2A7DE1;
        --price:#D97A2E;
        --cta:#FCD34D;
        --bg:#F8FAFC;
        --card:#FFFFFF;
        --ink:#0F172A;
        --muted:#475569;
        --border:#E2E8F0;
        --good:#16A34A;
        --bad:#DC2626;
        --warn:#F59E0B;
        --tier1:#16A34A;
        --tier2:#F59E0B;
        --tier3:#DC2626;
        /* 10 国 palette */
        --mp-US:#4F46E5; --mp-JP:#EC4899; --mp-UK:#2E7D32; --mp-DE:#E11D48;
        --mp-FR:#1D4ED8; --mp-IT:#CA8A04; --mp-ES:#7C3AED; --mp-CA:#B45309;
        --mp-IN:#F59E0B; --mp-MX:#15803D;
        --font-display:'Inter Display',Inter,'Helvetica Neue',Helvetica,Arial,sans-serif;
        --font-body:Inter,'Helvetica Neue',Helvetica,Arial,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        --font-mono:'JetBrains Mono','SF Mono',Consolas,Menlo,monospace;
      }
      *{box-sizing:border-box}
      html,body{margin:0;padding:0;background:var(--bg);color:var(--ink);
        font-family:var(--font-body);font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}
      a{color:var(--link);text-decoration:none} a:hover{text-decoration:underline}
      .sp-topbar{background:var(--topbar-bg);color:#fff;padding:10px 20px;font-family:var(--font-display);
        position:sticky;top:0;z-index:50;border-bottom:2px solid var(--brand-yellow)}
      .sp-topbar-inner{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
      .sp-brand{display:flex;align-items:center;gap:8px;color:#fff;font-weight:700;font-size:15px}
      .sp-brand-mark{width:14px;height:14px;background:var(--brand-yellow);border-radius:2px;display:inline-block;
        box-shadow:0 0 0 2px var(--topbar-bg), 0 0 0 4px var(--brand-yellow)}
      .sp-brand-name{color:var(--brand-yellow);letter-spacing:.5px}
      .sp-topbar-divider{color:#3a4553}
      .sp-topbar-niche{color:#d5d9dd;font-size:13px}
      .sp-topbar-nav{display:flex;gap:14px;margin-left:auto;flex-wrap:wrap;align-items:center}
      .sp-topbar-nav a{color:#fff;padding:4px 8px;border-radius:6px;font-size:13px}
      .sp-topbar-nav a:hover{background:#232f3e;text-decoration:none}
      .sp-topbar-nav a.is-active{background:#37475a}
      .sp-topbar-meta{color:#9aa3ad;font-size:12px;font-family:var(--font-mono)}
      .sp-topbar-dropdown{position:relative;display:inline-block}
      .sp-topbar-dropdown .sp-topbar-mp{color:#fff;padding:4px 8px;border-radius:6px;font-size:13px;cursor:pointer}
      .sp-topbar-dropdown .sp-topbar-mp:hover{background:#232f3e}
      .sp-topbar-dropdown-menu{display:none;position:absolute;right:0;top:100%;background:#fff;
        border:1px solid var(--border);border-radius:8px;min-width:200px;padding:6px;box-shadow:0 8px 24px rgba(0,0,0,.15);z-index:60}
      .sp-topbar-dropdown:hover .sp-topbar-dropdown-menu{display:flex;flex-direction:column;gap:2px}
      .sp-topbar-dropdown-menu a{color:var(--ink)!important;padding:6px 10px;border-radius:4px;font-size:13px}
      .sp-topbar-dropdown-menu a:hover{background:#f1f5f9;text-decoration:none}

      section{padding:48px 20px}
      section.alt-bg{background:#f2f4f6}
      .wrap{max-width:1180px;margin:0 auto}
      h1,h2,h3{font-family:var(--font-display);margin:0 0 12px}
      h1{font-size:30px;font-weight:700;letter-spacing:-.01em}
      h2{font-size:22px;margin-top:0}
      h3{font-size:18px;font-weight:600}
      .sp-muted{color:var(--muted)}
      .brand-orange{color:var(--price)}
      .mono{font-family:var(--font-mono)}

      .hero{background:linear-gradient(135deg,#0A1A2F 0%,#163E73 100%);color:#fff;padding:56px 20px 48px;
        border-bottom:1px solid var(--border)}
      .hero-eyebrow{font-size:13px;font-weight:600;color:var(--brand-yellow);letter-spacing:.3px;margin-bottom:6px}
      .hero h1{margin:0 0 8px;color:#fff}
      .hero-sub{font-size:17px;color:#cbd5e1;max-width:780px;margin:0 0 18px}
      .hero-chips{display:flex;flex-wrap:wrap;gap:10px}
      .chip{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);padding:4px 14px;
        border-radius:20px;font-size:13px;color:#fff}
      .chip strong{font-weight:600;color:var(--brand-yellow)}

      .site-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}
      .site-card{background:var(--card);border:1px solid var(--border);border-radius:10px;
        padding:20px;transition:box-shadow .15s, transform .15s;display:block;color:inherit;
        position:relative;overflow:hidden}
      .site-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);transform:translateY(-2px);text-decoration:none}
      .site-card-bar{position:absolute;top:0;left:0;right:0;height:3px;background:var(--mp-color,var(--link))}
      .site-card-h{display:flex;align-items:center;gap:12px;margin-bottom:14px}
      .site-flag{font-size:32px;line-height:1}
      .site-card-title{flex:1;min-width:0}
      .site-name{font-size:18px;font-weight:700;color:var(--ink)}
      .site-domain{font-size:12px;color:var(--muted);font-family:var(--font-mono)}
      .site-metrics{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}
      .site-metric{background:#f7f8fa;border-radius:6px;padding:6px 10px;display:flex;flex-direction:column}
      .site-metric-label{font-size:11px;color:var(--muted);letter-spacing:.3px}
      .site-metric-value{font-weight:700;font-size:16px;color:var(--ink);font-family:var(--font-mono)}
      .site-metric-wide{grid-column:1 / -1;background:#eef3f8;border:1px dashed #cbd5e1}
      .site-best{font-size:14px;border-top:1px solid var(--border);padding-top:12px;margin-top:4px;color:var(--muted)}
      .site-best strong{color:var(--ink)}
      .site-best .score{float:right;font-weight:700;color:var(--price);font-family:var(--font-mono);font-size:16px}

      .metric-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px}
      .metric-card{background:var(--card);border:1px solid var(--border);border-radius:10px;
        padding:16px 18px;text-align:center}
      .metric-name{font-size:13px;font-weight:600;margin-bottom:2px}
      .metric-cat{font-size:11px;color:var(--muted);margin-bottom:6px}
      /* V3.1.1 · cnstudio 风格 stat card（细切画像 8 卡用） */
      .cn-stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:0 0 20px}
      .metric-card.cn-stat{text-align:left;padding:14px 16px}
      .metric-val-lg{font-family:var(--font-mono);font-size:20px;font-weight:700;color:var(--ink);
        margin:6px 0;line-height:1.2}
      .metric-val-lg .sub{font-size:12px;color:var(--muted);font-weight:400;margin-left:4px}
      .metric-src{font-size:10.5px;color:var(--muted);font-family:var(--font-mono);border-top:1px dashed var(--border);
        padding-top:6px;margin-top:4px}

      .charts-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
      @media (max-width:800px){.charts-grid{grid-template-columns:1fr}}
      .chart-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px}
      .chart-card h4{margin:0 0 12px;font-family:var(--font-display);font-weight:600;font-size:15px}
      .chart-card .chart-src{font-size:11px;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px dashed var(--border)}
      canvas.sp-chart{max-height:320px;max-width:100%}

      .score-card{background:var(--card);border:1px solid var(--border);border-radius:10px;
        padding:24px;display:grid;grid-template-columns:220px 1fr;gap:24px}
      @media (max-width:700px){.score-card{grid-template-columns:1fr}}
      .score-display{text-align:center;padding:8px 0}
      .score-big{font-size:60px;font-weight:700;font-family:var(--font-mono);
        line-height:1;letter-spacing:-.02em;margin-bottom:8px}
      .score-big.tier-t1{color:var(--tier1)}
      .score-big.tier-t2{color:var(--tier2)}
      .score-big.tier-t3{color:var(--tier3)}
      .score-meta{display:flex;flex-direction:column;align-items:center;gap:4px}
      .score-label{font-size:13px;color:var(--muted)}
      .dim-breakdown{min-width:0}
      .dim-breakdown-h{font-size:13px;font-weight:600;margin-bottom:10px;color:var(--muted)}
      .dim-row{display:grid;grid-template-columns:120px 1fr 50px;align-items:center;gap:10px;padding:6px 0;
        cursor:help;position:relative}
      .dim-row-name{font-size:13px;font-weight:500;line-height:1.3}
      .dim-row-en{font-weight:400;color:var(--muted);font-size:11px}
      .dim-row-track{height:8px;background:#eef0f2;border-radius:4px;overflow:hidden}
      .dim-row-fill{height:100%;border-radius:4px;transition:width .2s}
      .dim-row-fill.high{background:var(--tier1)}
      .dim-row-fill.mid{background:var(--tier2)}
      .dim-row-fill.low{background:var(--tier3)}
      .dim-row-score{font-family:var(--font-mono);text-align:right;font-size:18px;font-weight:700}
      .dim-row-score .max{font-size:13px;color:var(--muted);font-weight:400}
      .dim-row:hover .dim-anno{display:block}
      .dim-anno{display:none;position:absolute;left:130px;top:24px;background:#0F172A;color:#fff;
        padding:8px 12px;border-radius:6px;font-size:12px;line-height:1.5;z-index:30;max-width:300px;
        box-shadow:0 4px 12px rgba(0,0,0,.2);font-family:var(--font-body);white-space:pre-line}
      .dim-anno::before{content:"";position:absolute;left:-4px;top:6px;width:0;height:0;
        border:4px solid transparent;border-right-color:#0F172A}

      .skill25-card{background:#f4f7fa;border:1px solid var(--border);border-radius:10px;
        padding:16px 20px;margin-top:16px}
      .skill25-header{font-weight:700;font-size:15px;margin-bottom:10px}
      .skill25-grid{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
      @media (max-width:600px){.skill25-grid{grid-template-columns:1fr}}
      .skill25-item{background:var(--card);padding:8px 12px;border-radius:6px}
      .skill25-label{display:block;font-size:11px;color:var(--muted);letter-spacing:.3px}
      .skill25-value{font-weight:700;font-size:16px;font-family:var(--font-mono)}
      .skill25-check{font-size:13px;margin-left:8px;color:var(--muted)}
      .skill25-result .skill25-value{color:var(--price)}

      .matrix-wrap{overflow-x:auto;border-radius:10px;border:1px solid var(--border)}
      .matrix{width:100%;border-collapse:collapse;font-size:13px;background:var(--card)}
      .matrix th,.matrix td{padding:8px 12px;border:1px solid var(--border);text-align:left;vertical-align:top}
      .matrix th{background:#f0f3f7;font-weight:600;color:var(--muted);font-family:var(--font-display)}
      .matrix .row-h{background:#f9fafb;font-weight:600;text-align:center;white-space:nowrap}
      .matrix .warn{color:var(--bad);font-weight:600}
      .matrix .muted{color:var(--muted);font-weight:400}
      .matrix .mono{font-family:var(--font-mono);font-size:12px}
      .matrix .price{color:var(--price);font-family:var(--font-mono);font-weight:600}
      .matrix .tier-1{background:#dcfce7;color:#15803d;font-weight:700}
      .matrix .tier-2{background:#fef3c7;color:#92400e;font-weight:700}
      .matrix .tier-3{background:#fee2e2;color:#991b1b;font-weight:700}

      .tier-badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:12px;font-weight:700}
      .tier-badge.t1{background:#dcfce7;color:#15803d}
      .tier-badge.t2{background:#fef3c7;color:#92400e}
      .tier-badge.t3{background:#fee2e2;color:#991b1b}

      .period-chip{display:inline-flex;align-items:center;gap:6px;background:#f1f5f9;
        border:1px solid var(--border);border-radius:20px;padding:4px 12px;font-size:12px;color:var(--muted);
        font-family:var(--font-mono);margin-bottom:12px}

      .matrix-cell{display:flex;flex-direction:column;align-items:flex-start;gap:2px;padding:6px 8px;
        border-radius:6px;font-size:12px}
      .matrix-cell .score{font-size:18px;font-weight:700;font-family:var(--font-mono);line-height:1.1}
      .matrix-cell .sub{font-size:11px;color:var(--muted)}
      .matrix-cell .metric-line{font-size:11px;color:var(--ink);font-family:var(--font-mono)}

      .risk-list{display:grid;gap:8px;margin-top:12px}
      .risk-item{background:#fef2f2;border-left:3px solid var(--bad);padding:10px 14px;border-radius:0 6px 6px 0;font-size:13.5px}
      .risk-item b{color:var(--bad)}

      .medal-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:12px}
      @media (max-width:900px){.medal-grid{grid-template-columns:1fr}}
      .medal-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:20px;
        position:relative;display:block;color:inherit}
      .medal-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);text-decoration:none;transform:translateY(-2px)}
      .medal-rank{position:absolute;top:-12px;left:20px;width:36px;height:36px;border-radius:50%;
        background:var(--brand-yellow);color:#0F172A;font-weight:700;font-size:18px;
        display:flex;align-items:center;justify-content:center;border:3px solid var(--card);
        font-family:var(--font-display)}
      .medal-card h4{margin:8px 0 6px;font-size:16px}
      .medal-meta{font-size:13px;color:var(--muted);margin-bottom:8px}
      .medal-metrics{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:10px}
      .medal-metric{background:#f7f8fa;padding:6px 10px;border-radius:6px;font-size:12px}
      .medal-metric .v{font-weight:700;font-family:var(--font-mono);color:var(--ink)}

      .about-section{background:#f1f5f9;border:1px solid var(--border);border-radius:10px;padding:24px;
        margin-top:32px}
      .about-section p{margin:6px 0;font-size:14px}
      .about-meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-top:10px}
      .about-meta-item{background:#fff;padding:8px 12px;border-radius:6px;font-size:13px}
      .about-meta-item b{display:block;color:var(--muted);font-size:11px;letter-spacing:.3px;margin-bottom:2px}
      .about-meta-item span{color:var(--ink);font-weight:600;font-family:var(--font-mono)}

      .sp-footer{background:#f5f5f5;border-top:1px solid var(--border);font-size:0.9em;color:var(--muted);
        margin-top:48px;padding:24px 20px}
      .sp-footer-inner{max-width:1180px;margin:0 auto;display:grid;
        grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:24px}
      .sp-footer-block h5{font-size:13px;color:var(--ink);font-weight:600;margin:0 0 8px;font-family:var(--font-display)}
      .sp-footer-block p, .sp-footer-block li{font-size:12.5px;line-height:1.6;margin:2px 0}
      .sp-footer-block ul{list-style:none;padding:0;margin:0}
      .sp-footer-block a{color:var(--link)}
      .sp-footer-block .data-table{width:100%;font-size:12px}
      .sp-footer-block .data-table td{padding:3px 6px;border-bottom:1px dashed var(--border)}
      .sp-footer-block .data-table td:first-child{color:var(--muted);width:50%}

      .sp-card{background:var(--card);border:1px solid var(--border);border-radius:10px;padding:18px;margin-bottom:16px}
      .sp-grid{display:grid;gap:16px}
      .sp-grid-3{grid-template-columns:repeat(3,1fr)}
      .sp-grid-4{grid-template-columns:repeat(4,1fr)}
      .sp-grid-2{grid-template-columns:repeat(2,1fr)}
      @media (max-width:1100px){.sp-grid-4{grid-template-columns:repeat(3,1fr)}}
      @media (max-width:900px){.sp-grid-3,.sp-grid-4{grid-template-columns:repeat(2,1fr)}.sp-grid-2{grid-template-columns:1fr}}
      @media (max-width:640px){.sp-grid-3,.sp-grid-4{grid-template-columns:1fr}}
      @media (max-width:380px){.sp-topbar-nav{gap:6px}.sp-topbar-nav a{font-size:12px;padding:3px 6px}}
      .sp-kpi{font-family:var(--font-mono);font-size:24px;color:var(--price);font-weight:600}
      .sp-kpi-label{font-size:12px;color:var(--muted);letter-spacing:.5px}
      .sp-tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:600;
        background:#eef3f8;color:#0f1111;margin-right:6px}
      .sp-tag.t1{background:#dcfce7;color:#15803d}
      .sp-tag.t2{background:#fef3c7;color:#92400e}
      .sp-tag.t3{background:#fee2e2;color:#991b1b}
      .sp-tag.skill{background:#ede9fe;color:#5b21b6}
      .sp-cta{display:inline-block;background:var(--cta);color:#0F172A;font-weight:700;
        padding:8px 14px;border-radius:6px;border:1px solid #fcd200;cursor:pointer;font-size:13px}
      .sp-cta:hover{background:#f7ca00;text-decoration:none}
      .sp-link{color:var(--link)}
      .sp-price{color:var(--price);font-family:var(--font-mono);font-weight:600}
      .sp-mono{font-family:var(--font-mono)}
      .sp-good{color:var(--good)} .sp-bad{color:var(--bad)}
      .sp-footnote{font-size:12px;color:var(--muted);border-top:1px solid var(--border);
        margin-top:32px;padding:14px 20px;font-family:var(--font-mono);background:var(--bg);text-align:center}
      .sp-skill-callout{background:#f5f3ff;border-left:4px solid #7c3aed;
        padding:10px 14px;border-radius:0 6px 6px 0;margin:10px 0;font-size:13px}
      .sp-skill-callout strong{color:#5b21b6}
      .sp-t1{background:linear-gradient(135deg,#dcfce7,#fff);border-color:#86efac}
      .sp-t2{background:linear-gradient(135deg,#fef3c7,#fff);border-color:#fcd34d}
      .sp-t3{background:linear-gradient(135deg,#fee2e2,#fff);border-color:#fca5a5}

      .sec-head{margin-bottom:18px;display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}
      .sec-head h2{font-size:22px;margin:0 0 6px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
      .sec-head p{margin:0;font-size:13px}
      /* V3.1 · 区块编号 01/02/03/04 （与 cnstudio 一致） */
      .sp-sec-num{font-family:var(--font-mono);font-size:13px;font-weight:700;
        color:var(--brand-yellow);background:rgba(252,211,77,.15);
        border:1px solid var(--brand-yellow);border-radius:4px;
        padding:2px 8px;letter-spacing:.5px}
      .sp-sec-title{color:var(--ink);font-weight:700}
      .about-section .sp-sec-num{background:rgba(252,211,77,.25)}
      .rhythm-value{font-size:18px;font-weight:700;color:var(--ink);margin:6px 0 4px;
        font-family:var(--font-display);line-height:1.3}
      .skill-core-logic{font-family:var(--font-mono);font-size:11.5px;color:#5a5e63;
        background:rgba(255,255,255,.6);border:1px dashed #c8cbd1;border-radius:4px;
        padding:6px 8px;margin-top:6px;line-height:1.5;word-break:break-word}
    </style>
    """


def base_html(title: str, body: str, active: str = "", niche: str = "Yoga Mats",
               marketplaces: list = None, current_mp: str = "") -> str:
    """V3.1 基础 HTML 框架。marketplaces 必传，current_mp 驱动顶栏二级链接。"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
{style_block()}
</head>
<body>
{topbar(active=active, niche=niche, marketplaces=marketplaces, current_mp=current_mp)}
{body}
<footer class="sp-footnote">
  报告基于 SellerSprite MCP 数据生成（mock 占位数据），遵循 SOP V3.1 · 仅供内部选品决策参考 · © LIVIN.COM
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# V3.1 · Section / 卡片包装 / 标签
# ---------------------------------------------------------------------------
def section(title: str, body: str, *, alt: bool = False, sub: str = "") -> str:
    """V3.1 包装一个 section（与 cnstudio 一致）。"""
    cls = "section" + (" alt-bg" if alt else "")
    head = ""
    if title or sub:
        head = f"<div class='sec-head'><h2>{html.escape(title)}</h2>"
        if sub:
            head += f"<p class='sp-muted'>{sub}</p>"
        head += "</div>"
    return f"<section class='{cls}'><div class='wrap'>{head}{body}</div></section>"


def chart_card(title: str, body: str) -> str:
    """V3.1 图表卡（与 cnstudio 一致）。"""
    return f"<div class='chart-card'><h4>{title}</h4>{body}</div>"


def flag_emoji(marketplace: str) -> str:
    return {"UK": "🇬🇧", "US": "🇺🇸", "DE": "🇩🇪", "FR": "🇫🇷", "IT": "🇮🇹",
            "ES": "🇪🇸", "CA": "🇨🇦", "JP": "🇯🇵", "IN": "🇮🇳", "MX": "🇲🇽"}.get(
        marketplace.upper() if isinstance(marketplace, str) else "",
        "🌐"
    )


# ---------------------------------------------------------------------------
# V3.1 · 0 主观自动加权（程序根据硬阈值自动打分）
# ---------------------------------------------------------------------------
def auto_score(stats: dict, brand: dict, product: dict, price: dict,
                listing: dict, demand_trend: dict, rating: dict) -> dict:
    """
    根据 V3.1 第 4 节"自动评分矩阵总表"由原始数据直接映射 1-5 分。
    返回 {dim_key: {"score": int, "reason_zh": str, "reason_en": str}}
    """
    monthly_gmv = stats.get("monthlyGmvUsd", 0)
    monthly_search = stats.get("monthlySearchVolume", 0)
    yoy = stats.get("yoyTrendPct", 0)
    mom = stats.get("monthlyTrendPct", 0)
    sample = stats.get("sampleSizeListings", 0)

    # ---------- 维度 1：市场需求 ----------
    if sample < 50:
        d1_score, d1_reason = 1, f"样本量 {sample} < 50，强制 1 分（否决）"
    elif monthly_gmv >= 1_000_000 and mom > 5:
        d1_score, d1_reason = 5, f"GMV {monthly_gmv/1e6:.1f}M 且连增 {mom:.1f}%"
    elif monthly_gmv >= 500_000 and mom > 0:
        d1_score, d1_reason = 4, f"GMV {monthly_gmv/1e6:.2f}M 环比 {mom:+.1f}%"
    elif monthly_gmv >= 150_000:
        d1_score, d1_reason = 3, f"GMV {monthly_gmv/1e6:.2f}M，无大季节"
    elif monthly_gmv >= 50_000:
        d1_score, d1_reason = 2, f"GMV {monthly_gmv/1e3:.0f}K，持平"
    else:
        d1_score, d1_reason = 1, f"GMV {monthly_gmv/1e3:.0f}K 不足 50K"

    # ---------- 维度 2：分散度 ----------
    cr10 = max(brand.get("brandCr10", 0), product.get("productCr10", 0))
    if cr10 >= 0.70:
        d2_score, d2_reason = 1, f"CR10 {cr10*100:.0f}% 高度垄断"
    elif cr10 >= 0.60:
        d2_score, d2_reason = 2, f"CR10 {cr10*100:.0f}%"
    elif cr10 >= 0.45:
        d2_score, d2_reason = 3, f"CR10 {cr10*100:.0f}%"
    elif cr10 >= 0.30:
        d2_score, d2_reason = 4, f"CR10 {cr10*100:.0f}%"
    else:
        d2_score, d2_reason = 5, f"CR10 {cr10*100:.0f}% 高度分散"

    # ---------- 维度 3：定价空间（毛利率） ----------
    avg_price = stats.get("averagePriceUsd", price.get("medianPrice", 0))
    median_price = price.get("medianPrice", 0) or avg_price
    # 简化：基于售价推算净利率（参考 FBA 履约模型 + 头程 + 佣金）
    # - 售价越高，单位毛利绝对值越大
    # - 售价越低，FBA 履约占比越重
    # 经验公式：margin ≈ 0.62 - 1.2/sqrt(price)  （price ≥ 8）
    p = max(8.0, median_price or 20.0)
    import math as _m
    margin = max(0.10, min(0.65, 0.62 - 1.2 / _m.sqrt(p)))
    if margin >= 0.45:
        d3_score, d3_reason = 5, f"毛利率 {margin*100:.0f}% 暴利空间"
    elif margin >= 0.35:
        d3_score, d3_reason = 4, f"毛利率 {margin*100:.0f}% 优质空间"
    elif margin >= 0.25:
        d3_score, d3_reason = 3, f"毛利率 {margin*100:.0f}% 健康及格"
    elif margin >= 0.15:
        d3_score, d3_reason = 2, f"毛利率 {margin*100:.0f}% (D2 触发降档)"
    else:
        d3_score, d3_reason = 1, f"毛利率 {margin*100:.0f}% (D2 触发降档)"

    # ---------- 维度 4：新品机会 ----------
    new_ratio = listing.get("newReleaseRatio", 0)
    if new_ratio >= 0.20:
        d4_score, d4_reason = 5, f"新品占比 {new_ratio*100:.1f}%"
    elif new_ratio >= 0.12:
        d4_score, d4_reason = 4, f"新品占比 {new_ratio*100:.1f}%"
    elif new_ratio >= 0.05:
        d4_score, d4_reason = 3, f"新品占比 {new_ratio*100:.1f}%"
    elif new_ratio > 0:
        d4_score, d4_reason = 2, f"新品占比 {new_ratio*100:.1f}%"
    else:
        d4_score, d4_reason = 1, "新品占比 0%"

    # ---------- 维度 5：需求强度 ----------
    if yoy < -10 and mom < 0:
        d5_score, d5_reason = 1, f"同比 {yoy:+.1f}% 且环比 {mom:+.1f}%"
    elif yoy < -5:
        d5_score, d5_reason = 2, f"同比 {yoy:+.1f}%"
    elif abs(yoy) <= 5:
        d5_score, d5_reason = 3, f"同比 {yoy:+.1f}% ±5% 波动"
    elif yoy < 15:
        d5_score, d5_reason = 4, f"同比 {yoy:+.1f}% 连增"
    else:
        d5_score, d5_reason = 5, f"同比 {yoy:+.1f}% 爆发"

    return {
        "market_demand":   {"score": d1_score, "reason": d1_reason, "label": "市场需求 / Market Demand"},
        "dispersion":      {"score": d2_score, "reason": d2_reason, "label": "市场分散度 / Dispersion"},
        "price":           {"score": d3_score, "reason": d3_reason, "label": "定价空间 / Pricing"},
        "new_opportunity": {"score": d4_score, "reason": d4_reason, "label": "新品机会 / New-Opp"},
        "demand_strength": {"score": d5_score, "reason": d5_reason, "label": "需求强度 / Demand"},
    }


def auto_total(scores: dict, direction: str, brand_compliance: int = 4) -> dict:
    """
    按 V3.1 第 3 节权重加权汇总，返回:
    {weighted_total, weighted_breakdown, tier, veto_records, dim6_veto_active}
    """
    weights = WEIGHTS.get(direction, WEIGHTS["D2"])
    weighted_breakdown = []
    total = 0.0
    for k, w in weights.items():
        if w is None or k == "brand_compliance":
            continue
        s = scores.get(k, {}).get("score", 0)
        sub = round(s * w, 2)
        weighted_breakdown.append((k, s, w, sub))
        total += sub

    # 维度 6 权重：D2 20%
    if weights.get("brand_compliance") is not None:
        total += round(brand_compliance * weights["brand_compliance"], 2)

    # 否决（D2 特殊：D3 = 1/2 直接降 T3）
    veto_records = []
    if direction == "D2" and scores["price"]["score"] in (1, 2):
        veto_records.append(f"维度3 = {scores['price']['score']}（D2 触发降档）")
        total = 0  # 强制 T3

    weighted_total = round(total, 1)
    tier = compute_tier(direction, weighted_total)
    return {
        "weighted_total": weighted_total,
        "weighted_breakdown": weighted_breakdown,
        "tier": tier,
        "veto_records": veto_records,
    }


def score_annotation(marketplace: str, direction: str, scores: dict,
                     total: dict) -> str:
    """V3.1 · 评分批注（hover/click 展开 Excel 风格批注）。"""
    rows = []
    for k, s, w, sub in total["weighted_breakdown"]:
        meta = scores[k]
        rows.append(
            f"<div class='ann-row'>"
            f"<span class='ann-dim'>{html.escape(meta['label'])}</span>"
            f"<span class='ann-formula'>{s} × {w*100:.0f}% = {sub}</span>"
            f"<span class='ann-reason'>{html.escape(meta['reason'])}</span>"
            f"</div>"
        )
    veto_html = ""
    if total["veto_records"]:
        veto_html = "<div class='ann-veto'>⚠ 否决记录：" + " · ".join(
            html.escape(v) for v in total["veto_records"]) + "</div>"
    return (
        f"<details class='ann-wrap'>"
        f"<summary>📊 查看 {html.escape(marketplace.upper())} · {html.escape(direction)} 评分明细</summary>"
        f"<div class='ann-body'>{''.join(rows)}{veto_html}"
        f"<div class='ann-final'>Σ 加权分 = <b>{total['weighted_total']}</b> → "
        f"<span class='tier-badge {total['tier'].lower()}'>{total['tier']}</span></div>"
        f"</div></details>"
    )


# ---------------------------------------------------------------------------
# 业务计算：六维评分 / 方向判定 / 图表数据
# ---------------------------------------------------------------------------
def judge_direction(supply_demand_median: float) -> str:
    if supply_demand_median is None:
        return "D3"
    if supply_demand_median > 10:
        return "D1"
    if supply_demand_median >= 3:
        return "D2"
    return "D3"


WEIGHTS = {
    "D1": {"market_demand": 0.25, "dispersion": 0.20, "price": 0.15, "new_opportunity": 0.15, "demand_strength": 0.25, "brand_compliance": None},
    "D2": {"market_demand": 0.05, "dispersion": 0.15, "price": 0.25, "new_opportunity": 0.25, "demand_strength": 0.10, "brand_compliance": 0.20},
    "D3": {"market_demand": 0.10, "dispersion": 0.30, "price": 0.15, "new_opportunity": 0.20, "demand_strength": 0.25, "brand_compliance": None},
}

TIER_RANGE = {
    "D1": {"T1": 4.0, "T2": 3.0, "T3": 0},
    "D2": {"T1": 4.25, "T2": 3.5, "T3": 0},
    "D3": {"T1": 3.75, "T2": 2.75, "T3": 0},
}


def compute_tier(direction: str, weighted_total: float) -> str:
    r = TIER_RANGE[direction]
    if weighted_total >= r["T1"]:
        return "T1"
    if weighted_total >= r["T2"]:
        return "T2"
    return "T3"


def fmt_int(n: Optional[float]) -> str:
    if n is None:
        return "—"
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return f"{int(n)}"


def fmt_pct(x: Optional[float], digits: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x*100:.{digits}f}%"


# ---------------------------------------------------------------------------
# 简单 SVG 图表（无外部依赖）
# ---------------------------------------------------------------------------
def svg_bar(buckets: List[Dict[str, Any]], value_key: str, label_key: str = "range",
            width: int = 640, height: int = 240, palette: Optional[List[str]] = None,
            unit: str = "") -> str:
    if not buckets:
        return "<div class='sp-muted'>无数据</div>"
    palette = palette or ["#ff4d4d", "#ffab00", "#4d9fff", "#5cb85c",
                          "#a974ff", "#f06292", "#26c6da", "#f0ad4e"]
    pad_l, pad_r, pad_t, pad_b = 110, 20, 12, 28
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    max_v = max((b[value_key] for b in buckets), default=1) or 1
    bar_h = max(8, (plot_h - 6 * (len(buckets) - 1)) / max(1, len(buckets)))
    parts = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
             f'style="width:100%;height:auto;max-width:{width}px;font-family:var(--font-mono)">']
    for i, b in enumerate(buckets):
        y = pad_t + i * (bar_h + 6)
        w = max(2, (b[value_key] / max_v) * plot_w)
        color = palette[i % len(palette)]
        parts.append(f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="{bar_h:.1f}" '
                     f'fill="{color}" rx="2"/>')
        parts.append(f'<text x="{pad_l - 8}" y="{y + bar_h/2 + 4:.1f}" font-size="11" '
                     f'fill="#565959" text-anchor="end">{html.escape(str(b[label_key]))}</text>')
        val = b[value_key]
        val_text = f"{val*100:.1f}%" if value_key.endswith("share") else (f"{val:,.0f}{unit}")
        parts.append(f'<text x="{pad_l + w + 6:.1f}" y="{y + bar_h/2 + 4:.1f}" font-size="11" '
                     f'fill="#0f1111">{val_text}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_line(series: List[Dict[str, Any]], value_key: str = "value",
             label_key: str = "label", width: int = 720, height: int = 260,
             palette: Optional[List[str]] = None,
             y_formatter: Optional[Any] = None) -> str:
    """series: [{"label": "Aug", "value": 12.0}, ...]"""
    if not series:
        return "<div class='sp-muted'>无数据</div>"
    palette = palette or ["#4d9fff", "#ff4d4d", "#5cb85c", "#a974ff",
                          "#ffab00", "#f06292", "#26c6da", "#f0ad4e"]
    pad_l, pad_r, pad_t, pad_b = 56, 20, 16, 32
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    vals = [s[value_key] for s in series]
    vmin, vmax = min(vals), max(vals)
    if vmax == vmin:
        vmax = vmin + 1
    n = len(series)
    step = plot_w / max(1, n - 1)
    pts = []
    for i, s in enumerate(series):
        x = pad_l + i * step
        y = pad_t + (1 - (s[value_key] - vmin) / (vmax - vmin)) * plot_h
        pts.append((x, y, s[label_key], s[value_key]))
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto;max-width:{width}px;font-family:var(--font-mono)">']
    # grid + y labels (4 ticks)
    for k in range(5):
        gy = pad_t + k * plot_h / 4
        gv = vmax - k * (vmax - vmin) / 4
        out.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+plot_w}" y2="{gy:.1f}" '
                   f'stroke="#eef0f2" stroke-width="1"/>')
        if y_formatter:
            lbl = y_formatter(gv)
        else:
            lbl = f"{gv:,.0f}"
        out.append(f'<text x="{pad_l-8}" y="{gy+4:.1f}" font-size="10" fill="#9aa3ad" '
                   f'text-anchor="end">{html.escape(lbl)}</text>')
    # line
    path = " ".join(f"{('M' if i==0 else 'L')} {x:.1f} {y:.1f}" for i, (x, y, _, _) in enumerate(pts))
    out.append(f'<path d="{path}" fill="none" stroke="{palette[0]}" stroke-width="2.2"/>')
    # points + x labels
    for i, (x, y, lbl, val) in enumerate(pts):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{palette[0]}"/>')
        if i % max(1, n // 6) == 0 or i == n - 1:
            out.append(f'<text x="{x:.1f}" y="{pad_t+plot_h+18:.1f}" font-size="10" '
                       f'fill="#9aa3ad" text-anchor="middle">{html.escape(str(lbl))}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_multi_line(series_list: List[Dict[str, Any]], width: int = 760, height: int = 280,
                   palette: Optional[List[str]] = None) -> str:
    """
    series_list: [{"name":"kw1","labels":["M1","M2",...],"values":[v1,v2,...]}]
    """
    if not series_list:
        return "<div class='sp-muted'>无数据</div>"
    palette = palette or ["#4d9fff", "#ff4d4d", "#5cb85c", "#a974ff",
                          "#ffab00", "#f06292", "#26c6da", "#f0ad4e"]
    pad_l, pad_r, pad_t, pad_b = 60, 20, 16, 36
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    all_vals = [v for s in series_list for v in s["values"]]
    vmin, vmax = min(all_vals), max(all_vals)
    if vmax == vmin:
        vmax = vmin + 1
    n = len(series_list[0]["labels"])
    step = plot_w / max(1, n - 1)
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto;max-width:{width}px;font-family:var(--font-mono)">']
    # grid
    for k in range(5):
        gy = pad_t + k * plot_h / 4
        gv = vmax - k * (vmax - vmin) / 4
        out.append(f'<line x1="{pad_l}" y1="{gy:.1f}" x2="{pad_l+plot_w}" y2="{gy:.1f}" '
                   f'stroke="#eef0f2" stroke-width="1"/>')
        out.append(f'<text x="{pad_l-8}" y="{gy+4:.1f}" font-size="10" fill="#9aa3ad" '
                   f'text-anchor="end">{gv:,.0f}</text>')
    # series
    for i, s in enumerate(series_list):
        color = palette[i % len(palette)]
        pts = []
        for j, v in enumerate(s["values"]):
            x = pad_l + j * step
            y = pad_t + (1 - (v - vmin) / (vmax - vmin)) * plot_h
            pts.append((x, y))
        path = " ".join(f"{('M' if j==0 else 'L')} {x:.1f} {y:.1f}" for j, (x, y) in enumerate(pts))
        out.append(f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2"/>')
    # x labels
    for j, lbl in enumerate(series_list[0]["labels"]):
        x = pad_l + j * step
        if j % max(1, n // 6) == 0 or j == n - 1:
            out.append(f'<text x="{x:.1f}" y="{pad_t+plot_h+18:.1f}" font-size="10" '
                       f'fill="#9aa3ad" text-anchor="middle">{html.escape(str(lbl))}</text>')
    # legend
    for i, s in enumerate(series_list):
        color = palette[i % len(palette)]
        lx = pad_l + i * 120
        ly = 8
        out.append(f'<rect x="{lx}" y="{ly}" width="10" height="10" fill="{color}" rx="2"/>')
        out.append(f'<text x="{lx+14}" y="{ly+9}" font-size="11" fill="#0f1111">{html.escape(s["name"])}</text>')
    out.append("</svg>")
    return "".join(out)


def svg_cr10_chart(brand_cr10: float, product_cr10: float, width: int = 460, height: int = 200) -> str:
    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto;max-width:{width}px;font-family:var(--font-mono)">']
    pad_l, pad_r, pad_t, pad_b = 24, 80, 24, 24
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    max_v = max(brand_cr10, product_cr10, 0.6)
    for label, v, color in [("Brand CR10 / 品牌集中度", brand_cr10, "#ff4d4d"),
                            ("Product CR10 / 商品集中度", product_cr10, "#4d9fff")]:
        i = ["Brand CR10 / 品牌集中度", "Product CR10 / 商品集中度"].index(label)
        y = pad_t + i * 50
        w = (v / max_v) * plot_w
        out.append(f'<text x="{pad_l}" y="{y - 6}" font-size="11" fill="#565959">{label}</text>')
        out.append(f'<rect x="{pad_l}" y="{y}" width="{plot_w}" height="22" fill="#eef0f2" rx="3"/>')
        out.append(f'<rect x="{pad_l}" y="{y}" width="{w:.1f}" height="22" fill="{color}" rx="3"/>')
        out.append(f'<text x="{pad_l + w + 6:.1f}" y="{y + 15}" font-size="12" fill="#0f1111" '
                   f'font-weight="600">{v*100:.1f}%</text>')
    out.append("</svg>")
    return "".join(out)