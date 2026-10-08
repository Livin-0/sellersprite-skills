"""
sp_render_split.py
==================
SOP V3.0 STEP 8 · 渲染脚本 1/4
功能：总览页 index.html + 各站点独立页 {marketplace}.html
      包含：六维评分卡 / 评分矩阵 / 关键 KPI / 方向判定 / 否决项速查
输入：data/config.json + raw/* + score/scoring.json
输出：output/index.html, output/{marketplace}.html
"""
from __future__ import annotations
import os
import sys
import html as _html
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)


def _tier_badge(tier: str) -> str:
    """返回档位标签的 HTML"""
    cls = {"T1": "t1", "T2": "t2", "T3": "t3"}[tier]
    label = {"T1": "T1 · 必做", "T2": "T2 · 可做(复议)", "T3": "T3 · 放弃"}[tier]
    return f"<span class='tier-badge {cls}'>{label}</span>"


# ---------------------------------------------------------------------------
# V3.1 · 站点指标聚合（用于总览页的 5-指标卡片 / 矩阵 / Top 3 / 避坑）
# ---------------------------------------------------------------------------
def _currency_symbol(mp: str) -> str:
    return {"UK": "£", "US": "$", "DE": "€", "FR": "€", "IT": "€",
            "ES": "€", "JP": "¥", "CA": "C$", "IN": "₹", "MX": "MX$"}.get(mp.upper(), "$")


def _gather_site_metrics(mp: str, project: dict, cfg: dict = None) -> dict:
    """汇总一个站点的关键指标：用于总览页 5 指标卡 / 矩阵 / Top 3。

    V3.1 fix: 用真实字段名（totalProducts/totalUnits/totalRevenue/avgPrice），
    supplyDemandRatio 同时从 market_research.items[*] 和 data/config.json 双向取值。
    """
    stats  = sp.load_normalized(ROOT, mp, "market_research")
    brand  = sp.load_normalized(ROOT, mp, "market_brand")
    seller = sp.load_normalized(ROOT, mp, "market_seller-country")
    kw_res = sp.load_normalized(ROOT, mp, "keyword_research")

    # V3.1.1 fix: supplyDemandRatio 直接从 normalize 后的 stats 取（移除 supply_demand_median 兜底）
    sdr = stats.get("supplyDemandRatio", 0) or 0
    # 备选：从 keyword_research 里取中位数（仅当 stats 字段为 0 时使用）
    if (not sdr) and kw_res.get("keywords"):
        try:
            vals = sorted([k.get("supplyDemandRatio", 0) for k in kw_res["keywords"] if k.get("supplyDemandRatio", 0) > 0])
            sdr = vals[len(vals) // 2] if vals else 0
        except Exception:
            sdr = 0

    return {
        "monthlyGmvUsd":     stats.get("monthlyGmvUsd", 0),  # 已 normalize 为 totalRevenue
        "activeAsinCount":   stats.get("activeAsinCount", 0),  # = totalProducts
        "averagePriceUsd":   stats.get("averagePriceUsd", 0),  # = avgPrice
        "chinaSellerRatio":  seller.get("chinaSellerRatio", 0),
        "brandCr10":         brand.get("brandCr10", 0),
        "supplyDemandRatio": round(float(sdr), 2) if sdr else 0,
        "currency":          _currency_symbol(mp),
        "niche":             project["niche"],
    }


def _chip_row(marketplaces: list) -> str:
    """Hero 区下方 4 个统计 chip（站点数 / 细切数 / 有效组合 / Chart.js 数）。"""
    n_mp = len(marketplaces)
    n_niche = 1  # 当前实现：1 个细切（多细切在后续版本支持）
    n_combo = n_mp * n_niche
    return (
        f"<div class='hero-chips'>"
        f"<span class='chip'>{n_mp} 个站点</span>"
        f"<span class='chip'>{n_niche} 个细切</span>"
        f"<span class='chip'><strong>{n_combo}/{n_combo}</strong> 有效组合</span>"
        f"<span class='chip'>Chart.js 互动图表</span>"
        f"</div>"
    )


def _hero_block(project: dict, marketplaces: list) -> str:
    n_mp = len(marketplaces)
    n_niche = 1
    return (
        "<section class='hero'>"
        "<div class='wrap'>"
        f"<div class='hero-eyebrow'>📊 SOP V3.1 · 0 主观自动加权版</div>"
        f"<h1>选品总览 · <span class='brand-orange'>{_html.escape(project['niche'])}</span></h1>"
        f"<p class='hero-sub'>{n_mp} 个 Amazon 站点同一套指标、同一份机会分模型。"
        f"细切在多站的横向对比一眼看清。点国旗下钻该站深耕报告（带 Chart.js 图表）。</p>"
        f"{_chip_row(marketplaces)}"
        "</div></section>"
    )


def _render_site_card(mp: str, scoring_mp: dict, metrics: dict) -> str:
    """5 指标站点卡（细切数 / 商品总数 / 均价均值 / 中国占比 / 最佳）。"""
    flag = sp.flag_emoji(mp)
    name = sp.MARKETPLACE_NAME.get(mp.upper(), mp.upper())
    domain = f"{mp.lower()}.amazon.com"
    color = sp.site_color(mp)
    asin_n = metrics["activeAsinCount"]
    avg_p = metrics["averagePriceUsd"]
    cur = metrics["currency"]
    china = metrics["chinaSellerRatio"]
    total = scoring_mp.get("weighted_total", 0)
    tier = scoring_mp.get("tier", "T3")
    direction = scoring_mp.get("direction", "—")
    # 细切数：本实现 1 细切固定
    n_niche = 1
    # 评分进度点
    dot_color = {"T1": "var(--tier1)", "T2": "var(--tier2)", "T3": "var(--tier3)"}.get(tier, "var(--tier3)")
    return (
        f"<a class='site-card' href='{mp.lower()}.html' style='--mp-color:{color};'>"
        f"<span class='site-card-bar'></span>"
        f"<div class='site-card-h'>"
        f"<div class='site-flag'>{flag}</div>"
        f"<div class='site-card-title'>"
        f"<div class='site-name'>{name}</div>"
        f"<div class='site-domain'>{domain}</div>"
        f"</div></div>"
        f"<div class='site-metrics'>"
        f"<div class='site-metric'><span class='site-metric-label'>细切数</span>"
        f"<span class='site-metric-value'>{n_niche}/{n_niche} "
        f"<span style='color:{dot_color};font-size:12px;'>●</span></span></div>"
        f"<div class='site-metric'><span class='site-metric-label'>商品总数</span>"
        f"<span class='site-metric-value'>{sp.fmt_int(asin_n)}</span></div>"
        f"<div class='site-metric'><span class='site-metric-label'>均价均值</span>"
        f"<span class='site-metric-value'>{cur}{avg_p:.0f}</span></div>"
        f"<div class='site-metric'><span class='site-metric-label'>中国占比</span>"
        f"<span class='site-metric-value'>{china*100:.0f}%</span></div>"
        f"</div>"
        # V3.1 fix: 供需比（之前未在卡片上显示）— 单独一行 5 指标
        f"<div class='site-metric site-metric-wide'>"
        f"<span class='site-metric-label'>供需比 Supply / Demand</span>"
        f"<span class='site-metric-value'>{metrics.get('supplyDemandRatio', 0):.2f}"
        f" <span class='sp-muted' style='font-size:11px;'>({'D1需求驱动' if metrics.get('supplyDemandRatio', 0) > 10 else 'D2红海' if metrics.get('supplyDemandRatio', 0) >= 3 else 'D3细分'})</span>"
        f"</span></div>"
        f"<div class='site-best'>最佳: <strong>{_html.escape(metrics['niche'])}</strong> "
        f"<span class='score'>{total:.1f} 分 · {direction}</span></div>"
        f"</a>"
    )


def _sec_label(num: str, title: str) -> str:
    """V3.1 · 与 cnstudio 一致的区块编号（01 / 5 站大盘 风格）。"""
    return f"<span class='sp-sec-num'>{num}</span> <span class='sp-sec-title'>{_html.escape(title)}</span>"


def _render_cross_matrix(marketplaces: list, scoring: dict, metrics_map: dict) -> str:
    """5-站矩阵（行=细切，列=站点，含 5+1 维评分细分，100 分制 sum=100）。

    V3.1 强制：每个 cell 必须显示「加权合计 = N/100」且 N = Σ 维分。
    6 维权重归一方式：
      - 5 个计分维（market_demand/dispersion/price/new_opportunity/demand_strength）
        + brand_compliance = 总权重 1.0
      - 在 cell 中 5 维显示 brand_compliance 用合并行展示（不破坏 5 维结构）
    """
    if len(marketplaces) < 2:
        return ""
    niche = next(iter(metrics_map.values()))["niche"]
    head_cells = ["<th class='row-h'>细切</th>"]
    for m in marketplaces:
        flag = sp.flag_emoji(m)
        head_cells.append(f"<th class='row-h'>{flag} {m.upper()}</th>")
    head_cells.append("<th class='row-h'>最佳站</th>")

    cells_per_mp = []
    weakest_dim_global = ("", 5, 0, "")  # name, raw_score, weight, mp

    for m in marketplaces:
        sc = scoring.get(m, {})
        mt = metrics_map[m]
        cur = mt["currency"]
        total_5 = sc.get("weighted_total", 0)  # 5 分制总分（含 D6）
        avg = mt["averagePriceUsd"]
        gmv = mt["monthlyGmvUsd"]
        china = mt["chinaSellerRatio"] * 100
        rs = sc.get("raw_scores", {}) or {}
        d1 = rs.get("market_demand", "—")
        d2 = rs.get("dispersion", "—")
        d3 = rs.get("price", "—")
        d4 = rs.get("new_opportunity", "—")
        d5 = rs.get("demand_strength", "—")
        d6 = rs.get("brand_compliance", "—")
        direction = sc.get("direction", "D2")
        weights = sp.WEIGHTS.get(direction, sp.WEIGHTS["D2"])
        # V3.1 强制：100 分制（cnstudio 风格），6 维权重直接 / 1.0 * 100
        # 每个维的满分 = 该维的权重 × 100
        d1w = round(weights.get("market_demand", 0) * 100)        # D2: 5
        d2w = round(weights.get("dispersion", 0) * 100)           # D2: 15
        d3w = round(weights.get("price", 0) * 100)                # D2: 25
        d4w = round(weights.get("new_opportunity", 0) * 100)      # D2: 25
        d5w = round(weights.get("demand_strength", 0) * 100)      # D2: 10
        d6w = round((weights.get("brand_compliance") or 0) * 100)  # D2: 20
        sum_max = d1w + d2w + d3w + d4w + d5w + d6w  # 必须 = 100

        def to_100(score, w):
            if not isinstance(score, (int, float)):
                return "—"
            return int(round(score * w / 5))
        d1_100 = to_100(d1, d1w)
        d2_100 = to_100(d2, d2w)
        d3_100 = to_100(d3, d3w)
        d4_100 = to_100(d4, d4w)
        d5_100 = to_100(d5, d5w)
        d6_100 = to_100(d6, d6w)
        sum_100 = sum(x for x in [d1_100, d2_100, d3_100, d4_100, d5_100, d6_100]
                      if isinstance(x, int))
        # 找该站最弱维度
        dims = [("规模", d1, d1w), ("分散", d2, d2w),
                ("定价", d3, d3w), ("新品", d4, d4w),
                ("需求", d5, d5w), ("合规", d6, d6w)]
        for name, sc_v, w in dims:
            if isinstance(sc_v, (int, float)) and (weakest_dim_global[1] is None
                                                   or sc_v < weakest_dim_global[1]):
                weakest_dim_global = (name, sc_v, w, m)
        # tier 颜色（按 5 分制 tier）
        tier_cls = "tier-1" if total_5 >= 4.0 else ("tier-2" if total_5 >= 3.0 else "tier-3")
        cells_per_mp.append(
            f"<td>"
            f"<div class='matrix-cell'>"
            f"<span class='score {tier_cls}'>{total_5:.1f}</span>"
            f"<span class='sub'>均价{cur}{avg:.0f} · 月营收{cur}{gmv/1000:.1f}K · 中国{china:.0f}%</span>"
            f"<div class='metric-line'>6 维加权（满分 100）</div>"
            f"<div class='metric-line'>规模{d1_100}/{d1w} 分散{d2_100}/{d2w} 定价{d3_100}/{d3w} 新品{d4_100}/{d4w} 需求{d5_100}/{d5w} 合规{d6_100}/{d6w}</div>"
            f"<div class='metric-line'>加权合计 <b>{sum_100}</b>/{sum_max}（{round(sum_100/sum_max*100)}%）</div>"
            f"</div></td>"
        )
    # 第一列：细切名 + 方向
    directions = [scoring.get(m, {}).get("direction", "D2") for m in marketplaces]
    if len(set(directions)) == 1:
        direction_text = f"{directions[0]} 方向"
    else:
        direction_text = " · ".join(f"{m.upper()} {d}" for m, d in zip(marketplaces, directions))
    first = f"<td><strong>{_html.escape(niche)}</strong><br><span class='sub' style='color:var(--muted);font-size:11px;'>{direction_text}</span></td>"
    # 最弱维度扣分提示（合并显示在该行下方，colspan 跨整行）
    weak_cell = ""
    if weakest_dim_global[0]:
        sc_v, w, mp = weakest_dim_global[1], weakest_dim_global[2], weakest_dim_global[3]
        actual = round(sc_v * w / 5, 1) if isinstance(sc_v, (int, float)) else 0
        loss = round(w - actual, 1) if isinstance(sc_v, (int, float)) else 0
        weak_cell = (f"<tr><td colspan='{2 + len(marketplaces)}' class='sub' "
                     f"style='color:var(--bad);text-align:left;background:#fef2f2;'>"
                     f"✗ <b>{weakest_dim_global[0]}</b> 扣 {loss} 分（{actual}/{w}）"
                     f"<span class='sp-muted' style='margin-left:8px;'>— {mp.upper()} 站最弱维</span>"
                     f"</td></tr>")
    # 找最佳站
    best_mp = max(marketplaces, key=lambda m: scoring.get(m, {}).get("weighted_total", 0))
    best_flag = sp.flag_emoji(best_mp)
    best_cell = f"<td>{best_flag} <strong>{best_mp.upper()}</strong><br><span class='sub'>{scoring.get(best_mp,{}).get('weighted_total',0):.1f}</span></td>"

    row = f"<tr>{first}{''.join(cells_per_mp)}{best_cell}</tr>"

    return (
        "<section class='alt-bg'>"
        "<div class='wrap'>"
        "<div class='sec-head'>"
        f"<h2>{_sec_label('02', '5 站矩阵 · 多站机会分对比')}</h2>"
        f"<p class='sp-muted'>金 (≥75) / 绿 (60-74) / 橙 (&lt;60) 三档颜色。最右列「最佳站」自动定位该细切的最优站点。</p>"
        "</div>"
        "<div class='matrix-wrap'>"
        "<table class='matrix'>"
        f"<thead><tr>{''.join(head_cells)}</tr></thead>"
        f"<tbody>{row}{weak_cell}</tbody>"
        "</table></div></div></section>"
    )


def _render_top3_medals(marketplaces: list, scoring: dict, metrics_map: dict) -> str:
    """Top 3 跨站组合（按综合分排序）。"""
    if not marketplaces:
        return ""
    # 按综合分排序
    ranked = sorted(marketplaces, key=lambda m: scoring.get(m, {}).get("weighted_total", 0), reverse=True)
    medals = []
    for i, m in enumerate(ranked[:3], 1):
        sc = scoring.get(m, {})
        mt = metrics_map[m]
        cur = mt["currency"]
        flag = sp.flag_emoji(m)
        name = sp.MARKETPLACE_NAME.get(m.upper(), m.upper())
        total = sc.get("weighted_total", 0)
        avg = mt["averagePriceUsd"]
        china = mt["chinaSellerRatio"] * 100
        tier = sc.get("tier", "T3")
        medals.append(
            f"<a class='medal-card' href='{m.lower()}.html#{m.lower()}_main'>"
            f"<span class='medal-rank'>{i}</span>"
            f"<h4>{flag} {_html.escape(mt['niche'])}</h4>"
            f"<div class='medal-meta'>{sp._esc(name)} · <strong>{total:.0f} 分</strong> {_tier_badge(tier)}</div>"
            f"<div class='medal-metrics'>"
            f"<div class='medal-metric'><span>客单价</span><span class='v'>{cur}{avg:.0f}</span></div>"
            f"<div class='medal-metric'><span>中国占比</span><span class='v'>{china:.0f}%</span></div>"
            f"</div>"
            f"<div style='margin-top:10px;font-size:13px;color:var(--link);'>"
            f"点击进入 {m.upper()} 站深耕 →</div>"
            f"</a>"
        )
    # 不足 3 个时填充占位
    while len(medals) < 3:
        medals.append(
            "<div class='medal-card' style='opacity:.5;'>"
            "<span class='medal-rank'>—</span>"
            "<h4>暂无更多数据</h4>"
            "<div class='sp-muted'>该项目仅配置了 1~2 个站点</div></div>"
        )
    return (
        "<section>"
        "<div class='wrap'>"
        "<div class='sec-head'>"
        f"<h2><span class='sp-sec-num'>03</span> <span class='sp-sec-title'>🏆 Top 3 跨站组合</span></h2>"
        f"<p class='sp-muted'>{len(marketplaces)*1} 个 (站 × 切) 组合中按综合机会分排序。点击奖牌进入该站深耕报告。</p>"
        "</div>"
        f"<div class='medal-grid'>{''.join(medals)}</div>"
        "</div></section>"
    )


def _render_risk_panel(marketplaces: list) -> str:
    """04 避坑 - 通用 + 站级风险提示。"""
    # 通用风险池（按站点名匹配）
    general_risks = [
        ("UK", "<b>UK 站合规</b>：UKCA 标志过渡期 2024 年底已结束，销往英国的商品需 UKCA 标志；GEM 首饰需禁锢镍释放测试。"),
        ("FR", "<b>FR 站合规成本</b>：包装法（Citeo）、EPR 多（DEEE、电池法等）—— 客单价低于 €15 的细切慎入，毛利覆盖不了。"),
        ("FR", "<b>FR 站小语种</b>：法语 Listing / A+ 视频必须本地化（不是机翻），是转化率的最大杠杆。"),
        ("DE", "<b>DE 站合规</b>：包装法（LUCID）、WEEE、电池法 BattG、EPR 多 —— 客单价低于 €15 的细切慎入。"),
        ("IT", "<b>IT 站退货率</b>：南欧站退货率通常高于 UK/DE，<b>不要用 UK 数据直接外推</b>，必须在目标站实测。"),
        ("ES", "<b>ES 站数据稀疏</b>：ES 站 Sports & Outdoors 整体体量小，部分叶子节点无数据，进入前用 product_research 验证。"),
        ("ES", "<b>ES 站 ACoS</b>：ES 站的 CPC 通常比 UK 高 20-40%，广告预算要多备。"),
    ]
    # 选中当前项目涉及的站点
    items = []
    for mp in marketplaces:
        for tag, text in general_risks:
            if tag == mp.upper():
                items.append(f"<div class='risk-item'>{text}</div>")
    # 至少给一条通用提示
    if not items:
        items.append("<div class='risk-item'>所有目标站点均需 <b>本地化 Listing（不是机翻）</b> 与 <b>实测广告 ACoS</b>。</div>")
    # 拼接面板
    return (
        "<section class='alt-bg'>"
        "<div class='wrap'>"
        "<div class='sec-head'>"
        "<h2><span class='sp-sec-num'>04</span> <span class='sp-sec-title'>⚠️ 避坑 · 多站全局风险提示</span></h2>"
        f"<p class='sp-muted'>针对本项目配置的 {len(marketplaces)} 个站点的合规 / 流量 / 退货等通用风险。</p>"
        "</div>"
        f"<div class='risk-list'>{''.join(items)}</div>"
        "</div></section>"
    )


def _render_about(marketplaces: list, project: dict) -> str:
    """About + 数据透明 + 5 站入口。"""
    n_mp = len(marketplaces)
    n_niche = 1
    n_combo = n_mp * n_niche
    # 5 站入口列表
    links = "".join(
        f"<li>{sp.flag_emoji(m)} <a href='{m.lower()}.html'>{m.upper()} {sp.MARKETPLACE_NAME.get(m.upper(),'')}</a> · <span class='mono'>{m.lower()}.amazon.com</span></li>"
        for m in marketplaces
    )
    return (
        "<section>"
        "<div class='wrap'>"
        "<div class='about-section'>"
        f"<h2 style='margin-top:0;'>{_sec_label('06', '关于本报告 · 数据透明')}</h2>"
        f"<p>本报告由 <b>SellerSprite MCP 12+ 工具</b> 自动采集 + <b>SOP V3.1 自动评分模型</b> 渲染生成。"
        f"{n_mp} 站 × {n_niche} 细切 = {n_combo}+ 数据维度，原始 JSON 落盘 <code>raw/</code>。</p>"
        "<h3 style='margin-top:18px;font-size:15px;'>🔍 数据透明</h3>"
        "<div class='about-meta'>"
        f"<div class='about-meta-item'><b>SOP 版本</b><span>V3.1 · 0 主观自动加权版</span></div>"
        f"<div class='about-meta-item'><b>数据月份</b><span>{datetime.now().strftime('%Y-%m')}</span></div>"
        f"<div class='about-meta-item'><b>类目</b><span>{_html.escape(project['niche'])}</span></div>"
        f"<div class='about-meta-item'><b>目标站点</b><span>{n_mp} 个 ({', '.join(m.upper() for m in marketplaces)})</span></div>"
        f"<div class='about-meta-item'><b>有效组合</b><span>{n_combo}/{n_combo}</span></div>"
        f"<div class='about-meta-item'><b>API 调用</b><span>约 {n_mp * 18} 次 (12 核心 + 6 辅助)</span></div>"
        "</div>"
        "<h3 style='margin-top:18px;font-size:15px;'>🔗 5 站入口</h3>"
        f"<ul style='list-style:none;padding:0;margin:0;font-size:13.5px;line-height:1.9;'>{links}</ul>"
        "</div></div></section>"
    )


def _chartjs_block(marketplaces: list, scoring: dict, metrics_map: dict) -> str:
    """总览页底部 Chart.js 脚本：5 站横向柱状图（GMV / 均价 / 中国占比）。"""
    # 准备数据
    labels = [m.upper() for m in marketplaces]
    gmv = [round(metrics_map[m]["monthlyGmvUsd"]/1000, 1) for m in marketplaces]  # K USD
    avg = [round(metrics_map[m]["averagePriceUsd"], 1) for m in marketplaces]
    china = [round(metrics_map[m]["chinaSellerRatio"]*100, 1) for m in marketplaces]
    score = [scoring.get(m, {}).get("weighted_total", 0) for m in marketplaces]
    # 站色
    border_colors = [sp.site_color(m) for m in marketplaces]
    bg_colors = [sp.site_color(m) + "B3" for m in marketplaces]  # 70% alpha
    import json as _json
    return f"""
<section>
  <div class='wrap'>
    <div class='sec-head'>
      <h2><span class='sp-sec-num'>05</span> <span class='sp-sec-title'>📈 Chart.js 互动图表 · 5 站横向对比</span></h2>
      <p class='sp-muted'>悬停查看每个站点的具体数值。Chart.js 4.x 渲染，可点击图例隐藏/显示系列。</p>
    </div>
    <div class='charts-grid'>
      <div class='chart-card'>
        <h4>📦 月 GMV（千美元）</h4>
        <canvas class='sp-chart' id='ch-gmv'></canvas>
        <p class='chart-src'>来源: market_research.totalRevenue · V3.1 强制悬停交互</p>
      </div>
      <div class='chart-card'>
        <h4>💰 均价（USD 等值）</h4>
        <canvas class='sp-chart' id='ch-avg'></canvas>
        <p class='chart-src'>来源: market_research.avgPrice · 已换算为 USD 便于跨站比较</p>
      </div>
      <div class='chart-card'>
        <h4>🌍 中国卖家占比（%）</h4>
        <canvas class='sp-chart' id='ch-china'></canvas>
        <p class='chart-src'>来源: market_seller_country_distribution · unitsRatio 汇总</p>
      </div>
      <div class='chart-card'>
        <h4>🏆 综合机会分（满分 5.0）</h4>
        <canvas class='sp-chart' id='ch-score'></canvas>
        <p class='chart-src'>来源: scoring.json.weighted_total · V3.1 六维自动加权</p>
      </div>
    </div>
  </div>
</section>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>
<script>
(function(){{
  const LABELS = {_json.dumps(labels)};
  const COLORS = {_json.dumps(border_colors)};
  const BG     = {_json.dumps(bg_colors)};
  const DATA   = {{
    gmv:   {_json.dumps(gmv)},
    avg:   {_json.dumps(avg)},
    china: {_json.dumps(china)},
    score: {_json.dumps(score)}
  }};
  const baseOpts = (yLabel, suggestedMax) => ({{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        enabled: true,
        backgroundColor: '#0F172A',
        titleColor: '#FCD34D',
        bodyColor: '#fff',
        borderColor: '#FCD34D',
        borderWidth: 1,
        padding: 10,
        displayColors: true,
        callbacks: {{ label: (ctx) => yLabel + ': ' + ctx.parsed.y }}
      }}
    }},
    scales: {{
      y: {{ beginAtZero: true, suggestedMax, ticks: {{ font: {{ family: 'JetBrains Mono' }} }} }},
      x: {{ ticks: {{ font: {{ family: 'JetBrains Mono' }} }} }}
    }}
  }});
  const mk = (id, label, data, suggestedMax) => {{
    const ctx = document.getElementById(id);
    if (!ctx) return;
    new Chart(ctx, {{
      type: 'bar',
      data: {{
        labels: LABELS,
        datasets: [{{
          label: label,
          data: data,
          backgroundColor: BG,
          borderColor: COLORS,
          borderWidth: 2,
          borderRadius: 6
        }}]
      }},
      options: baseOpts(label, suggestedMax)
    }});
  }};
  mk('ch-gmv',   'GMV (K USD)',   DATA.gmv,   Math.max(100, Math.max(...DATA.gmv)*1.2));
  mk('ch-avg',   '均价 (USD)',    DATA.avg,   Math.max(20,  Math.max(...DATA.avg)*1.2));
  mk('ch-china', '中国占比 (%)',   DATA.china, 100);
  mk('ch-score', '综合分 (5.0)',  DATA.score, 5);
  // 高亮悬停效果
  document.querySelectorAll('.sp-chart').forEach(c => {{
    c.addEventListener('mouseenter', () => c.style.transform = 'scale(1.02)');
    c.addEventListener('mouseleave', () => c.style.transform = 'scale(1.0)');
  }});
}})();
</script>
"""


def _site_chartjs_block(marketplace: str, stats: dict, brand: dict,
                        product: dict, country: dict, scoring: dict) -> str:
    """V3.1 · 站点页 Chart.js 互动：4 个对比图（V3.0 仅 SVG，V3.1 补 Chart.js）。

    图表：CR10 集中度、评分分布、TOP 10 ASIN 销量、新品占比 vs 中国占比。
    """
    flag = sp.flag_emoji(marketplace)
    color = sp.site_color(marketplace)
    bg = color + "B3"
    import json as _json
    cr10 = brand.get("brandCr10", 0) * 100
    pcr10 = product.get("productCr10", 0) * 100
    china = country.get("chinaSellerRatio", 0) * 100
    us_local = country.get("usSellerRatio", 0) * 100
    other = country.get("otherSellerRatio", 0) * 100
    # TOP 10 ASIN 销量柱状图
    top10 = product.get("topProducts", [])[:10]
    asin_labels = [p.get("asin", "?")[-6:] for p in top10]
    asin_sales = [p.get("monthlySales", 0) for p in top10]
    # 评分分布（来自 rating 文件）
    rating = sp.load_normalized(ROOT, marketplace, "market_rating")
    rating_buckets = rating.get("buckets", [])
    rating_labels = [b.get("range", "?") for b in rating_buckets]
    rating_share = [round(b.get("share", 0) * 100, 1) for b in rating_buckets]
    return f"""
<section>
  <div class='wrap'>
    <div class='sec-head'>
      <h2>📈 {flag} {marketplace.upper()} 站 · Chart.js 互动图表</h2>
      <p class='sp-muted'>悬停查看具体数值（V3.1 强制 · 与 cnstudio 一致）。</p>
    </div>
    <div class='charts-grid'>
      <div class='chart-card'>
        <h4>🎯 CR10 集中度对比（%）</h4>
        <canvas class='sp-chart' id='site-cr10-{marketplace.lower()}'></canvas>
        <p class='chart-src'>品牌 vs 商品 CR10 · 来源: market_brand / market_product</p>
      </div>
      <div class='chart-card'>
        <h4>🌍 卖家国家分布（%）</h4>
        <canvas class='sp-chart' id='site-country-{marketplace.lower()}'></canvas>
        <p class='chart-src'>CN / US / Other · 来源: market_seller_country</p>
      </div>
      <div class='chart-card'>
        <h4>⭐ 评分分布（%）</h4>
        <canvas class='sp-chart' id='site-rating-{marketplace.lower()}'></canvas>
        <p class='chart-src'>来源: market_rating · unitsRatio 汇总</p>
      </div>
      <div class='chart-card'>
        <h4>🏆 TOP 10 ASIN 月销量</h4>
        <canvas class='sp-chart' id='site-top10-{marketplace.lower()}'></canvas>
        <p class='chart-src'>来源: market_product.topProducts · ASIN 后 6 位</p>
      </div>
    </div>
  </div>
</section>
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>
<script>
(function(){{
  const COLOR = '{color}';
  const BG    = '{bg}';
  const TOOLTIP_OPTS = {{
    enabled: true,
    backgroundColor: '#0F172A',
    titleColor: '#FCD34D',
    bodyColor: '#fff',
    borderColor: '#FCD34D',
    borderWidth: 1,
    padding: 10
  }};
  const base = (yLabel) => ({{
    responsive: true,
    maintainAspectRatio: false,
    interaction: {{ mode: 'index', intersect: false }},
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{ ...TOOLTIP_OPTS, callbacks: {{ label: (c) => yLabel + ': ' + c.parsed.y }} }}
    }},
    scales: {{
      y: {{ beginAtZero: true, ticks: {{ font: {{ family: 'JetBrains Mono' }} }} }},
      x: {{ ticks: {{ font: {{ family: 'JetBrains Mono' }} }} }}
    }}
  }});
  // 1) CR10 对比
  const cr10Labels = ['品牌 CR10', '商品 CR10'];
  const cr10Data   = [{round(cr10,1)}, {round(pcr10,1)}];
  new Chart(document.getElementById('site-cr10-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{ labels: cr10Labels, datasets: [{{
      label: 'CR10 (%)', data: cr10Data,
      backgroundColor: BG, borderColor: COLOR, borderWidth: 2, borderRadius: 6
    }}]}},
    options: base('CR10 (%)')
  }});
  // 2) 卖家国家分布
  const ctryLabels = ['中国 CN', '本地 US', '其他 Other'];
  const ctryData   = [{round(china,1)}, {round(us_local,1)}, {round(other,1)}];
  new Chart(document.getElementById('site-country-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{ labels: ctryLabels, datasets: [{{
      label: '占比 (%)', data: ctryData,
      backgroundColor: BG, borderColor: COLOR, borderWidth: 2, borderRadius: 6
    }}]}},
    options: base('占比 (%)')
  }});
  // 3) 评分分布
  const rLabels = {_json.dumps(rating_labels)};
  const rData   = {_json.dumps(rating_share)};
  new Chart(document.getElementById('site-rating-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{ labels: rLabels, datasets: [{{
      label: '占比 (%)', data: rData,
      backgroundColor: BG, borderColor: COLOR, borderWidth: 2, borderRadius: 6
    }}]}},
    options: base('占比 (%)')
  }});
  // 4) TOP 10 ASIN 月销量
  const aLabels = {_json.dumps(asin_labels)};
  const aData   = {_json.dumps(asin_sales)};
  new Chart(document.getElementById('site-top10-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{ labels: aLabels, datasets: [{{
      label: '月销量', data: aData,
      backgroundColor: BG, borderColor: COLOR, borderWidth: 2, borderRadius: 6
    }}]}},
    options: base('月销量')
  }});
  // 悬停缩放
  document.querySelectorAll('.sp-chart').forEach(c => {{
    c.addEventListener('mouseenter', () => c.style.transform = 'scale(1.02)');
    c.addEventListener('mouseleave', () => c.style.transform = 'scale(1.0)');
  }});
}})();
</script>
"""


def _render_subcategory_profile(marketplace: str, project: dict, scoring: dict,
                                 stats: dict, brand: dict, product: dict,
                                 price: dict, rating: dict, country: dict,
                                 kw: dict, listing: dict, comp_raw: dict) -> str:
    """V3.1.1 · 细切完整画像（cnstudio.com/AI/eu_country_uk.html 风格）

    8 个 stat cards + 4 个 Chart.js 图（6 维雷达 / 价格带柱 / 评分横向条 / 卖家国别环）
    + 卖家国别分布表 + Top 关键词表。
    """
    import json as _json
    flag = sp.flag_emoji(marketplace)
    cur = _currency_symbol(marketplace)
    niche = project["niche"]

    # 1) 派生 stat cards 数据
    asin_n = stats.get("activeAsinCount", 0)
    brand_n = len(brand.get("topBrands", []) or brand.get("items", []))
    # 卖家数：用 market_seller-country 的国别数作代理
    seller_country_items = country.get("items", country.get("buckets", []))
    seller_n = sum(1 for c in seller_country_items if c.get("products", 0) > 0)
    # 月均销量 = totalUnits / 30
    monthly_units = stats.get("monthlyGmvUsd", 0)  # totalRevenue
    units = 0
    if isinstance(price.get("items"), list):
        units = sum(b.get("units", 0) for b in price["items"])
    monthly_avg = units // 30 if units else 0
    revenue = monthly_units
    avg_p = stats.get("averagePriceUsd", 0)
    avg_rating = rating.get("averageRating", 0)
    # 评分数 = 销量从 rating 估算或来自 review
    rating_count = rating.get("ratingCount", 0) or rating.get("reviewCount", 0)
    # 新品占比：从 listing + brand 算
    new_units = sum(b.get("newUnits", 0) for b in brand.get("items", []))
    new_ratio = new_units / units if units else 0
    # 退货率：本项目无数据 → —
    return_rate = "—"
    avg_return = "—"
    # 搜索购买比 = Σpurchases / Σsearch
    total_search = sum(k.get("search", 0) for k in kw.get("keywords", []))
    total_purch = sum(k.get("purchases", 0) for k in kw.get("keywords", []))
    purchase_ratio = round(total_purch / total_search, 2) if total_search else "—"
    avg_purchase_ratio = "—"  # 站均无直接数据
    china_pct = country.get("chinaSellerRatio", 0) * 100
    # CR10 集中度（来自 market_brand / market_product）
    cr10_brand = round(brand.get("brandCr10", 0) * 100, 1)
    cr10_product = round(product.get("productCr10", 0) * 100, 1)

    # 2) 派生 4 个 Chart.js 图数据
    # 6 维雷达（满分 100）
    rs = scoring.get("raw_scores", {})
    radar_labels = ["规模", "分散", "定价", "新品", "需求", "合规"]
    radar_keys   = ["market_demand", "dispersion", "price",
                    "new_opportunity", "demand_strength", "brand_compliance"]
    radar_values = [rs.get(k, 0) * 20 for k in radar_keys]
    # 价格带柱状图
    price_buckets = price.get("items", [])
    p_labels = [b.get("label", "?") for b in price_buckets]
    p_shares = [round(b.get("unitsRatio", 0) * 100, 1) for b in price_buckets]
    # 评分横向条形图（只显示 share>0 的）
    rating_buckets = [b for b in rating.get("items", []) if b.get("unitsRatio", 0) > 0]
    r_labels = [b.get("label", "?") for b in rating_buckets]
    r_shares = [round(b.get("unitsRatio", 0) * 100, 1) for b in rating_buckets]
    # 卖家国别环形图（销量占比）
    country_buckets = [c for c in country.get("items", []) if c.get("unitsRatio", 0) > 0]
    c_labels = [c.get("label", "?") for c in country_buckets]
    c_shares = [round(c.get("unitsRatio", 0) * 100, 1) for c in country_buckets]
    # 上架时间分布（V3.1.1 新增：横轴=时间窗口，纵轴=占比）
    listing_buckets = listing.get("items", []) if isinstance(listing, dict) else listing
    l_labels = [b.get("label", "?") for b in listing_buckets]
    l_shares = [round(b.get("unitsRatio", 0) * 100, 1) for b in listing_buckets]
    # CR10 对比（横轴=类别，纵轴=CR10%）
    cr10_chart_labels = ["品牌 CR10", "商品 CR10"]
    cr10_chart_values = [cr10_brand, cr10_product]

    # 3) 8 个 stat cards
    stat_cards = [
        ("商品 / 品牌 / 卖家", "Products / Brands / Sellers",
         f"<b>{asin_n}</b> / <b>{brand_n}</b> / <b>{seller_n}</b>",
         "data: market_research / market_brand / market_seller-country"),
        ("月均销量", "Avg Monthly Units",
         f"<b>{monthly_avg:,}</b>",
         f"<span class='sub'>营收 {cur}{revenue/1000:.1f}K</span>"),
        ("客单价", "Avg Order Value",
         f"<b>{cur}{avg_p:.2f}</b>",
         "data: market_research.avgPrice"),
        ("评分 / 评分数", "Rating / Reviews",
         f"<b>{avg_rating:.1f}</b> / <b>{sp.fmt_int(rating_count)}</b>",
         "data: market_rating"),
        ("新品占比", "New-Product Share",
         f"<b>{new_ratio*100:.0f}%</b>",
         f"<span class='sub'>月均销 {cur}—</span>"),
        ("退货率 (本 / 均)", "Return Rate (this / avg)",
         f"<b>{return_rate}</b> <span class='sub'>/ {avg_return}</span>",
         "data: — (项目无此字段)"),
        ("搜索购买比 (本 / 均)", "Search-to-Buy Ratio",
         f"<b>{purchase_ratio}</b> <span class='sub'>/ {avg_purchase_ratio}</span>",
         "data: keyword_research"),
        ("中国卖家销量占比", "CN Seller Share",
         f"<b>{china_pct:.1f}%</b>",
         "data: market_seller-country"),
        ("品牌 CR10", "Brand CR10",
         f"<b>{cr10_brand:.1f}%</b>",
         f"<span class='sub'>{'⚠️ 头部垄断' if cr10_brand >= 70 else '✅ 分散健康' if cr10_brand < 50 else '中等'}</span>"),
        ("商品 CR10", "Product CR10",
         f"<b>{cr10_product:.1f}%</b>",
         f"<span class='sub'>{'⚠️ 头部垄断' if cr10_product >= 70 else '✅ 分散健康' if cr10_product < 50 else '中等'}</span>"),
    ]
    sc_html = []
    for label_zh, label_en, val, src in stat_cards:
        sc_html.append(
            f"<div class='metric-card cn-stat'>"
            f"<div class='metric-name'>{label_zh}</div>"
            f"<div class='metric-cat'>{label_en}</div>"
            f"<div class='metric-val-lg'>{val}</div>"
            f"<div class='metric-src'>{src}</div>"
            f"</div>"
        )

    # 4) 6 个 chart cards（2x3 布局）
    chart_cards = (
        f"<div class='chart-card'>"
        f"<h4>🎯 机会分 6 维雷达</h4>"
        f"<canvas class='sp-chart' id='ch-radar-{marketplace.lower()}'></canvas>"
        f"<p class='chart-src'>满分 100 · 6 维加权（规模/分散/定价/新品/需求/合规）</p>"
        f"</div>"
        f"<div class='chart-card'>"
        f"<h4>💰 价格带销量分布</h4>"
        f"<canvas class='sp-chart' id='ch-price-{marketplace.lower()}'></canvas>"
        f"<p class='chart-src'>来源：market_price.unitsRatio · 横轴=价格带，纵轴=销量占比</p>"
        f"</div>"
        f"<div class='chart-card'>"
        f"<h4>⭐ 评分分布</h4>"
        f"<canvas class='sp-chart' id='ch-rating-h-{marketplace.lower()}'></canvas>"
        f"<p class='chart-src'>来源：market_rating.unitsRatio · 横向条形图：y 轴=评分带，x 轴=占比</p>"
        f"</div>"
        f"<div class='chart-card'>"
        f"<h4>🌍 卖家国别（销量占比）</h4>"
        f"<canvas class='sp-chart' id='ch-country-ring-{marketplace.lower()}'></canvas>"
        f"<p class='chart-src'>来源：market_seller-country · 环形图</p>"
        f"</div>"
        f"<div class='chart-card'>"
        f"<h4>📅 上架时间分布</h4>"
        f"<canvas class='sp-chart' id='ch-listing-{marketplace.lower()}'></canvas>"
        f"<p class='chart-src'>来源：market_listing-date.unitsRatio · 横轴=时间窗口，纵轴=销量占比</p>"
        f"</div>"
        f"<div class='chart-card'>"
        f"<h4>🎯 CR10 集中度对比</h4>"
        f"<canvas class='sp-chart' id='ch-cr10-{marketplace.lower()}'></canvas>"
        f"<p class='chart-src'>横轴=类别（品牌/商品），纵轴=CR10% · &gt;70% 头部垄断</p>"
        f"</div>"
    )

    # 5) 卖家国别分布表
    country_rows = []
    for c in country_buckets:
        rev = c.get("revenue", 0)
        total_rev = sum(x.get("revenue", 0) for x in country_buckets) or 1
        country_rows.append(
            f"<tr><td>{sp._esc(c.get('label','—'))}</td>"
            f"<td>{c.get('products', 0)}</td>"
            f"<td>{c.get('unitsRatio', 0)*100:.1f}%</td>"
            f"<td>{rev/total_rev*100:.1f}%</td></tr>"
        )
    country_table = (
        "<div class='chart-card'>"
        "<h4>🌍 卖家国别分布</h4>"
        "<div class='matrix-wrap'>"
        "<table class='matrix'><thead><tr>"
        "<th>国别</th><th>商品数</th><th>销量占比</th><th>销售额占比</th>"
        "</tr></thead><tbody>"
        + "".join(country_rows) +
        "</tbody></table></div></div>"
    )

    # 6) Top 关键词表
    top_kw = sorted(kw.get("keywords", []), key=lambda x: -x.get("search", 0))[:8]
    kw_rows = []
    for k in top_kw:
        pr = k.get("purchasesRate") or 0
        kw_rows.append(
            f"<tr><td><b>{sp._esc(k.get('keyword',''))}</b></td>"
            f"<td>{sp.fmt_int(k.get('search', 0))}</td>"
            f"<td>{sp.fmt_int(k.get('purchases', 0))}</td>"
            f"<td>{pr*100:.1f}%</td>"
            f"<td>{k.get('asinCount', 0):,}</td>"
            f"<td class='price'>{cur}{k.get('price', 0):.2f}</td>"
            f"<td>{k.get('supplyDemandRatio', 0):.1f}</td></tr>"
        )
    kw_table = (
        "<div class='chart-card'>"
        "<h4>🔑 Top 关键词</h4>"
        "<div class='matrix-wrap'>"
        "<table class='matrix'><thead><tr>"
        "<th>关键词</th><th>月搜索量</th><th>月购买量</th><th>购买率</th>"
        "<th>商品数</th><th>均价</th><th>供需比</th>"
        "</tr></thead><tbody>"
        + "".join(kw_rows) +
        "</tbody></table></div></div>"
    )

    # 6b) TOP 10 销量 ASIN 表（V3.1.1 新增：搬自旧「卖家来源 + TOP 10 ASIN」section）
    top10_asin = (product.get("topProducts") or [])[:10]
    asin_rows = []
    for p in top10_asin:
        asin_rows.append(
            f"<tr><td class='mono'>{p.get('asin', '?')}</td>"
            f"<td>{sp._esc(p.get('brand', '—'))}</td>"
            f"<td>{p.get('monthlySales', 0):,}</td>"
            f"<td>{p.get('share', 0)*100:.1f}%</td>"
            f"<td>{p.get('rating', '—')}</td>"
            f"<td class='price'>{cur}{p.get('price', 0):.0f}</td></tr>"
        )
    asin_table = (
        "<div class='chart-card'>"
        "<h4>🏆 TOP 10 销量 ASIN</h4>"
        "<div class='matrix-wrap'>"
        "<table class='matrix'><thead><tr>"
        "<th>ASIN</th><th>品牌</th><th>月销量</th><th>份额</th><th>评分</th><th>价格</th>"
        "</tr></thead><tbody>"
        + "".join(asin_rows) +
        "</tbody></table></div></div>"
    )

    # 7) 拼装 6 个图表 + 3 个表
    sec = (
        "<section class='alt-bg'>"
        "<div class='wrap'>"
        "<div class='sec-head'>"
        f"<h2><span class='sp-sec-num'>03</span> <span class='sp-sec-title'>"
        f"🧘 细切完整画像 · {sp._esc(niche)}</span></h2>"
        f"<p class='sp-muted'>10 维 stat cards + 6 维 Chart.js 图 + 卖家国别表 + Top 关键词 + TOP10 ASIN"
        f"（V3.1.1 cnstudio 风格）</p>"
        "</div>"
        # 10 stat cards
        "<div class='cn-stats-grid'>" + "".join(sc_html) + "</div>"
        # 6 图表（3x2）
        "<div class='charts-grid'>" + chart_cards + "</div>"
        # 3 表
        "<div class='charts-grid'>" + country_table + kw_table + asin_table + "</div>"
        "</div></section>"
    )

    # 8) Chart.js 初始化脚本（与 _season_chartjs_block 同模式）
    return sec + _subcategory_chartjs_block(
        marketplace, radar_labels, radar_values,
        p_labels, p_shares,
        r_labels, r_shares,
        c_labels, c_shares,
        l_labels, l_shares,
        cr10_chart_labels, cr10_chart_values,
    )


def _subcategory_chartjs_block(marketplace: str,
                                radar_labels: list, radar_values: list,
                                p_labels: list, p_shares: list,
                                r_labels: list, r_shares: list,
                                c_labels: list, c_shares: list,
                                l_labels: list, l_shares: list,
                                cr10_chart_labels: list, cr10_chart_values: list) -> str:
    """V3.1.1 · 细切画像 6 个 Chart.js 互动
    （6 维雷达 / 价格柱 / 评分竖柱 / 国别环 / 上架时间柱 / CR10 对比）。"""
    import json as _json
    color = sp.site_color(marketplace)
    return f"""
<script src='https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js'></script>
<script>
(function(){{
  const TOOLTIP = {{
    enabled: true, backgroundColor: '#0F172A', titleColor: '#FCD34D',
    bodyColor: '#fff', borderColor: '#FCD34D', borderWidth: 1, padding: 8
  }};
  // 1) 6 维雷达
  new Chart(document.getElementById('ch-radar-{marketplace.lower()}'), {{
    type: 'radar',
    data: {{
      labels: {_json.dumps(radar_labels)},
      datasets: [{{
        label: '机会分（满分 100）',
        data: {_json.dumps(radar_values)},
        backgroundColor: '{color}40',
        borderColor: '{color}', borderWidth: 2, pointRadius: 4
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ position: 'bottom' }}, tooltip: TOOLTIP }},
      scales: {{ r: {{ beginAtZero: true, max: 100, ticks: {{ stepSize: 20 }} }} }}
    }}
  }});
  // 2) 价格带柱状图（横轴=价格，纵轴=占比）
  new Chart(document.getElementById('ch-price-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{
      labels: {_json.dumps(p_labels)},
      datasets: [{{
        label: '销量占比 (%)',
        data: {_json.dumps(p_shares)},
        backgroundColor: '{color}B3', borderColor: '{color}',
        borderWidth: 2, borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: TOOLTIP }},
      scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => v + '%' }} }} }}
    }}
  }});
  // 3) 评分分布（V3.1.1 按图改回横向条形：y 轴=评分带，x 轴=占比，更直观）
  new Chart(document.getElementById('ch-rating-h-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{
      labels: {_json.dumps(r_labels)},
      datasets: [{{
        label: '占比 (%)',
        data: {_json.dumps(r_shares)},
        backgroundColor: '#14532DCC', borderColor: '#14532D',
        borderWidth: 2, borderRadius: 4
      }}]
    }},
    options: {{
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: TOOLTIP }},
      scales: {{
        x: {{ beginAtZero: true, ticks: {{ callback: v => v + '%' }}, grid: {{ color: '#E2E8F0' }} }},
        y: {{ grid: {{ display: false }} }}
      }}
    }}
  }});
  // 4) 卖家国别环形图（按图片配色：英国深绿 / 中国橙红 / 美国蓝 / 未知灰）
  const cLabels = {_json.dumps(c_labels)};
  const cData   = {_json.dumps(c_shares)};
  const palette = ['#14532D', '#B45309', '#1D4ED8', '#94A3B8', '#7C3AED', '#059669', '#DC2626', '#0891B2'];
  new Chart(document.getElementById('ch-country-ring-{marketplace.lower()}'), {{
    type: 'doughnut',
    data: {{
      labels: cLabels,
      datasets: [{{
        data: cData,
        backgroundColor: cLabels.map((_, i) => palette[i % palette.length] + 'CC'),
        borderColor: cLabels.map((_, i) => palette[i % palette.length]),
        borderWidth: 2
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{
        legend: {{ position: 'right' }},
        tooltip: {{ ...TOOLTIP, callbacks: {{ label: c => c.label + ': ' + c.parsed + '%' }} }}
      }}
    }}
  }});
  // 5) 上架时间分布（横轴=时间窗口，纵轴=占比）
  new Chart(document.getElementById('ch-listing-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{
      labels: {_json.dumps(l_labels)},
      datasets: [{{
        label: '销量占比 (%)',
        data: {_json.dumps(l_shares)},
        backgroundColor: '{color}B3', borderColor: '{color}',
        borderWidth: 2, borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: TOOLTIP }},
      scales: {{ y: {{ beginAtZero: true, ticks: {{ callback: v => v + '%' }} }} }}
    }}
  }});
  // 6) CR10 对比（横轴=类别，纵轴=CR10%）
  new Chart(document.getElementById('ch-cr10-{marketplace.lower()}'), {{
    type: 'bar',
    data: {{
      labels: {_json.dumps(cr10_chart_labels)},
      datasets: [{{
        label: 'CR10 (%)',
        data: {_json.dumps(cr10_chart_values)},
        backgroundColor: ['{color}B3', '#D97706B3'],
        borderColor: ['{color}', '#D97706'],
        borderWidth: 2, borderRadius: 4
      }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: TOOLTIP }},
      scales: {{
        y: {{ beginAtZero: true, max: 100, ticks: {{ callback: v => v + '%' }} }}
      }}
    }}
  }});
  // 悬停缩放
  document.querySelectorAll('.sp-chart').forEach(c => {{
    c.addEventListener('mouseenter', () => c.style.transform = 'scale(1.02)');
    c.addEventListener('mouseleave', () => c.style.transform = 'scale(1.0)');
  }});
}})();
</script>
"""


def _score_table(direction: str, raw_scores: dict) -> str:
    """生成六维评分卡（带进度条）"""
    weights = sp.WEIGHTS[direction]
    rows = []
    for dim, label_zh, label_en in [
        ("market_demand",    "市场需求",  "Market Demand"),
        ("dispersion",       "市场分散度", "Dispersion"),
        ("price",            "定价空间",  "Pricing"),
        ("new_opportunity",  "新品机会",  "New-Opp"),
        ("demand_strength",  "需求强度",  "Demand Strength"),
        ("brand_compliance", "品牌与合规", "Brand & Compliance"),
    ]:
        s = raw_scores.get(dim, "—")
        w = weights.get(dim, 0)
        pct = s * 20 if isinstance(s, (int, float)) else 0
        # 根据分数决定进度条颜色
        if s >= 4:
            bar_cls = "high"
        elif s >= 3:
            bar_cls = "mid"
        else:
            bar_cls = "low"
        rows.append(
            f"<div class='dim-row'>"
            f"<span class='dim-row-name'>{label_zh}<br><span class='dim-row-en'>{label_en}</span></span>"
            f"<div class='dim-row-track'><div class='dim-row-fill {bar_cls}' style='width:{pct}%;'></div></div>"
            f"<span class='dim-row-score'>{s}<span class='max'>/5</span></span>"
            f"</div>"
        )
    return "".join(rows)


def _render_skill25_card(scoring: dict) -> str:
    """渲染 Skill 25 破格状态卡片"""
    s25 = scoring.get("skill_25_breakout", {})
    growth_val = s25.get("next_month_growth_pct", 0)
    yoy_val = s25.get("off_season_yoy_pct", 0)
    applied = s25.get("applied", False)
    growth_ok = growth_val > 100
    yoy_ok = yoy_val > 10
    status = "✅ 已应用（维度5 +1）" if applied else "⛔ 未触发"
    return (
        f"<div class='skill25-card'>"
        f"<div class='skill25-header'>🎯 Skill 25 季节破格</div>"
        f"<div class='skill25-grid'>"
        f"<div class='skill25-item'><span class='skill25-label'>下月增长率</span><span class='skill25-value'>{growth_val:.1f}%</span><span class='skill25-check'>{'✅' if growth_ok else '❌'} &gt;100%</span></div>"
        f"<div class='skill25-item'><span class='skill25-label'>淡季同比</span><span class='skill25-value'>{yoy_val:.1f}%</span><span class='skill25-check'>{'✅' if yoy_ok else '❌'} &gt;10%</span></div>"
        f"<div class='skill25-item skill25-result'><span class='skill25-label'>最终结论</span><span class='skill25-value'>{status}</span></div>"
        f"</div></div>"
    )


def render_overview(cfg: dict) -> str:
    """渲染总览页 index.html - V3.1 对照 cnstudio 5 大区块结构。

    区块结构（与 cnstudio.com/AI/index.html 一一对应）：
      1. Hero          : 标题 + 4 个统计 chip（站点数 / 细切数 / 有效组合 / Chart.js）
      2. 5 站大盘      : 每站 5 指标卡（细切数 / 商品总数 / 均价 / 中国占比 / 最佳）
      3. 横向矩阵      : 站点 × 细切 矩阵，含 5 维评分细分与最弱维度扣分提示
      4. Top 3 跨站组合 : 奖牌卡，按综合机会分排序
      5. 避坑          : 站级风险提示（合规、退货、ACoS、本地化）
      6. Chart.js 互动 : 4 个对比柱状图（GMV / 均价 / 中国占比 / 综合分）
      7. About + 数据透明 + 5 站入口
    """
    marketplaces = cfg["marketplaces"]
    project = cfg["project"]
    scoring = sp.load_json(ROOT, "score/scoring.json")
    # 聚合每个站点的关键指标
    metrics_map = {m: _gather_site_metrics(m, project, cfg) for m in marketplaces}
    body = []

    # 1. Hero
    body.append(_hero_block(project, marketplaces))

    # 2. 5 站大盘
    body.append("<section>")
    body.append("<div class='wrap'>")
    body.append("<div class='sec-head'>"
                f"<h2>{_sec_label('01', '5 站大盘 · 点国旗下钻')}</h2>"
                f"<p class='sp-muted'>点国旗下钻该站完整报告（{len(marketplaces)} 个 EU 站点）</p></div>")
    body.append("<div class='site-grid'>")
    for m in marketplaces:
        body.append(_render_site_card(m, scoring.get(m, {}), metrics_map[m]))
    body.append("</div></div></section>")

    # 3. 横向矩阵
    body.append(_render_cross_matrix(marketplaces, scoring, metrics_map))

    # 4. Top 3 跨站组合
    body.append(_render_top3_medals(marketplaces, scoring, metrics_map))

    # 5. 避坑
    body.append(_render_risk_panel(marketplaces))

    # 6. Chart.js 互动
    body.append(_chartjs_block(marketplaces, scoring, metrics_map))

    # 7. About + 数据透明
    body.append(_render_about(marketplaces, project))

    return sp.base_html(
        f"选品总览 · {project['niche']}",
        "\n".join(body),
        active="overview",
        niche=project["niche"],
        marketplaces=marketplaces,
    )


def render_site(marketplace: str, cfg: dict) -> str:
    """渲染站点独立页 {marketplace}.html"""
    project = cfg["project"]
    scoring = sp.load_json(ROOT, "score/scoring.json")[marketplace]
    stats = sp.load_normalized(ROOT, marketplace, "market_research")
    brand = sp.load_normalized(ROOT, marketplace, "market_brand")
    product = sp.load_normalized(ROOT, marketplace, "market_product")
    price = sp.load_normalized(ROOT, marketplace, "market_price")
    rating = sp.load_normalized(ROOT, marketplace, "market_rating")
    country = sp.load_normalized(ROOT, marketplace, "market_seller-country")
    ebc = sp.load_normalized(ROOT, marketplace, "market_ebc")
    listing = sp.load_normalized(ROOT, marketplace, "market_listing-date")
    kw = sp.load_normalized(ROOT, marketplace, "keyword_research")
    # V3.1 · 竞品毛利率 + 叶子节点链路（之前遗漏导致 NameError）
    comp_raw = sp.load_normalized(ROOT, marketplace, "competitor_lookup")
    competitors = comp_raw.get("competitors", []) if isinstance(comp_raw, dict) else []
    pnode_raw = sp.load_json(ROOT, f"raw/{marketplace}/product_node.json")
    pnode_top = (pnode_raw.get("items", [{}])[0] if isinstance(pnode_raw, dict) and pnode_raw.get("items") else pnode_raw) if pnode_raw else {}

    flag = sp.flag_emoji(marketplace)

    body = []

    # Hero 区域
    body.append("<section class='hero'>")
    body.append("<div class='wrap'>")
    body.append(f"<div class='hero-eyebrow'>{flag} {marketplace.lower()}.amazon.com</div>")
    body.append(f"<h1>{sp.MARKETPLACE_NAME.get(marketplace, marketplace)} · <span class='brand-orange'>{project['niche']}</span></h1>")
    body.append(f"<p class='hero-sub'>{_html.escape(scoring.get('summary_zh', ''))}</p>")
    body.append("<div class='hero-chips'>")
    body.append(f"<span class='chip'>方向 <strong>{scoring['direction']}</strong></span>")
    body.append(f"<span class='chip'>综合分 <strong>{scoring['weighted_total']:.1f}</strong></span>")
    body.append(f"<span class='chip'>{_tier_badge(scoring['tier'])}</span>")
    body.append("</div></div></section>")

    # V3.1.1 · 细切完整画像（cnstudio 风格：10 stat cards + 6 Chart.js 图 + 3 表）
    # 旧 section（KPI 卡片 / 六维评分卡 / CR10+价格 / 评分+上架时间 / 卖家来源+TOP10 ASIN / 关键词速览）
    # 已全部删除，其数据已搬入新画像区域。
    # V3.1.1 修复：图表横纵坐标全部按常识——
    #   - 评分分布：横轴=评分带，纵轴=销量占比（原"横向条形图"违反常识，已改竖向）
    #   - 价格带：横轴=价格带，纵轴=占比
    #   - 上架时间：横轴=时间窗口，纵轴=占比
    #   - CR10 对比：横轴=类别（品牌/商品），纵轴=CR10%
    body.append(_render_subcategory_profile(
        marketplace, project, scoring, stats, brand, product, price, rating, country, kw, listing, comp_raw,
    ))

    # V3.1 · 竞品毛利率快照（来自 competitor_lookup.json）
    if competitors and competitors[0].get("asin") != "B0NODATA":
        comp_html = ("<p class='sp-muted'>数据源：competitor_lookup.json · 估算成本已扣 FBA 履约费与头程。"
                     "毛利率 ≥ 35% 为优质空间，&lt; 25% 慎入。</p>"
                     "<div class='matrix-wrap'><table class='matrix'>"
                     "<thead><tr><th>ASIN</th><th>标题</th><th>价格</th><th>估算成本</th>"
                     "<th>FBA Fee</th><th>估算毛利率</th></tr></thead><tbody>")
        for c in competitors[:10]:
            m = c.get("estimatedMarginPct", 0)
            cls = "sp-good" if m >= 0.35 else ("sp-bad" if m < 0.25 else "")
            comp_html += (f"<tr><td class='mono'>{c.get('asin','?')}</td>"
                          f"<td class='sp-muted'>{(c.get('title','') or '')[:50]}…</td>"
                          f"<td class='price'>${c.get('priceUsd', 0):.0f}</td>"
                          f"<td>${c.get('estimatedCostUsd', 0):.0f}</td>"
                          f"<td>${c.get('fbaFeeUsd', 0):.0f}</td>"
                          f"<td class='{cls}'><b>{m*100:.1f}%</b></td></tr>")
        comp_html += "</tbody></table></div>"
        body.append("<section>")
        body.append("<div class='wrap'>")
        body.append("<div class='sec-head'>"
                    "<h2>💰 竞品毛利率快照（V3.1 新增 · 来自 competitor_lookup）</h2></div>")
        body.append(comp_html)
        body.append("</div></section>")
    else:
        body.append("<section><div class='wrap'><div class='sp-muted'>⚠️ "
                    f"该站点 competitor_lookup.json 未拉取到有效数据（可能 API 错误）。"
                    f"详细诊断见 <a href='{marketplace}_needs.html'>用户需求页</a>。</div></div></section>")

    # V3.1 · 叶子节点链路（来自 product_node.json）
    if pnode_top.get("nodeLabelPath"):
        pn_html = (f"<p>当前细切的叶子节点链路："
                   f"<span class='mono'>{pnode_top.get('nodeLabelPath','')}</span></p>"
                   f"<p>叶子节点 ID：<span class='mono'>{pnode_top.get('nodeIdPath','')}</span></p>")
        body.append("<section class='alt-bg'><div class='wrap'>"
                    "<div class='sec-head'><h2>🌿 叶子节点链路（V3.1 新增 · 来自 product_node）</h2></div>"
                    + pn_html + "</div></section>")

    # V3.1.1 · 底部「Chart.js 互动图表」section 已删除（其 4 图与上方细切画像
    # 区域里的 CR10 对比 / 卖家国别 / 评分分布 / TOP 10 ASIN 重复，按用户要求清理）

    return sp.base_html(
        f"{sp.MARKETPLACE_NAME.get(marketplace, marketplace)} · {project['niche']}",
        "\n".join(body),
        active="site",
        niche=project["niche"],
        marketplaces=cfg["marketplaces"],
        current_mp=marketplace,
    )


def main() -> None:
    cfg = sp.load_config(ROOT)
    out_dir = cfg["output"]["dir"]
    # 总览
    overview_html = render_overview(cfg)
    p1 = sp.write_html(ROOT, os.path.join(out_dir, cfg["output"]["index_file"]), overview_html)
    print(f"[ok] {p1}")
    # 各站点
    for m in cfg["marketplaces"]:
        html_text = render_site(m, cfg)
        p = sp.write_html(ROOT, os.path.join(out_dir, f"{m}.html"), html_text)
        print(f"[ok] {p}")


if __name__ == "__main__":
    main()