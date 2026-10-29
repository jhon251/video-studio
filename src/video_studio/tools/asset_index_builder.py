# -*- coding: utf-8 -*-
"""P7-2：**项目级 AssetIndex 构建器**（确定性、离线、零网络、只读扫描）。

输入（全部只读）
  · `projects/<pid>/media/**`（项目资产范围；含 `external/` 及其 `.index.json`）
  · 显式纳入的 H5 两件素材（人工验收记录在 `phase6g_exec_h5.json`）
  · `render_output.material_timeline`（6-G 母片**实际使用**的资产 + legacy asset_id）

输出：`asset_index.json`（候选契约见 `core.asset_candidate`；含近重复四类关系与整体 hash）

复用（不新增算法）：`orchestration/content_identity.py`（MD5/dHash/hamming/聚类）、
`orchestration/crop_recheck.py`（`full_bleed_box` 及其默认阈值）。
未接线/未提供的能力**明确记 UNKNOWN**（如镜像不变比较、完整 G0–G9 门禁），不得冒充。
"""
from __future__ import annotations

import json
import pathlib
import subprocess

from ..core.asset_candidate import (INDEX_SCHEMA, INDEX_VERSION, INTEGRITY_STATES, MEDIA_KINDS,
                                    NOT_AVAILABLE, UNKNOWN, family_id, make_candidate,
                                    perceptual_identity, stable_asset_id, validate_candidate,
                                    candidate_hash)
from ..core.materials import DEFAULT_POLICY, classify_license, license_gate_applies
from ..orchestration.content_identity import (build_content_index, dhash_arr, dhash_of, hamming,
                                              md5_of)
from ..orchestration.crop_recheck import full_bleed_box

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff")
VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi")
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")
META_EXT = (".json", ".txt", ".md", ".csv")

SAME_BAND = 6            # content_identity 默认（不为通过测试而调整）
SUSPECT_BAND = 10
CROP_MAX_SHIFT = 14      # crop_recheck.evaluate_crop 默认 max_shift
MIN_VISIBLE = 0.55       # crop_recheck 默认 min_visible
ASPECT_TOL = 0.05


def sha256_file(p) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _probe(p: pathlib.Path) -> dict:
    """PIL（图像）或 ffprobe（视频）实测；失败明确记录，不猜。"""
    out = {"decode_status": UNKNOWN, "detail": "", "width": UNKNOWN, "height": UNKNOWN,
           "duration_s": NOT_AVAILABLE, "frame_count": NOT_AVAILABLE, "kind": "other"}
    ext = p.suffix.lower()
    if ext in IMAGE_EXT:
        out["kind"] = "image"
        try:
            from PIL import Image
            with Image.open(p) as im:
                out.update({"width": int(im.size[0]), "height": int(im.size[1]),
                            "decode_status": "OK", "detail": "PIL:{}".format(im.format)})
        except Exception as exc:                                          # noqa: BLE001
            out.update({"decode_status": "FAILED", "detail": "PIL:{}".format(type(exc).__name__)})
        return out
    if ext in VIDEO_EXT:
        out["kind"] = "video"
        ff = str(pathlib.Path(r"C:\mp4agent\video-studio\bin\ffprobe.exe"))
        try:
            r = subprocess.run([ff, "-v", "error", "-show_entries",
                                "format=duration:stream=codec_type,width,height,nb_frames",
                                "-of", "json", str(p)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            j = json.loads(r.stdout or "{}")
            v = next((x for x in (j.get("streams") or []) if x.get("codec_type") == "video"), None)
            if v:
                out.update({"width": v.get("width") or UNKNOWN, "height": v.get("height") or UNKNOWN,
                            "decode_status": "OK", "detail": "ffprobe"})
                if v.get("nb_frames"):
                    out["frame_count"] = int(v["nb_frames"])
            else:
                out.update({"decode_status": "FAILED", "detail": "ffprobe:no_video_stream"})
            if (j.get("format") or {}).get("duration"):
                out["duration_s"] = round(float(j["format"]["duration"]), 3)
        except Exception as exc:                                          # noqa: BLE001
            out.update({"decode_status": "FAILED", "detail": "ffprobe:{}".format(
                type(exc).__name__)})
        return out
    if ext in AUDIO_EXT:
        out["kind"] = "audio"
        return out
    return out


def classify_kind(p: pathlib.Path) -> str:
    ext = p.suffix.lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    return "other"


def load_external_index(media_root: pathlib.Path) -> dict:
    """`media/external/.index.json`：{provider|source_id: {file,...}} → 反查 file→(provider,id)。"""
    p = media_root / "external" / ".index.json"
    if not p.is_file():
        return {"by_file": {}, "entries": 0, "missing_files": []}
    j = json.loads(p.read_text(encoding="utf-8"))
    by_file = {}
    for key, rec in j.items():
        prov, _, sid = str(key).partition("|")
        fn = rec.get("file")
        if fn:
            by_file[fn] = {"provider": prov, "source_id": sid, "bytes": rec.get("bytes")}
    present = {f.name for f in (media_root / "external").glob("*") if f.is_file()}
    missing = sorted(set(by_file) - present)
    return {"by_file": by_file, "entries": len(j), "missing_files": missing}


def build_index(*, project_media: str, h5_assets: list[dict], master_used: dict,
                metadata_sources: list[dict], media_root_label: str = "") -> dict:
    """构建 AssetIndex（纯函数式：输入 → 确定性 artifact）。"""
    root = pathlib.Path(project_media)
    visual_paths, non_visual = [], []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        k = classify_kind(p)
        if k in ("image", "video"):
            visual_paths.append(p)
        else:
            non_visual.append({"path": str(p), "media_kind": k, "bytes": p.stat().st_size,
                               "sha256": sha256_file(p),
                               "note": "非视觉媒体/元数据（不计入视觉身份与家族）"})
    ext_idx = load_external_index(root)
    h5_by_sha = {r["sha256"]: r for r in h5_assets}
    used_by_sha, used_by_id = {}, {}
    for aid, sa in (master_used or {}).items():
        if sa.get("sha256"):
            used_by_sha[sa["sha256"]] = aid
        used_by_id[aid] = sa

    cands = []
    groups: dict[tuple, list] = {}
    for p in visual_paths + [pathlib.Path(h["path"]) for h in h5_assets]:
        sha = sha256_file(p)
        kind0 = classify_kind(p)
        groups.setdefault((sha, kind0), []).append(p)
    for (sha, kind0), paths_g in sorted(groups.items()):
        p = sorted(paths_g, key=lambda x: str(x))[0]          # 规范路径（确定性）
        duplicate_paths = [str(x) for x in sorted(paths_g, key=lambda x: str(x))[1:]]
        pr = _probe(p)
        kind = pr["kind"] if pr["kind"] in MEDIA_KINDS else classify_kind(p)
        h5 = h5_by_sha.get(sha)
        ext = ext_idx["by_file"].get(p.name)
        in_external = p.parent.name == "external"
        if h5 is not None:
            src_type, prov = "web", h5.get("provider") or UNKNOWN
            sid, surl = h5.get("source_id") or UNKNOWN, h5.get("source_url") or UNKNOWN
            lic, lclass = h5.get("license") or UNKNOWN, h5.get("license_class") or UNKNOWN
            attr = h5.get("attribution") or UNKNOWN
            legacy = [h5.get("asset_id")] if h5.get("asset_id") else []
            src_note = "H5 人工验收素材记录（phase6g_exec_h5.json）"
        elif in_external or ext:
            src_type = "external"
            prov = (ext or {}).get("provider") or UNKNOWN
            sid = (ext or {}).get("source_id") or UNKNOWN
            surl = UNKNOWN          # 缓存索引未记录 URL；**不构造**
            lic, lclass = UNKNOWN, UNKNOWN
            attr = UNKNOWN
            legacy = [used_by_sha[sha]] if sha in used_by_sha else []
            src_note = "media/external/.index.json（无 license/url 字段 ⇒ UNKNOWN）"
        else:
            src_type, prov = "local", "local_ingest"
            sid, surl, attr = UNKNOWN, UNKNOWN, UNKNOWN
            lic = "unchecked"
            lclass = classify_license(lic)[0]
            legacy = [used_by_sha[sha]] if sha in used_by_sha else []
            src_note = "项目 media/ 本地素材（material_timeline: provider=local_ingest）"
        lc = lclass
        lr = True if lc == "RESTRICTED" else (False if lc in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION")
                                              else UNKNOWN)
        gate = license_gate_applies({"provider": prov})
        legacy = [x for x in (legacy or []) if x]
        # 母片实际使用：优先按 sha 命中，其次按 path/name 命中
        role = "NOT_USED"
        if sha in used_by_sha:
            role = "USED_IN_6G_MASTER"
            legacy = sorted(set(legacy + [used_by_sha[sha]]))
        else:
            for aid, sa in used_by_id.items():
                if sa.get("path") and pathlib.Path(sa["path"]).name == p.name:
                    role = "USED_IN_6G_MASTER"
                    legacy = sorted(set(legacy + [aid]))
        # 感知身份（复用 content_identity；解码失败 ⇒ UNKNOWN）
        if pr["decode_status"] == "OK" and kind == "image":
            dh = dhash_of(p)
            pi = perceptual_identity(dh, 8, md5_of(p), "OK")
        else:
            pi = perceptual_identity(None, 8, None, UNKNOWN,
                                     "decode_status={}（无法计算 dHash）".format(
                                         pr["decode_status"]))
        # 完整性：最小尺寸 + 解码（完整 G0–G9 未接线 ⇒ 显式标注）
        reasons, integ = [], "OK"
        if pr["decode_status"] != "OK":
            integ, reasons = "BLOCK", ["decode_failed:{}".format(pr["detail"])]
        elif isinstance(pr["width"], int) and (pr["width"] < DEFAULT_POLICY["min_asset_width"]
                                               or pr["height"] < DEFAULT_POLICY["min_asset_height"]):
            integ, reasons = "DEMOTE", ["below_min_dims:{}x{}<{}x{}".format(
                pr["width"], pr["height"], DEFAULT_POLICY["min_asset_width"],
                DEFAULT_POLICY["min_asset_height"])]
        prov_rec = {
            "scan_root": media_root_label or str(root), "source_note": src_note,
            "metadata_sources": metadata_sources,
            "reused_modules": ["orchestration.content_identity（dHash/hamming/md5）",
                               "orchestration.crop_recheck.full_bleed_box（裁剪探测）",
                               "core.materials（许可分类/门禁/最小尺寸）"],
            "network": "none（P7-2 零网络）",
            "full_gate_status": "NOT_WIRED（G0–G9 完整性门禁未接线；本字段仅为最小判定）",
        }
        c = make_candidate(
            path=str(p), sha256=sha, media_kind=kind, width=pr["width"], height=pr["height"],
            duration_s=pr["duration_s"], frame_count=pr["frame_count"], source_type=src_type,
            provider=prov, source_id=sid, source_url=surl, license=lic, license_class=lc,
            attribution=attr, license_restricted=lr, license_gate_applies=gate,
            decode_status=pr["decode_status"], decode_detail=pr["detail"],
            integrity_status=integ, integrity_reasons=reasons, perceptual_identity=pi,
            provenance=prov_rec, bytes_=p.stat().st_size, legacy_asset_ids=legacy,
            role_in_master=role)
        c["duplicate_paths"] = duplicate_paths
        c["deterministic_hash"] = candidate_hash(c)
        cands.append(c)

    cands.sort(key=lambda c: c["asset_id"])
    rel = _relationships(cands, visual_paths)
    counts = {
        "paths_scanned": len(visual_paths) + len(h5_assets),
        "candidates": len(cands),
        "duplicate_path_groups": sum(1 for c in cands if c.get("duplicate_paths")),
        "visual": sum(1 for c in cands if c["media_kind"] in ("image", "video")),
        "by_media_kind": {k: sum(1 for c in cands if c["media_kind"] == k) for k in MEDIA_KINDS},
        "decode_failed": sum(1 for c in cands if c["decode_status"] != "OK"),
        "decode_unknown": sum(1 for c in cands if c["decode_status"] == UNKNOWN),
        "integrity": {s: sum(1 for c in cands if c["integrity_status"] == s)
                      for s in INTEGRITY_STATES},
        "used_in_6g_master": sum(1 for c in cands if c["role_in_master"] == "USED_IN_6G_MASTER"),
        "license_class": {k: sum(1 for c in cands if c["license_class"] == k)
                          for k in ("PUBLIC_DOMAIN", "FREE_ATTRIBUTION", "RESTRICTED", UNKNOWN)},
        "perceptual_unknown": sum(1 for c in cands
                                  if c["perceptual_identity"]["status"] != "OK"),
        "legacy_ids_mapped": sum(1 for c in cands if c["legacy_asset_ids"]),
    }
    art = {
        "schema": INDEX_SCHEMA, "version": INDEX_VERSION,
        "generation_method": "deterministic-offline（零网络；复用 content_identity/crop_recheck）",
        "bands": {"same_band": SAME_BAND, "suspect_band": SUSPECT_BAND,
                  "crop_max_shift": CROP_MAX_SHIFT, "min_visible": MIN_VISIBLE},
        "scan_roots": [{"role": "project_media", "path": str(root),
                        "visual_files": len(visual_paths), "non_visual_files": len(non_visual)},
                       {"role": "h5_accepted_assets",
                        "paths": [h["path"] for h in h5_assets], "count": len(h5_assets)}],
        "metadata_sources": metadata_sources,
        "candidates": cands,
        "relationships": rel,
        "counts": counts,
        "non_visual_inventory": non_visual,
        "external_cache": {"index_entries": ext_idx["entries"],
                           "cache_missing_files": ext_idx["missing_files"],
                           "cache_missing_count": len(ext_idx["missing_files"]),
                           "note": "缓存索引记录的文件在磁盘上不存在 ⇒ 溯源存在指向缺失文件的记录"},
        "unknown_policy": "不知道 ≠ 猜测：无法确定者记 UNKNOWN；类别不适用者记 NOT_AVAILABLE；"
                          "镜像不变比较与完整 G0–G9 门禁未提供/未接线 ⇒ UNKNOWN / NOT_WIRED",
        "dq_note": "P7-2 **只建立身份与关系记录，不修改 DQ-2 或任何 DQ 阈值**",
        "artifact_hash": "",
    }
    art["artifact_hash"] = index_hash(art)
    return art


def index_body(art: dict) -> dict:
    return {k: v for k, v in art.items() if k != "artifact_hash"}


def index_hash(art: dict) -> str:
    from ..core.visual_requirement import canonical, sha256_text
    return sha256_text(canonical(index_body(art)))


def _relationships(cands: list, visual_paths: list) -> dict:
    """A/B/C/D 四类关系（确定性；只记录，不改 DQ）。"""
    exact = [{"sha256": c["sha256"], "canonical_path": c["path"],
              "paths": [c["path"]] + list(c.get("duplicate_paths") or [])}
             for c in sorted(cands, key=lambda x: x["asset_id"]) if c.get("duplicate_paths")]
    paths = [c["path"] for c in cands]
    decodable = [c for c in cands if c["perceptual_identity"].get("status") == "OK"
                 and c["perceptual_identity"].get("dhash_hex") not in (None, UNKNOWN)]
    if decodable:
        # 仅对**可解码**条目做感知聚类，并注入已算得的 dHash/MD5（不重复解码；不可解码者
        # 已在候选里记 perceptual=UNKNOWN，不参与家族）
        cid = build_content_index(
            [c["path"] for c in decodable], same_band=SAME_BAND, suspect_band=SUSPECT_BAND,
            merge_suspect=False,
            _dh={c["path"]: _bits(c["perceptual_identity"]["dhash_hex"]) for c in decodable},
            _md5={c["path"]: c["perceptual_identity"]["md5"] for c in decodable})
        by_path = {c["path"]: c for c in cands}
        fams = []
        for _cluster, members in sorted(cid.members.items()):
            ids = sorted(by_path[m]["asset_id"] for m in members if m in by_path)
            hs = sorted(by_path[m]["perceptual_identity"].get("dhash_hex") or ""
                        for m in members if m in by_path)
            hs = [h for h in hs if h and h != UNKNOWN]
            if not hs:
                continue
            fams.append({"family_id": family_id(hs), "members": ids,
                         "distinct_sha256": len({by_path[m]["sha256"] for m in members
                                                 if m in by_path}),
                         "method": "content_identity.build_content_index（dHash≤{}）".format(SAME_BAND),
                         "source_cluster_label": _cluster})
        fams.sort(key=lambda f: f["family_id"])
        suspects = [{"a": _aid(by_path, a), "b": _aid(by_path, b), "hamming": d}
                    for a, b, d in sorted(cid.suspect_links)]
    else:
        fams, suspects = [], []
    transforms = _transform_relations(cands)
    in_rel = set()
    by_path = {c["path"]: c for c in cands}
    for g in exact:
        c = by_path.get(g["canonical_path"])
        if c:
            in_rel.add(c["asset_id"])
    for f in fams:
        if f["distinct_sha256"] > 1:
            in_rel |= set(f["members"])
    for t in transforms:
        in_rel |= {t["a"], t["b"]}
    independent = sorted(c["asset_id"] for c in cands if c["asset_id"] not in in_rel)
    return {"exact_duplicate_groups": exact,
            "perceptual_families": fams,
            "transform_relations": transforms,
            "suspect_links": suspects,
            "independent_asset_ids": independent,
            "classification_legend": {
                "A_exact_same_file": "same sha256",
                "B_same_perceptual_family": "different sha256 + same perceptual family",
                "C_crop_or_transform": "perceptual/crop relationship（**候选关系**，带实测证据）",
                "D_independent": "不同 perceptual family"},
            "mirror_invariance": {"status": UNKNOWN,
                                  "reason": "既有实现未提供镜像不变比较；P7-2 不新增算法"}}


def _aid(by_path: dict, path: str) -> str:
    c = by_path.get(path)
    return c["asset_id"] if c else UNKNOWN


def _transform_relations(cands: list) -> list:
    """裁剪/缩放/变换**候选**关系：复用 crop_recheck.full_bleed_box + dHash（不新增算法）。"""
    out = []
    for i, a in enumerate(cands):
        for b in cands[i + 1:]:
            pa, pb = a["perceptual_identity"], b["perceptual_identity"]
            ha, hb = pa.get("dhash_hex"), pb.get("dhash_hex")
            if not ha or not hb or UNKNOWN in (ha, hb) or len(ha) != len(hb):
                continue
            if a["sha256"] == b["sha256"]:
                continue
            wa, hgt_a = a["width"], a["height"]
            wb, hgt_b = b["width"], b["height"]
            if not all(isinstance(x, int) for x in (wa, hgt_a, wb, hgt_b)):
                continue
            dist = hamming(_bits(ha), _bits(hb))
            same_dims = (wa, hgt_a) == (wb, hgt_b)
            if dist <= SAME_BAND and same_dims:
                out.append({"kind": "reencode_or_rescale", "status": "CANDIDATE", "a": a["asset_id"],
                            "b": b["asset_id"], "dhash_hamming": dist,
                            "method": "content_identity.dhash（同族同尺寸、字节不同）"})
                continue
            ar_a, ar_b = wa / hgt_a, wb / hgt_b
            if abs(ar_a - ar_b) / max(ar_a, ar_b) <= ASPECT_TOL:
                continue                    # 同宽高比 ⇒ 非裁剪形变
            wide, other = (a, b) if ar_a > ar_b else (b, a)
            ar_other = (ar_b if ar_a > ar_b else ar_a)
            box = full_bleed_box(wide["width"], wide["height"], ar_other)
            l, t, r, bt = box
            vis = round(max(0.0, min(1.0, (r - l) * (bt - t) / (wide["width"] * wide["height"]))), 3)
            try:
                from PIL import Image
                import numpy as np
                with Image.open(wide["path"]) as im:
                    crop_dh = dhash_arr(np.asarray(im.convert("L").crop(box)))
                shift = hamming(crop_dh, _bits(other["perceptual_identity"]["dhash_hex"]))
            except Exception:                                             # noqa: BLE001
                continue
            if shift <= CROP_MAX_SHIFT and vis >= 0.0:
                out.append({"kind": "crop_to_aspect", "status": "CANDIDATE",
                            "a": wide["asset_id"], "b": other["asset_id"],
                            "visible_frac": vis, "dhash_shift": shift,
                            "aspect_ratio_a": round(ar_a, 4), "aspect_ratio_b": round(ar_b, 4),
                            "thresholds": {"max_shift": CROP_MAX_SHIFT, "min_visible": MIN_VISIBLE},
                            "method": "crop_recheck.full_bleed_box + content_identity.dhash/hamming"})
    out.sort(key=lambda x: (x["kind"], x["a"], x["b"]))
    return out


def _bits(hexstr: str):
    import numpy as np
    return np.array([c == "1" for c in hexstr])


def validate_index(art: dict) -> list[str]:
    errs = []
    if art.get("schema") != INDEX_SCHEMA:
        errs.append("index schema 非法")
    if art.get("artifact_hash") != index_hash(art):
        errs.append("artifact_hash 不一致")
    cs = art.get("candidates") or []
    ids = [c["asset_id"] for c in cs]
    if len(ids) != len(set(ids)):
        errs.append("asset_id 重复（内容身份碰撞或扫描重复）")
    for c in cs:
        for e in validate_candidate(c):
            errs.append("{}: {}".format(c.get("asset_id"), e))
    if art.get("counts", {}).get("candidates") != len(cs):
        errs.append("counts.candidates 不一致")
    if ids != sorted(ids):
        errs.append("candidates 未按 asset_id 排序（破坏确定性）")
    return errs
