"""
sp_render_kwneeds.py
====================
SOP V3.1 STEP 8 · 渲染脚本 4/4
功能：关键词机会页 {marketplace}_kwneeds.html（cnstudio 风格）
      SKILL 26 · 高转化长尾筛选表
      SKILL 20 · 流量分散型蓝海词筛选表
输入：raw/keyword_mine.json + raw/keyword_research.json
输出：output/{marketplace}_kwneeds.html

V3.1 调整：
  - 完全按 DeepSeek 链接里的标准输出表格模板重写：
      SKILL 26：关键词 / 搜索量(月) / 购买量 / 购买率 / 标题密度 / 机会评分 / 建议行动
      SKILL 20：关键词 / 搜索量(月) / 点击垄断率 / 供需比 / 机会评分 / 建议行动
  - 删除原 SKILL 23（低质高销）相关代码。
  - 调用 keyword_mine / keyword_research 等 MCP 工具时，优先用 keywordList 数组参数
    一次查多词（参见 sp_fetch_data.py 改造），减少 token 消耗。
"""
from __future__ import annotations
import os
import sys
import json as _json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)


# V3.1 · Skill 核心逻辑（数据驱动版，filter 直接作用于归一化后的字段）
SKILL_CORE = {
    "26": "高转化长尾 · titleDensity ≤ 5 AND purchasesRate > 5% · Listing 标题/广告长尾词",
    "20": "流量分散蓝海 · search > 5000 AND monopolyClickRate < 50% · 避开头部垄断",
}


def _skill_callout(skill_id: str, extra: str = "") -> str:
    return (
        "<div class='sp-skill-callout'>"
        f"<strong>Skill {skill_id}</strong> · 核心逻辑：{SKILL_CORE.get(skill_id, '—')}"
        f"<div class='skill-core-logic'>📐 {extra}</div>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# SKILL 26 · 高转化长尾
# ---------------------------------------------------------------------------
def _skill26_long_tail(miner_items: list) -> list:
    """titleDensity ≤ 5 AND purchasesRate > 5% → Listing 标题/广告长尾词。"""
    out = []
    for k in miner_items:
        td = k.get("titleDensity") or 100
        pr = k.get("purchasesRate") or 0
        if td > 5 or pr <= 0.05:
            continue
        s = k.get("search") or 0
        p = k.get("purchases") or 0
        # 机会评分：5 = 搜索>5000 + 购买率>8%；4 = 搜索>2000；3 = 其余
        if s > 5000 and pr > 0.08:
            score = 5
        elif s > 2000 and pr > 0.06:
            score = 4
        else:
            score = 3
        action = (f"Listing 标题埋入 + 精准广告投放（搜索 {s:,}，购买率 {pr*100:.1f}%）"
                  if score >= 4 else
                  f"广告长尾词测试（搜索 {s:,}，购买率 {pr*100:.1f}%）")
        out.append({
            "keyword": k.get("keyword", "—"),
            "search": s,
            "purchases": p,
            "asinCount": k.get("asinCount", 0),
            "purchasesRate": pr,
            "titleDensity": td,
            "score": score,
            "action": action,
        })
    out.sort(key=lambda x: (-x["score"], -x["purchases"]))
    return out[:15]


def _render_skill26_table(items: list) -> str:
    if not items:
        return ('<p class="sp-muted">📭 该站数据未拉取成功或规则无命中（titleDensity ≤ 5 '
                'AND purchasesRate &gt; 5%）。</p>')
    head = ("<th>关键词</th><th>搜索量(月)</th><th>购买量</th><th>ASIN数</th>"
            "<th>购买率</th><th>标题密度</th><th>机会评分（1~5）</th><th>建议行动</th>")
    rows = ""
    for it in items:
        score_cls = "sp-good" if it["score"] >= 4 else ""
        rows += (
            "<tr>"
            f"<td><strong>{sp._esc(it['keyword'])}</strong></td>"
            f"<td><b>{it['search']:,}</b></td>"
            f"<td>{it['purchases']:,}</td>"
            f"<td>{it['asinCount']}</td>"
            f"<td class='sp-good'>{it['purchasesRate']*100:.1f}%</td>"
            f"<td>{it['titleDensity']:.1f}%</td>"
            f"<td class='{score_cls}'><b>{it['score']}</b></td>"
            f"<td>{sp._esc(it['action'])}</td>"
            "</tr>"
        )
    return (f"<div class='matrix-wrap'><table class='matrix'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
            + _skill_callout("26",
                "触发条件：maxTitleDensity ≤ 5 AND minPurchasesRate > 5% · "
                "MCP 调用：keyword_mine --keywordList kw1,kw2,kw3 数组参数"))


# ---------------------------------------------------------------------------
# SKILL 20 · 流量分散型蓝海词
# ---------------------------------------------------------------------------
def _skill20_blue_ocean(miner_items: list) -> list:
    """search > 5000 AND monopolyClickRate < 50% → 流量分散型蓝海词。"""
    out = []
    for k in miner_items:
        s = k.get("search") or 0
        mcr = k.get("monopolyClickRate") or 0
        if s <= 5000 or mcr >= 0.5:
            continue
        sdr = k.get("supplyDemandRatio") or 0
        # 机会评分：5 = 搜索>10K + 垄断<30% + 供需比<5；4 = 其余
        if s > 10_000 and mcr < 0.3 and sdr < 5:
            score = 5
        elif s > 8000 and mcr < 0.4:
            score = 4
        else:
            score = 3
        if score == 5:
            action = "**首选切入**：高搜索 + 低垄断 + 供需宽松，Listing + 广告同步布局"
        elif score == 4:
            action = "可切入：搜索量充足，避开头部 ASIN 垄断，差异化主图 + 标题"
        else:
            action = "观察：垄断/竞争仍偏紧，待差异化方案明确后切入"
        out.append({
            "keyword": k.get("keyword", "—"),
            "search": s,
            "purchases": k.get("purchases", 0),
            "monopolyClickRate": mcr,
            "supplyDemandRatio": sdr,
            "score": score,
            "action": action,
        })
    out.sort(key=lambda x: (-x["score"], -x["search"]))
    return out[:15]


def _render_skill20_table(items: list) -> str:
    if not items:
        return ('<p class="sp-muted">📭 该站数据未拉取成功或规则无命中（search &gt; 5000 '
                'AND monopolyClickRate &lt; 50%）。</p>')
    head = ("<th>关键词</th><th>搜索量(月)</th><th>购买量</th><th>点击垄断率</th>"
            "<th>供需比</th><th>机会评分（1~5）</th><th>建议行动</th>")
    rows = ""
    for it in items:
        score_cls = "sp-good" if it["score"] >= 4 else ""
        mcr_cls = "sp-good" if it["monopolyClickRate"] < 0.3 else ("sp-bad" if it["monopolyClickRate"] >= 0.5 else "")
        rows += (
            "<tr>"
            f"<td><strong>{sp._esc(it['keyword'])}</strong></td>"
            f"<td><b>{it['search']:,}</b></td>"
            f"<td>{it['purchases']:,}</td>"
            f"<td class='{mcr_cls}'>{it['monopolyClickRate']*100:.0f}%</td>"
            f"<td>{it['supplyDemandRatio']:.1f}</td>"
            f"<td class='{score_cls}'><b>{it['score']}</b></td>"
            f"<td>{sp._esc(it['action'])}</td>"
            "</tr>"
        )
    return (f"<div class='matrix-wrap'><table class='matrix'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
            + _skill_callout("20",
                "触发条件：minSearch > 5000 AND maxMonopolyClickRate < 50% · "
                "MCP 调用：keyword_mine --keywordList 数组参数批量拉取"))


# ---------------------------------------------------------------------------
# 渲染入口
# ---------------------------------------------------------------------------
def render(marketplace: str, cfg: dict) -> str:
    project = cfg["project"]
    miner = sp.load_normalized(ROOT, marketplace, "keyword_mine")
    miner_items = miner.get("mined", []) if isinstance(miner, dict) else []

    skill26 = _skill26_long_tail(miner_items)
    skill20 = _skill20_blue_ocean(miner_items)

    flag = sp.flag_emoji(marketplace)
    sections = []
    period_chip = ("<span class='chip'>📅 数据周期 · 月粒度 · "
                   "search = searches · purchaseRate = purchases / search</span>")
    sections.append(
        f"<section class='hero'><div class='wrap'>"
        f"<div class='hero-eyebrow'>{flag} {marketplace.lower()}.amazon.com · 关键词机会</div>"
        f"<h1>{sp.MARKETPLACE_NAME.get(marketplace, marketplace)} · "
        f"<span class='brand-orange'>{project['niche']}</span></h1>"
        f"<p class='hero-sub'>Skill 26 高转化长尾 + Skill 20 流量分散蓝海 · {period_chip}</p></div></section>"
    )

    s26_html = _render_skill26_table(skill26)
    sections.append(sp.section("🎯 Skill 26 · 高转化长尾筛选表", s26_html))

    s20_html = _render_skill20_table(skill20)
    sections.append(sp.section("🌐 Skill 20 · 流量分散型蓝海词筛选表", s20_html, alt=True))

    return sp.base_html(f"{marketplace} · 关键词机会 · {project['niche']}",
                        "\n".join(sections), active="kw", niche=project["niche"],
                        marketplaces=cfg["marketplaces"],
                        current_mp=marketplace)


def main() -> None:
    cfg = sp.load_config(ROOT)
    for m in cfg["marketplaces"]:
        html_text = render(m, cfg)
        p = sp.write_html(ROOT, f"output/{m}_kwneeds.html", html_text)
        print(f"[ok] {p}")


if __name__ == "__main__":
    main()
