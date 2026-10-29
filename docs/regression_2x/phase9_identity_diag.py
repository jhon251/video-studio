# -*- coding: utf-8 -*-
"""Phase 9 诊断：定位「二次运行 vs 首次」判定内容比较的差异键（用真实缓存与真实产物）。"""
import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.visual_requirement import canonical                          # noqa: E402
from video_studio.ops import retention as OPS                                       # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
cache = json.loads((LOGS / "phase9_retention_cache.json").read_text(encoding="utf-8"))
print("缓存条目:", len(cache))
EXCL = ("cache_hit", "usage", "cost_usd", "latency_ms", "price_band", "elapsed_s", "tokens",
        "reasoning_tokens", "raw_text_sha256", "detail", "raw_text")


def judged(rep):
    d = {k: v for k, v in rep.items() if k != "taken_at_utc"}
    d["llm"] = {k: v for k, v in (rep.get("llm") or {}).items() if k not in EXCL}
    return d


def diff(a, b, path="$"):
    out = []
    if type(a) is not type(b):
        return ["{}: type {} != {}".format(path, type(a).__name__, type(b).__name__)]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append("{}.{}: 仅第二次有".format(path, k))
            elif k not in b:
                out.append("{}.{}: 仅第一次有".format(path, k))
            else:
                out += diff(a[k], b[k], "{}.{}".format(path, k))
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("{}: 长度 {} != {}".format(path, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff(x, y, "{}[{}]".format(path, i))
    elif a != b:
        out.append("{}: {!r} != {!r}".format(path, str(a)[:60], str(b)[:60]))
    return out


for arm, fixture in (("v2", "phase8_ab_v2.json"), ("v3", "phase8_ab_v3.json")):
    art = json.loads((LOGS / "phase9_backtest_{}.json".format(arm)).read_text(encoding="utf-8"))
    first = art["report"]
    payload = json.loads((LOGS / fixture).read_text(encoding="utf-8"))
    script = payload.get("script") if isinstance(payload.get("script"), dict) else payload
    second = OPS.evaluate(script, source=first.get("source"), cache=cache, llm=True,
                          taken_at=first.get("taken_at_utc"))
    print("==", arm, "| first.cache_hit:", first["llm"].get("cache_hit"),
          "second.cache_hit:", second["llm"].get("cache_hit"))
    d = diff(judged(first), judged(second))
    print("   差异:", d[:8] if d else "NONE（判定内容一致）")
