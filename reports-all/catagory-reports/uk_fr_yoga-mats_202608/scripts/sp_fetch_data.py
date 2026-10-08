"""
sp_fetch_data.py
=================
SOP V3.1 STEP 1-6 · 真实数据抓取（通过 sellersprite-cli v0.1.21）
CLI 实际接口：sellersprite {group} {tool} [options] [{pos_arg}]
"""
from __future__ import annotations
import json
import os
import subprocess
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)
SS = r"C:\Users\HP\AppData\Roaming\Python\Python313\Scripts\sellersprite.exe"

# 工具名 → (子组, 工具, 构造函数)
TOOL_BUILDERS = {}

# 1. product node：--keyword / --node-id-path
KEYWORD = "yoga mats"
def build_product_node(mp, np, asin="", kw=KEYWORD):
    return (["product", "node", "--marketplace", mp.upper(), "--keyword", kw], {})

# 2. market research：--keyword + extra
def build_market_research(mp, np, asin="", kw=KEYWORD):
    return (["market", "research", "--marketplace", mp.upper(), "--keyword", kw,
             f"nodeIdPath={np}"], {})

# 3. market 9 个：--node-id-path（tool_name 形如 "market stats"，需拆分）
def build_market_tool(tool_name):
    group, _, sub = tool_name.partition(" ")
    def fn(mp, np, asin="", kw=""):
        return ([group, sub, "--marketplace", mp.upper(), "--node-id-path", np], {})
    return fn

# 4. keyword mine：V3.1.1 支持 keywordList 数组参数，一次查多词节省 token
#    - 单个关键词：--keyword kw1
#    - 多个关键词（数组）：--keywordList kw1,kw2,kw3
def _join_kw_list(value) -> str:
    """把 list/str 统一成逗号分隔的字符串。"""
    if isinstance(value, (list, tuple)):
        return ",".join(str(v).strip() for v in value if v)
    return str(value).strip()


def build_keyword_mine(mp, np, asin="", kw=KEYWORD):
    """V3.1.1：若 kw 是 list / tuple 且 len>1，优先用 --keywordList 数组参数。
    单个关键词仍走 --keyword 保持向后兼容。
    """
    base = ["keyword", "mine", "--marketplace", mp.upper(), f"nodeIdPath={np}"]
    if isinstance(kw, (list, tuple)) and len(kw) > 1:
        base += ["--keywordList", _join_kw_list(kw)]
    else:
        single = kw[0] if isinstance(kw, (list, tuple)) else kw
        base += ["--keyword", single]
    return (base, {})

# 5. keyword research：V3.1.1 同上支持 keywordList 数组参数
def build_keyword_research(mp, np, asin="", kw=KEYWORD):
    base = ["keyword", "research", "--marketplace", mp.upper(), f"nodeIdPath={np}"]
    if isinstance(kw, (list, tuple)) and len(kw) > 1:
        base += ["--keywordList", _join_kw_list(kw)]
    else:
        single = kw[0] if isinstance(kw, (list, tuple)) else kw
        base += ["--keywords", single]
    return (base, {})

# 6. keyword trends {kw}
def build_keyword_trends(mp, np, asin="", kw=KEYWORD):
    return (["keyword", "trends", kw, "--marketplace", mp.upper()], {})

# 7. trend review {asin}
def build_trend_review(mp, np, asin="", kw=""):
    return (["trend", "review", asin, "--marketplace", mp.upper(),
             "--star-list", "1,2,3", "--size", "50"], {})

# 8. trend google：--keyword --google-prop --monthly（monthly 是布尔 flag，不接值）
# V3.1 多语言回退：英文复数 "yoga mats" 在 FR/DE/IT/ES 站经常返回空，
# 需用本地语言关键词（tapis de yoga / Yogamatte / tappetino / esterilla）。
TREND_GOOGLE_KEYWORDS = {
    "us": ["yoga mat", "yoga mats", "yoga"],
    "uk": ["yoga mat", "yoga mats", "yoga"],
    "ca": ["yoga mat", "yoga mats"],
    "in": ["yoga mat", "yoga mats"],
    "fr": ["tapis de yoga", "tapis yoga", "yoga", "yoga mat"],
    "de": ["yogamatte", "yoga matte", "yoga mat", "yoga"],
    "it": ["tappetino yoga", "tappetino", "yoga", "yoga mat"],
    "es": ["esterilla yoga", "esterilla", "yoga", "yoga mat"],
    "mx": ["esterilla yoga", "esterilla", "yoga", "yoga mat"],
    "jp": ["ヨガマット", "yoga mat"],
}


def build_trend_google(mp, np, asin="", kw=KEYWORD):
    """V3.1：返回 spec dict，调用方按 candidates 顺序试 keyword/prop。"""
    geo = {"uk": "GB", "fr": "FR"}.get(mp, mp.upper())
    return {
        "geo": geo,
        "candidates": TREND_GOOGLE_KEYWORDS.get(mp.lower(), [kw, "yoga mat", "yoga"]),
    }


def run_trend_google(mp: str) -> dict:
    """V3.1：按 candidates 顺序试 keyword/prop，遇到 items 非空就返回；都空则保留最后一次结果。"""
    geo = {"uk": "GB", "fr": "FR"}.get(mp, mp.upper())
    candidates = TREND_GOOGLE_KEYWORDS.get(mp.lower(), [KEYWORD, "yoga mat", "yoga"])
    last = None
    for kw in candidates:
        for prop in ("shoppingCart", "web"):
            args = ["trend", "google", "--keyword", kw,
                    "--google-prop", prop, "--monthly",
                    "--marketplace", geo]
            d = run(args)
            # 保存每一次尝试到独立文件，便于排查
            save(mp, f"google_trend_{kw.replace(' ', '_')}_{prop}", d)
            last = d
            items = d.get("items") if isinstance(d, dict) else None
            if isinstance(items, list) and len(items) > 0:
                print(f"   [trend_google] OK {mp} kw='{kw}' prop={prop} items={len(items)}")
                save(mp, "google_trend", d)
                return d
            print(f"   [trend_google] - {mp} kw='{kw}' prop={prop} empty, try next")
    save(mp, "google_trend", last or {"_error": "all keyword/prop candidates empty"})
    return last or {"_error": "all keyword/prop candidates empty"}

# 9. asin predict {asin}
def build_asin_predict(mp, np, asin="", kw=""):
    return (["asin", "predict", asin, "--marketplace", mp.upper()], {})

# 10. product competitor：--asins
def build_product_competitor(mp, np, asin="", kw=""):
    return (["product", "competitor", "--marketplace", mp.upper(), "--asins", asin], {})


TOOL_BUILDERS = {
    "product_node": build_product_node,
    "market_research": build_market_research,
    "market_stats": build_market_tool("market stats"),
    "market_brand": build_market_tool("market brand"),
    "market_product": build_market_tool("market product"),
    "market_price": build_market_tool("market price"),
    "market_listing-date": build_market_tool("market listing-date"),
    "market_ebc": build_market_tool("market ebc"),
    "market_rating": build_market_tool("market rating"),
    "market_demand": build_market_tool("market demand"),
    "market_seller-country": build_market_tool("market seller-country"),
    "keyword_mine": build_keyword_mine,
    "keyword_research": build_keyword_research,
    "keyword_trends": build_keyword_trends,
    "trend_google": build_trend_google,
    "asin_predict": build_asin_predict,
    "product_competitor": build_product_competitor,
    "trend_review": build_trend_review,
}


def run(args: list, timeout: int = 90) -> dict:
    """调用 sellersprite CLI 并解析 JSON 输出。"""
    try:
        r = subprocess.run([SS] + args, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    except subprocess.TimeoutExpired:
        return {"_error": "timeout", "_cmd": " ".join(args)}
    out = r.stdout.strip()
    if not out:
        return {"_error": f"empty (exit={r.returncode})", "_cmd": " ".join(args),
                "_stderr": (r.stderr or "")[-400:]}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"_raw": out[:1500], "_stderr": (r.stderr or "")[-200:]}


def save(mp: str, name: str, data) -> str:
    p = os.path.join(ROOT, "raw", mp, f"{name}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    # 顶层 list → 包成 {"items": [...]} 便于下游统一处理
    if isinstance(data, list):
        data = {"items": data, "_list_wrapped": True}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def is_ok(d) -> bool:
    """统一判断返回是否成功（兼容 dict / list 包装 / 错误 dict）。"""
    if isinstance(d, dict) and d.get("_error"):
        return False
    return True


def resolve_node(mp: str) -> str:
    """调用 product_node 找到 nodeIdPath（兼容顶层数组/包装对象两种结构）。

    V3.1 多语言匹配：Yoga mats 在不同站点的叶子节点名是本地语言
    （FR=Tapis / DE=Matte / IT=Tappetino / ES=Esterilla / JP=マット 等），
    原 `:mats` 匹配器对 FR/DE/IT/ES 全部 miss，会回退到 449 的 "Yoga" 大类。
    """
    args, _ = build_product_node(mp, "")
    d = run(args)
    save(mp, "product_node", d)
    # 兼容：可能是顶层 list，也可能是 {"leaves":[...]} 或 {"data":{"leaves":[...]}}
    leaves = None
    if isinstance(d, list):
        leaves = d
    elif isinstance(d, dict):
        leaves = d.get("leaves")
        if not leaves and isinstance(d.get("data"), dict):
            leaves = d["data"].get("leaves")
        if not leaves:
            for v in d.values():
                if isinstance(v, list) and v and isinstance(v[0], dict) and "nodeIdPath" in v[0]:
                    leaves = v; break
    if not leaves:
        return ""
    # V3.1 多语言映射：每个站点 yoga mats 的本地叶子词
    MATS_KEYWORDS = {
        "us": ["mats", "mat"],
        "uk": ["mats", "mat"],
        "ca": ["mats", "mat"],
        "in": ["mats", "mat"],
        "fr": ["tapis"],            # Tapis de yoga
        "de": ["matte", "matten"],  # Yogamatte
        "it": ["tappetino", "tappetini"],
        "es": ["esterilla", "esterillas", "colchoneta"],
        "mx": ["esterilla", "esterillas"],
        "jp": ["マット"],
    }
    mats_words = MATS_KEYWORDS.get(mp.lower(), ["mats", "mat"])
    best = None
    for n in leaves:
        if not isinstance(n, dict):
            continue
        path = (n.get("nodeLabelPath") or "").lower()
        # 必须含 "yoga" 且末段是 mats/tapis/matte/...
        if ":yoga:" not in path and not path.endswith(":yoga"):
            continue
        last = path.rsplit(":", 1)[-1]
        if last in mats_words and n.get("products", 0) > 0:
            return n.get("nodeIdPath", "")
        # 记一个候选：含 yoga 且产品数 ≥ 30 的最具体路径（segment 最多的优先）
        if n.get("products", 0) > 0 and ":yoga:" in path:
            depth = path.count(":")
            if best is None or depth > best[0]:
                best = (depth, n)
    if best:
        return best[1].get("nodeIdPath", "")
    # 兜底：取 products 最多的一个
    leaves = [n for n in leaves if isinstance(n, dict) and n.get("products", 0) > 0]
    if leaves:
        leaves.sort(key=lambda x: -x.get("products", 0))
        return leaves[0].get("nodeIdPath", "")
    return ""


def call_tool(key: str, mp: str, np: str = "", asin: str = "", kw: str = KEYWORD) -> dict:
    args, _ = TOOL_BUILDERS[key](mp, np, asin, kw=kw)
    return run(args)


# V3.1.1 · 关键词候选集合（用于 keyword_mine / keyword_research 一次查多词）
# 把根词 + 常见长尾同时拉，节省 N 次请求的 token 消耗
KEYWORD_BATCH_CANDIDATES = {
    "us": ["yoga mat", "yoga mats", "yoga mat thick", "yoga mat non slip", "yoga mat extra thick"],
    "uk": ["yoga mat", "yoga mats", "yoga mat thick", "yoga mat non slip", "yoga mat extra thick"],
    "fr": ["tapis de yoga", "tapis yoga", "tapis yoga epais", "tapis yoga antidérapant"],
    "de": ["yogamatte", "yoga matte", "yogamatte dick", "yogamatte rutschfest"],
    "it": ["tappetino yoga", "tappetino yoga spesso", "tappetino yoga antiscivolo"],
    "es": ["esterilla yoga", "esterilla yoga gruesa", "esterilla yoga antideslizante"],
}


def _kw_batch(mp: str) -> list:
    """返回该站点的关键词数组（用于 keyword_mine / keyword_research 一次查多词）。"""
    return KEYWORD_BATCH_CANDIDATES.get(mp.lower(), [KEYWORD])


def fetch_marketplace(mp: str) -> None:
    print(f"\n=== {mp.upper()} ===")
    node_id_path = resolve_node(mp)
    if not node_id_path:
        node_id_path = "2619525011:3741271"
    print(f"   nodeIdPath = {node_id_path}")

    # market 系列 10
    market_keys = ["market_research", "market_stats", "market_brand", "market_product",
                   "market_price", "market_listing-date", "market_ebc", "market_rating",
                   "market_demand", "market_seller-country"]
    for i, k in enumerate(market_keys, start=1):
        d = call_tool(k, mp, node_id_path)
        save(mp, k, d)
        ok = "✓" if is_ok(d) else "✗"
        err = (d.get("_error", "") if isinstance(d, dict) else "")[:60]
        print(f"  [{i:>2}/{len(market_keys)}] {k:<28} {ok} {err}")

    # 关键词 3：V3.1.1 keyword_mine / keyword_research 改用 keywordList 数组参数
    #   - 把根词 + 常见长尾一次拉取，减少 token 消耗
    #   - keyword_trends 仍走单参数（API 限制：单 keyword）
    kw_batch = _kw_batch(mp)
    print(f"  - keyword batch: {kw_batch}")
    d = call_tool("keyword_mine", mp, node_id_path, kw=kw_batch)
    save(mp, "keyword_mine", d)
    ok = "✓" if is_ok(d) else "✗"
    err = (d.get("_error", "") if isinstance(d, dict) else "")[:60]
    print(f"  - keyword_mine (array)         {ok} {err}")
    d = call_tool("keyword_research", mp, node_id_path, kw=kw_batch)
    save(mp, "keyword_research", d)
    ok = "✓" if is_ok(d) else "✗"
    err = (d.get("_error", "") if isinstance(d, dict) else "")[:60]
    print(f"  - keyword_research (array)     {ok} {err}")
    d = call_tool("keyword_trends", mp, node_id_path)
    save(mp, "keyword_research_trends", d)
    ok = "✓" if is_ok(d) else "✗"
    err = (d.get("_error", "") if isinstance(d, dict) else "")[:60]
    print(f"  - keyword_trends               {ok} {err}")

    # Google Trend
    g = run_trend_google(mp)
    ok = "✓" if is_ok(g) else "✗"
    err = (g.get("_error", "") if isinstance(g, dict) else "")[:50]
    print(f"  - trend_google                  {ok} {err}")

    # 取 TOP ASIN
    asins = []
    try:
        with open(os.path.join(ROOT, "raw", mp, "market_product.json"), "r", encoding="utf-8") as f:
            mp_data = json.load(f)
        items = mp_data.get("items") if isinstance(mp_data, dict) and mp_data.get("_list_wrapped") else mp_data
        top = (items if isinstance(items, list) else (mp_data.get("topProducts") or []))[:5]
        asins = [a.get("asin") for a in top if isinstance(a, dict) and a.get("asin")]
    except Exception:
        pass

    if asins:
        d = call_tool("product_competitor", mp, asin=",".join(asins[:3]))
        save(mp, "competitor_lookup", d)
        for a in asins[:3]:
            d = call_tool("asin_predict", mp, asin=a)
            save(mp, f"asin_predict_{a}", d)
            d = call_tool("trend_review", mp, asin=a)
            save(mp, f"review_{a}", d)
        print(f"  - asin/competitor/review × {len(asins[:3])} ASINs done")
    else:
        print(f"  - [warn] no ASINs in market_product, skipping per-ASIN tools")


def main() -> None:
    cfg = sp.load_config(ROOT)
    for mp in cfg["marketplaces"]:
        try:
            fetch_marketplace(mp)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[ERROR] {mp}: {e}")


if __name__ == "__main__":
    main()
