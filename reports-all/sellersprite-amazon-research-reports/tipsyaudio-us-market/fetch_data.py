#!/usr/bin/env python3
"""TipsyAudio US Market 全景调研数据采集脚本"""
import sys, json, urllib.request, urllib.error, time, os
from datetime import datetime

# === 由用户在对话中提供，仅本次任务使用，不写入任何持久文件 ===
SECRET_KEY = "__REDACTED__"
URL = "https://mcp.sellersprite.com/mcp"
OUT_DIR = r"p:\trae.ai\TraeCN projects learning\amazon-sellersprite-reasearch-MCP-skill\reports-all\sellersprite-amazon-research-reports\tipsyaudio-us-market"

# TipsyAudio 主品类: Wireless Lavalier Microphones (叶子节点)
NODE_ID = "11091801:11974521:8882489011:11974711:11974761"

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

os.makedirs(OUT_DIR, exist_ok=True)


def call_tool(name: str, arguments: dict):
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": name, "arguments": arguments}
    }).encode('utf-8')
    req = urllib.request.Request(URL, data=payload,
        headers={"Content-Type": "application/json", "secret-key": SECRET_KEY,
                 "Accept": "application/json, text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode('utf-8')
            data = json.loads(raw)
            text0 = data['result']['content'][0]['text']
            return json.loads(text0)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode('utf-8')
        except Exception:
            pass
        return {"error": f"HTTP{e.code}", "body": body, "_tool": name}
    except Exception as e:
        return {"error": str(e), "_tool": name}


REQUEST_BASE = {"marketplace": "US", "nodeIdPath": NODE_ID, "topNum": 10, "size": 50}

TOOLS = {
    "market_research": {"request": {**REQUEST_BASE}},
    "market_research_statistics": {"request": {"marketplace": "US", "nodeIdPath": NODE_ID, "topN": 10, "newProduct": 6}},
    "market_price_distribution": {"request": {**REQUEST_BASE}},
    "market_brand_concentration": {"request": {**REQUEST_BASE}},
    "market_product_concentration": {"request": {**REQUEST_BASE}},
    "market_seller_concentration": {"request": {**REQUEST_BASE}},
    "market_rating_distribution": {"request": {**REQUEST_BASE}},
    "market_ratings_count_distribution": {"request": {**REQUEST_BASE}},
    "market_listing_date_distribution": {"request": {**REQUEST_BASE}},
    "market_listing_trend_distribution": {"request": {**REQUEST_BASE}},
    "market_seller_country_distribution": {"request": {**REQUEST_BASE}},
    "market_seller_type_concentration": {"request": {**REQUEST_BASE}},
    "market_ebc_distribution": {"request": {**REQUEST_BASE}},
    "market_product_demand_trend": {"request": {**REQUEST_BASE}},
}

results = {}
print(f"[INFO] {datetime.now().isoformat()} 开始批量调用 sellersprite MCP，共 {len(TOOLS)} 个工具")
for i, (tool_name, args) in enumerate(TOOLS.items(), 1):
    start = time.time()
    result = call_tool(tool_name, args)
    elapsed = time.time() - start
    results[tool_name] = result
    if isinstance(result, dict) and result.get("code") == "OK":
        status = "OK"
    elif isinstance(result, dict) and "error" in result:
        status = f"ERR {result.get('error')}"
    else:
        status = f"UNK ({list(result.keys())[:3]})"
    print(f"  [{i:02d}/{len(TOOLS)}] {tool_name:40s} -> {status:20s} ({elapsed:.1f}s)")
    # 轻微限流，避免 429
    time.sleep(1.5)

# 保存原始数据
out_file = os.path.join(OUT_DIR, "research_data.json")
with open(out_file, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"[DONE] 原始数据已保存到 {out_file}")

# 输出摘要
print("\n=== 关键工具返回摘要 ===")
mr = results.get("market_research", {})
if isinstance(mr, dict) and mr.get("code") == "OK":
    items = mr.get("data", {}).get("items", []) or []
    print(f"market_research: items={len(items)}")
    for it in items[:3]:
        print(f"  - {it.get('nodeLabelPath','?')[:80]} | products={it.get('totalProducts',0)} | units={it.get('totalUnits',0)}")