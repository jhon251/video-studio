"""4.x Phase 4-G：只读节奏报告（`run.py rhythm <project_id>`）。

**只读**：数据库以 `file:<path>?mode=ro` 打开（SQLite 层面禁止写入）；只读取已有产物
（`render_output` / `voice_output`），不调用调度器、不创建/修改任务与产物、**不写任何文件**、不访问网络。

输出 = `core.rhythm.analyze_rhythm()` 的纯函数结果 + 输入指纹（产物 id/sha256，便于复算与核对）。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..core.rhythm import analyze_rhythm, rhythm_settings
from .report import readonly_connection


def _sha256_file(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _load_payload(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _latest(con, pid: str, type_: str, artifact_id: str | None = None):
    if artifact_id:
        row = con.execute("select * from artifacts where artifact_id=? and project_id=?",
                          (artifact_id, pid)).fetchone()
        return dict(row) if row else None
    row = con.execute("select * from artifacts where project_id=? and type=? "
                      "order by created_at desc limit 1", (pid, type_)).fetchone()
    return dict(row) if row else None


def collect_rhythm_inputs(db_path, project_id: str, *, artifact_id: str | None = None) -> dict:
    """读取渲染/旁白产物 → 组装分析输入（**只读**）。缺失时字段为 None/[]，由分析器给出 UNKNOWN。"""
    con = readonly_connection(db_path)
    try:
        ro = _latest(con, project_id, "render_output", artifact_id)
        vo = _latest(con, project_id, "voice_output")
        proj = con.execute("select * from projects where project_id=?",
                           (project_id,)).fetchone()
    finally:
        con.close()
    if proj is None:
        return {"found": False, "project_id": project_id}
    ro_payload = _load_payload(ro["path"]) if ro else None
    vo_payload = _load_payload(vo["path"]) if vo else None
    timeline = list((ro_payload or {}).get("material_timeline") or [])
    bgm_ev = (ro_payload or {}).get("bgm") or {}
    intervals = list(bgm_ev.get("narration_intervals") or [])
    narration_total = None
    if vo_payload:
        narration_total = vo_payload.get("narration_duration_s")
        if narration_total is None:
            ds = [s.get("duration_s") for s in (vo_payload.get("segments") or [])
                  if isinstance(s.get("duration_s"), (int, float))]
            narration_total = round(sum(ds), 3) if ds else None
    dcontract = (ro_payload or {}).get("duration_contract") or {}
    return {
        "found": True, "project_id": project_id,
        "project": {"project_id": project_id, "name": proj["name"], "goal": proj["goal"],
                    "status": proj["status"]},
        "render_artifact": ({"artifact_id": ro["artifact_id"], "task_id": ro["task_id"],
                             "path": ro["path"], "sha256": _sha256_file(Path(ro["path"])),
                             "created_at": ro["created_at"]} if ro else None),
        "voice_artifact": ({"artifact_id": vo["artifact_id"], "task_id": vo["task_id"],
                            "path": vo["path"], "sha256": _sha256_file(Path(vo["path"])),
                            "created_at": vo["created_at"]} if vo else None),
        "film_duration_s": (ro_payload or {}).get("video_duration_s"),
        "timeline": timeline,
        "narration": ({"total_s": narration_total,
                       "segments": list((vo_payload or {}).get("segments") or []),
                       "complete": (vo_payload or {}).get("complete"),
                       "trimmed": bool(dcontract.get("audio_trimmed_to_timeline")),
                       "padded": bool(dcontract.get("audio_padded_to_timeline"))}
                      if vo_payload else None),
        "bgm": {"enabled": bool(bgm_ev.get("enabled")), "applied": bool(bgm_ev.get("applied")),
                "intervals": intervals,
                "bed_db": (bgm_ev.get("settings") or {}).get("bed_db"),
                "duck_db": (bgm_ev.get("settings") or {}).get("duck_db"),
                "ramp_ms": (bgm_ev.get("settings") or {}).get("ramp_ms")},
        "sources": {
            "render_output": ({"artifact_id": ro["artifact_id"], "sha256": _sha256_file(Path(ro["path"]))}
                              if ro else None),
            "voice_output": ({"artifact_id": vo["artifact_id"], "sha256": _sha256_file(Path(vo["path"]))}
                             if vo else None),
        },
    }


def rhythm_report(db_path, project_id: str, *, artifact_id: str | None = None,
                  settings: dict | None = None, config: dict | None = None) -> dict:
    """只读节奏报告：输入组装 + 纯函数分析（不写任何东西）。项目不存在 → {"found": False}。"""
    inputs = collect_rhythm_inputs(db_path, project_id, artifact_id=artifact_id)
    if not inputs.get("found"):
        return {"found": False, "project_id": project_id}
    st = settings or rhythm_settings(config)
    rep = analyze_rhythm(inputs, settings=st)
    rep["meta"] = {
        "project_id": project_id, "project": inputs.get("project"),
        "render_artifact": inputs.get("render_artifact"),
        "voice_artifact": inputs.get("voice_artifact"),
        "readonly": True, "db_writes": 0, "files_written": 0, "tasks_created": 0,
        "network_calls": 0,
    }
    return rep


def format_rhythm(rep: dict) -> str:
    """人类可读输出：显式标注"建议（未执行）"。"""
    if not rep.get("found", True):
        return "项目不存在: {}".format(rep.get("project_id"))
    s, lines = rep["summary"], []
    lines.append("# 节奏分析（只读建议，未执行任何改动）")
    lines.append("项目 {} | 成片 {}s | 镜头 {} 个 | 切换 {} 次（{}/min）".format(
        rep["meta"]["project_id"], s.get("film_duration_s"), s.get("scene_count"),
        s.get("cuts"), s.get("cuts_per_min")))
    lines.append("旁白总时长 {}s（{} 段）| BGM：{}".format(
        s.get("narration_total_s"), s.get("narration_segments"),
        json.dumps(s.get("bgm"), ensure_ascii=False)))
    lines.append("建议 {} 条 / 无法判断 {} 条（阈值 {}）".format(
        s.get("suggestions"), s.get("unknowns"),
        json.dumps(rep.get("settings"), ensure_ascii=False)))
    lines.append("")
    for sg in rep["suggestions"]:
        lines.append("· [建议·未执行] {} {}（当前 {}s，阈值 {}）".format(
            sg["scene_id"] or "（片级）", sg["rule"], sg["current_duration_s"], sg["threshold_s"]))
        lines.append("    依据: {}".format(json.dumps(sg["evidence"], ensure_ascii=False)))
        lines.append("    动作: {}（置信度 {}）".format(sg["action"], sg["confidence"]))
        lines.append("    风险: {}".format(sg["risk"]))
    for un in rep["unknowns"]:
        lines.append("· [无法判断] {} {} — {}".format(un["scene_id"] or "（片级）", un["rule"],
                                                     un["reason"]))
    lines.append("")
    lines.append("（只读：未修改数据库/任务/产物/事件/decisions/changelog，未触发 redo，未访问网络；"
                 "applied_changes={}）".format(rep.get("applied_changes")))
    return "\n".join(lines)
