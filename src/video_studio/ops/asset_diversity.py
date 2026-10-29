# -*- coding: utf-8 -*-
"""P7-3：视觉多样性度量 **ops 入口**（**严格只读**：不写文件、零网络、零 LLM、无 DB 写入）。

用法：
  python -m video_studio.ops.asset_diversity build [--json]
  python -m video_studio.ops.asset_diversity verify PATH

只读消费：P7-2 `asset_index.json`、P7-1 `visual_requirements.json`、6-G 生产 `render_output`
（material_timeline）、Batch-1/H3c 注册提案、H5 报告、DCv2 计划 —— 全部为**既有产物**，DB 以
`mode=ro` + `query_only` 打开。artifact 落盘由阶段脚本
`docs/regression_2x/phase7_p7_3_build.py` 负责（既有 ops 契约：ops 不得写文件）。
fail-closed：源缺失 / 场景→资产映射不可建立 / schema 或 hash 不一致 ⇒ 非零退出。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

from ..core.asset_diversity import (NOT_ASSESSABLE, build_report, validate_report)
from ..ops.execution import split_plan                                    # 只读使用

DEFAULT_DB = r"C:\mp4agent\video-studio\projects\video_studio.db"
DEFAULT_TASK = "t_d0a54bdf1810"
DEFAULT_LOGS = r"C:\mp4agent\video-studio\docs\regression_2x\logs"
DEFAULT_OUT = r"C:\mp4agent\video-studio\docs\regression_2x\logs\asset_diversity.json"
PRIMARY_SCOPE = "accepted_chain_48_subscenes"


class SourceMissing(RuntimeError):
    """必需输入产物缺失 ⇒ fail-closed。"""


class MappingNotAssessable(RuntimeError):
    """场景→资产无法建立稳定映射 ⇒ fail-closed（不静默回落）。"""


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def _json(p) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _db_ro(db: str) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def _require(p: Path, what: str) -> Path:
    if not p.is_file():
        raise SourceMissing("{} 缺失：{}".format(what, p))
    return p


def load_sources(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
                 logs: str = DEFAULT_LOGS) -> dict:
    L = Path(logs)
    index_p = _require(L / "asset_index.json", "P7-2 asset_index")
    reqs_p = _require(L / "visual_requirements.json", "P7-1 visual_requirements")
    plan_p = _require(L / "phase6f_rebuild_plan_v2.json", "DCv2 计划")
    b1_p = _require(L / "phase6g_exec_batch1.json", "Batch-1 报告")
    reg_p = _require(L / "phase6g_rebuild_proposal_register.jsonl", "注册链")
    h5_p = _require(L / "phase6g_exec_h5.json", "H5 报告")
    con = _db_ro(db)
    try:
        row = con.execute("select artifact_id,path from artifacts where type='render_output' "
                          "and task_id=? order by created_at desc limit 1", (task_id,)).fetchone()
        if not row:
            raise SourceMissing("render_output(task={}) 缺失".format(task_id))
        ro = dict(row)
    finally:
        con.close()
    ro_p = _require(Path(ro["path"]), "render_output")
    return {"index": _json(index_p), "requirements": _json(reqs_p), "plan": _json(plan_p),
            "batch1": _json(b1_p), "h5": _json(h5_p),
            "register": [json.loads(x) for x in reg_p.read_text(encoding="utf-8").splitlines()
                         if x.strip()],
            "render_output": _json(ro_p),
            "sources": [{"role": r, "path": str(p), "sha256": sha256_file(p)}
                        for r, p in (("p7_2_asset_index", index_p),
                                     ("p7_1_visual_requirements", reqs_p),
                                     ("dcv2_plan", plan_p), ("batch1_report", b1_p),
                                     ("proposal_register", reg_p), ("h5_report", h5_p),
                                     ("render_output", ro_p))]}


def _scope_21(render: dict) -> list[dict]:
    rows = []
    for seg in render.get("material_timeline") or []:
        sa = seg.get("selected_asset") or {}
        rows.append({"scene_id": seg.get("scene_id"), "asset_id": sa.get("asset_id"),
                     "sha256": sa.get("sha256")})
    return rows


def _scope_48(plan: dict, batch1: dict, register: list, h5: dict, render: dict) -> list[dict]:
    """accepted-chain 投影（与 6-G DQ 同口径）：21 场景 → 切分 → H5 替换。"""
    OLD = {}
    for seg in render.get("material_timeline") or []:
        sa = seg.get("selected_asset") or {}
        if sa.get("asset_id"):
            OLD[str(seg.get("scene_id"))] = sa
    new = {s: h5["asset_records"][s] for s in (h5.get("asset_records") or {})}
    tl = [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
           "end_s": c["new_timeline_window_s"][1]} for c in plan["remapping_21_segments"]]
    proj = [dict(e, asset_id=(OLD.get(str(e["scene_id"])) or {}).get("asset_id"),
                 sha256=(OLD.get(str(e["scene_id"])) or {}).get("sha256")) for e in tl]

    def apply(sp, replace_scenes=()):
        for rr in sp.get("scenes", []):
            base = next(e for e in proj if e["scene_id"] == rr["scene_id"])
            d = rr["sub_duration_s"]
            sa = OLD.get(str(rr["scene_id"])) or {}
            if rr["scene_id"] in replace_scenes and rr["scene_id"] in new:
                sa = new[rr["scene_id"]]
            subs = [{"scene_id": "{}.{}".format(rr["scene_id"], j + 1),
                     "start_s": round(rr["window"][0] + d * j, 3),
                     "end_s": round(rr["window"][0] + d * (j + 1), 3),
                     "asset_id": sa.get("asset_id"), "sha256": sa.get("sha256")}
                    for j in range(rr["sub_count"])]
            i = proj.index(base)
            proj[i:i + 1] = subs

    for st in ("H3a", "H3b"):
        sp = next(s["exec"]["exec_evidence"]["split_plan"] for s in batch1["stages"]
                  if s["stage"] == st)
        apply(sp, ("S11",) if st == "H3b" else ())
    for lab in ("H3c-1", "H3c-2"):
        p = next((x for x in register if x.get("label") == lab), None)
        if p is None:
            raise SourceMissing("注册链缺少 {}".format(lab))
        apply(split_plan({"timeline": [dict(e) for e in tl], "timeline_identity": None,
                          "caption_timeline": None}, p), ("S05",))
    for s, rec in new.items():
        for e in proj:
            if e["scene_id"] == s:
                e["asset_id"], e["sha256"] = rec["asset_id"], rec["sha256"]
    return [{"scene_id": e["scene_id"], "asset_id": e["asset_id"], "sha256": e.get("sha256")}
            for e in proj]


def build(db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK, logs: str = DEFAULT_LOGS) -> dict:
    src = load_sources(db, task_id, logs)
    scopes = []
    for label, rows, note in (
            ("master_21_scenes", _scope_21(src["render_output"]),
             "6-G 生产 render_output.material_timeline（21 场景；**H5 替换之前**的生产状态）"),
            (PRIMARY_SCOPE, _scope_48(src["plan"], src["batch1"], src["register"], src["h5"],
                                      src["render_output"]),
             "accepted chain 投影（21→切分→H5 替换；与 6-G DQ 同口径）＝最终母片实际素材分布")):
        from ..core.asset_diversity import measure
        m = measure(timeline_rows=rows, index=src["index"], requirements=src["requirements"],
                    scope_label=label, scope_note=note)
        if m["mapping"]["status"] != "OK":
            raise MappingNotAssessable(
                "{} 存在无法映射到索引的资产：{}".format(label, m["mapping"]["unmapped_scenes"][:5]))
        scopes.append(m)
    art = build_report(index=src["index"], scopes=scopes, requirements=src["requirements"],
                       primary_scope=PRIMARY_SCOPE, sources=src["sources"])
    errs = validate_report(art)
    if errs:
        raise ValueError("diversity 报告校验失败：{}".format("; ".join(errs[:5])))
    return art


def verify(path: str, db: str = DEFAULT_DB, task_id: str = DEFAULT_TASK,
           logs: str = DEFAULT_LOGS) -> dict:
    old = _json(path)
    new = build(db, task_id, logs)
    if old.get("artifact_hash") != new.get("artifact_hash"):
        raise ValueError("verify 失败：artifact_hash 不一致")
    return {"ok": True, "artifact_hash": new["artifact_hash"],
            "scopes": [s["scope"] for s in new["scopes"]]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="asset_diversity")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--task-id", default=DEFAULT_TASK)
    b.add_argument("--logs", default=DEFAULT_LOGS)
    b.add_argument("--json", action="store_true")
    v = sub.add_parser("verify")
    v.add_argument("path")
    v.add_argument("--db", default=DEFAULT_DB)
    v.add_argument("--task-id", default=DEFAULT_TASK)
    v.add_argument("--logs", default=DEFAULT_LOGS)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "build":
            art = build(a.db, a.task_id, a.logs)
            if a.json:
                print(json.dumps(art, ensure_ascii=False, indent=1))
                return 0
            for s in art["scopes"]:
                A, B, C, D = (s["A_asset_level"], s["B_scene_level"], s["C_concentration"],
                              s["D_independence"])
                print("[{}] scenes={} unique_assets={} families={} source_families={} "
                      "max_reuse={} reuse_rate={} asset_hhi={}".format(
                          s["scope"], B["scene_count"], A["unique_assets"],
                          A["unique_perceptual_families"], A["unique_source_families"],
                          A["max_asset_reuse"], B["scene_asset_reuse_rate"], C["asset_hhi"]))
            print("artifact_hash={}".format(art["artifact_hash"]))
            return 0
        r = verify(a.path, a.db, a.task_id, a.logs)
        print("verify OK:", json.dumps(r, ensure_ascii=False))
        return 0
    except Exception as exc:                                              # noqa: BLE001
        print("FAIL-CLOSED [{}]: {}".format(type(exc).__name__, exc), file=sys.stderr)
        return 2


if __name__ == "__main__":                                                 # pragma: no cover
    sys.exit(main())
