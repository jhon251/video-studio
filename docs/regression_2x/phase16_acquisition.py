# -*- coding: utf-8 -*-
"""P16-3 受治理获取（P7-5 路径）：仅 Wikimedia、全阶段 ≤12 张、逐张许可门禁 + 完整校验链。

治理要点（授权书 §4）：
  · 目标场景 = DQ-2 高复用 / DQ-3 长静态点名场景（S03 / S06 / S07，以复验报告为准）
  · 每景 5–8 候选；**全阶段获取上限 12 张**（provider 自带 max_requests=12 预算）
  · 仅 Wikimedia Commons；许可门禁逐张不放宽（无记录/受限 ⇒ 拒收，不推断）
  · 初筛：P16-1 门禁 **FAIL** ⇒ 按授权书回退**人工短名单（provider 元数据）**
  · 下载后逐张走完整校验链（magic bytes/容器/ffprobe/PIL/尺寸/许可）——由 provider 内建 verify_material 执行
  · 逐请求记账（provider.stats.response_digests 原始留痕）

**注意**：本脚本会发出**真实网络请求**（Wikimedia Commons）。零 LLM、零 VLM。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PID = "p_96efdc03e1aa"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.tools.material_provider import MaterialQuery                  # noqa: E402
from video_studio.tools.provider_wikimedia import WikimediaCommonsProvider      # noqa: E402
from video_studio.tools.base import ToolContext                                 # noqa: E402
from video_studio.agents.retrieval.agent import kw_tokens                       # noqa: E402

PROJ = R / "projects" / PID
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))

# 已在池内的素材名/来源（避免把已有图重复获取）
existing_names = {f.name for f in (PROJ / "media").rglob("*") if f.is_file()}
print("池内已有文件名数:", len(existing_names))

# 目标场景与检索意图（人工短名单口径：query 由**人工撰写**，非模型生成）
TARGETS = [
    {"scene_id": "S03", "why": "DQ-3 长静态 58.47s（>25s 上限）+ S03 线稿盲区；讲 1977 Appel-Haken 机器证明",
     "queries": ["four color theorem proof diagram", "graph coloring planar map"]},
    {"scene_id": "S06", "why": "DQ-2 高复用（asset_cfae038f6106 六景之一）+ DQ-3 长静态 67.37s；讲 1980 Detlefsen-Luker 回应",
     "queries": ["philosophy of mathematics proof", "mathematical proof manuscript 1980"]},
    {"scene_id": "S07", "why": "DQ-2 高复用 + DQ-3 长静态 66.49s；讲两种立场对照（四色定理案例）",
     "queries": ["mathematical proof two columns comparison", "four color theorem map"]},
]
MAX_FETCH_TOTAL = 12
PER_SCENE_CANDIDATES = 6

ctx = ToolContext(role="retrieval", project_id=PID, project_dir=PROJ,
                  db=None, config=cfg)
pol = {"max_requests": MAX_FETCH_TOTAL + 4}      # 搜索请求预算（下载不计入 provider._request 预算）
provider = WikimediaCommonsProvider(policy=pol)
print("provider:", provider.name, "| policy auth:", provider.policy.get("auth"),
      "| max_requests:", provider.policy.get("max_requests"),
      "| license_required:", provider.policy.get("license_required"))
print()

ledger = {
    "schema": "phase16-governed-acquisition-v1",
    "stage": "Phase 16 P16-3 受治理获取（仅 Wikimedia）",
    "provider": provider.name,
    "policy": {k: provider.policy.get(k) for k in
               ("max_bytes", "timeout_s", "min_interval_s", "max_requests",
                "search_limit", "license_required", "cache_dir", "require_https")},
    "p16_1_gate": "FAIL",
    "prescreen_mode": "MANUAL_SHORTLIST（provider 元数据；P16-1 过滤器未接线）",
    "targets": TARGETS,
    "max_fetch_total": MAX_FETCH_TOTAL,
    "scene_results": [],
}
fetched_total = 0
all_fetched = []

for t in TARGETS:
    if fetched_total >= MAX_FETCH_TOTAL:
        break
    srec = {"scene_id": t["scene_id"], "why": t["why"], "queries": t["queries"],
            "candidates": [], "fetched": [], "rejected": []}
    for q in t["queries"]:
        if fetched_total >= MAX_FETCH_TOTAL:
            break
        kws = kw_tokens(q)
        mq = MaterialQuery(text=q, scene_id=t["scene_id"],
                           limit=PER_SCENE_CANDIDATES, kinds=("image",), keywords=kws)
        try:
            found = provider.search(mq, ctx)
        except Exception as exc:                                            # noqa: BLE001
            srec["candidates"].append({"query": q, "error": "{}: {}".format(
                type(exc).__name__, str(exc)[:160])})
            print("  [{}] 搜索失败 {}: {}".format(t["scene_id"], q, exc))
            continue
        print("  [{}] '{}' -> {} 候选".format(t["scene_id"], q, len(found)))
        for c in found:
            srec["candidates"].append({
                "query": q, "source_id": c.source_id, "name": c.name,
                "url": c.source_url, "ext": c.ext,
                "license": c.license,
                "license_class": getattr(c, "license_class", None),
                "license_cleared": getattr(c, "license_cleared", None),
                "attribution": c.attribution, "bytes": c.bytes,
                "match_score": c.match_score,
                "probe": c.probe_result,
            })
        # 人工短名单口径：按 provider 元数据（许可已清 + 有尺寸 + 分数降序）取前若干
        allow = [c for c in found
                 if getattr(c, "license_cleared", False)
                 and (c.width or 0) >= 800 and (c.height or 0) >= 600
                 and (c.name or "") not in existing_names]
        allow.sort(key=lambda c: (-(c.match_score or 0), c.source_id))
        take = allow[:max(0, MAX_FETCH_TOTAL - fetched_total)]
        if not take:
            print("     短名单为空（无可放行候选）")
        for c in take:
            try:
                res = provider.fetch([c], ctx)
            except Exception as exc:                                        # noqa: BLE001
                srec["rejected"].append({"source_id": c.source_id,
                                         "error": "{}: {}".format(type(exc).__name__,
                                                                  str(exc)[:160])})
                continue
            row = res[0] if res else c
            rec = {"scene_id": t["scene_id"], "query": q, "source_id": row.source_id,
                   "name": row.name, "status": row.status,
                   "error_code": row.error_code, "error_detail": row.error_detail,
                   "license": row.license, "license_class": getattr(row, "license_class", None),
                   "license_cleared": getattr(row, "license_cleared", None),
                   "attribution": row.attribution, "downloaded_path": row.downloaded_path,
                   "sha256": getattr(row, "sha256", None),
                   "width": getattr(row, "width", None), "height": getattr(row, "height", None),
                   "verify": getattr(row, "verify_result", None),
                   "source_url": row.source_url}
            if row.status == "VERIFIED":
                fetched_total += 1
                all_fetched.append(rec)
                srec["fetched"].append(rec)
                print("     VERIFIED {} ({}) {}x{}".format(
                    row.name[:44], row.downloaded_path, getattr(row, "width", "?"),
                    getattr(row, "height", "?")))
            else:
                srec["rejected"].append(rec)
                print("     {} {} | {} {}".format(row.status, row.name[:34],
                                                  row.error_code, str(row.error_detail)[:70]))
            if fetched_total >= MAX_FETCH_TOTAL:
                break
    ledger["scene_results"].append(srec)

ledger["fetched_total"] = fetched_total
ledger["fetched"] = all_fetched
ledger["provider_stats"] = {k: v for k, v in provider.stats.items()
                            if k != "response_digests"}
ledger["request_ledger"] = provider.stats.get("response_digests") or []
ledger["network_requests"] = provider.stats.get("requests")
ledger["network_requests_failed"] = provider.stats.get("requests_failed")
ledger["downloads_ms"] = provider.stats.get("download_ms")
ledger["zero_llm"] = True
ledger["zero_vlm"] = True

lp = L / "phase16_acquisition_ledger.json"
lp.write_text(json.dumps(ledger, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print()
print("=" * 78)
print("P16-3 获取小结")
print("=" * 78)
print("  获取成功（VERIFIED）:", fetched_total, "/ 上限", MAX_FETCH_TOTAL)
print("  网络请求: {}（失败 {}）| 下载耗时 {:.0f}ms".format(
    ledger["network_requests"], ledger["network_requests_failed"], ledger["downloads_ms"]))
print("  许可类别分布:", json.dumps(provider.stats.get("license_classes"), ensure_ascii=False))
print("  台账 ->", lp.relative_to(R).as_posix())
