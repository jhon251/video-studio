# -*- coding: utf-8 -*-
"""底片谱系守卫（Phase 13-E）：**防止修订候选绑错底片**。

背景（Phase 13-E 结论 A）：13-D 的 ctx 误把权威 21 景时间轴绑到 **v9 1532 s 母片**，
导致 PI-1/2/3/5/6 报出的数值**逐值等于 v9 历史缺陷**（PI-1 0.6277=961.7/1532；570.344/570.874 s；73 条 orphan；
PI-6 漂移 552.16 ≈ 1532.0−978.7）——即**度量伪影**，而非 S05 替换的问题。
权威底片是 **DCv2/H5 978.7 s 谱系**（PI 历史全 PASS）。

纪律：本模块只做 **sha256 + 时长（±容差）** 双校验与常量登记；**不改任何门禁阈值**、不写文件、不联网。
任何 REPLACE/ADD 类修订候选在构建 ctx 前**必须**通过 `assert_lineage()`。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

SCHEMA = "lineage-guard-v1"
TOLERANCE_S = 1.0

#: **权威谱系**（DCv2/H5）：修订候选的唯一合法底片。变更须走新授权并更新本常量。
AUTHORITATIVE_LINEAGE = {
    "id": "DCv2_H5_978s",
    "film": "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
    "sha256": "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be",
    "duration_s": 978.7,
    "timeline_source": "docs/regression_2x/logs/phase6f_rebuild_plan_v2.json#new_production_timeline",
    "scenes": 21,
    "s05_window": [181.776, 221.862],
    "pi_history": "phase6g_exec_h5.json: PI-1/2/3/4/5/6=PASS + G-TL/G-PAD/G-SUB=PASS + frozen_recheck=PASS",
}

#: **历史谱系**（v9 1532 s）：**不得**作为修订候选底片（携带 #65/#67 缺陷）。
LEGACY_LINEAGE = {
    "id": "v9_1532s",
    "film": "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4",
    "sha256": "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651",
    "duration_s": 1532.0,
    "s05_window": [245.0, 300.0],
    "known_defects": ["PI-1 0.6277 = 961.7/1532（#65）", "PI-2/PI-3 570.344/570.874 s（#67）",
                      "PI-5 73 条 orphan（33.8%）", "PI-6 漂移 552.16 s ≈ 1532.0−978.7"],
}


def sha256_file(path) -> str:
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def probe_duration(path, *, root=None) -> float:
    """ffprobe 读时长（失败返回 -1.0，绝不猜测）。"""
    base = pathlib.Path(root) if root else pathlib.Path(".")
    ffprobe = base / "bin" / "ffprobe.exe"
    exe = str(ffprobe) if ffprobe.is_file() else "ffprobe"
    try:
        out = subprocess.run([exe, "-v", "error", "-show_entries", "format=duration",
                              "-of", "json", str(path)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120).stdout
        return round(float(json.loads(out)["format"]["duration"]), 1) if out else -1.0
    except Exception:                                                     # noqa: BLE001
        return -1.0


def check_lineage(film, *, root=None, expected: dict | None = None) -> dict:
    """返回校验记录（不抛错）：`verdict` ∈ {LINEAGE_OK, LINEAGE_MISMATCH, FILM_MISSING}。"""
    exp = expected or AUTHORITATIVE_LINEAGE
    base = pathlib.Path(root) if root else pathlib.Path(".")
    p = pathlib.Path(film)
    p = p if p.is_absolute() else base / p
    rec = {"schema": SCHEMA, "film": str(p), "expected_id": exp["id"],
           "expected_sha256": exp["sha256"], "expected_duration_s": exp["duration_s"],
           "tolerance_s": TOLERANCE_S, "sha256": None, "duration_s": None,
           "sha_match": False, "duration_match": False, "verdict": "FILM_MISSING",
           "is_legacy_lineage": False}
    if not p.is_file():
        return rec
    rec["sha256"] = sha256_file(p)
    rec["duration_s"] = probe_duration(p, root=base)
    rec["sha_match"] = rec["sha256"] == exp["sha256"]
    rec["duration_match"] = abs(rec["duration_s"] - exp["duration_s"]) <= TOLERANCE_S
    rec["is_legacy_lineage"] = rec["sha256"] == LEGACY_LINEAGE["sha256"]
    rec["verdict"] = ("LINEAGE_OK" if (rec["sha_match"] and rec["duration_match"])
                      else "LINEAGE_MISMATCH")
    return rec


def assert_lineage(film, *, root=None, expected: dict | None = None) -> dict:
    """守卫入口：不符即抛 `ValueError`（禁止据此构建 ctx）。"""
    rec = check_lineage(film, root=root, expected=expected)
    if rec["verdict"] != "LINEAGE_OK":
        raise ValueError("底片谱系不符（禁止据此构建修订 ctx）: {}".format(
            json.dumps(rec, ensure_ascii=False)))
    return rec


def authoritative_film(root) -> pathlib.Path:
    return pathlib.Path(root) / AUTHORITATIVE_LINEAGE["film"]


def load_authoritative_timeline(root) -> list:
    """读取 DCv2 权威时间轴（`new_production_timeline`，21 景）。只读；缺失即抛错（不猜测）。"""
    rel = AUTHORITATIVE_LINEAGE["timeline_source"].split("#")[0]
    p = pathlib.Path(root) / rel
    if not p.is_file():
        raise ValueError("权威时间轴文件缺失: {}".format(p))
    tl = json.loads(p.read_text(encoding="utf-8")).get("new_production_timeline")
    if not isinstance(tl, list) or not tl:
        raise ValueError("权威时间轴为空或结构不符: {}".format(p))
    return tl
