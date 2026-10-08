"""诊断脚本：检查 9 个 HTML 页面与 12 类原始数据的状态。"""
import os
import re
import json
from pathlib import Path

ROOT = Path("p:/trae.ai/TraeCN projects learning/amazon-select-product/uk_fr_yoga-mats_202608")
OUT = ROOT / "output"
RAW = ROOT / "raw"

print("=" * 64)
print(" V3.1 设计约束落实情况诊断")
print("=" * 64)

# 1. 9 个 HTML 页面核查
html_files = sorted(OUT.glob("*.html"))
print(f"\n[1] HTML 页面：{len(html_files)} 个")
for f in html_files:
    text = f.read_text(encoding="utf-8")
    has_style = "--topbar-bg:#0A1A2F" in text
    has_yellow = "#FCD34D" in text
    has_chart_cdn = "cdn.jsdelivr.net/npm/chart.js" in text
    n_charts = len(re.findall(r'<canvas[^>]+class="sp-chart"', text))
    has_sop = "SOP V3.1" in text
    print(f"  {f.name:25}  样式={has_style}  黄={has_yellow}  CDN={has_chart_cdn}  "
          f"Chart.js={n_charts}个  SOP标={has_sop}")

# 2. index.html 区块编号核查
print("\n[2] index.html 区块编号")
idx = (OUT / "index.html").read_text(encoding="utf-8")
for n in ["01", "02", "03", "04", "05", "06"]:
    pattern = r"sp-sec-num'>" + n + r"</span> <span class='sp-sec-title'>([^<]+)</span>"
    m = re.search(pattern, idx)
    if m:
        print(f"  [{n}] {m.group(1).strip()}")
    else:
        print(f"  [{n}] [NOT FOUND]")

# 3. 总览页 5 站大盘实际渲染数
print("\n[3] 5 站大盘 站点卡数")
n_cards = len(re.findall(r'class=\'site-card\'', idx))
print(f"  共 {n_cards} 张站点卡")

# 4. 原始数据上墙核查
print("\n[4] raw 数据 vs 上墙页面（uk）")
data_files = {
    "market_research.json":       ("index", "uk.html", "矩阵/5站大盘"),
    "market_brand.json":          ("uk.html", None, "CR10 图"),
    "market_seller-country.json": ("uk.html", "index", "国家分布 + 中国占比"),
    "market_rating.json":         ("uk.html", None, "评分分布"),
    "market_product.json":        ("uk.html", None, "TOP 10 ASIN"),
    "keyword_mine.json":          ("uk_kwneeds.html", None, "词表 + 2 Chart.js"),
    "keyword_research.json":      ("uk_kwneeds.html", None, "品牌大词"),
    "competitor_lookup.json":     ("uk.html", None, "毛利率快照"),
    "product_node.json":          ("uk.html", None, "叶子节点链路"),
    "google_trend.json":          ("uk_seasonality.html", "index", "Chart.js 第二条线"),
    "keyword_research_trends.json":("uk_seasonality.html", None, "Chart.js 第一条线"),
    "review_B01MS8ZBY8.json":     ("uk_needs.html", None, "差评聚类"),
    "asin_predict_B01MS8ZBY8.json": ("uk_needs.html", None, "LQS / 月销量"),
}
for fn, (primary, secondary, usage) in data_files.items():
    p = RAW / "uk" / fn
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        is_err = isinstance(d, dict) and "_error" in d
        size = p.stat().st_size
        status = "❌ _error" if is_err else "✓"
        print(f"  {status}  {fn:35}  → {primary:25}  ({size} B)  [{usage}]")
    else:
        print(f"  ?  {fn:35}  → MISSING")

# 5. Chart.js 总实例数
print("\n[5] Chart.js 实例分布")
total = 0
for f in html_files:
    text = f.read_text(encoding="utf-8")
    n = len(re.findall(r"<canvas[^>]+class=['\"]sp-chart['\"]", text))
    if n > 0:
        print(f"  {f.name:30}  {n} 个")
        total += n
print(f"  {'合计':30}  {total} 个  (CDN: cdn.jsdelivr.net/npm/chart.js@4.4.1)")
