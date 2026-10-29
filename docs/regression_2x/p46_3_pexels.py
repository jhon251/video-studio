# -*- coding: utf-8 -*-
"""Phase 45 / P45-2：**Pexels 定向获取**（受治；≤20 请求 / ≤14 张入池）。

治理要点（沿用 P7-5 / P33-2 路径 + P45-1 overlay 方案）：
  · 仅 Pexels API；**Pexels License 全池统一**，凭据走 `PEXELS_API_KEY`；
  · **overlay 携带 provider-verified 许可**（`license_class` / `license_cleared` /
    `source_of_record`），使候选**直接被门禁消费**而**无需改 `core/materials.py`**；
  · 逐张完整校验：magic bytes / 容器 / **PIL 完整解码** / 尺寸下限；
  · 摄影师署名（courtesy）+ source_url + sha256 全链留痕；
  · 失败逐条登记（配额、坏 JSON、校验失败）；
  · **目标场景 = 抽象论述景**；目标视觉语言 = 黑板/粉笔手写、抽象概念可视化、
    数学工作场景。

账本：`docs/regression_2x/logs/p45_2_pexels_ledger.json`
入池 payload：`docs/regression_2x/logs/p45_2_pexels_payload.json`
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core.env import load_env                                  # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUTDIR = R / "output" / "phase45_acquired"
API = "https://api.pexels.com/v1/search"
UA = "video-studio/1.0 (local governed pipeline)"
MAX_REQ = 20
MAX_ITEMS = 14
MIN_W, MIN_H = 640, 360
PER_QUERY = 3

# 查询阶梯（授权书 §2 示例 + 抽象段补充）
QUERIES = [
    ("blackboard mathematics", "抽象段·黑板"),
    ("chalk math symbols", "抽象段·粉笔符号"),
    ("mathematician blackboard", "数学工作场景"),
    ("abstract network", "抽象概念可视化"),
    ("teacher classroom math", "数学工作场景"),
    ("formula writing hand", "抽象段·手写公式"),
    ("geometry drawing compass", "几何构图"),
    ("numbers mathematics abstract", "抽象概念可视化"),
]
LICENSE_NOTE = ("Pexels License（免费使用、免强制署名）；本仓按**更保守口径**映射为 "
                "FREE_ATTRIBUTION 并照记摄影师署名（courtesy）")


def main() -> int:
    load_env(R / ".env")
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        print("FAIL-CLOSED: 缺 PEXELS_API_KEY")
        return 1
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ledger = {"schema": "p45-2-pexels-ledger-v1", "source": "Pexels API",
              "license_note": LICENSE_NOTE, "max_requests": MAX_REQ,
              "max_items": MAX_ITEMS, "requests": 0, "downloaded": 0,
              "verified": 0, "rejected": 0, "failures": [], "items": [],
              "started_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    items = []
    for q, purpose in QUERIES:
        if ledger["requests"] >= MAX_REQ or ledger["verified"] >= MAX_ITEMS:
            break
        url = API + "?" + urllib.parse.urlencode(
            {"query": q, "per_page": PER_QUERY, "orientation": "landscape"})
        try:
            req = urllib.request.Request(
                url, headers={"Authorization": key, "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.loads(r.read().decode("utf-8"))
            ledger["requests"] += 1
        except Exception as exc:                                            # noqa: BLE001
            ledger["requests"] += 1
            ledger["failures"].append({"query": q, "stage": "search",
                                       "error": "{}: {}".format(
                                           type(exc).__name__, str(exc)[:120])})
            print("  搜索失败 {}: {}".format(q, type(exc).__name__))
            continue
        photos = data.get("photos") or []
        print("  [{}] {} ⇒ {} 张候选".format(q, purpose, len(photos)))
        for ph in photos:
            if ledger["verified"] >= MAX_ITEMS:
                break
            src = ((ph.get("src") or {}).get("large")
                   or (ph.get("src") or {}).get("original"))
            if not src:
                ledger["failures"].append({"query": q, "stage": "src",
                                           "error": "无 large/original URL"})
                continue
            try:
                req2 = urllib.request.Request(src, headers={"User-Agent": UA})
                with urllib.request.urlopen(req2, timeout=60) as r2:
                    blob = r2.read(12 * 1024 * 1024)
                ledger["downloaded"] += 1
            except Exception as exc:                                        # noqa: BLE001
                ledger["failures"].append({"query": q, "stage": "download",
                                           "error": "{}: {}".format(
                                               type(exc).__name__, str(exc)[:120])})
                continue
            # ---- 完整校验链 ----
            if not blob[:3] in (b"\xff\xd8\xff",) and not blob[:8].startswith(b"\x89PNG"):
                ledger["rejected"] += 1
                ledger["failures"].append({"query": q, "stage": "magic",
                                           "error": "magic bytes 不符"})
                continue
            if len(blob) < 10 * 1024:
                ledger["rejected"] += 1
                ledger["failures"].append({"query": q, "stage": "size",
                                           "error": "文件过小 {} B".format(len(blob))})
                continue
            try:
                with Image.open(io.BytesIO(blob)) as im:
                    im.verify()
                with Image.open(io.BytesIO(blob)) as im:
                    w, h = im.size
                    im.load()                     # **完整解码**
            except Exception as exc:                                        # noqa: BLE001
                ledger["rejected"] += 1
                ledger["failures"].append({"query": q, "stage": "pil",
                                           "error": "{}: {}".format(
                                               type(exc).__name__, str(exc)[:110])})
                continue
            if w < MIN_W or h < MIN_H:
                ledger["rejected"] += 1
                ledger["failures"].append({"query": q, "stage": "dim",
                                           "error": "{}x{} < {}x{}".format(
                                               w, h, MIN_W, MIN_H)})
                continue
            sha = hashlib.sha256(blob).hexdigest()
            if any(x["sha256"] == sha for x in items):
                continue                          # 去重
            ext = ".jpg" if blob[:3] == b"\xff\xd8\xff" else ".png"
            dest = OUTDIR / "{}{}".format(sha[:16], ext)
            dest.write_bytes(blob)
            it = {
                "asset_id": "asset_" + sha[:12],
                "sha256": sha, "path": str(dest), "bytes": len(blob),
                "width": w, "height": h, "media_type": "image",
                "provider": "pexels", "source_id": str(ph.get("id")),
                "source_url": ph.get("url"),
                "photographer": ph.get("photographer"),
                "photographer_url": ph.get("photographer_url"),
                "license": "Pexels License",
                # ---- P45-1 **overlay**：provider-verified 许可（门禁直接消费）----
                "license_class": "FREE_ATTRIBUTION",
                "license_cleared": True,
                "provider_verified": True,
                "source_of_record": "Pexels API response (photo object)",
                "attribution": "Pexels / {}".format(ph.get("photographer") or "unknown"),
                "query": q, "purpose": purpose,
                "usable": True, "match_score": 0,
            }
            items.append(it)
            ledger["verified"] += 1
            print("     + {} {}x{} {}B by {}".format(
                it["asset_id"], w, h, len(blob), str(ph.get("photographer"))[:18]))
    payload = {"schema": "p45-2-pexels-payload-v1",
               "material_mode": "mixed", "material_provided": True,
               "candidates_total": len(items), "candidates": items,
               "license_overlay": {
                   "source_of_record": "Pexels API response",
                   "license": "Pexels License",
                   "license_class": "FREE_ATTRIBUTION",
                   "license_cleared": True,
                   "note": LICENSE_NOTE,
                   "applied_to": [i["asset_id"] for i in items]}}
    (L / "p45_2_pexels_payload.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    ledger["items"] = [{k: v for k, v in i.items()
                        if k in ("asset_id", "sha256", "width", "height", "bytes",
                                 "photographer", "source_url", "query", "purpose",
                                 "license", "license_class", "license_cleared",
                                 "source_of_record")} for i in items]
    ledger["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (L / "p45_2_pexels_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("请求 {} / 上限 {} | 下载 {} | **入池 {} / 上限 {}** | 拒收 {} | 失败 {}".format(
        ledger["requests"], MAX_REQ, ledger["downloaded"], ledger["verified"],
        MAX_ITEMS, ledger["rejected"], len(ledger["failures"])))
    print("-> docs/regression_2x/logs/p45_2_pexels_{ledger,payload}.json")
    return 0 if items else 1


if __name__ == "__main__":
    raise SystemExit(main())
