# -*- coding: utf-8 -*-
"""P33-2：**受治理素材获取**（仅 Wikimedia Commons；许可门不放宽；≤10 张）。

治理要点（沿用 P7-5 / P16-3 路径）：
  · 仅 `WikimediaCommonsProvider`；许可门**逐张不放宽**（无记录/受限 ⇒ 拒收，不推断）；
  · 全阶段**获取上限 = 10 张**（授权书）；
  · 目标：池 **12 → ≥20**；
  · 下载后逐张走 provider 内建 `verify_material`（magic bytes/容器/ffprobe/PIL/尺寸/许可）；
  · 逐请求记账（`provider.stats.response_digests` 原始留痕）。

**本脚本会发出真实网络请求。** 零 LLM、零 VLM。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.tools.base import ToolContext                                  # noqa: E402
from video_studio.tools.material_provider import MaterialQuery                   # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider       # noqa: E402
from video_studio.agents.retrieval.agent import kw_tokens                        # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
OUTDIR = R / "output" / "phase33_acquired"
PROJ_MEDIA = R / "projects" / "p_96efdc03e1aa" / "media" / "acquired_materials"
POOL = L / "phase16_retrieval_payload.json"
MAX_FETCH = 10
PER_QUERY = 4

QUERIES = [
    ("four color theorem map proof", "S03"),
    ("mathematical proof diagram", "S04"),
    ("formal verification mathematics", "S11"),
    ("computer assisted proof", "S06"),
    ("graph theory planar graph", "S07"),
    ("mathematical logic symbols", "S09"),
    ("theorem proving software", "S13"),
    ("mathematical manuscript old", "S14"),
    ("geometry theorem diagram", "S15"),
    ("mathematics blackboard formula", "S18"),
]


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    PROJ_MEDIA.mkdir(parents=True, exist_ok=True)
    cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    existing = [c for c in pool["candidates"] if c.get("path")]
    have_sha = {c["sha256"] for c in existing}
    have_names = {c.get("name") for c in existing}
    print("现有池 {} 张 | 目标 ≥20 | 上限 {} 张".format(len(existing), MAX_FETCH))

    ctx = ToolContext(role="retrieval", project_id="p_96efdc03e1aa",
                      project_dir=R / "projects" / "p_96efdc03e1aa",
                      db=None, config=cfg)
    provider = WikimediaCommonsProvider(policy={"max_requests": MAX_FETCH + 8})

    ledger = {"schema": "p33-2-governed-acquisition-v1",
              "provider": provider.name, "max_fetch_total": MAX_FETCH,
              "target_pool": 20, "queries": [q for q, _ in QUERIES],
              "fetched": [], "rejected": [], "candidates_seen": []}
    fetched = 0
    for q, sid in QUERIES:
        if fetched >= MAX_FETCH:
            break
        mq = MaterialQuery(text=q, scene_id=sid, limit=PER_QUERY, kinds=("image",),
                           keywords=kw_tokens(q))
        try:
            found = provider.search(mq, ctx)
        except Exception as exc:                                            # noqa: BLE001
            print("  [{}] 搜索失败: {}".format(q, str(exc)[:120]), flush=True)
            continue
        print("  [{}] {} 候选".format(q, len(found)), flush=True)
        allow = [c for c in found
                 if getattr(c, "license_cleared", False)
                 and (c.width or 0) >= 800 and (c.height or 0) >= 600
                 and c.sha256 not in have_sha and (c.name or "") not in have_names]
        allow.sort(key=lambda c: (-(c.match_score or 0), c.source_id))
        for c in allow:
            if fetched >= MAX_FETCH:
                break
            try:
                res = provider.fetch([c], ctx)
            except Exception as exc:                                        # noqa: BLE001
                ledger["rejected"].append({"source_id": c.source_id, "name": c.name,
                                           "error": "{}: {}".format(
                                               type(exc).__name__, str(exc)[:140])})
                continue
            row = res[0] if res else c
            if row.status != "VERIFIED":
                ledger["rejected"].append({"source_id": row.source_id, "name": row.name,
                                           "status": row.status,
                                           "error_code": row.error_code,
                                           "detail": str(row.error_detail)[:140]})
                print("     {} {}".format(row.status, str(row.name)[:40]), flush=True)
                continue
            # 复制到项目素材目录（供渲染链按绝对路径读取）
            # 注意：provider 的 `cache_dir="external"` 是**相对项目 media 目录**的，
            # 故 `downloaded_path` 可能是相对路径 —— 需先按 media 目录解析（实测踩坑）。
            src = pathlib.Path(str(row.downloaded_path))
            cand_paths = [src, PROJ_MEDIA.parent / src, R / src,
                          PROJ_MEDIA / src.name]
            real = next((q for q in cand_paths if q.is_file()), None)
            if real is None:
                ledger["rejected"].append({"source_id": row.source_id, "name": row.name,
                                           "error": "DOWNLOADED_PATH_NOT_FOUND: {}".format(
                                               str(row.downloaded_path)[:160])})
                print("     路径不可达: {}".format(str(row.downloaded_path)[:80]),
                      flush=True)
                continue
            src = real
            ext = src.suffix or ".jpg"
            dst = PROJ_MEDIA / "{}{}".format(row.sha256[:32], ext)
            if not dst.is_file():
                shutil.copy2(src, dst)
            rec = {
                "asset_id": "asset_p33_" + row.sha256[:12],
                "name": row.name, "sha256": row.sha256,
                "path": str(dst), "relative_path": "acquired_materials/" + dst.name,
                "bytes": dst.stat().st_size, "width": getattr(row, "width", None),
                "height": getattr(row, "height", None),
                "license": row.license,
                "license_class": getattr(row, "license_class", None),
                "license_cleared": getattr(row, "license_cleared", None),
                "attribution": row.attribution, "provider": provider.name,
                "source_id": row.source_id, "source_url": row.source_url,
                "media_type": (src.suffix or "").lstrip(".").lower() or "jpg",
                "origin": "P33-2 governed acquisition", "match_score": 0,
                "query": q, "scene_hint": sid,
            }
            have_sha.add(row.sha256)
            have_names.add(row.name)
            ledger["fetched"].append(rec)
            fetched += 1
            print("     VERIFIED {:<44} {}x{} {}".format(
                str(row.name)[:44], row.width, row.height, row.license), flush=True)

    ledger["fetched_total"] = fetched
    ledger["provider_stats"] = {k: v for k, v in provider.stats.items()
                                if k != "response_digests"}
    ledger["request_ledger"] = provider.stats.get("response_digests") or []
    ledger["network_requests"] = provider.stats.get("requests")
    ledger["network_requests_failed"] = provider.stats.get("requests_failed")
    ledger["zero_llm"] = True
    ledger["zero_vlm"] = True
    (L / "p33_2_acquisition_ledger.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    # ---- 合并成新池（既有 12 + 新获取）----
    merged = existing + ledger["fetched"]
    newpool = {**pool, "candidates": merged, "candidates_total": len(merged),
               "index_source": "phase16_retrieval_payload.json + phase33_acquired",
               "note": "P33-2 池扩容：{} 张（含本轮受治理获取 {} 张）".format(
                   len(merged), fetched)}
    (L / "phase33_retrieval_payload.json").write_text(
        json.dumps(newpool, ensure_ascii=False, indent=1), encoding="utf-8")

    print()
    print("=" * 72)
    print("获取 {} 张（上限 {}）| 网络请求 {}（失败 {}）".format(
        fetched, MAX_FETCH, ledger["network_requests"],
        ledger["network_requests_failed"]))
    print("新池 = {} 张（既有 {} + 新 {}）".format(
        len(merged), len(existing), fetched))
    print("许可类别:", json.dumps(provider.stats.get("license_classes") or {},
                                   ensure_ascii=False))
    print("-> " + str((L / "phase33_retrieval_payload.json").relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
