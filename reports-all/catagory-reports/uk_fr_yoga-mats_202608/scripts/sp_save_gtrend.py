"""Save google_trend for both sites (handle ANSI in CLI output)."""
import os
import re
import json
import subprocess
import time

ROOT = r"p:\trae.ai\TraeCN projects learning\amazon-select-product\uk_fr_yoga-mats_202608"
SS = r"C:\Users\HP\AppData\Roaming\Python\Python313\Scripts\sellersprite.exe"

ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")


def call(args, timeout=60):
    r = subprocess.run([SS] + args, capture_output=True, text=True,
                       encoding="utf-8", timeout=timeout)
    return ANSI.sub("", r.stdout).strip()


for mp, geo in [("uk", "GB"), ("fr", "FR")]:
    raw = call(["trend", "google", "--keyword", "yoga mats",
                "--google-prop", "shoppingCart", "--monthly",
                "--marketplace", geo])
    try:
        d = json.loads(raw)
    except Exception as e:
        print(f"{mp} parse error: {e}; raw[:200]={raw[:200]}")
        continue
    p = os.path.join(ROOT, "raw", mp, "google_trend.json")
    if isinstance(d, list):
        d = {"items": d, "_list_wrapped": True}
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    items = d.get("items", []) if isinstance(d, dict) else d
    print(f"{mp} saved, items={len(items) if isinstance(items, list) else '?'}")
    time.sleep(2)
