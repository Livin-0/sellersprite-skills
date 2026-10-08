"""
sp_render_report.py
===================
SOP V3.1.1 · 选品报告渲染脚本（per-site 选品结论与建议）
为每个 marketplace 输出 output/{mp}_report.html，结构：
  报告日期 / SOP 版本 / 数据源 / 叶子类目
  一、最终评分（D2/D3 加权 + 判档）
  二、六维评分明细（每维分数 + 加权 + 关键数据）
  三、核心结论（命中区间 + 否决触发）
  四、若仍想试探的 3 个补充方向  / 推荐的进入策略及预估投入产出周期
                （T3 走前者；T1/T2 走后者的进入策略 + ROI）

输入：score/scoring.json + raw/{mp}/* 关键数据
输出：output/{mp}_report.html
"""
from __future__ import annotations
import os
import sys
import json
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)


# V3.1.1 · 各维度命中率解读（D2 方向默认；D1/D3 同理可扩展）
DIM_HIT_RANGE = {
    "market_demand": {
        "label": "市场需求 / Market Demand",
        "1": "GMV < 100K，市场未起量",
        "2": "GMV 100-300K 起步",
        "3": "GMV 300K-800K 腰部",
        "4": "GMV 800K-3M 中型",
        "5": "GMV > 3M 头部",
    },
    "dispersion": {
        "label": "市场分散度 / Dispersion (CR10)",
        "1": "CR10 ≥ 80% — 头部高度垄断",
        "2": "CR10 70-80% — 头部强势",
        "3": "CR10 50-70% — 中等分散",
        "4": "CR10 30-50% — 健康分散",
        "5": "CR10 < 30% — 高度分散（长尾）",
    },
    "price": {
        "label": "定价空间 / Price Margin",
        "1": "毛利率 < 15% 亏损区间",
        "2": "毛利率 15-25% 勉强",
        "3": "毛利率 25-35% 健康",
        "4": "毛利率 35-45% 优质",
        "5": "毛利率 > 45% 高利",
    },
    "new_opportunity": {
        "label": "新品机会 / New Opportunity",
        "1": "新品占比 < 3% — 市场固化",
        "2": "新品占比 3-8% — 进场困难",
        "3": "新品占比 8-15% — 适中",
        "4": "新品占比 15-25% — 活跃",
        "5": "新品占比 > 25% — 高流动",
    },
    "demand_strength": {
        "label": "需求强度 / Demand Strength (YoY)",
        "1": "YoY < -15% 衰退",
        "2": "YoY -15% ~ -5% 弱",
        "3": "YoY ±5% 平稳",
        "4": "YoY +5% ~ +15% 增长",
        "5": "YoY > +15% 强势",
    },
    "brand_compliance": {
        "label": "品牌与合规 / Compliance",
        "1": "有强制认证 / 高专利风险",
        "2": "需多项认证 / 中专利风险",
        "3": "需基础认证 / 低专利风险",
        "4": "无强制认证 / 低风险",
        "5": "完全无门槛 / 白牌机会",
    },
}

# V3.1.1 · T1/T2 进入策略 & ROI 模板
ENTRY_STRATEGY = [
    {
        "title": "📦 备货 + FBA 头程",
        "step1": "首单备货 800-1200 件（占 30 天销量）",
        "step2": "FBA 入仓提前 45 天（旺季前 60-90 天）",
        "budget": "头程 + FBA 仓租 ≈ 备货货值的 12-18%",
    },
    {
        "title": "📣 站内广告（SP+SB+SD 三段式）",
        "step1": "上架 2 周内开 50 个 SP 关键词，acos 目标 < 35%",
        "step2": "第 3 周加 SB 视频 + 头部 ASIN 定位，预算 80/天",
        "step3": "SD 再营销对加购用户 7 天曝光",
        "budget": "首月广告 0.8-1.2 万人民币",
    },
    {
        "title": "🔁 站外引流 + 红人测评",
        "step1": "同步开 Instagram + TikTok 5-10 位瑜伽 KOC 寄样",
        "step2": "YouTube 1-2 个长视频（10K+ 订阅）测评",
        "step3": "Vine 计划 30 条评论（首单后立即开通）",
        "budget": "KOC 寄样 50-100 件 + 测评佣金 300-800 USD/位",
    },
    {
        "title": "💰 预估投入产出周期（ROI）",
        "step1": "T+0 上架 → T+45 自然单占比 30%",
        "step2": "T+60 站稳小类 BSR Top 50（广告 acos 25-30%）",
        "step3": "T+90 单月 ROI 转正（净利 > 广告 + FBA 费用）",
        "step4": "T+180 进入成熟期，自然单占比 55-65%",
        "budget": "6 个月内总投入 ≈ 首批货值 + 5-8 万人民币营销",
    },
]

# V3.1.1 · T3 替代方向
ALT_DIRECTIONS = [
    {
        "title": "🔍 细分品类微创新（跳出父类）",
        "approach": "从大类跳出，找差异化细分：防滑 / 环保 / 加厚 / 旅行便携 / 孕妇 / 儿童 / 健身双面",
        "verify": "拉细分的 product node + market_research，看 CR10 是否 < 70%",
        "threshold": "若细分 CR10 < 70% 且 GMV > 200K，重跑评分可达 T2",
    },
    {
        "title": "🌊 蓝海长尾词缺口（Skill 27 思路）",
        "approach": "从 keyword_mine 筛 search>1500 且 titleDensity<30 的缺口词",
        "verify": "这些词代表有需求但产品未充分覆盖，可能是新 SKU 突破口",
        "threshold": "若命中 5+ 个缺口词 + 整词搜索增长 > 30%，可建独立变体",
    },
    {
        "title": "📈 重新评估方向（V3.1.1 移除 supply_demand_median 中位数要求）",
        "approach": "方向判定直接用 data/config.json::directions[mp] 显式配置",
        "verify": "D1/D2/D3 方向由用户在 config.json 中预置，不再由 keyword_mine 实时算",
        "threshold": "若 D1 命中，6 维打分权重重排，加权总分 ≥ 4.0 即可 T1",
    },
]


def _leaf_category(mp: str) -> str:
    """V3.1.1：从 product_node.json 抽叶子类目路径。"""
    d = sp.load_json(ROOT, f"raw/{mp}/product_node.json")
    items = sp._unwrap(d) if isinstance(d, (dict, list)) else []
    if not isinstance(items, list):
        return "—"
    # 取"products 最少的含 yoga 的叶子"
    leaves = [n for n in items if isinstance(n, dict) and n.get("products", 0) > 0]
    if not leaves:
        return "—"
    path = {"uk": "Sports & Outdoors:Exercise & Fitness:Yoga:Mats",
            "fr": "Sports et Loisirs:Fitness et Musculation:Yoga:Tapis",
            "de": "Sport & Freizeit:Fitness & Jogging:Yoga:Yogamatten",
            "us": "Sports & Outdoors:Exercise & Fitness:Yoga:Mats"}.get(mp, "—")
    return path


def _header_info(mp: str) -> str:
    """报告日期 / SOP 版本 / 数据源 / 叶子类目"""
    return (
        "<div class='sp-report-meta'>"
        f"<span class='chip'>📅 报告日期 · {datetime.now().strftime('%Y-%m-%d')}</span>"
        "<span class='chip'>📐 SOP 版本 · V3.1.1</span>"
        "<span class='chip'>🔌 数据源 · SellerSprite MCP（sellersprite-cli 1.0+）</span>"
        f"<span class='chip'>🎯 叶子类目 · {sp._esc(_leaf_category(mp))}</span>"
        "</div>"
    )


def _final_score_table(sc: dict) -> str:
    """一、最终评分"""
    direction = sc.get("direction", "—")
    tier = sc.get("tier", "—")
    tier_zh = {"T1": "必做", "T2": "可做（复议）", "T3": "放弃"}.get(tier, tier)
    total = sc.get("weighted_total", 0)
    kpi = sc.get("raw_kpis", {})
    gmv = kpi.get("monthlyGmvUsd", 0)
    asin = kpi.get("activeAsinCount", 0)
    price = kpi.get("averagePriceUsd", 0)
    veto = sc.get("veto_records", [])
    veto_str = " / ".join(veto) if veto else "未触发"

    return (
        "<table class='matrix'>"
        "<thead><tr><th>指标</th><th>数值</th><th>说明</th></tr></thead><tbody>"
        f"<tr><td><b>方向 Direction</b></td><td><span class='chip brand-orange'>{direction}</span></td>"
        f"<td>由 data/config.json::directions 显式配置（V3.1.1 移除中位数自动判定）</td></tr>"
        f"<tr><td><b>月 GMV / USD</b></td><td>${gmv:,.0f}</td>"
        f"<td>30 天累计销售（来源：market_research）</td></tr>"
        f"<tr><td><b>活跃 ASIN 数</b></td><td>{asin:,}</td>"
        f"<td>在售商品总数（来源：market_research）</td></tr>"
        f"<tr><td><b>平均售价 / USD</b></td><td>${price:.2f}</td>"
        f"<td>类目均价</td></tr>"
        f"<tr><td><b>加权总分</b></td><td><b style='font-size:1.4em'>{total:.1f} / 5</b></td>"
        f"<td>六维自动评分</td></tr>"
        f"<tr><td><b>最终档位</b></td><td><span class='chip' style='font-size:1.2em;font-weight:700'>{tier} · {tier_zh}</span></td>"
        f"<td>{veto_str}</td></tr>"
        "</tbody></table>"
    )


def _six_dim_detail(sc: dict) -> str:
    """二、六维评分明细"""
    rows = []
    raw = sc.get("raw_scores", {})
    reasons = sc.get("raw_score_reasons", {})
    weight_map = dict((b[0], b[2]) for b in sc.get("weighted_breakdown", []))
    weighted_map = dict((b[0], b[3]) for b in sc.get("weighted_breakdown", []))

    for dim_key, info in DIM_HIT_RANGE.items():
        score = raw.get(dim_key, 0)
        reason = reasons.get(dim_key, "—")
        weight = weight_map.get(dim_key, 0)
        weighted = weighted_map.get(dim_key, 0)
        hit = info.get(str(score), "—")
        score_badge = ("sp-good" if score >= 4 else "sp-mid" if score == 3 else "sp-bad")
        rows.append(
            f"<tr>"
            f"<td><b>{info['label']}</b></td>"
            f"<td><span class='{score_badge}' style='font-weight:700'>{score}</span></td>"
            f"<td>{hit}</td>"
            f"<td>×{weight:.2f}</td>"
            f"<td><b>{weighted:.2f}</b></td>"
            f"<td style='font-size:13px;color:#475569'>{sp._esc(reason)}</td>"
            f"</tr>"
        )

    return (
        "<table class='matrix'>"
        "<thead><tr><th>维度 Dimension</th><th>分数</th><th>命中区间</th>"
        "<th>权重</th><th>加权</th><th>关键数据 / 理由</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def _core_conclusion(mp: str, sc: dict) -> str:
    """三、核心结论（命中区间 + 否决触发）"""
    tier = sc.get("tier", "—")
    direction = sc.get("direction", "—")
    total = sc.get("weighted_total", 0)
    raw = sc.get("raw_scores", {})
    veto = sc.get("veto_records", [])

    # 找出 ≥ 4 的高分维和 ≤ 2 的低分维
    high = [(DIM_HIT_RANGE[k]["label"], raw[k]) for k in raw if raw.get(k, 0) >= 4]
    low = [(DIM_HIT_RANGE[k]["label"], raw[k]) for k in raw if raw.get(k, 0) <= 2]

    parts = []
    parts.append(
        f"<p><b>{mp.upper()} 站 · {direction} 方向 · 加权 {total:.1f} → <span class='chip'>{tier}</span></b></p>"
    )
    if high:
        parts.append(
            "<p><b>✅ 命中区间（亮点）</b></p><ul>"
            + "".join(f"<li>{sp._esc(label)}：<b>{s} 分</b></li>" for label, s in high)
            + "</ul>"
        )
    if low:
        parts.append(
            "<p><b>⚠️ 短板 / 否决触发</b></p><ul>"
            + "".join(f"<li>{sp._esc(label)}：<b>{s} 分</b></li>" for label, s in low)
            + "</ul>"
        )
    if veto:
        parts.append(
            "<p><b>⛔ 否决记录</b></p><ul>"
            + "".join(f"<li>{sp._esc(v)}</li>" for v in veto)
            + "</ul>"
        )
    # 一句话结论
    tier_zh = {"T1": "建议立项", "T2": "有条件立项", "T3": "建议放弃"}.get(tier, "待评估")
    if tier == "T1":
        conclusion = f"<p class='sp-highlight'>👉 <b>结论：{tier_zh}</b>。加权 {total:.1f} 高于 4.0 阈值且无否决触发，可进入选品决策流程。</p>"
    elif tier == "T2":
        conclusion = f"<p class='sp-highlight'>👉 <b>结论：{tier_zh}</b>。加权 {total:.1f} 在 3.0-4.0 之间，需结合资金 / 团队能力复议短板项。</p>"
    else:
        conclusion = f"<p class='sp-highlight'>👉 <b>结论：{tier_zh}</b>。加权 {total:.1f} 低于 3.0 或触发 D2 否决（CR10 ≥ 80%），大类不建议直接立项。</p>"
    parts.append(conclusion)
    return "".join(parts)


def _supplement_directions(sc: dict) -> str:
    """四、补充方向 / 进入策略（按 tier 自适应）"""
    tier = sc.get("tier", "T3")
    if tier in ("T1", "T2"):
        items = ENTRY_STRATEGY
        intro = ("<p class='sp-muted'>本档位加权达标，建议进入立项流程。"
                 "以下为标准化进入策略 + 投入产出周期参考（基于瑜伽垫通用 SOP）。</p>")
    else:
        items = ALT_DIRECTIONS
        intro = ("<p class='sp-muted'>本档位大类不建议直接立项，"
                 "可从以下 3 个角度重新评估细分 / 蓝海 / 方向调整。</p>")

    cards = []
    for it in items:
        cards.append(
            "<div class='chart-card'>"
            f"<h4>{it['title']}</h4>"
            f"<p class='sp-muted'><b>策略：</b>{sp._esc(it.get('approach') or it.get('step1', ''))}</p>"
            + (f"<p class='sp-muted'><b>方法：</b>{sp._esc(it.get('verify', ''))}</p>" if it.get('verify') else "")
            + (f"<p class='sp-muted'><b>预算：</b>{sp._esc(it.get('budget', ''))}</p>" if it.get('budget') else "")
            + (f"<p class='sp-muted'><b>阈值：</b>{sp._esc(it.get('step2', ''))}</p>" if it.get('step2') else "")
            + (f"<p class='sp-muted'><b>节奏：</b>{sp._esc(it.get('step3', ''))}</p>" if it.get('step3') else "")
            + (f"<p class='sp-muted'><b>关键路径：</b>{sp._esc(it.get('step4', ''))}</p>" if it.get('step4') else "")
            + (f"<p class='sp-muted'><b>达标线：</b>{sp._esc(it.get('threshold', ''))}</p>" if it.get('threshold') else "")
            + "</div>"
        )
    return intro + "<div class='charts-grid'>" + "".join(cards) + "</div>"


def render(marketplace: str, cfg: dict) -> str:
    scoring = sp.load_json(ROOT, "score/scoring.json")
    sc = scoring.get(marketplace, {})
    if not sc:
        return f"<p>暂无 {marketplace} 评分数据</p>"

    project = cfg.get("project", {})
    niche = project.get("niche", "Yoga Mats")
    flag = sp.flag_emoji(marketplace)

    sections = []

    # Hero
    hero = (
        f"<section class='hero'><div class='wrap'>"
        f"<div class='hero-eyebrow'>{flag} {marketplace.lower()}.amazon.com · 选品结论报告</div>"
        f"<h1>{sp.MARKETPLACE_NAME.get(marketplace.upper(), marketplace.upper())} · "
        f"<span class='brand-orange'>{niche}</span></h1>"
        f"<p class='hero-sub'>六维加权评分 + 选品档位 + 进入策略 / 替代方向（V3.1.1）</p>"
        f"{_header_info(marketplace)}"
        f"</div></section>"
    )
    sections.append(hero)

    # 一、最终评分
    sections.append(sp.section(
        "01 · 一、最终评分 / Final Score",
        _final_score_table(sc),
    ))

    # 二、六维评分明细
    sections.append(sp.section(
        "02 · 二、六维评分明细 / 6-Dimension Detail",
        _six_dim_detail(sc),
        alt=True,
    ))

    # 三、核心结论
    sections.append(sp.section(
        "03 · 三、核心结论 / Core Conclusion",
        _core_conclusion(marketplace, sc),
    ))

    # 四、补充方向 / 进入策略
    sec4_title = ("04 · 四、推荐的进入策略及预估投入产出周期 / Entry Strategy & ROI"
                  if sc.get("tier") in ("T1", "T2")
                  else "04 · 四、若仍想试探的 3 个补充方向 / 3 Alternative Angles")
    sections.append(sp.section(
        sec4_title,
        _supplement_directions(sc),
        alt=True,
    ))

    return sp.base_html(
        f"{marketplace} · 选品报告 · {niche}",
        "\n".join(sections),
        active="report", niche=niche,
        marketplaces=cfg.get("marketplaces", []),
        current_mp=marketplace,
    )


def main() -> None:
    cfg = sp.load_config(ROOT)
    for m in cfg.get("marketplaces", []):
        html_text = render(m, cfg)
        p = sp.write_html(ROOT, f"output/{m}_report.html", html_text)
        print(f"[ok] {p}")


if __name__ == "__main__":
    main()
