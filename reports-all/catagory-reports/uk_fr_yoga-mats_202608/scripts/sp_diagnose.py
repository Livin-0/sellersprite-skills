#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""静态诊断脚本：检查 V3.1 各项设计约束是否落实在各产出 HTML 中。"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")

print("=" * 60)
print("【1. 产出文件清单 + Chart.js 实例数】")
print("=" * 60)
for f in sorted(os.listdir(OUT)):
    if not f.endswith(".html"):
        continue
    p = os.path.join(OUT, f)
    size = os.path.getsize(p)
    with open(p, "r", encoding="utf-8") as fp:
        text = fp.read()
    chartjs_cdn = text.count("cdn.jsdelivr.net/npm/chart.js")
    canvas_ids = re.findall(r'<canvas[^>]*id=[\"\']?(ch-|site-)([^\"\'>\s]+)', text)
    canvas_count = len(re.findall(r'<canvas', text))
    print(f"  {f:30s} {size:>7d}B  chartjs_cdn={chartjs_cdn}  canvas={canvas_count}  ids={[c[1] for c in canvas_ids]}")

print()
print("=" * 60)
print("【2. index.html 关键设计约束对照】")
print("=" * 60)
with open(os.path.join(OUT, "index.html"), "r", encoding="utf-8") as fp:
    idx = fp.read()

# 区块编号 01/02/03/04
has_num_01 = "01" in idx and "5 站大盘" in idx
has_num_02 = "02" in idx and "横向矩阵" in idx
has_num_03 = "03" in idx and "Top 3" in idx
has_num_04 = "04" in idx and "避坑" in idx
print(f"  区块编号 01/5站大盘: {has_num_01}")
print(f"  区块编号 02/横向矩阵: {has_num_02}")
print(f"  区块编号 03/Top 3: {has_num_03}")
print(f"  区块编号 04/避坑: {has_num_04}")

# 调色板
has_palette = "--topbar-bg:#0A1A2F" in idx and "--brand-yellow:#FCD34D" in idx
print(f"  V3.1 调色板(--topbar-bg/--brand-yellow): {has_palette}")

# 5 维加权
has_5dim = "5 维加权" in idx or "5 维评分" in idx
print(f"  5 维评分细分: {has_5dim}")
has_weighted = "加权合计" in idx
print(f"  100 分制加权合计: {has_weighted}")
has_weak = re.search(r"扣\s*\d+(\.\d+)?\s*分", idx) is not None
print(f"  最弱维度扣分提示: {has_weak}")

# 最佳站
has_best_mp = re.search(r"最佳站", idx) is not None
print(f"  最佳站列: {has_best_mp}")

# Chart.js
has_chartjs_idx = "cdn.jsdelivr.net/npm/chart.js" in idx
print(f"  Chart.js 互动(总览页底部): {has_chartjs_idx}")

# 顶栏导航
has_uk_link = "uk_needs.html" in idx and "uk_kwneeds.html" in idx
has_fr_link = "fr_needs.html" in idx and "fr_kwneeds.html" in idx
print(f"  顶栏动态生成 UK 链接: {has_uk_link}")
print(f"  顶栏动态生成 FR 链接: {has_fr_link}")

# About
has_about = "关于本报告" in idx or "数据透明" in idx
print(f"  About + 数据透明: {has_about}")

print()
print("=" * 60)
print("【3. 站点页 (uk.html / fr.html) 必备元素】")
print("=" * 60)
for f in ["uk.html", "fr.html"]:
    with open(os.path.join(OUT, f), "r", encoding="utf-8") as fp:
        text = fp.read()
    print(f"\n  {f}:")
    print(f"    Hero/方向/供需比 chip: {'方向' in text and '供需比' in text and '综合分' in text}")
    print(f"    4 列 KPI (月GMV/搜索/活跃ASIN/供需比): {'月 GMV' in text and '月搜索量' in text and '活跃 ASIN' in text}")
    print(f"    六维评分卡(进度条): {'六维评分卡' in text and 'dim-row' in text}")
    print(f"    CR10 + 价格分布(SVG): {'svg_cr10_chart' in text or 'CR10 集中度' in text}")
    print(f"    评分分布 + 上架时间(SVG): {'评分分布' in text and '上架时间' in text}")
    print(f"    卖家来源 + TOP 10 ASIN: {'卖家来源' in text and 'TOP 10' in text}")
    print(f"    关键词速览 TOP 8: {'关键词速览' in text}")
    print(f"    Chart.js 互动 4 图表: {text.count('site-cr10-') + text.count('site-country-') + text.count('site-rating-') + text.count('site-top10-')}/4")

print()
print("=" * 60)
print("【4. 子页面 (uk_seasonality.html / uk_needs.html / uk_kwneeds.html) 状态】")
print("=" * 60)
for f in ["uk_seasonality.html", "uk_needs.html", "uk_kwneeds.html",
          "fr_seasonality.html", "fr_needs.html", "fr_kwneeds.html"]:
    p = os.path.join(OUT, f)
    if not os.path.exists(p):
        print(f"  {f:30s} ❌ 不存在")
        continue
    with open(p, "r", encoding="utf-8") as fp:
        text = fp.read()
    has_chartjs = "cdn.jsdelivr.net/npm/chart.js" in text
    canvas_n = len(re.findall(r"<canvas", text))
    print(f"  {f:30s} size={os.path.getsize(p):>7d}  Chart.js={has_chartjs}  canvas={canvas_n}")

print()
print("=" * 60)
print("【5. 拉取的原始数据文件 vs 实际使用情况】")
print("=" * 60)
# 列出 raw/uk 下所有 JSON，看哪些被使用
raw_files = sorted(os.listdir(os.path.join(ROOT, "raw", "uk")))
print(f"  UK raw 数据文件 ({len(raw_files)}): {raw_files}")
# 检查哪些 normalize 函数有引用
with open(os.path.join(ROOT, "scripts", "sp_render_split.py"), "r", encoding="utf-8") as fp:
    render_text = fp.read()
for f in raw_files:
    name = f.replace(".json", "")
    used = name in render_text
    print(f"    {f:30s} 在 split 渲染中: {'✓' if used else '✗'}")
