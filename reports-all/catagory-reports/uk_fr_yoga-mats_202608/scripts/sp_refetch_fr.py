"""Re-fetch FR marketplace with correct nodeIdPath (325614031:339867031:486077031:486084031)."""
from __future__ import annotations
import json
import os
import sys
import time
import subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)
SS = r"C:\Users\HP\AppData\Roaming\Python\Python313\Scripts\sellersprite.exe"
MP = "fr"
NP = "325614031:339867031:486077031:486084031"
KEYWORD = "yoga mats"


def run(args, timeout=90):
    try:
        r = subprocess.run([SS] + args, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8")
    except subprocess.TimeoutExpired:
        return {"_error": "timeout"}
    out = r.stdout.strip()
    if not out:
        return {"_error": f"empty (exit={r.returncode})",
                "_stderr": (r.stderr or "")[-300:]}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"_raw": out[:1500]}


def save(name, data):
    p = os.path.join(ROOT, "raw", MP, f"{name}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if isinstance(data, list):
        data = {"items": data, "_list_wrapped": True}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


# market 系列（10 个） + 关键词 3 + google trend 1
JOBS = [
    ("market_stats",          ["market", "stats", "--marketplace", MP, "--node-id-path", NP]),
    ("market_brand",          ["market", "brand", "--marketplace", MP, "--node-id-path", NP]),
    ("market_product",        ["market", "product", "--marketplace", MP, "--node-id-path", NP]),
    ("market_price",          ["market", "price", "--marketplace", MP, "--node-id-path", NP]),
    ("market_listing-date",   ["market", "listing-date", "--marketplace", MP, "--node-id-path", NP]),
    ("market_ebc",            ["market", "ebc", "--marketplace", MP, "--node-id-path", NP]),
    ("market_rating",         ["market", "rating", "--marketplace", MP, "--node-id-path", NP]),
    ("market_demand",         ["market", "demand", "--marketplace", MP, "--node-id-path", NP]),
    ("market_seller-country", ["market", "seller-country", "--marketplace", MP, "--node-id-path", NP]),
    ("market_research",       ["market", "research", "--marketplace", MP, "--keyword", KEYWORD, f"nodeIdPath={NP}"]),
    ("keyword_mine",          ["keyword", "mine", "--marketplace", MP, "--keyword", KEYWORD, f"nodeIdPath={NP}"]),
    ("keyword_research",      ["keyword", "research", "--marketplace", MP, "--keywords", KEYWORD, f"nodeIdPath={NP}"]),
    ("keyword_research_trends", ["keyword", "trends", KEYWORD, "--marketplace", MP]),
    ("google_trend",          ["trend", "google", "--keyword", KEYWORD, "--google-prop", "shoppingCart",
                              "--monthly", "true", "--marketplace", "FR"]),
]

# Top ASINs from market_research
asin_jobs = []

def main():
    print(f"=== Re-fetching FR (nodeIdPath={NP}) ===")
    for i, (name, args) in enumerate(JOBS, start=1):
        d = run(args)
        save(name, d)
        ok = "✓" if not (isinstance(d, dict) and d.get("_error")) else "✗"
        err = ""
        if isinstance(d, dict) and "_error" in d:
            err = d["_error"][:60]
        items = d.get("items") if isinstance(d, dict) and d.get("_list_wrapped") else d
        n = len(items) if isinstance(items, list) else "?"
        print(f"  [{i:>2}/{len(JOBS)}] {name:<28} {ok}  items={n}  {err}")
        time.sleep(1.6)  # 限流

    # 取 TOP ASINs 做竞品 + 评论
    try:
        mp_data = json.load(open(os.path.join(ROOT, "raw", MP, "market_product.json"),
                                 encoding="utf-8"))
        items = mp_data.get("items") if mp_data.get("_list_wrapped") else mp_data
        top = items[:5] if isinstance(items, list) else []
        asins = [a.get("asin") for a in top if isinstance(a, dict) and a.get("asin")]
    except Exception as e:
        asins = []
        print(f"  [warn] cannot read top ASINs: {e}")

    if asins:
        d = run(["product", "competitor", "--marketplace", MP, "--asins", ",".join(asins[:3])])
        save("competitor_lookup", d)
        for a in asins[:3]:
            d = run(["asin", "predict", a, "--marketplace", MP])
            save(f"asin_predict_{a}", d)
            time.sleep(1.6)
            d = run(["trend", "review", a, "--marketplace", MP,
                     "--star-list", "1,2,3", "--size", "50"])
            save(f"review_{a}", d)
            time.sleep(1.6)
        print(f"  - asin/competitor/review × {len(asins[:3])} ASINs done")
    else:
        print("  [warn] no top ASINs, skipping per-ASIN tools")


if __name__ == "__main__":
    main()
