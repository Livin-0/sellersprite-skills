"""
sp_render_needs.py
==================
SOP V3.1 STEP 8 · 渲染脚本 3/4
功能：用户需求洞察页 {marketplace}_needs.html（cnstudio 风格）
      SKILL 24 · 差评痛点聚类与改良机会表
      SKILL 27 · 变体缺口机会表
输入：raw/review_*.json + raw/competitor_lookup.json + raw/asin_predict_*.json
      + raw/keyword_mine.json（用于 SKILL 27 缺口验证）
输出：output/{marketplace}_needs.html

V3.1 调整：
  - 完全按 DeepSeek 链接里的标准输出表格模板重写：
      SKILL 24：痛点主题 / 代表差评关键词 / 提及频率 / 严重程度 / 根因推断 / 改良方案 / 转化为卖点文案
      SKILL 27：变体属性维度 / 热销变体 / 滞销或低分变体 / 销量差异倍数 / 评分差异 / 缺失的属性组合 / 关键词搜索量验证 / 机会评分 / 建议行动
  - 删除原 SKILL 23（低质高销）相关代码（已迁移到其它子页或被覆盖）。
  - 触发 SKILL 24 / 27 / 11 时若调用 keyword_mine 等 MCP 工具支持 keywordList 数组参数，
    优先以数组形式批量查询（参见 sp_fetch_data.py 改造）。
"""
from __future__ import annotations
import os
import sys
import glob
import json as _json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)


# V3.1 · Skill 核心逻辑小字（与 README V3.1 附录同步）
SKILL_CORE = {
    "24": "差评聚类 · sentiment_cluster(review_1to3) · 提及率 > 20% → 痛点主题",
    "27": "变体拆解 · variant_sales_skew > 10x OR attribute_combination_missing → 缺口",
}


def _skill_callout(skill_id: str, extra: str = "") -> str:
    return (
        "<div class='sp-skill-callout'>"
        f"<strong>Skill {skill_id}</strong> · 核心逻辑：{SKILL_CORE.get(skill_id, '—')}"
        f"<div class='skill-core-logic'>📐 {extra}</div>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# 数据加载（统一从 raw/ 读，兼容 _error / 空文件）
# ---------------------------------------------------------------------------
def _load_reviews(marketplace: str) -> dict:
    _rd = os.path.join(ROOT, "raw", marketplace)
    reviews = {"marketplace": marketplace, "reviews": []}
    review_err = False
    for p in sorted(glob.glob(os.path.join(_rd, "review_*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            d = _json.load(f)
        if isinstance(d, dict) and "_error" in d:
            review_err = True
            continue
        rev_list = d.get("reviews") if isinstance(d, dict) else None
        if rev_list:
            for r in rev_list:
                r.setdefault("asin", r.get("asin") or os.path.basename(p).replace("review_", "").replace(".json", ""))
                reviews["reviews"].append(r)
    if not reviews["reviews"]:
        reviews = {
            "marketplace": marketplace, "reviews": [],
            "_empty_reason": "review_*.json 全部 _error（marketplace code 大小写）" if review_err
                             else "无评论数据",
        }
    return reviews


def _load_competitors(marketplace: str) -> list:
    comp_list = []
    for p in sorted(glob.glob(os.path.join(ROOT, "raw", marketplace, "competitor_*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            d = _json.load(f)
        if isinstance(d, dict) and "_error" in d:
            continue
        items = d.get("competitors") if isinstance(d, dict) else None
        if items:
            comp_list.extend(items)
    return comp_list


def _load_predictions(marketplace: str) -> list:
    pred_list = []
    for p in sorted(glob.glob(os.path.join(ROOT, "raw", marketplace, "asin_predict_*.json"))):
        with open(p, "r", encoding="utf-8") as f:
            d = _json.load(f)
        if isinstance(d, dict) and "_error" in d:
            continue
        items = d.get("predictions") if isinstance(d, dict) else None
        if items:
            pred_list.extend(items)
    return pred_list


# ---------------------------------------------------------------------------
# SKILL 24 · 差评痛点聚类与改良机会表
# ---------------------------------------------------------------------------
def _skill24_pain_points(reviews: dict) -> list:
    """聚合差评的 oneToThreeStar themes → 排序，取前 6 个高频痛点。"""
    pain_points = []
    for r in reviews["reviews"]:
        for t in r.get("oneToThreeStar", []) or []:
            pain_points.append({
                "theme": t.get("theme", "—"),
                "mentions": int(t.get("mentions", 0)),
                "share": float(t.get("share", 0)),
                "asin": r.get("asin", "—"),
                "title": r.get("title", "—"),
                "sample_quotes": t.get("quotes", []) or [],
            })
    pain_points.sort(key=lambda x: -x["mentions"])
    return pain_points[:6]


# 改良方案 / 卖点文案 的简易映射（基于 theme 关键词，避免硬编码业务词）
_THEME_TEMPLATES = {
    "smell":    ("气味",   "选择低气味 TPE / NBR 材质 · 出厂前通风 48h",
                "**Odor-Free TPE Material – Safe for Indoor Practice**"),
    "odour":    ("气味",   "选择低气味 TPE / NBR 材质 · 出厂前通风 48h",
                "**Odor-Free TPE Material – Safe for Indoor Practice**"),
    "slip":     ("防滑",   "表面激光刻纹 + 双面防滑 · 湿态静摩擦系数 ≥ 0.7",
                "**Dual-Sided Non-Slip Surface – Laser-Etched Grip**"),
    "grip":     ("防滑",   "表面激光刻纹 + 双面防滑 · 湿态静摩擦系数 ≥ 0.7",
                "**Dual-Sided Non-Slip Surface – Laser-Etched Grip**"),
    "thickness":("厚度",   "主推 8mm 双层结构 · 兼顾支撑与便携",
                "**8mm Dual-Layer Padding – Joint Support + Portability**"),
    "thin":     ("厚度",   "主推 8mm 双层结构 · 兼顾支撑与便携",
                "**8mm Dual-Layer Padding – Joint Support + Portability**"),
    "flatten":  ("平整度", "卷装改为平叠 + 配重纸盒 · 出厂压 72h",
                "**Compression-Packed Flat – No Curling, Ready to Use**"),
    "curl":     ("平整度", "卷装改为平叠 + 配重纸盒 · 出厂压 72h",
                "**Compression-Packed Flat – No Curling, Ready to Use**"),
    "durable":  ("耐久",   "双层复合工艺 · 抗撕裂 ≥ 30N",
                "**Reinforced Dual-Layer Build – Tear-Resistant for Daily Use**"),
    "tear":     ("耐久",   "双层复合工艺 · 抗撕裂 ≥ 30N",
                "**Reinforced Dual-Layer Build – Tear-Resistant for Daily Use**"),
    "size":     ("尺寸",   "提供 173/183cm 加长版 + 旅行折叠款",
                "**Multiple Sizes Available – 173 / 183cm & Travel Sizes**"),
    "color":    ("外观",   "采用环保水性油墨 · 抗 UV 褪色",
                "**Eco Water-Based Ink – Fade-Resistant, Vibrant Colors**"),
}


def _lookup_template(theme: str):
    t = theme.lower()
    for k, v in _THEME_TEMPLATES.items():
        if k in t:
            return v
    return ("通用改良", "按差评描述定位根因 → 改良方案回流到产品 Spec",
            "**Improved by Customer Feedback – Continuous Iteration**")


def _render_skill24_table(pain_points: list) -> str:
    if not pain_points:
        return ""
    head = ("<th>痛点主题</th><th>代表差评关键词（原文）</th><th>提及频率</th>"
            "<th>严重程度（1~5）</th><th>根因推断</th><th>改良方案</th>"
            "<th>转化为卖点文案（Bullet Point）</th>")
    rows = ""
    total_mentions = sum(p["mentions"] for p in pain_points) or 1
    for p in pain_points:
        category, fix, bullet = _lookup_template(p["theme"])
        quotes = " / ".join(f"“{q}”" for q in p["sample_quotes"][:3]) or "—"
        # 严重程度：提及率 × 5 向上取整，并按 mentions 体量微调
        severity = max(1, min(5, round(p["share"] * 5 + (1 if p["mentions"] > 50 else 0))))
        sev_cls = "sp-bad" if severity >= 4 else ("sp-good" if severity <= 2 else "")
        rate_pct = p["share"] * 100
        rows += (
            "<tr>"
            f"<td><strong>{sp._esc(p['theme'])}</strong><br>"
            f"<span class='sp-muted' style='font-size:11px;'>{category}</span></td>"
            f"<td class='sp-muted'>{sp._esc(quotes)}</td>"
            f"<td><b>{rate_pct:.0f}%</b><br>"
            f"<span class='sp-muted' style='font-size:11px;'>{p['mentions']}/{total_mentions} 条</span></td>"
            f"<td class='{sev_cls}'><b>{severity}</b></td>"
            f"<td>差评高频词触发“{category}”类问题，结合 ASIN {sp._esc(p['asin'])} 客诉归纳</td>"
            f"<td>{sp._esc(fix)}</td>"
            f"<td><code style='font-size:11px;'>{sp._esc(bullet)}</code></td>"
            "</tr>"
        )
    return (f"<div class='matrix-wrap'><table class='matrix'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
            + _skill_callout("24",
                "提及率 = theme_mentions / total_negative_reviews · 触发条件 ≥ 20% · "
                "严重程度 = round(share × 5 + mentions>50 ? 1 : 0)"))


# ---------------------------------------------------------------------------
# SKILL 27 · 变体缺口机会表
# ---------------------------------------------------------------------------
def _skill27_variant_gaps(competitors: list, miner_items: list) -> list:
    """基于 asin_predict 月销 + review 评分，找出"高销量与低分/低销变体"的属性缺口。
    若有 keyword_mine 长尾词（高搜索 + 低标题密度），加入"缺失的属性组合"列做交叉验证。"""
    # 取每个父体下的子变体销量差异（同一 group=asin_predict title 同一段）
    groups: dict = {}
    for c in competitors:
        asin = c.get("asin", "—")
        title = (c.get("title") or "").lower()
        # 简单归一化：用 title 前 30 字符做 group key
        gk = asin[:6]
        if gk not in groups:
            groups[gk] = {"samples": [], "asin": asin, "title": c.get("title", "—")}
        groups[gk]["samples"].append({
            "asin": asin, "title": c.get("title", "—"),
            "monthlySales": c.get("amzUnit") or c.get("monthlySales") or 0,
            "rating": c.get("rating") or 0,
        })
    # 用 miner 的长尾词作为"缺失属性组合"的候选项
    long_tail = [k for k in miner_items
                 if (k.get("search") or 0) > 1500 and (k.get("titleDensity") or 100) < 30]
    long_tail.sort(key=lambda k: -(k.get("search") or 0))

    # 维度枚举：尺寸 / 厚度 / 材质 / 长度 / 颜色（基于 title 关键词）
    DIM_KEYS = [
        ("尺寸/厚度", ["6mm", "8mm", "10mm", "15mm", "thin", "extra thick"]),
        ("长度/宽度", ["183cm", "173cm", "72 inch", "extra long", "travel"]),
        ("材质/表面", ["tpe", "nbr", "rubber", "eco", "natural", "cotton"]),
        ("颜色/图案", ["grey", "black", "pink", "purple", "blue", "neutral"]),
    ]

    gaps = []
    for dim_name, dim_keys in DIM_KEYS:
        # 从 competitors 标题里找匹配的样本
        hits = [c for c in competitors
                if any(k in (c.get("title") or "").lower() for k in dim_keys)]
        if not hits and not long_tail:
            continue
        # 取销量最高 vs 最低作差异倍数
        with_sales = [c for c in hits
                      if (c.get("amzUnit") or c.get("monthlySales") or 0) > 0]
        if len(with_sales) >= 2:
            sorted_by_sales = sorted(with_sales,
                                     key=lambda c: c.get("amzUnit") or c.get("monthlySales") or 0)
            low, high = sorted_by_sales[0], sorted_by_sales[-1]
            hi_sales = high.get("amzUnit") or high.get("monthlySales") or 0
            lo_sales = low.get("amzUnit") or low.get("monthlySales") or 1
            skew = round(hi_sales / lo_sales, 1)
            hi_str = f"{hi_sales:,}/月"
            lo_str = f"{lo_sales:,}/月"
        else:
            skew, hi_str, lo_str = "—", "—", "—"
            low = high = None

        # 评分差异
        with_rating = [c for c in hits if c.get("rating")]
        if len(with_rating) >= 2:
            rmin = min(c["rating"] for c in with_rating)
            rmax = max(c["rating"] for c in with_rating)
            rating_diff = round(rmax - rmin, 1)
        else:
            rating_diff = "—"

        # 缺失的属性组合：取 miner 中第一个匹配维度但未在竞品标题出现的关键词
        in_title = " ".join((c.get("title") or "").lower() for c in hits)
        missing_kw = next(
            (k for k in long_tail
             if any(dk in k["keyword"].lower() for dk in dim_keys)
             and k["keyword"].lower() not in in_title),
            None,
        )
        if missing_kw:
            missing_combo = missing_kw["keyword"]
            search_val = int(missing_kw.get("search") or 0)
            search_str = f"“{missing_combo}” 月搜 {search_val:,}"
        else:
            search_str = "—（无 miner 数据交叉）"

        # 机会评分
        if isinstance(skew, (int, float)) and skew >= 10:
            score = 5
        elif isinstance(skew, (int, float)) and skew >= 5:
            score = 4
        elif missing_kw:
            score = 4 if (missing_kw.get("search") or 0) > 5000 else 3
        else:
            score = 3

        # 建议行动
        if missing_kw and high and low:
            action = (f"开发 {missing_combo} 变体（介于「{high.get('title','—')[:18]}」"
                      f"与「{low.get('title','—')[:18]}」之间），补齐缺口")
        elif missing_kw:
            action = f"主推 {missing_combo} 长尾词，验证需求后定向补款"
        else:
            action = "保持监控，待 miner 数据补全后重评"

        gaps.append({
            "dim": dim_name,
            "hot": high.get("title", "—") if high else "—",
            "hot_sales": hi_str,
            "cold": low.get("title", "—") if low else "—",
            "cold_sales": lo_str,
            "skew": skew,
            "rating_diff": rating_diff,
            "missing": search_str,
            "score": score,
            "action": action,
        })
    return gaps


def _render_skill27_table(gaps: list) -> str:
    if not gaps:
        return ('<p class="sp-muted">📭 该站数据未拉取成功或规则无命中。</p>')
    head = ("<th>变体属性维度</th><th>热销变体</th><th>滞销/低分变体</th>"
            "<th>销量差异倍数</th><th>评分差异</th>"
            "<th>缺失的属性组合（缺口）</th><th>关键词搜索量验证</th>"
            "<th>机会评分（1~5）</th><th>建议行动</th>")
    rows = ""
    for g in gaps:
        skew_cls = "sp-bad" if isinstance(g["skew"], (int, float)) and g["skew"] >= 10 else ""
        score_cls = "sp-good" if g["score"] >= 4 else ("sp-bad" if g["score"] <= 2 else "")
        rows += (
            "<tr>"
            f"<td><strong>{sp._esc(g['dim'])}</strong></td>"
            f"<td class='sp-muted'>{sp._esc(g['hot'])}<br><b>{g['hot_sales']}</b></td>"
            f"<td class='sp-muted'>{sp._esc(g['cold'])}<br><b>{g['cold_sales']}</b></td>"
            f"<td class='{skew_cls}'><b>{g['skew']}×</b></td>"
            f"<td>{g['rating_diff']}</td>"
            f"<td class='sp-muted'>{sp._esc(g['missing'].split('（')[0])}</td>"
            f"<td><b>{g['missing']}</b></td>"
            f"<td class='{score_cls}'><b>{g['score']}</b></td>"
            f"<td>{sp._esc(g['action'])}</td>"
            "</tr>"
        )
    return (f"<div class='matrix-wrap'><table class='matrix'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
            + _skill_callout("27",
                "缺口判定 = max(variant_sales) / min(variant_sales) > 10 OR attribute_missing = TRUE · "
                "关键词搜索量用 keyword_mine 的 keywordList 数组参数批量校验"))


# ---------------------------------------------------------------------------
# 渲染入口
# ---------------------------------------------------------------------------
def render(marketplace: str, cfg: dict) -> str:
    project = cfg["project"]
    reviews = _load_reviews(marketplace)
    competitors = _load_competitors(marketplace)
    predictions = _load_predictions(marketplace)
    miner = sp.load_normalized(ROOT, marketplace, "keyword_mine")
    miner_items = miner.get("mined", []) if isinstance(miner, dict) else []

    pain_points = _skill24_pain_points(reviews)
    variant_gaps = _skill27_variant_gaps(competitors, miner_items)

    flag = sp.flag_emoji(marketplace)
    sections = []

    # Hero
    sections.append(
        f"<section class='hero'><div class='wrap'>"
        f"<div class='hero-eyebrow'>{flag} {marketplace.lower()}.amazon.com · 用户需求洞察</div>"
        f"<h1>{sp.MARKETPLACE_NAME.get(marketplace, marketplace)} · "
        f"<span class='brand-orange'>{project['niche']}</span></h1>"
        f"<p class='hero-sub'>Skill 24 差评聚类 + Skill 27 变体拆解 · "
        f"<span class='chip'>仅作佐证，不参与维度 1-5 计分</span></p></div></section>"
    )

    # SKILL 24
    if not pain_points:
        empty_reason = reviews.get("_empty_reason", "无评论数据")
        s24_html = (f'<p class="sp-muted" style="background:#fff7ed;border:1px dashed #f59e0b;'
                    f'padding:12px 16px;border-radius:6px;">'
                    f'⚠️ Skill 24 暂无数据：{empty_reason}。<br>'
                    f'修复：使用 <code>sellersprite trend_review --marketplace UK</code> '
                    f'重拉（注意 marketplace 必须大写）。</p>')
    else:
        s24_html = _render_skill24_table(pain_points)
    sections.append(sp.section("🩺 Skill 24 · 差评痛点聚类与改良机会表", s24_html))

    # SKILL 27
    s27_html = _render_skill27_table(variant_gaps)
    sections.append(sp.section("🧩 Skill 27 · 变体缺口机会表", s27_html, alt=True))

    return sp.base_html(f"{marketplace} · 用户需求 · {project['niche']}",
                        "\n".join(sections), active="needs", niche=project["niche"],
                        marketplaces=cfg["marketplaces"],
                        current_mp=marketplace)


def main() -> None:
    cfg = sp.load_config(ROOT)
    for m in cfg["marketplaces"]:
        html_text = render(m, cfg)
        p = sp.write_html(ROOT, f"output/{m}_needs.html", html_text)
        print(f"[ok] {p}")


if __name__ == "__main__":
    main()
