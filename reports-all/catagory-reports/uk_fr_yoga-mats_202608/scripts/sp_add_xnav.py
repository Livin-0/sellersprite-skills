"""
sp_add_xnav.py
==============
SOP V3.0 STEP 8 · 后处理脚本 6/7
功能：跨页导航（已由 sp_render_*.py 注入顶栏）。本脚本补充：
      1) 报告底部跨页导航（Prev / Next）
      2) 报告间同 anchor（#dimension-N）跨页跳转
      3) 把 sp_topbar 的站点下拉换成多站点切换（如有多个 mp）
输入：output/*.html
输出：原地修改 output/*.html
"""
from __future__ import annotations
import os
import re
import sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sp_common as sp   # noqa: E402

ROOT = os.path.dirname(HERE)
FOOT_SLOT = "<!-- SP_XNAV_FOOT -->"


def _xnav_html(marketplace: str, cfg: dict) -> str:
    pages = [
        ("index.html", "总览"),
        (f"{marketplace}.html", "站点分析"),
        (f"{marketplace}_seasonality.html", "季节性"),
        (f"{marketplace}_needs.html", "用户需求"),
        (f"{marketplace}_kwneeds.html", "关键词机会"),
    ]
    items = "".join(
        f"<a class='sp-xnav-link' href='{p}'>{label}</a>" for p, label in pages
    )
    mp_links = ""
    if len(cfg["marketplaces"]) > 1:
        mp_links = "<div class='sp-xnav-mp'>" + "".join(
            f"<a href='{m}.html' class='sp-xnav-mp-link'>{sp.MARKETPLACE_NAME.get(m, m)}</a>"
            for m in cfg["marketplaces"]
        ) + "</div>"
    return (
        "<nav class='sp-xnav' aria-label='cross-page navigation'>"
        "<div class='sp-xnav-title'>📑 跨页导航 / Cross-Page Navigation</div>"
        "<div class='sp-xnav-grid'>" + items + "</div>"
        + mp_links +
        "</nav>"
    )


def patch(path: str, body: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    if FOOT_SLOT in text:
        text = text.replace(FOOT_SLOT, body, 1)
    else:
        # 插在主容器末尾之前
        text = text.replace("</main>", body + "\n</main>", 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def add_styles() -> None:
    css = """
    <style>
      .sp-xnav{background:#fff;border:1px solid var(--border);border-radius:8px;
        padding:14px 18px;margin-top:24px;margin-bottom:24px}
      .sp-xnav-title{font-weight:700;font-size:14px;margin-bottom:8px;color:#0f1111}
      .sp-xnav-grid{display:flex;flex-wrap:wrap;gap:8px}
      .sp-xnav-link{display:inline-block;background:#f0f3f7;color:#0f1111;
        padding:6px 12px;border-radius:6px;font-size:13px;border:1px solid #e1e6ec}
      .sp-xnav-link:hover{background:#e3e9ef;text-decoration:none}
      .sp-xnav-mp{margin-top:10px;font-size:12px;color:var(--muted)}
      .sp-xnav-mp-link{color:var(--link);margin-right:10px}
    </style>
    """
    out_dir = os.path.join(ROOT, "output")
    for name in os.listdir(out_dir):
        if not name.endswith(".html"):
            continue
        p = os.path.join(out_dir, name)
        with open(p, "r", encoding="utf-8") as f:
            text = f.read()
        if ".sp-xnav" in text:
            continue
        text = text.replace("</head>", css + "\n</head>", 1)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


def main() -> None:
    cfg = sp.load_config(ROOT)
    add_styles()
    for m in cfg["marketplaces"]:
        body = _xnav_html(m, cfg)
        for fname in [f"{m}.html", f"{m}_seasonality.html",
                      f"{m}_needs.html", f"{m}_kwneeds.html"]:
            p = os.path.join(ROOT, "output", fname)
            if patch(p, body):
                print(f"[ok] xnav → {p}")
            else:
                print(f"[skip] {p}")
    # 总览页也加一份（指向 US）
    body0 = _xnav_html("us", cfg)
    p0 = os.path.join(ROOT, "output", "index.html")
    if patch(p0, body0):
        print(f"[ok] xnav → {p0}")
    print("[done] xnav injected")


if __name__ == "__main__":
    main()
