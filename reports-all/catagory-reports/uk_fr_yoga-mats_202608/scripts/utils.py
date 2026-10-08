"""
utils.py
========
SOP V3.1 配套工具库
功能：
  1. 加载 dev_config.json（开发模式 / 试跑站点 / 限流参数）。
  2. safe_call(func, *args, **kwargs)：统一封装「请求间隔 + 429 指数退避 + mock 短路」三件套，
     所有调用 sellersprite 的脚本都建议通过它走，避免在每个脚本里重复写 time.sleep / 重试。
  3. active_marketplaces()：返回当前 dev_config.json 允许跑的站点列表（默认从 data/config.json 读）。
  4. 其它与限流/Mock 相关的辅助函数。

设计原则：
  - mock_mode = true 时，**不发起任何真实网络请求**，直接读 mock_data/{mp}/*.json，
    让"渲染脚本"和"重跑诊断"在零 API 消耗下完成。
  - mock_mode = false 时，正常按 request_interval 节流调用，遇 429 自动 5/10/20 秒退避。
"""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "dev_config.json"
DATA_CONFIG = ROOT / "data" / "config.json"


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """读取 dev_config.json；不存在则返回安全默认值（mock 关、全站点、间隔 1.5s）。"""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[utils] ⚠️ dev_config.json 解析失败: {e}，使用安全默认值。")
    return {
        "mock_mode": False,
        "active_sites": None,         # None = 不限制，跑 data/config.json 中全部站点
        "mock_data_path": "mock_data",
        "request_interval": 1.5,
        "max_retries": 3,
        "batch_size": 3,
        "rate_limit_per_min": 40,
    }


CONFIG = load_config()


def reload_config() -> dict:
    """热重载：脚本内修改 dev_config.json 后可调用本函数刷新。"""
    global CONFIG
    CONFIG = load_config()
    return CONFIG


# ---------------------------------------------------------------------------
# 站点列表过滤
# ---------------------------------------------------------------------------
def active_marketplaces(default: Optional[list] = None) -> list:
    """
    返回当前允许跑的站点列表：
      1. 优先用 dev_config.json 中的 active_sites（list）；
      2. 若为空 / 为 None，则用 data/config.json 中的 marketplaces；
      3. 都没有则用参数 default。
    用途：sp_fetch_data.py / sp_score.py 等批量脚本在开头调用一次，
         然后用 `for mp in active_marketplaces():` 即可实现"试跑只跑 1 个站"。
    """
    sites = CONFIG.get("active_sites")
    if sites:
        return [str(s).lower() for s in sites]
    if DATA_CONFIG.exists():
        try:
            with open(DATA_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            return [str(s).lower() for s in cfg.get("marketplaces", [])]
        except Exception:
            pass
    return default or ["us"]


# ---------------------------------------------------------------------------
# 限流 + Mock 短路
# ---------------------------------------------------------------------------
def _try_load_mock(marketplace: str, key: str) -> Optional[Any]:
    """从 mock_data/{marketplace}/{key}.json 读模拟数据，文件不存在返回 None。"""
    mock_dir = ROOT / CONFIG.get("mock_data_path", "mock_data")
    path = mock_dir / marketplace / f"{key}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[utils] ⚠️ 读取 mock 数据失败 {path}: {e}")
    return None


def safe_call(
    func: Callable,
    *args,
    marketplace: Optional[str] = None,
    mock_key: Optional[str] = None,
    **kwargs,
) -> Any:
    """
    统一封装「限流 + 429 退避 + Mock 短路」。

    用法：
        from utils import safe_call
        result = safe_call(
            sellersprite.market_research,
            marketplace="uk",
            niche="yoga mats",
            marketplace_for_mock="uk",
            mock_key="market_research",
        )

    行为：
      - mock_mode = true → 不调用 func，直接读 mock_data/{mp}/{mock_key}.json
      - mock_mode = false → 按 request_interval 等待后调用 func；
        若触发 429 / 限流，指数退避（5s, 10s, 20s，最多 max_retries 次）。
    """
    # 1) Mock 短路
    if CONFIG.get("mock_mode", False):
        mp = (marketplace or kwargs.get("marketplace_for_mock") or "").lower()
        if not mp:
            return {"_mock": True, "data": []}
        data = _try_load_mock(mp, mock_key or func.__name__.replace(".", "_"))
        if data is not None:
            print(f"[utils] 🟡 Mock 命中：{mp}/{mock_key or func.__name__}（零 API 消耗）")
            return data
        print(f"[utils] 🟡 Mock 未命中：{mp}/{mock_key or func.__name__}，返回空数据（零 API 消耗）")
        return {"_mock": True, "data": []}

    # 2) 真实调用：节流 + 退避
    interval = float(CONFIG.get("request_interval", 1.5))
    max_retries = int(CONFIG.get("max_retries", 3))
    # 即使在 mock 模式外，KeyboardInterrupt 也必须直接抛出
    time.sleep(interval)  # 请求间隔

    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        # V3.1 安全：限定异常范围，避免吞掉 KeyboardInterrupt/SystemExit
        except (IOError, OSError, ValueError, TypeError, KeyError, AttributeError,
                ConnectionError, TimeoutError) as e:
            last_err = e
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 429 or "rate" in str(e).lower() or "429" in str(e):
                wait = min(5 * (2 ** attempt), 60)
                print(f"[utils] 🚨 触发限流(429)，等待 {wait}s 后重试 ({attempt + 1}/{max_retries})…")
                time.sleep(wait)
                continue
            # 非限流错误直接抛出
            raise
    raise RuntimeError(f"[utils] 重试 {max_retries} 次仍失败：{last_err}")


# ---------------------------------------------------------------------------
# 其它辅助
# ---------------------------------------------------------------------------
def mock_sites_summary() -> str:
    """打印当前 mock 配置摘要，供 sp_diagnose_visual.py / README 引用。"""
    return (
        f"mock_mode={CONFIG.get('mock_mode')} | "
        f"active_sites={CONFIG.get('active_sites') or 'all'} | "
        f"interval={CONFIG.get('request_interval')}s | "
        f"batch_size={CONFIG.get('batch_size')}"
    )


if __name__ == "__main__":
    # 自检：直接 `python utils.py` 打印当前配置
    print("[utils] 当前配置：", json.dumps(CONFIG, ensure_ascii=False, indent=2))
    print("[utils] 允许跑的站点：", active_marketplaces())
    print("[utils] 摘要：", mock_sites_summary())
