# -*- coding: utf-8 -*-
"""P7-1：VisualRequirement **ops 入口**（**严格只读**：不写任何文件、无网络、无 DB 写入）。

用法：
  python -m video_studio.ops.visual_requirement build [--json] [--expect-scenes 21]
  python -m video_studio.ops.visual_requirement verify PATH

按项目既有 `ops/` 契约（maintenance guard M8d/M8e）：`ops/` 模块**不得写文件**——
artifact 落盘由阶段脚本 `docs/regression_2x/phase7_p7_1_build.py` 负责（与本项目其它阶段产物一致）。
本模块只做：只读加载源 → 构建/校验 → 打印摘要或 JSON。

输入（只读）：项目 DB 中的 `render_output`（material_timeline，镜头身份与显式字段）、
`script_output`（旁白）、`visual_plan_output`（shot.source 等）。DB 以 `mode=ro` + `query_only`
打开。fail-closed：源缺失 / 镜头数不符 / schema 或 hash 不一致 ⇒ 非零退出（不静默降级）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from ..tools.visual_requirement_builder import (artifact_digest, build_artifact,
                                                validate_artifact)

DEFAULT_DB = r"C:\mp4agent\video-studio\projects\video_studio.db"
DEFAULT_TASK = "t_d0a54bdf1810"
DEFAULT_PROJECT = "p_96efdc03e1aa"
DEFAULT_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\visual_requirements.json"


def sha256_file(p: str | Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _load_json(p: str | Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


class SourceMissing(RuntimeError):
    """源 artifact 缺失 ⇒ fail-closed。"""


class SceneCountMismatch(RuntimeError):
    """镜头数不符 ⇒ fail-closed。"""


def _db_ro(db: str) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _pick(con, atype: str, *, task_id: str | None = None,
          project_id: str | None = None) -> dict:
    q = "select artifact_id,task_id,path,created_at from artifacts where type=?"
    args: list = [atype]
    if task_id:
        q += " and task_id=?"
        args.append(task_id)
    if project_id:
        q += " and project_id=?"
        args.append(project_id)
    q += " order by created_at desc limit 1"
    row = con.execute(q, tuple(args)).fetchone()
    if not row:
        raise SourceMissing("{}（task={} project={}）无 artifact".format(atype, task_id,
                                                                        project_id))
    return dict(row)


def load_sources(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
                 project_id: str = DEFAULT_PROJECT) -> dict:
    """只读加载三类源 + 记录 source identity（含文件 sha256）。"""
    con = _db_ro(db)
    try:
        ro = _pick(con, "render_output", task_id=task_id)
        sc = _pick(con, "script_output", project_id=project_id)
        vp = _pick(con, "visual_plan_output", project_id=project_id)
    finally:
        con.close()
    ro_j, sc_j, vp_j = _load_json(ro["path"]), _load_json(sc["path"]), _load_json(vp["path"])
    scenes = list(ro_j.get("material_timeline") or [])
    if not scenes:
        raise SourceMissing("render_output 无 material_timeline：{}".format(ro["path"]))
    segments = list(sc_j.get("segments") or [])
    shots = {int(s.get("index")): s for s in (vp_j.get("shots") or [])
             if isinstance(s.get("index"), int)}
    sources = [
        {"role": "scene_identity+explicit_fields", "artifact_id": ro["artifact_id"],
         "task_id": ro["task_id"], "path": ro["path"], "sha256": sha256_file(ro["path"]),
         "record_count": len(scenes)},
        {"role": "narration", "artifact_id": sc["artifact_id"], "task_id": sc["task_id"],
         "path": sc["path"], "sha256": sha256_file(sc["path"]),
         "record_count": len(segments)},
        {"role": "shot_plan", "artifact_id": vp["artifact_id"], "task_id": vp["task_id"],
         "path": vp["path"], "sha256": sha256_file(vp["path"]),
         "record_count": len(vp_j.get("shots") or [])},
    ]
    narrations = _align_narrations(scenes, segments)
    mapping = ("segment_index→segments[i]" if len(segments) == len(scenes)
               else "index-in-non-empty-filter" if _nonempty(segments) else "none")
    return {"scenes": scenes, "narrations": narrations, "shots": shots, "sources": sources,
            "mapping": mapping}


def _nonempty(segments: list) -> list:
    return [s for s in segments if str(s.get("narration") or "").strip()]


def _align_narrations(scenes: list, segments: list) -> list:
    """旁白对齐：优先 segment_index 直取；长度不符时退回**非空旁白**序列；再不行按序尽力。"""
    if len(segments) == len(scenes):
        return [s.get("narration") for s in segments]
    ne = _nonempty(segments)
    if len(ne) == len(scenes):
        return [s.get("narration") for s in ne]
    out = []
    for i, sc in enumerate(scenes):
        idx = sc.get("segment_index")
        src = segments[idx] if isinstance(idx, int) and 0 <= idx < len(segments) else None
        out.append(src.get("narration") if src else None)
    return out


def build(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, project_id: str = DEFAULT_PROJECT,
          expect_scenes: int = 21) -> dict:
    src = load_sources(db, task_id, project_id)
    if expect_scenes and len(src["scenes"]) != expect_scenes:
        raise SceneCountMismatch("期望 {} 镜，实际 {}".format(expect_scenes, len(src["scenes"])))
    art = build_artifact(src["scenes"], narrations=src["narrations"], shots=src["shots"],
                         sources=src["sources"], narration_mapping=src["mapping"])
    # 覆盖性：每镜都有 requirement（scene_id 集合一致）
    got = {r["scene_id"] for r in art["requirements"]}
    want = {s.get("scene_id") for s in src["scenes"]}
    if got != want:
        raise SceneCountMismatch("requirement 覆盖不一致：缺失 {}".format(sorted(want - got)))
    errs = validate_artifact(art)
    if errs:
        raise ValueError("artifact 校验失败：{}".format("; ".join(errs[:5])))
    return art


def verify(path: str, db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
           project_id: str = DEFAULT_PROJECT) -> dict:
    """重算并与既有 artifact 比对（hash 不一致 ⇒ fail-closed）。"""
    old = _load_json(path)
    new = build(db, task_id, project_id, expect_scenes=len(old.get("requirements") or []))
    diffs = []
    if old.get("artifact_hash") != new.get("artifact_hash"):
        diffs.append("artifact_hash")
    for r in old.get("requirements") or []:
        sid = r.get("scene_id")
        nr = next((x for x in new["requirements"] if x["scene_id"] == sid), None)
        if nr is None or nr["deterministic_hash"] != r.get("deterministic_hash"):
            diffs.append("requirement:{}".format(sid))
    if diffs:
        raise ValueError("verify 失败（不一致）：{}".format(", ".join(diffs[:8])))
    return {"ok": True, "artifact_hash": new["artifact_hash"],
            "requirements": len(new["requirements"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="visual_requirement")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--task-id", default=DEFAULT_TASK)
    b.add_argument("--project-id", default=DEFAULT_PROJECT)
    b.add_argument("--expect-scenes", type=int, default=21)
    b.add_argument("--json", action="store_true", help="把 artifact 打到 stdout（不落盘）")
    v = sub.add_parser("verify")
    v.add_argument("path")
    v.add_argument("--db", default=DEFAULT_DB)
    v.add_argument("--task-id", default=DEFAULT_TASK)
    v.add_argument("--project-id", default=DEFAULT_PROJECT)
    a = ap.parse_args(argv)

    try:
        if a.cmd == "build":
            art = build(a.db, a.task_id, a.project_id, a.expect_scenes)
            c = art["counts"]
            if a.json:
                print(json.dumps(art, ensure_ascii=False, indent=1))
                return 0
            print("requirements={} derivable={} not_derivable={}".format(
                c["requirements"], c["derivable"], c["not_derivable"]))
            print("artifact_hash={}".format(art["artifact_hash"]))
            print("digest={}".format(artifact_digest(art)))
            nd = {k: v["NOT_DERIVABLE"] for k, v in c["field_status_counts"].items()
                  if v["NOT_DERIVABLE"]}
            print("NOT_DERIVABLE 字段计数:", json.dumps(nd, ensure_ascii=False))
            return 0
        r = verify(a.path, a.db, a.task_id, a.project_id)
        print("verify OK:", json.dumps(r, ensure_ascii=False))
        return 0
    except Exception as exc:                                            # noqa: BLE001
        print("FAIL-CLOSED [{}]: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":                                             # pragma: no cover
    sys.exit(main())
