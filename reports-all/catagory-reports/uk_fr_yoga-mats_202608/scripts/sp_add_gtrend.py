"""
sp_add_gtrend.py
================
SOP V3.1 STEP 8 · 后处理脚本 5/7
功能：把 Google Trends 对比图注入到总览页（index.html），
      替换占位标记 <!-- SP_GTREND_SLOT -->
输入：output/index.html（已由 sp_render_split.py 生成）
      raw/google_trend.json
输出：原地修改 output/index.html
说明（V3.1 fix）：
      - 不再向 {mp}.html / {mp}_needs.html / {mp}_kwneeds.html 注入
        （Google Trends 与季节性数据本应在 *_seasonality.html 中展示）
      - 季节性页 (sp_render_seasonality.py) 已自带 Chart.js 折线图，
        此处只补全总览页的速览
"""
from __future__ import annotations
import os
import re
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)
SLOT = "<!-- SP_GTREND_SLOT -->"
ANCHOR = '<footer class="sp-footnote">'


def build_block(marketplaces: list) -> str:
    """V3.1 · 一次性汇总所有站点的 Google Trends（用月聚合），用于总览页对比。"""
    import datetime as _dt
    from collections import OrderedDict
    all_series = []
    has_any = False
    for mp in marketplaces:
        g = sp.load_json(ROOT, f"raw/{mp}/google_trend.json")
        if not isinstance(g, dict) or "_error" in g or not isinstance(g.get("items"), list):
            all_series.append({"name": f"{mp.upper()}", "labels": [f"M{i+1}" for i in range(12)],
                               "values": [0]*12, "_empty": True})
            continue
        monthly = OrderedDict()
        for it in g["items"]:
            if not isinstance(it, dict):
                continue
            t, v = it.get("time"), it.get("value")
            if not isinstance(t, (int, float)) or not isinstance(v, (int, float)):
                continue
            try:
                d = _dt.datetime.fromtimestamp(t / 1000)
                key = f"{d.year}-{d.month:02d}"
                monthly[key] = monthly.get(key, 0) + v
            except (ValueError, OSError):
                continue
        if monthly:
            vals = list(monthly.values())[-12:]
            while len(vals) < 12:
                vals.insert(0, 0)
            all_series.append({"name": f"{mp.upper()}", "labels": [f"M{i+1}" for i in range(12)],
                               "values": vals})
            has_any = True
        else:
            all_series.append({"name": f"{mp.upper()}", "labels": [f"M{i+1}" for i in range(12)],
                               "values": [0]*12, "_empty": True})
    if not has_any:
        return ('<div class="sp-card" id="sp-gtrend">'
                '<h2>🌐 Google Trends 速览 / Google Trends Snapshot</h2>'
                '<p class="sp-muted">（所有站点均未拉取到 Google Trends 数据；可能受 marketplace code 大小写或 API 限流影响）'
                '</p></div>')
    svg = sp.svg_multi_line(all_series, width=820, height=260)
    return (
        '<div class="sp-card" id="sp-gtrend">'
        '<h2>🌐 Google Trends 速览 / Google Trends Snapshot</h2>'
        '<p class="sp-muted">shoppingCart 购物搜索 12 个月指数（多站对比 · '
        '来源：SellerSprite <code>trend_google</code> · 按月聚合）。</p>'
        + svg +
        '</div>'
    )


def patch_file(path: str, block: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if "sp-gtrend" in text:
        return False
    if SLOT in text:
        text = text.replace(SLOT, block, 1)
    elif ANCHOR in text:
        text = text.replace(ANCHOR, block + "\n" + ANCHOR, 1)
    else:
        text = text.replace("</main>", block + "\n</main>", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def main() -> None:
    """V3.1 · 2026-08-30 用户决定总览页也不要 Google Trends 速览块。
    本脚本保留为 no-op，避免误删代码后无法恢复。sp_render_seasonality.py
    已在季节性页（*_seasonality.html）自带 AMZ + Google 两张 Chart.js 折线图。"""
    print("[skip] sp_add_gtrend: 用户已确认 index.html 不再注入 Google Trends 块")
    print("       季节性页（*_seasonality.html）由 sp_render_seasonality.py 自带 Chart.js 图")


if __name__ == "__main__":
    main()
