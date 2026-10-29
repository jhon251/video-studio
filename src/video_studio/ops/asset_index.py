# -*- coding: utf-8 -*-
"""P7-2：AssetIndex **ops 入口**（**严格只读**：不写任何文件、零网络、无 DB 写入）。

用法：
  python -m video_studio.ops.asset_index build [--json]
  python -m video_studio.ops.asset_index verify PATH

按项目既有 `ops/` 契约（maintenance guard M8d/M8e）：ops 模块不得写文件 ⇒ artifact 落盘由
阶段脚本 `docs/regression_2x/phase7_p7_2_build.py` 负责。DB 以 `mode=ro` + `query_only` 打开。
fail-closed：源缺失 / 文件不存在 / schema 或 hash 不一致 ⇒ 非零退出（不静默跳过）。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from ..tools.asset_index_builder import build_index, validate_index

DEFAULT_DB = r"C:\mp4agent\video-studio\projects\video_studio.db"
DEFAULT_TASK = "t_d0a54bdf1810"
DEFAULT_PROJECT_MEDIA = r"C:\mp4agent\video-studio\projects\p_96efdc03e1aa\media"
DEFAULT_H5_REPORT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\phase6g_exec_h5.json"
DEFAULT_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\asset_index.json"


class SourceMissing(RuntimeError):
    """源缺失或文件不存在 ⇒ fail-closed。"""


def sha256_file(p) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _db_ro(db: str) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def load_sources(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
                 project_media: str = DEFAULT_PROJECT_MEDIA,
                 h5_report: str = DEFAULT_H5_REPORT) -> dict:
    """只读加载：6-G 母片使用的资产（DB）+ H5 两件素材记录 + 项目 media 根。"""
    con = _db_ro(db)
    try:
        row = con.execute("select artifact_id,path from artifacts where type='render_output' "
                          "and task_id=? order by created_at desc limit 1", (task_id,)).fetchone()
        if not row:
            raise SourceMissing("render_output(task={}) 缺失".format(task_id))
        ro = dict(row)
    finally:
        con.close()
    ro_path = Path(ro["path"])
    if not ro_path.is_file():
        raise SourceMissing("render_output 文件不存在：{}".format(ro_path))
    tl = (json.loads(ro_path.read_text(encoding="utf-8")).get("material_timeline") or [])
    master_used = {}
    for seg in tl:
        sa = seg.get("selected_asset") or {}
        if sa.get("asset_id"):
            master_used[sa["asset_id"]] = sa
    h5p = Path(h5_report)
    if not h5p.is_file():
        raise SourceMissing("H5 素材记录缺失：{}".format(h5p))
    h5j = json.loads(h5p.read_text(encoding="utf-8"))
    recs = h5j.get("asset_records") or {}
    h5_assets = []
    for s in sorted(recs):
        r = recs[s]
        p = Path(r["path"])
        if not p.is_file():
            raise SourceMissing("H5 素材文件不存在（{}）：{}".format(s, p))
        if sha256_file(p) != r["sha256"]:
            raise SourceMissing("H5 素材 sha256 与正式记录不一致（{}）：{}".format(s, p))
        h5_assets.append({**r, "scene": s})
    media = Path(project_media)
    if not media.is_dir():
        raise SourceMissing("项目 media 目录不存在：{}".format(media))
    meta = [
        {"role": "master_used_assets", "artifact_id": ro["artifact_id"], "path": str(ro_path),
         "sha256": sha256_file(ro_path)},
        {"role": "h5_asset_records", "path": str(h5p), "sha256": sha256_file(h5p),
         "records": len(h5_assets)},
    ]
    ext = media / "external" / ".index.json"
    if ext.is_file():
        meta.append({"role": "external_cache_index", "path": str(ext),
                     "sha256": sha256_file(ext)})
    return {"master_used": master_used, "h5_assets": h5_assets, "project_media": str(media),
            "metadata_sources": meta}


def build(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
          project_media: str = DEFAULT_PROJECT_MEDIA, h5_report: str = DEFAULT_H5_REPORT) -> dict:
    src = load_sources(db, task_id, project_media, h5_report)
    art = build_index(project_media=src["project_media"], h5_assets=src["h5_assets"],
                      master_used=src["master_used"], metadata_sources=src["metadata_sources"],
                      media_root_label=src["project_media"])
    errs = validate_index(art)
    if errs:
        raise ValueError("AssetIndex 校验失败：{}".format("; ".join(errs[:5])))
    return art


def verify(path: str, db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
           project_media: str = DEFAULT_PROJECT_MEDIA,
           h5_report: str = DEFAULT_H5_REPORT) -> dict:
    old = json.loads(Path(path).read_text(encoding="utf-8"))
    new = build(db, task_id, project_media, h5_report)
    diffs = []
    if old.get("artifact_hash") != new.get("artifact_hash"):
        diffs.append("artifact_hash")
    old_by = {c["asset_id"]: c for c in (old.get("candidates") or [])}
    new_by = {c["asset_id"]: c for c in new["candidates"]}
    if set(old_by) != set(new_by):
        diffs.append("asset_id_set")
    for aid in sorted(set(old_by) & set(new_by)):
        if old_by[aid]["deterministic_hash"] != new_by[aid]["deterministic_hash"]:
            diffs.append("candidate:{}".format(aid))
    if diffs:
        raise ValueError("verify 失败（不一致）：{}".format(", ".join(diffs[:8])))
    return {"ok": True, "artifact_hash": new["artifact_hash"], "candidates": len(new["candidates"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="asset_index")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--task-id", default=DEFAULT_TASK)
    b.add_argument("--project-media", default=DEFAULT_PROJECT_MEDIA)
    b.add_argument("--h5-report", default=DEFAULT_H5_REPORT)
    b.add_argument("--json", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("path")
    v.add_argument("--db", default=DEFAULT_DB)
    v.add_argument("--task-id", default=DEFAULT_TASK)
    v.add_argument("--project-media", default=DEFAULT_PROJECT_MEDIA)
    v.add_argument("--h5-report", default=DEFAULT_H5_REPORT)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            art = build(a.db, a.task_id, a.project_media, a.h5_report)
            if a.json:
                print(json.dumps(art, ensure_ascii=False, indent=1))
                return 0
            print("candidates={} visual={} used_in_master={} decode_failed={}".format(
                art["counts"]["candidates"], art["counts"]["visual"],
                art["counts"]["used_in_6g_master"], art["counts"]["decode_failed"]))
            print("artifact_hash={}".format(art["artifact_hash"]))
            rel = art["relationships"]
            print("relationships: exact={} families={} transforms={} independent={}".format(
                len(rel["exact_duplicate_groups"]), len(rel["perceptual_families"]),
                len(rel["transform_relations"]), len(rel["independent_asset_ids"])))
            return 0
        r = verify(a.path, a.db, a.task_id, a.project_media, a.h5_report)
        print("verify OK:", json.dumps(r, ensure_ascii=False))
        return 0
    except Exception as exc:                                              # noqa: BLE001
        print("FAIL-CLOSED [{}]: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":                                                 # pragma: no cover
    sys.exit(main())
