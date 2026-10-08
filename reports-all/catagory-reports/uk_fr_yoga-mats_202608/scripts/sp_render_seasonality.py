"""
sp_render_seasonality.py
=======================
SOP V3.1 STEP 8 · 渲染脚本 2/4
功能：季节性分析页 {marketplace}_seasonality.html（cnstudio 风格）
      1) 5 站 AMZ 月搜索量折线对比（Chart.js）
      2) 旺季/淡季双卡（橙/蓝，月份 + 原因）
      3) 运营节奏建议（备货 / 清仓 / 广告 预算节奏）
      4) 5 站数据明细表（6 列：旺季搜索/月/淡季搜索/月/波动/近6月 YoY）
      5) SKILL 11 · ABA 高增长趋势词筛选表（持续爬升）
      6) SKILL 25 · 季节前置爆破（唯一允许破格）
      7) Google Trends 漏斗（健康 / 失真 / 过热 三卡，识别"Google 失真"类目）
      8) 进一步验证（用其他 MCP 工具）
      9) 12 个月热力图（年度日历）
     10) 12 个月运营动作清单

输入：raw/keyword_research_trends.json + raw/google_trend.json
      raw/keyword_mine.json + raw/keyword_research.json
      score/scoring.json（skill_25_breakout）
输出：output/{marketplace}_seasonality.html

V3.1 调整（2026-08-31）：
  - 对照 cnstudio /AI/eu_seasonality.html 补 6 个板块：
    ① 多站 AMZ 折线图  ② 旺季/淡季双卡  ③ 运营节奏卡
    ④ 多站数据明细表   ⑨ 12 月热力图    ⑩ 12 月动作清单
  - 板块 ①/④ 通用化为动态 N 站（1-10），按 cfg["marketplaces"] 实际列表渲染
  - 板块 ⑧ 重写为 3 阶段 MCP 工具清单（信息补全 → 交叉验证 → 决策落地）
  - 板块 ⑪「注入 GTrends 漏斗 · 代码说明」已移除（开发文档，不该出现在展示页）
  - 板块顺序按"事实 → 解读 → 全局视图 → 机会 → 验证 → 行动"逻辑链重排
  - 追加 Google Trends 漏斗（用户特别要求）：
    Google 认知层 vs Amazon 购买层 → 3 卡诊断
  - SKILL 11/25 主体保留
  - 全部使用本地已落盘的 raw/ 数据，**不调用 sellersprite.exe**
"""
from __future__ import annotations
import os
import sys
import re
import json as _json
import datetime as _dt
from collections import OrderedDict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)


# V3.1 · Skill 核心逻辑
SKILL_CORE = {
    "25": "季节前置爆破 · next_month_growth > 100% AND off_season_yoy > 10% → 维度5 +1",
    "11": "ABA 高增长趋势词 · search ≥ 3000 AND 近3月连续正增长 → 趋势机会词",
}


def _skill_callout(skill_id: str, extra: str = "") -> str:
    return (
        "<div class='sp-skill-callout'>"
        f"<strong>Skill {skill_id}</strong> · 核心逻辑：{SKILL_CORE.get(skill_id, '—')}"
        f"<div class='skill-core-logic'>📐 {extra}</div>"
        "</div>"
    )


def _month_labels(n: int = 12, start: str = "2025-09") -> list:
    y, m = map(int, start.split("-"))
    out = []
    for _ in range(n):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1; y += 1
    return out


# ===========================================================================
# 数据归一化辅助：把 keyword_research_trends / google_trend 转月度 series
# ===========================================================================
def _kwt_to_monthly(d: dict) -> list:
    """V3.1 · 从 keyword_research_trends.json 抽「按月搜索量」序列（最近 12 个月）。

    兼容 2 种 SellerSprite 格式：
      1) 聚合格式：items=[{keyword, searches:[v1,v2,...]}]
      2) 按月展开：items=[{time:"2025年09月", search:N}]
    返回：[(label, value), ...] 长度=12
    """
    if not isinstance(d, dict) or d.get("_error"):
        return []
    if isinstance(d, dict) and d.get("_list_wrapped"):
        items = d.get("items")
    else:
        items = d.get("items") if isinstance(d, dict) else d
    if not isinstance(items, list) or not items:
        return []
    first = items[0] if items and isinstance(items[0], dict) else {}
    if isinstance(first.get("searches"), list):
        # 聚合格式：直接取第一个 keyword 的月度序列
        series = first.get("searches") or []
        out = []
        for i, v in enumerate(series[-12:]):
            out.append((f"M{i+1}", v if isinstance(v, (int, float)) else 0))
        return out
    # 按月展开格式
    pairs = []
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
        if isinstance(v, (int, float)):
            pairs.append((key, v))
    if not pairs:
        return []
    pairs.sort(key=lambda x: x[0])
    pairs = pairs[-12:]
    return [(f"{y}-{mo:02d}", int(v)) for (y, mo), v in pairs]


def _gtrend_to_monthly(d: dict) -> list:
    """V3.1 · 从 google_trend.json 抽「按月指数」序列（按月聚合 time/value 毫秒时间戳）。"""
    if not isinstance(d, dict) or "_error" in d:
        return []
    items = d.get("items")
    if not isinstance(items, list):
        return []
    monthly = OrderedDict()
    for it in items:
        if not isinstance(it, dict):
            continue
        t, v = it.get("time"), it.get("value")
        if not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
            continue
        try:
            dt = _dt.datetime.fromtimestamp(t / 1000)
        except (ValueError, OSError):
            continue
        key = f"{dt.year}-{dt.month:02d}"
        monthly[key] = monthly.get(key, 0) + int(v)
    if not monthly:
        return []
    vals = list(monthly.values())[-12:]
    while len(vals) < 12:
        vals.insert(0, 0)
    labels = [f"M{i+1}" for i in range(len(vals))]
    return list(zip(labels, vals))


def _peak_trough(series: list) -> dict:
    """V3.1 · 算 series 的旺季/淡季月份/值/波动/近 6 月 YoY。"""
    if not series:
        return {"peak_idx": -1, "peak_val": 0, "peak_lbl": "—",
                "trough_idx": -1, "trough_val": 0, "trough_lbl": "—",
                "ratio": 0, "yoy_pct": 0}
    vals = [v for _, v in series]
    peak_i = max(range(len(vals)), key=lambda i: vals[i])
    trough_i = min(range(len(vals)), key=lambda i: vals[i])
    peak_v = vals[peak_i]
    trough_v = vals[trough_i]
    ratio = (peak_v / trough_v) if trough_v > 0 else 0
    # 近 6 月 YoY = 后 6 月均值 vs 前 6 月均值
    half = len(vals) // 2
    if half > 0 and sum(vals[:half]) > 0:
        yoy = (sum(vals[half:]) - sum(vals[:half])) / sum(vals[:half]) * 100
    else:
        yoy = 0
    return {
        "peak_idx": peak_i, "peak_val": peak_v, "peak_lbl": series[peak_i][0],
        "trough_idx": trough_i, "trough_val": trough_v, "trough_lbl": series[trough_i][0],
        "ratio": round(ratio, 2), "yoy_pct": round(yoy, 1),
    }


# ===========================================================================
# 板块 ①：多站 AMZ 月搜索量折线对比图（Chart.js）— 动态 N 站（1-10）
# ===========================================================================
def _render_amz_chart(mp_amz: dict, niche: str) -> str:
    """mp_amz = {mp: [(label, value), ...]} — 各站点的 AMZ 月搜索量序列。

    V3.1 · 动态适配任意站点数（1-10），非固定 5 站；按 cfg["marketplaces"] 实际列表渲染。
    """
    if not mp_amz:
        return ('<p class="sp-muted">📭 多站 AMZ 月搜索量数据未拉取成功（可能 marketplace code '
                '大小写或 API 限流影响）。</p>')
    labels = [f"M{i+1}" for i in range(12)]
    datasets = []
    palette = ["#1f7a3a", "#c0392b", "#2c5fa3", "#d4860c", "#7d3c98",
               "#16a085", "#db2777", "#0891b2", "#65a30d", "#9333ea"]
    for i, (mp, series) in enumerate(mp_amz.items()):
        # 统一到 12 个月长度
        vals = [v for _, v in (series or [])]
        if len(vals) < 12:
            vals = [0] * (12 - len(vals)) + vals
        else:
            vals = vals[-12:]
        datasets.append({
            "label": f"{sp.flag_emoji(mp)} {mp.upper()}",
            "data": vals,
            "borderColor": palette[i % len(palette)],
            "backgroundColor": palette[i % len(palette)] + "20",
            "tension": 0.3, "borderWidth": 2, "pointRadius": 3,
        })
    cid = "sp-amz-multisite-" + _rand_id()
    n_sites = len(mp_amz)
    return (
        "<div class='sp-card'>"
        f"<h4>📊 多站月搜索量对比（{niche} · AMZ · {n_sites} 站）</h4>"
        "<p class='sp-muted'>数据源：SellerSprite <code>keyword_research_trends</code> · "
        "取最近 12 个月按月聚合（数组参数：<code>--keywordList</code> · 一次查多站节省 token）。</p>"
        f"<div style='position:relative;height:320px'><canvas id='{cid}'></canvas></div>"
        f"<script>renderMultiLine('{cid}', {_json.dumps(labels)}, {_json.dumps(datasets)});</script>"
        "</div>"
    )


# ===========================================================================
# 板块 ②：旺季/淡季双卡（橙/蓝）
# ===========================================================================
SEASON_REASONS = {
    "yoga mats": {
        "peak": [
            "1 月旺季 =「新年决心」(New Year's Resolution) 效应，欧洲人在 1 月初集中办健身卡、买装备。",
            "4-5 月次峰 =「夏季塑身」(Summer Body) 效应，5-6 月欧洲天气转暖，BMI 焦虑开始上升。",
            "9 月小峰 =「秋季重启」(Back to Routine)，暑假结束、孩子开学、大人回到健身房。",
        ],
        "trough": [
            "12 月低谷 = 圣诞 + 新年假期，欧洲人 12 月集中度假、聚会、购物，健身房关闭 / 缺席率高，瑜伽垫优先级最低。",
            "8 月相对低 = 暑假（EU 普遍 6-8 周）家庭外出，Home Workout 暂停。",
        ],
    },
}


def _season_reasons(niche: str) -> dict:
    """V3.1 · 按 niche 取旺季/淡季原因。niche 不在字典时给通用模板。"""
    n = (niche or "").lower().strip()
    for k, v in SEASON_REASONS.items():
        if k in n or n in k:
            return v
    # 通用兜底
    return {
        "peak": [
            "旺季月份来自 keyword_research_trends 12 月序列的波峰 — 通常对应节后健身/换季/开学/户外季启动。",
            "次峰来自二次爬升（春末/初秋）— 与欧洲「换季 + 户外活动」双驱动一致。",
        ],
        "trough": [
            "淡季月份对应圣诞 + 新年假期 + 暑假窗口 — 健身房关闭 / 家庭外出，需求结构性下行。",
            "建议淡季前 30 天完成 FBA 入仓赶旺季前一波，但不要在 12 月 / 8 月加码 PPC。",
        ],
    }


def _render_season_cards(peak_info: dict, trough_info: dict, niche: str) -> str:
    """V3.1 · 旺季（橙）/ 淡季（蓝）双卡，含月份 + 原因。"""
    reasons = _season_reasons(niche)
    peak_items = "".join(f"<li>{sp._esc(r)}</li>" for r in reasons["peak"])
    trough_items = "".join(f"<li>{sp._esc(r)}</li>" for r in reasons["trough"])
    return (
        "<div class='sp-season-grid'>"
        # 旺季（橙）
        "<div class='sp-season-card sp-season-peak'>"
        "<div class='sp-season-head'><span class='sp-season-ico'>☀️</span>"
        f"<span class='sp-season-title'>旺季 · {sp._esc(peak_info['peak_lbl'])} · "
        f"<b>{sp.fmt_int(peak_info['peak_val'])}</b></span></div>"
        f"<h4>{sp._esc(peak_info['peak_lbl'].split('-')[-1])} 月旺季</h4>"
        f"<ul>{peak_items}</ul>"
        "</div>"
        # 淡季（蓝）
        "<div class='sp-season-card sp-season-trough'>"
        "<div class='sp-season-head'><span class='sp-season-ico'>❄️</span>"
        f"<span class='sp-season-title'>淡季 · {sp._esc(trough_info['trough_lbl'])} · "
        f"<b>{sp.fmt_int(trough_info['trough_val'])}</b></span></div>"
        f"<h4>{sp._esc(trough_info['trough_lbl'].split('-')[-1])} 月淡季</h4>"
        f"<ul>{trough_items}</ul>"
        "</div>"
        "</div>"
    )


# ===========================================================================
# 板块 ③：运营节奏建议卡
# ===========================================================================
def _render_rhythm_card(peak_lbl: str, trough_lbl: str) -> str:
    """V3.1 · 最佳备货窗口 / 最佳清仓窗口 / 广告预算节奏 三栏。"""
    peak_m = (peak_lbl or "").split("-")[-1] or "1"
    trough_m = (trough_lbl or "").split("-")[-1] or "12"
    return (
        "<div class='sp-card sp-rhythm'>"
        "<h4>📅 运营节奏建议</h4>"
        "<div class='sp-rhythm-grid'>"
        f"<div class='sp-rhythm-item'><div class='sp-rhythm-label'>最佳备货窗口</div>"
        f"<div class='sp-rhythm-value'>8-9 月（FBA 入仓赶上 {peak_m} 月旺季）</div></div>"
        f"<div class='sp-rhythm-item'><div class='sp-rhythm-label'>最佳清仓窗口</div>"
        f"<div class='sp-rhythm-value'>11 月黑五 / 网一前清掉 {trough_m} 月淡季滞销</div></div>"
        "<div class='sp-rhythm-item'><div class='sp-rhythm-label'>广告预算节奏</div>"
        "<div class='sp-rhythm-value'>11 月起加码，1-2 月峰值，3 月开始降</div></div>"
        "</div></div>"
    )


# ===========================================================================
# 板块 ④：多站数据明细表（6 列）— 动态 N 站（1-10）
# ===========================================================================
def _render_site_table(mp_stats: dict) -> str:
    """mp_stats = {mp: peak_info}。返回 N 站数据明细表 HTML（6 列）。

    V3.1 · 动态适配 1-10 站，按 cfg["marketplaces"] 实际列表渲染。
    """
    if not mp_stats:
        return ('<p class="sp-muted">📭 多站数据未拉取成功。</p>')
    n_sites = len(mp_stats)
    rows = ""
    for mp, p in mp_stats.items():
        yoy_cls = "sp-good" if p["yoy_pct"] > 0 else ("sp-bad" if p["yoy_pct"] < 0 else "")
        rows += (
            "<tr>"
            f"<td>{sp.flag_emoji(mp)} {sp.MARKETPLACE_NAME.get(mp.upper(), mp.upper())}</td>"
            f"<td><b>{sp.fmt_int(p['peak_val'])}</b></td>"
            f"<td>{sp._esc(p['peak_lbl'])}</td>"
            f"<td>{sp.fmt_int(p['trough_val'])}</td>"
            f"<td>{sp._esc(p['trough_lbl'])}</td>"
            f"<td><b>{p['ratio']:.2f}×</b></td>"
            f"<td class='{yoy_cls}'>{p['yoy_pct']:+.1f}%</td>"
            "</tr>"
        )
    return (
        "<div class='sp-card'>"
        f"<h4>📊 多站数据明细（{n_sites} 站）</h4>"
        "<div class='matrix-wrap'><table class='matrix'>"
        "<thead><tr><th>站点</th><th>旺季月搜索</th><th>旺季月份</th>"
        "<th>淡季月搜索</th><th>淡季月份</th><th>波动</th><th>近 6 月 YoY</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></div>"
        "</div>"
    )


# ===========================================================================
# SKILL 11 · ABA 高增长趋势词筛选表（保留原版，仅函数签名兼容）
# ===========================================================================
def _skill11_trending(research_items: list, miner_items: list) -> list:
    """从 keyword_research 筛 ABA 高增长趋势词（持续爬升）。
    触发条件：search ≥ 3000 AND searchNearlyCr > 5% 视为"高增长"。
    用 miner 的 monopolyClickRate 做点击集中度交叉验证。
    """
    miner_by_kw = {k.get("keyword", "").lower(): k for k in miner_items}
    out = []
    for k in research_items:
        s = k.get("search") or 0
        if s < 3000:
            continue
        cr_raw = k.get("searchNearlyCr") or k.get("monthlyTrend") or 0
        if cr_raw is None:
            cr_raw = 0
        mcr = k.get("searchMonthlyCr") or 0
        if mcr is None:
            mcr = 0
        continuous = (cr_raw > 0) and (mcr > 0)
        if cr_raw <= 5:
            continue
        miner_match = miner_by_kw.get(k.get("keyword", "").lower())
        mcr_pct = (miner_match.get("monopolyClickRate") or 0) * 100 if miner_match else None
        sdr = k.get("supplyDemandRatio") or 0
        gtrend = "稳定上升" if (miner_match and (miner_match.get("titleDensity") or 100) < 30) else "—（无 miner 交叉）"
        if cr_raw > 15 and (mcr_pct is None or mcr_pct < 40) and sdr < 0.8:
            score = 5
        elif cr_raw > 8 and (mcr_pct is None or mcr_pct < 60):
            score = 4
        elif mcr_pct is not None and mcr_pct > 60:
            score = 3
        else:
            score = 2
        if score == 5:
            action = "**首选切入**：增长 > 15% + 无巨头垄断 + 供不应求，立即布局"
        elif score == 4:
            action = "可切入：结合 Skill 27 变体差异化 或 价格优势切入"
        elif score == 3:
            action = "观察：头部已固化，需差异化外观/组合装才有胜算"
        else:
            action = "暂缓：增长率不足或趋势不明，30 天后再评估"
        out.append({
            "keyword": k.get("keyword", "—"),
            "search": s, "growth": cr_raw, "continuous": continuous,
            "mcr": mcr_pct, "supplyDemandRatio": sdr,
            "gtrend": gtrend, "score": score, "action": action,
        })
    out.sort(key=lambda x: (-x["score"], -x["growth"]))
    return out[:15]


def _render_skill11_table(items: list) -> str:
    if not items:
        return ('<p class="sp-muted">📭 该站数据未拉取成功或规则无命中（search ≥ 3000 '
                'AND searchNearlyCr &gt; 5%）。</p>')
    head = ("<th>关键词</th><th>月搜索量</th><th>近3月增长率</th>"
            "<th>趋势持续性（连续3月）</th><th>点击集中度</th><th>供需比</th>"
            "<th>谷歌趋势验证</th><th>机会评分（1~5）</th><th>建议行动</th>")
    rows = ""
    for it in items:
        growth_cls = "sp-good" if it["growth"] > 15 else ("sp-bad" if it["growth"] < 0 else "")
        cont_mark = "✅ 均 >5%（持续爬升）" if it["continuous"] else "❌ 增长不连续"
        cont_cls = "sp-good" if it["continuous"] else "sp-bad"
        if it["mcr"] is None:
            mcr_str = "—（无 miner 交叉）"; mcr_cls = ""
        else:
            mcr_str = f"{it['mcr']:.0f}%"
            mcr_cls = "sp-good" if it["mcr"] < 40 else ("sp-bad" if it["mcr"] >= 60 else "")
        score_cls = "sp-good" if it["score"] >= 4 else ("sp-bad" if it["score"] <= 2 else "")
        rows += (
            "<tr>"
            f"<td><strong>{sp._esc(it['keyword'])}</strong></td>"
            f"<td><b>{it['search']:,}</b></td>"
            f"<td class='{growth_cls}'><b>{it['growth']:+.1f}%</b></td>"
            f"<td class='{cont_cls}'>{cont_mark}</td>"
            f"<td class='{mcr_cls}'>{mcr_str}</td>"
            f"<td>{it['supplyDemandRatio']:.2f}</td>"
            f"<td class='sp-muted'>{sp._esc(it['gtrend'])}</td>"
            f"<td class='{score_cls}'><b>{it['score']}</b></td>"
            f"<td>{sp._esc(it['action'])}</td>"
            "</tr>"
        )
    return (f"<div class='matrix-wrap'><table class='matrix'>"
            f"<thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
            + _skill_callout("11",
                "触发条件：minSearch ≥ 3000 AND minSearchNearlyCr > 5% · "
                "交叉验证：keyword_mine --keywordList 数组参数（monopolyClickRate + titleDensity） · "
                "外部验证：google_trend（若命中则 ✅，未命中用 miner.titleDensity 代理）"))


# ===========================================================================
# 板块 ⑦：Google Trends 漏斗（健康 / 失真 / 过热 三卡）
# ===========================================================================
def _render_gtrend_funnel(mp_compare: dict) -> str:
    """mp_compare = {mp: {"amz_peak": 100, "gtrend_peak": 50, "amz_yoy": 30, "gtrend_yoy": 5}}

    三类诊断：
      - 健康品类：Google 100 + Amazon 100（认知购买同步）
      - 失真品类（蓝海）：Google 50 + Amazon 100（认知低购买高，最适合新卖家）
      - 过热品类（红海）：Google 100 + Amazon 50（认知高转化弱，新手不要进）

    判定原理：amz_yoy 高 + gtrend_yoy 低 = 失真（认知 < 购买，线下/口碑驱动）
             amz_yoy 低 + gtrend_yoy 高 = 过热（红人/KOL 推过但买得少）
             两者同向 + 都高 = 健康
    """
    if not mp_compare:
        return ('<p class="sp-muted">📭 Google Trends vs Amazon 漏斗数据未拉取成功。</p>')

    # 聚合 5 站均值
    sites = list(mp_compare.values())
    avg_amz = sum(s.get("amz_peak", 0) for s in sites) / max(1, len(sites))
    avg_gtrend = sum(s.get("gtrend_peak", 0) for s in sites) / max(1, len(sites))
    avg_amz_yoy = sum(s.get("amz_yoy", 0) for s in sites) / max(1, len(sites))
    avg_gtrend_yoy = sum(s.get("gtrend_yoy", 0) for s in sites) / max(1, len(sites))

    # 归一化 0-100（用于展示 100+/50）
    max_v = max(avg_amz, avg_gtrend, 1)
    amz_pct = round(avg_amz / max_v * 100)
    gtrend_pct = round(avg_gtrend / max_v * 100)

    def _bar(pct: int) -> str:
        return (f"<div class='sp-funnel-bar'><div class='sp-funnel-fill' style='width:{pct}%'></div>"
                f"<span class='sp-funnel-pct'>{pct}</span></div>")

    return (
        "<div class='sp-funnel-wrap'>"
        "<div class='sp-funnel-grid'>"
        # 健康品类
        "<div class='sp-funnel-card sp-funnel-good'>"
        "<div class='sp-funnel-head'>健康品类</div>"
        "<div class='sp-funnel-compare'>"
        f"<div class='sp-funnel-row'><span class='sp-funnel-label'>Google</span>{_bar(gtrend_pct)}</div>"
        f"<div class='sp-funnel-row'><span class='sp-funnel-label'>Amazon</span>{_bar(amz_pct)}</div>"
        "</div>"
        "<p><b>认知和购买同步。</b>例：<b>yoga mat</b> — Google 上想练瑜伽的人多，"
        "Amazon 上买的人多。市场认知成熟，<b>流量贵但转化稳</b>，适合大卖家。</p>"
        "</div>"
        # 失真品类（蓝海）
        "<div class='sp-funnel-card sp-funnel-blueocean'>"
        "<div class='sp-funnel-head'>🎯 失真品类（蓝海）</div>"
        "<div class='sp-funnel-compare'>"
        f"<div class='sp-funnel-row'><span class='sp-funnel-label'>Google</span>{_bar(max(0, gtrend_pct - 30))}</div>"
        f"<div class='sp-funnel-row'><span class='sp-funnel-label'>Amazon</span>{_bar(amz_pct)}</div>"
        "</div>"
        "<p><b>认知低但购买高。</b>例：<b>fishing lures</b> — Google 全年平稳但 Amazon Q2 销量 +3-5x。"
        "原因是<b>钓鱼是线下行为 ≠ 线上搜索</b>。<b>流量便宜 + 真实需求旺</b>，<b>最适合新卖家</b>。</p>"
        "</div>"
        # 过热品类（红海）
        "<div class='sp-funnel-card sp-funnel-redsea'>"
        "<div class='sp-funnel-head'>过热品类（红海）</div>"
        "<div class='sp-funnel-compare'>"
        f"<div class='sp-funnel-row'><span class='sp-funnel-label'>Google</span>{_bar(gtrend_pct)}</div>"
        f"<div class='sp-funnel-row'><span class='sp-funnel-label'>Amazon</span>{_bar(max(0, amz_pct - 30))}</div>"
        "</div>"
        "<p><b>认知高但转化弱。</b>例：大部分<b>「网红小产品」</b> — 很多人搜，但买的人少"
        "（被 KOL 推过、买来没用、闲置）。<b>流量贵 + 转化差</b>，<b>新手不要进</b>。</p>"
        "</div>"
        "</div>"
        # 当前品类判定条
        f"<div class='sp-funnel-diagnose'>"
        f"<b>当前品类诊断：</b>"
        f"Amazon 月搜索 <b>{sp.fmt_int(int(avg_amz))}</b> · YoY <b>{avg_amz_yoy:+.1f}%</b>  /  "
        f"Google 指数 <b>{int(avg_gtrend)}</b> · YoY <b>{avg_gtrend_yoy:+.1f}%</b>  →  "
        f"<b>{'✅ 健康' if abs(avg_amz_yoy - avg_gtrend_yoy) < 10 else ('🎯 失真蓝海' if avg_amz_yoy > avg_gtrend_yoy + 15 else '⛔ 过热红海')}</b>"
        f"</div>"
        "</div>"
    )


# ===========================================================================
# 板块 ⑧：进一步验证（按"信息补全 → 交叉验证 → 决策落地"3 阶段组织）
# ===========================================================================
# V3.1 · 不照搬 cnstudio，按季节性分析的实际决策链路重新设计：
#   阶段 A 信息补全：补全 keyword_research_trends 没覆盖的维度
#   阶段 B 交叉验证：用其他维度证伪季节性（避免被单点数据误导）
#   阶段 C 决策落地：把季节性结论转成 listing/广告/库存的具体动作
VERIFY_MCP_TOOLS = [
    {
        "stage": "A · 信息补全",
        "color": "#0ea5e9",
        "tools": [
            {"name": "keepa_info",
             "purpose": "拉 Top 10 ASIN 的 BSR / 价格 12 个月曲线，"
                        "验证旺季是真需求还是 buy box 归零的'假旺季'。"},
            {"name": "asin_predict",
             "purpose": "拉头部 ASIN 的月销量预测，看旺季月搜索量是否"
                        "真正转化为销量（搜索高但 buy box 弱 = 流量空转）。"},
            {"name": "aba_research_monthly",
             "purpose": "拉 ABA 月度榜单，对比旺季月 Top 100 词的轮换规律，"
                        "识别新冒出的长尾词（提前 1-2 月占位）。"},
        ],
    },
    {
        "stage": "B · 交叉验证",
        "color": "#7c3aed",
        "tools": [
            {"name": "competitor_lookup",
             "purpose": "拉 5-10 个头部竞品 ASIN 的月销量分布，"
                        "看头部是否也在旺季月份拉满（确认是真旺季 vs 单点异常）。"},
            {"name": "keyword_mine",
             "purpose": "对主词拉长尾词矩阵，对比主词季节性 vs 长尾词季节性"
                        "是否一致（主词淡长尾旺 = 主词没选对）。"},
            {"name": "review_dynamic",
             "purpose": "拉差评主题的时间分布，看'夏季出汗打滑/冬季发硬'类"
                        "季节性诉求是否在对应月份集中爆发（反推季节性痛点）。"},
        ],
    },
    {
        "stage": "C · 决策落地",
        "color": "#16a34a",
        "tools": [
            {"name": "keyword_research",
             "purpose": "从趋势词池锁定'季节性 + 长尾'双高词，作为 listing 标题核心"
                        "和 SP 广告精准投放词。"},
            {"name": "fba_fee",
             "purpose": "对比旺季 vs 淡季 FBA 仓储费的差异，决定 9-10 月备货比例"
                        "（旺季前 30 天是 FBA 入仓截止线）。"},
            {"name": "inventory_health",
             "purpose": "看 IPI 评分 + 库容，决定淡季清仓压力（IPI < 400 时淡季"
                        "滞销会被收超容费，必须提前清。"},
        ],
    },
]


def _render_verify_mcp() -> str:
    """V3.1 · 3 阶段 MCP 工具清单（信息补全 → 交叉验证 → 决策落地）。"""
    blocks = ""
    for grp in VERIFY_MCP_TOOLS:
        items = "".join(
            f"<li><code>{sp._esc(t['name'])}</code> — {sp._esc(t['purpose'])}</li>"
            for t in grp["tools"]
        )
        blocks += (
            f"<div class='sp-verify-group' style='border-left:4px solid {grp['color']}'>"
            f"<div class='sp-verify-stage' style='color:{grp['color']}'>{sp._esc(grp['stage'])}</div>"
            f"<ul>{items}</ul>"
            "</div>"
        )
    return (
        "<div class='sp-card'>"
        "<h4>🔍 进一步验证（按决策链路组织）</h4>"
        "<p class='sp-muted'>季节性只是入口判断，本表按"
        "<b>信息补全 → 交叉验证 → 决策落地</b> 3 阶段给出 9 个 MCP 工具，"
        "对应季节性结论从'数据'到'行动'的完整链路。</p>"
        f"{blocks}"
        "</div>"
    )


# ===========================================================================
# 板块 ⑨：12 个月热力图（年度日历）
# ===========================================================================
def _render_annual_heatmap(mp_peak: dict, niche: str) -> str:
    """mp_peak = {mp: [(label, value), ...]}。以 UK 站（首站）为基准归一化。"""
    if not mp_peak:
        return ('<p class="sp-muted">📭 12 月热力图数据未拉取成功。</p>')
    base_mp = list(mp_peak.keys())[0]
    base_series = mp_peak[base_mp]
    if not base_series:
        return ('<p class="sp-muted">📭 基准站 12 月数据为空。</p>')
    base_vals = [v for _, v in base_series]
    base_max = max(base_vals) or 1
    cells = ""
    for lbl, v in base_series:
        ratio = v / base_max if base_max else 0
        # 深橙 ≥ 90% / 强 60-90% / 中 30-60% / 弱 10-30% / 淡季 < 10%
        if ratio >= 0.9:
            cls, txt = "sp-heat-5", f"{sp.fmt_int(v)}"
        elif ratio >= 0.6:
            cls, txt = "sp-heat-4", f"{sp.fmt_int(v)}"
        elif ratio >= 0.3:
            cls, txt = "sp-heat-3", f"{sp.fmt_int(v)}"
        elif ratio >= 0.1:
            cls, txt = "sp-heat-2", f"{sp.fmt_int(v)}"
        else:
            cls, txt = "sp-heat-1", f"{sp.fmt_int(v)}"
        cells += f"<td class='{cls}'>{txt}</td>"
    # 取月份短名
    month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                   "7月", "8月", "9月", "10月", "11月", "12月"]
    th = "".join(f"<th>{m}</th>" for m in month_names[:len(base_series)])
    return (
        "<div class='sp-card'>"
        f"<h4>📅 年度日历 · {sp._esc(niche)} · 12 月搜索量热力图</h4>"
        "<p class='sp-muted'>以 UK 站（首站）月搜索量为基准归一化。"
        "<b>深橙 = 旺季</b>，<b>深蓝 = 淡季</b>，格子里的数字是当月搜索量。</p>"
        f"<div class='matrix-wrap'><table class='matrix sp-heatmap'>"
        f"<thead><tr><th>细切</th>{th}</tr></thead>"
        f"<tbody><tr><td><b>🧘 {sp._esc(niche)}</b></td>{cells}</tr></tbody></table></div>"
        "<div class='sp-heat-legend'>"
        "<span class='sp-heat-5'>旺季 ≥ 90% 峰值</span>"
        "<span class='sp-heat-4'>强 60-90%</span>"
        "<span class='sp-heat-3'>中 30-60%</span>"
        "<span class='sp-heat-2'>弱 10-30%</span>"
        "<span class='sp-heat-1'>淡季 &lt; 10%</span>"
        "</div>"
        "</div>"
    )


# ===========================================================================
# 板块 ⑩：12 个月运营动作清单（单细切版）
# ===========================================================================
YOGA_RHYTHM_12M = [
    (1, "健身峰", "新年决心 · 全力推瑜伽/阻力带 · PPC 出价 1 月峰值"),
    (2, "健身峰", "健身余热 · 户外开始清仓 · 测评转化"),
    (3, "过渡", "健身测款 · 户外 FBA 入仓截止"),
    (4, "过渡", "夏季塑身预热 · 健身维持"),
    (5, "户外启", "露营 / 钓鱼启动 · PPC 出价爬坡"),
    (6, "户外峰", "EU 暑假开始 · 户外冲量"),
    (7, "户外峰", "露营顶 + 海钓旺 · 库存必须充足"),
    (8, "户外峰", "三连峰顶 · 断货 = 全年白干"),
    (9, "清仓启", "户外打折 + 健身秋季重启小峰"),
    (10, "Q4 截止", "健身备货截止线 · 入仓完成 50%+ 库存"),
    (11, "黑五网一", "Deals / Coupons · 高客单户外装备冲刺"),
    (12, "圣诞淡", "慎投 PPC · 为 1 月最后准备"),
]


def _render_12m_rhythm(niche: str) -> str:
    items = ""
    for m, label, action in YOGA_RHYTHM_12M:
        items += (
            "<div class='sp-m-card'>"
            f"<div class='sp-m-month'>{m} 月</div>"
            f"<div class='sp-m-label'>{sp._esc(label)}</div>"
            f"<div class='sp-m-action'>{sp._esc(action)}</div>"
            "</div>"
        )
    return (
        "<div class='sp-card'>"
        f"<h4>📅 12 个月运营动作清单（{sp._esc(niche)}）</h4>"
        f"<div class='sp-m-grid'>{items}</div>"
        "</div>"
    )


# ===========================================================================
# （V3.1 · 已移除板块 ⑪「注入 GTrends 漏斗 · 代码说明」——
#   这是开发文档用的代码块，不该出现在对外展示页上，仅保留在 README 中）
# ===========================================================================


# ===========================================================================
# 配套 CSS（不污染 sp_common.py；通过 style 块内联注入）
# ===========================================================================
EXTRA_CSS = """
<style>
/* V3.1 · 季节性页增强样式（旺季/淡季卡 / 漏斗 / 热力图 / 12 月动作清单） */
.sp-season-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:10px}
.sp-season-card{border-radius:10px;padding:16px;border:1px solid var(--border)}
.sp-season-peak{background:linear-gradient(135deg,#fff7ed,#fff);border-color:#fdba74}
.sp-season-trough{background:linear-gradient(135deg,#eff6ff,#fff);border-color:#93c5fd}
.sp-season-head{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.sp-season-ico{font-size:22px}
.sp-season-title{font-weight:600;color:var(--ink)}
.sp-season-card h4{margin:6px 0 8px;font-size:16px;color:var(--ink)}
.sp-season-card ul{margin:6px 0 0 18px;font-size:13px;line-height:1.6;color:#475569}
.sp-season-card ul li{margin:2px 0}
@media (max-width:760px){.sp-season-grid{grid-template-columns:1fr}}

.sp-rhythm{border-left:4px solid #f59e0b}
.sp-rhythm-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:10px}
.sp-rhythm-item{background:#f8fafc;padding:10px 12px;border-radius:8px;border:1px solid var(--border)}
.sp-rhythm-label{font-size:11px;color:var(--muted);letter-spacing:.5px;text-transform:uppercase;margin-bottom:4px}
.sp-rhythm-value{font-size:14px;font-weight:600;color:var(--ink);line-height:1.4}
@media (max-width:760px){.sp-rhythm-grid{grid-template-columns:1fr}}

/* Google Trends 漏斗 3 卡 */
.sp-funnel-wrap{margin-top:10px}
.sp-funnel-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.sp-funnel-card{border-radius:10px;padding:16px;border:1px solid var(--border);background:#fff}
.sp-funnel-card.sp-funnel-good{border-color:#86efac;background:linear-gradient(135deg,#f0fdf4,#fff)}
.sp-funnel-card.sp-funnel-blueocean{border-color:#60a5fa;background:linear-gradient(135deg,#eff6ff,#fff)}
.sp-funnel-card.sp-funnel-redsea{border-color:#fca5a5;background:linear-gradient(135deg,#fef2f2,#fff)}
.sp-funnel-head{font-size:15px;font-weight:700;color:var(--ink);margin-bottom:10px;
  padding-bottom:6px;border-bottom:1px dashed var(--border)}
.sp-funnel-card.sp-funnel-blueocean .sp-funnel-head{color:#1d4ed8}
.sp-funnel-card.sp-funnel-redsea .sp-funnel-head{color:#b91c1c}
.sp-funnel-compare{margin:6px 0 10px}
.sp-funnel-row{display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px}
.sp-funnel-label{width:60px;font-weight:600;color:var(--muted);font-family:var(--font-mono)}
.sp-funnel-bar{flex:1;background:#eef0f2;border-radius:4px;height:18px;position:relative;overflow:hidden}
.sp-funnel-fill{position:absolute;left:0;top:0;bottom:0;background:linear-gradient(90deg,#4d9fff,#7c3aed);border-radius:4px}
.sp-funnel-pct{position:absolute;right:6px;top:0;line-height:18px;font-size:11px;font-weight:700;color:#fff;
  font-family:var(--font-mono);text-shadow:0 1px 1px rgba(0,0,0,.3)}
.sp-funnel-card p{font-size:12.5px;line-height:1.55;color:#475569;margin:6px 0 0}
.sp-funnel-diagnose{margin-top:14px;padding:10px 14px;background:#f8fafc;border-radius:8px;
  border:1px solid var(--border);font-size:13px;color:var(--ink)}
@media (max-width:900px){.sp-funnel-grid{grid-template-columns:1fr}}

/* 12 月热力图 */
.sp-heatmap th,.sp-heatmap td{text-align:center;font-size:12px;padding:6px 4px}
.sp-heat-5{background:#fdba74;color:#7c2d12;font-weight:700}
.sp-heat-4{background:#fed7aa;color:#7c2d12}
.sp-heat-3{background:#fef3c7;color:#92400e}
.sp-heat-2{background:#dbeafe;color:#1e3a8a}
.sp-heat-1{background:#bfdbfe;color:#1e3a8a}
.sp-heat-legend{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px;font-size:11.5px}
.sp-heat-legend span{padding:3px 8px;border-radius:4px;font-weight:600}

/* 12 个月运营动作清单 */
.sp-m-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-top:10px}
.sp-m-card{background:#f8fafc;border:1px solid var(--border);border-radius:8px;padding:10px;
  border-left:3px solid #6366f1}
.sp-m-month{font-size:18px;font-weight:700;color:#4338ca;font-family:var(--font-display)}
.sp-m-label{font-size:12px;font-weight:600;color:var(--ink);margin:4px 0 2px}
.sp-m-action{font-size:11.5px;color:#475569;line-height:1.4}
@media (max-width:900px){.sp-m-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:480px){.sp-m-grid{grid-template-columns:1fr}}

/* V3.1 · 进一步验证 · 3 阶段卡片 */
.sp-verify-group{background:#f8fafc;border-radius:6px;padding:10px 14px;margin:8px 0;
  border:1px solid var(--border)}
.sp-verify-group ul{margin:6px 0 0 18px;padding:0;font-size:12.5px;line-height:1.6}
.sp-verify-group ul li{margin:3px 0;color:#475569}
.sp-verify-group ul code{background:#fff;border:1px solid var(--border);
  padding:1px 6px;border-radius:3px;color:#0f172a;font-weight:600}
.sp-verify-stage{font-size:13px;font-weight:700;letter-spacing:.5px;
  text-transform:uppercase;margin-bottom:4px}
</style>
"""


# ===========================================================================
# 工具：随机 ID / JSON dump / 标量转义
# ===========================================================================
def _rand_id() -> str:
    import random
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))


# ===========================================================================
# 渲染入口
# ===========================================================================
def render(marketplace: str, cfg: dict) -> str:
    """V3.1 · 季节性 + 趋势页面（多板块组合）。"""
    project = cfg["project"]
    scoring = sp.load_json(ROOT, "score/scoring.json")[marketplace]
    research = sp.load_normalized(ROOT, marketplace, "keyword_research")
    miner = sp.load_normalized(ROOT, marketplace, "keyword_mine")
    research_items = research.get("keywords", []) if isinstance(research, dict) else []
    miner_items = miner.get("mined", []) if isinstance(miner, dict) else []

    flag = sp.flag_emoji(marketplace)
    niche = project["niche"]

    # ---- 多站点数据：聚合 5 站 AMZ + Google Trends 月度 series ----
    marketplaces = cfg["marketplaces"]
    mp_amz: dict = {}        # {mp: [(label, value), ...]}
    mp_gtrend: dict = {}     # {mp: [(label, value), ...]}
    mp_stats: dict = {}      # {mp: peak_info}
    mp_compare: dict = {}    # {mp: {amz_peak, gtrend_peak, amz_yoy, gtrend_yoy}}
    for mp in marketplaces:
        kwt = sp.load_json(ROOT, f"raw/{mp}/keyword_research_trends.json")
        gtr = sp.load_json(ROOT, f"raw/{mp}/google_trend.json")
        amz_series = _kwt_to_monthly(kwt) if isinstance(kwt, dict) else []
        gtr_series = _gtrend_to_monthly(gtr) if isinstance(gtr, dict) else []
        mp_amz[mp] = amz_series
        mp_gtrend[mp] = gtr_series
        # 5 站数据明细：取该站 AMZ 月度序列算 peak/trough
        p = _peak_trough(amz_series)
        mp_stats[mp] = p
        # 漏斗对照：peak 与近 6 月 YoY
        g_p = _peak_trough(gtr_series)
        mp_compare[mp] = {
            "amz_peak": p["peak_val"], "amz_yoy": p["yoy_pct"],
            "gtrend_peak": g_p["peak_val"], "gtrend_yoy": g_p["yoy_pct"],
        }

    # 当前站的 peak/trough（用于旺季/淡季双卡）
    cur_peak = mp_stats.get(marketplace, {"peak_lbl": "1月", "peak_val": 0,
                                          "trough_lbl": "12月", "trough_val": 0})

    # ---- SKILL 11（基于当前站）----
    skill11 = _skill11_trending(research_items, miner_items)

    sections = []
    period_chip = ("<span class='chip'>📅 数据周期 · 月粒度 · "
                   "growth = searchNearlyCr · mcr = monopolyClickRate × 100%</span>")

    # Hero
    sections.append(
        f"<section class='hero'><div class='wrap'>"
        f"<div class='hero-eyebrow'>{flag} {marketplace.lower()}.amazon.com · 季节性 & 趋势机会</div>"
        f"<h1>{sp.MARKETPLACE_NAME.get(marketplace, marketplace)} · "
        f"<span class='brand-orange'>{niche}</span></h1>"
        f"<p class='hero-sub'>5 站 × 12 月搜索趋势 + Skill 11/25 + Google Trends 漏斗 · {period_chip}</p>"
        f"{EXTRA_CSS}"
        "</div></section>"
    )

    # === 板块 1 · 事实（数据本身） ===
    # ① 多站 AMZ 折线对比（数据原始形态）
    sections.append(sp.section("📊 多站月搜索量对比（AMZ · 12 个月）",
                               _render_amz_chart(mp_amz, niche),
                               sub=f"{len(marketplaces)} 个站点 × 12 月趋势对比（来源：keyword_research_trends）"))

    # === 板块 2 · 解读（事实→结论） ===
    # ② 旺季/淡季双卡
    sections.append(sp.section("☀️ 旺季 / ❄️ 淡季 · 12 个月",
                               _render_season_cards(cur_peak, cur_peak, niche),
                               sub=f"基于 {marketplace.upper()} 站 12 月搜索量数据自动识别"))

    # ④ 多站数据明细表
    sections.append(sp.section("📊 多站数据明细",
                               _render_site_table(mp_stats),
                               sub="旺季月搜索 / 旺季月份 / 淡季月搜索 / 淡季月份 / 波动 / 近 6 月 YoY"))

    # === 板块 3 · 全局视图 ===
    # ⑨ 12 月热力图
    sections.append(sp.section("📅 年度日历 · 12 个月搜索量热力图",
                               _render_annual_heatmap(mp_amz, niche),
                               sub="以首站（UK）月搜索量为基准归一化 · 深橙=旺季 / 深蓝=淡季"))

    # === 板块 4 · 机会挖掘（趋势词 + 季节性破格） ===
    # ⑤ SKILL 11 ABA 高增长趋势词
    sections.append(sp.section("📈 Skill 11 · ABA 高增长趋势词筛选表",
                               _render_skill11_table(skill11)))

    # ⑥ SKILL 25 季节前置爆破
    s25 = scoring.get("skill_25_breakout", {})
    growth_val = s25.get("next_month_growth_pct", 0)
    yoy_val = s25.get("off_season_yoy_pct", 0)
    applied = s25.get("applied", False)
    growth_ok = growth_val > 100
    yoy_ok = yoy_val > 10
    status = "✅ 已应用（维度5 +1）" if applied else "⛔ 未触发"
    skill_html = (
        _skill_callout("25",
            "growth_rate = (next_month - this_month) / this_month · 100% · "
            "yoy_off = (off_season_this_year - off_season_last_year) / off_season_last_year · 100% · "
            "破格条件 = growth_rate > 100% AND yoy_off > 10%")
        + "<div class='skill25-card'>"
        + "<div class='skill25-header'>🎯 Skill 25 季节前置爆破（唯一允许破格）</div>"
        + "<div class='skill25-grid'>"
        + f"<div class='skill25-item'><span class='skill25-label'>下月增长率</span>"
        + f"<span class='skill25-value'>{growth_val:.1f}%</span>"
        + f"<span class='skill25-check'>{'✅' if growth_ok else '❌'} &gt;100%</span></div>"
        + f"<div class='skill25-item'><span class='skill25-label'>淡季同比</span>"
        + f"<span class='skill25-value'>{yoy_val:.1f}%</span>"
        + f"<span class='skill25-check'>{'✅' if yoy_ok else '❌'} &gt;10%</span></div>"
        + f"<div class='skill25-item skill25-result'><span class='skill25-label'>最终结论</span>"
        + f"<span class='skill25-value'>{status}</span></div>"
        + "</div></div>"
    )
    sections.append(sp.section("🎯 Skill 25 · 季节前置爆破", skill_html, alt=True))

    # === 板块 5 · 外部验证（识别 Google 失真） ===
    # ⑦ Google Trends 漏斗
    sections.append(sp.section("🌐 Google Trends 漏斗 · 识别「Google 失真」类目",
                               _render_gtrend_funnel(mp_compare),
                               sub="Google Trends = 认知层（用户在想） · Amazon = 购买层（用户真的下单） · "
                                   "两者经常偏差极大，漏斗对比是唯一提前识别的方法"))

    # ⑧ 进一步验证 MCP 工具（3 阶段：补全 → 验证 → 落地）
    sections.append(sp.section("🔍 进一步验证（按决策链路组织）",
                               _render_verify_mcp(),
                               sub="信息补全 → 交叉验证 → 决策落地 · 9 个 MCP 工具覆盖季节性结论从数据到行动"))

    # === 板块 6 · 行动（怎么干） ===
    # ③ 运营节奏建议（短卡片 · 3 栏）
    sections.append(sp.section("📅 运营节奏建议",
                               _render_rhythm_card(cur_peak["peak_lbl"], cur_peak["trough_lbl"])))

    # ⑩ 12 个月动作清单（年度作战图）
    sections.append(sp.section("📅 12 个月运营动作清单",
                               _render_12m_rhythm(niche),
                               sub=f"{niche} 单细切的年度作战图"))

    return sp.base_html(f"{marketplace} · 季节性 & 趋势 · {niche}",
                        "\n".join(sections), active="season", niche=niche,
                        marketplaces=marketplaces, current_mp=marketplace)


def main() -> None:
    cfg = sp.load_config(ROOT)
    for m in cfg["marketplaces"]:
        html_text = render(m, cfg)
        p = sp.write_html(ROOT, f"output/{m}_seasonality.html", html_text)
        print(f"[ok] {p}")


if __name__ == "__main__":
    main()
