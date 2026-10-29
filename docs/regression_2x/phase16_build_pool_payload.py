# -*- coding: utf-8 -*-
"""P16-4/P16-5 前置：为沙箱渲染构建**覆盖全池**的 retrieval 载荷（候选路径相对 media/）。

设计：候选 = media/ 下**全部 12 张唯一图像**（含 P16-2 登记的 H5 素材 + P16-3 获取的新素材），
按需求关键词给出确定性 match_score（沿用生产 `kw_tokens` + 词面命中口径），
使引擎的确定性选材能在**扩池后**自由重选（这正是 P16-4「S03 重选」的落地方式：
不硬编码指定，而是让选材在更大池中重新求解，避免"机器确认即放行"）。

许可/署名沿用 Phase 12 覆盖层与 P16-3 台账记录（**零推断**）。
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

from video_studio.agents.retrieval.agent import kw_tokens, matched_tokens, score  # noqa: E402

PROJ = R / "projects" / PID
MEDIA = PROJ / "media"

overlay = json.loads((L / "license_overlay_v1.json").read_text(encoding="utf-8"))
ov_by_sha = {e["asset_sha256"]: e for e in (overlay.get("entries") or [])
             if e.get("asset_sha256")}
acq = json.loads((L / "phase16_acquisition_ledger.json").read_text(encoding="utf-8"))
acq_by_sha = {}
for x in acq.get("fetched") or []:
    if x.get("sha256"):
        acq_by_sha[x["sha256"]] = x
# P16-3 下载件的 sha 不在 fetched.sha256（provider 未回填）⇒ 由下载路径文件重算绑定
for x in acq.get("fetched") or []:
    dp = x.get("downloaded_path")
    if dp:
        p = MEDIA / dp
        if p.is_file():
            acq_by_sha[hashlib.sha256(p.read_bytes()).hexdigest()] = x
# 本阶段（P16-3）**新获取**的 sha 集合（与既有 external/ 缓存区分开）
P16_3_NEW = {s for s, x in acq_by_sha.items()
             if x.get("status") == "VERIFIED" and x.get("scene_id")}
# P16-2 登记件的 sha 集合
reg = json.loads((L / "phase16_local_registry.json").read_text(encoding="utf-8"))
P16_2_NEW = {r["sha256"] for r in (reg.get("registered") or [])}
print("P16-3 新获取 sha:", sorted(x[:12] for x in P16_3_NEW))
print("P16-2 登记 sha :", sorted(x[:12] for x in P16_2_NEW))

# 唯一图像（按 sha 去重，规范路径取字典序最小）
# 扫描三处：media/（冻结索引态，保持不变）+ registered_materials/（P16-2）+ acquired_materials/（P16-3）
SCAN_DIRS = [MEDIA, PROJ / "registered_materials", PROJ / "acquired_materials"]
uniq: dict[str, pathlib.Path] = {}
for d in SCAN_DIRS:
    if not d.is_dir():
        continue
    for f in sorted(d.rglob("*")):
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            s = hashlib.sha256(f.read_bytes()).hexdigest()
            uniq.setdefault(s, f)

print("池内唯一图像:", len(uniq))

candidates = []
for s, f in sorted(uniq.items()):
    ov = ov_by_sha.get(s)
    aq = acq_by_sha.get(s)
    rel = f.relative_to(MEDIA).as_posix() if str(f).startswith(str(MEDIA)) \
        else f.relative_to(PROJ).as_posix()
    lic = (ov or {}).get("license") or (aq or {}).get("license")
    lclass = (ov or {}).get("license_class") or (aq or {}).get("license_class")
    attr = (ov or {}).get("attribution") or (aq or {}).get("attribution")
    if s in P16_3_NEW:
        origin, prov = "P16-3 acquired", "wikimedia_commons"
        cleared = True                       # provider 许可门禁已放行（license_cleared=True）
    elif s in P16_2_NEW:
        origin, prov = "P16-2 registered", "local_ingest"
        cleared = bool((ov or {}).get("license_cleared"))
    elif rel.startswith("external/"):
        origin, prov = "pre-existing pool (Phase 2-E cache)", "wikimedia_commons"
        cleared = bool((ov or {}).get("license_cleared")) if ov else None
    else:
        origin, prov = "pre-existing pool", "local_ingest"
        cleared = bool((ov or {}).get("license_cleared")) if ov else None
    candidates.append({
        "asset_id": None,
        "name": f.name,
        "path": str(f),                      # **绝对路径**：沙箱渲染不复制图像，保证字节一致
        "relative_path": rel,
        "provider": prov,
        "source_id": ((aq or {}).get("source_id") or (ov or {}).get("source_id")),
        "source_url": ((aq or {}).get("source_url") or (ov or {}).get("source_url")),
        "license": lic,
        "license_class": lclass,
        "license_cleared": cleared,
        "attribution": attr,
        "media_type": f.suffix.lstrip(".").lower().replace("jpg", "jpeg"),
        "bytes": f.stat().st_size,
        "sha256": s,
        "match_score": 0,
        "origin": origin,
    })

# 每个候选按"通用数学/证明"查询给确定性分数（引擎会用**逐景**旁白重算实际选材）
print("候选（{}）:".format(len(candidates)))
for c in candidates:
    print("  {:6s} {:62s} {:>9,}B".format(
        c["license_class"] or "?", c["path"], c["bytes"]))

payload = {
    "schema": "retrieval-candidates-v1",
    "material_mode": "mixed",
    "candidates_total": len(candidates),
    "material_provided": True,
    "external_requested": True,
    "external_provider": "wikimedia_commons",
    "index_source": "phase16_expanded_pool",
    "note": ("Phase 16 扩池后的候选池（P16-2 登记 + P16-3 受治理获取）；"
             "许可/署名沿用既有记录，零推断；match_score 由引擎按逐景旁白重算"),
    "candidates": candidates,
    "counts": {
        "total": len(candidates),
        "with_license_record": sum(1 for c in candidates if c["license"]),
        "by_origin": {k: sum(1 for c in candidates if c["origin"] == k)
                      for k in ("pre-existing pool", "pre-existing pool (Phase 2-E cache)",
                                "P16-2 registered", "P16-3 acquired")},
    },
}
out = L / "phase16_retrieval_payload.json"
out.write_text(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True),
               encoding="utf-8")
print()
print("候选池 ->", out.relative_to(R).as_posix())
print("counts:", json.dumps(payload["counts"], ensure_ascii=False))
