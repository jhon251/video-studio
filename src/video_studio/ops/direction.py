# -*- coding: utf-8 -*-
"""6-A / M1 —— Directorial Quality **只读编排**（`run.py direction`）。

只读保证（与 `ops/integrity.py` 相同）：
  · DB `mode=ro` + `PRAGMA query_only=ON`；不写库/不写项目目录/不写产物；
  · **不换素材、不剪辑、不重渲染、不发布**；不调用 `build_engine()`；
  · 语义项只**复用既有只读证据**（4-B/5-A/5-D/Judge 报告），无证据即 `NOT_ASSESSABLE`；
  · 报告默认打印；仅当显式 `out_path` 时写报告文件。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..core import direction as core_direction
from ..core import integrity as core_integrity

SCHEMA = "directorial-quality-v1"


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db_path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def load_evidence(path: str | Path | None, root: Path) -> dict | None:
    """从既有只读评估报告提取 {scene_id: {layer: state}}。

    支持形态：`{"rows": [{"scene_id": "S01", "layers": {...}}]}` 或
              `{"rows": [{"scene_id": "S01", "4b": "UNKNOWN", "5a": "...", "5d": "...",
                          "judge": "..."}]}` 或直接的 `{scene_id: {...}}`。
    """
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    if not p.is_file():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return None
    if isinstance(d, dict) and isinstance(d.get("rows"), list):
        out = {}
        for row in d["rows"]:
            sid = row.get("scene_id") or row.get("case_id")
            if not sid:
                continue
            if isinstance(row.get("layers"), dict):
                out[sid] = {k: str(v).upper() for k, v in row["layers"].items()}
            else:
                keys = ("4b", "4B", "5a", "5A", "5d", "5D", "judge", "final", "verdict")
                out[sid] = {k: str(row[k]).upper() for k in keys if row.get(k)}
        return out or None
    if isinstance(d, dict):
        return {k: ({kk: str(vv).upper() for kk, vv in v.items()} if isinstance(v, dict) else
                    {"verdict": str(v).upper()}) for k, v in d.items()}
    return None


def build_direction_report(project_id: str, db_path: Path, root: Path, config: dict,
                           film_task: str | None = None, film: str | None = None,
                           evidence_path: str | None = None, policy: dict | None = None,
                           measure_freeze: bool = True) -> dict:
    ff = ((config.get("tools") or {}).get("ffmpeg") or {})
    ffmpeg = ff.get("path")
    con = _connect_ro(db_path)
    try:
        recs = [dict(r) for r in con.execute(
            "select artifact_id, task_id, type, path from artifacts where project_id=? "
            "order by created_at", (project_id,))]
        tasks = [dict(r) for r in con.execute(
            "select task_id, task_type, status from tasks where project_id=?", (project_id,))]
    finally:
        con.close()
    by_type: dict[str, list[dict]] = {}
    for r in recs:
        by_type.setdefault(r["type"], []).append(r)

    def payload(rec):
        if not rec:
            return {}
        p = Path(rec["path"])
        if not p.is_absolute():
            p = root / p
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            return {}

    script = payload((by_type.get("script_output") or [None])[-1])
    render_rec = None
    if film_task:
        render_rec = next((r for r in (by_type.get("render_output") or [])
                           if r["task_id"] == film_task), None)
    if render_rec is None:
        ok = {t["task_id"] for t in tasks if t["status"] == "SUCCEEDED"}
        render_rec = next((r for r in reversed(by_type.get("render_output") or [])
                           if r["task_id"] in ok), None)
    render = payload(render_rec)
    timeline = render.get("material_timeline") or []
    script_segs = script.get("segments") or []
    timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s")
                           or (timeline[-1]["end_s"] if timeline else 0.0) or 0.0)
    film_path = film or render.get("output") or None

    freeze_blocks, freeze_error = None, None
    if measure_freeze and film_path and Path(film_path).is_file() and ffmpeg:
        try:
            freeze_blocks, err = core_direction.measure_freeze(film_path, ffmpeg, timeline_total)
            if not freeze_blocks:
                freeze_error = (err or "")[-400:]
        except Exception as exc:                                 # noqa: BLE001
            freeze_blocks, freeze_error = None, "{}: {}".format(type(exc).__name__, exc)

    evidence = load_evidence(evidence_path, root)
    # 片尾静音（只读复用 PI-3 度量；无成片则 None → 结构项按关键词判定）
    tail_silence = None
    if film_path and Path(film_path).is_file() and ffmpeg:
        try:
            prof = core_integrity.audio_silence_profile(film_path, ffmpeg, timeline_total, policy)
            tail_silence = prof.get("tail_silence_s")
        except Exception:                                        # noqa: BLE001
            tail_silence = None

    hook_id = (timeline[0].get("scene_id") if timeline else "S01")
    metrics = {
        "DQ-1": core_direction.hook_relevance(evidence, hook_scene=hook_id),
        "DQ-2": core_direction.asset_reuse(timeline, policy),
        "DQ-3": core_direction.static_hold(timeline, freeze_blocks, policy),
        "DQ-4": core_direction.visual_density(timeline, freeze_blocks, policy),
        "DQ-5": core_direction.climax_coverage(script_segs, timeline, evidence, policy),
        "DQ-6": core_direction.ending_completeness(script_segs, timeline, tail_silence, evidence,
                                                   policy),
        # 6-B/M1：逐镜"视觉语义支撑"（授权覆盖项之一），只读复用既有证据
        "DQ-8": core_direction.narration_visual_support(script_segs, timeline, evidence, policy),
    }
    inputs = {"project_id": project_id, "film": (str(film_path) if film_path else None),
              "film_task": (render.get("task_id") if render else None),
              "scenes": len(timeline), "script_segments": len(script_segs),
              "timeline_duration_s": timeline_total,
              "evidence": (str(evidence_path) if evidence else None),
              "freeze_measured": freeze_blocks is not None and bool(freeze_blocks),
              "freeze_error": freeze_error,
              "policy": {**(core_direction.DEFAULT_POLICY if policy is None else policy)}}
    return {"schema": SCHEMA, "kind": "directorial_quality", "read_only": True, "enforced": False,
            "advisory": True,
            "mode": "6-B/M1（只读诊断；不换素材/不剪辑/不重渲染/不接入 TASK_BLOCKED/不发布）",
            "inputs": inputs, "metrics": metrics,
            "summary": core_direction.summarize_direction(metrics)}


def write_report(report: dict, out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def format_direction(report: dict) -> str:
    L = ["Directorial Quality（只读 / M1 只诊断）  project={} film={}".format(
        report["inputs"]["project_id"], report["inputs"]["film"]),
        "  scenes={} script_segments={} timeline={} s | evidence={}".format(
            report["inputs"]["scenes"], report["inputs"]["script_segments"],
            report["inputs"]["timeline_duration_s"], report["inputs"]["evidence"])]
    for k in sorted(report["metrics"]):
        m = report["metrics"][k]
        L.append("  {:5s} {:14s} {}".format(k, m.get("state"), _brief(k, m)))
    s = report["summary"]
    L.append("  —— 汇总: {} | FAIL={} UNKNOWN={} NOT_ASSESSABLE={} PASS={}".format(
        s["overall"], s["counts"]["FAIL"], s["counts"]["UNKNOWN"],
        s["counts"]["NOT_ASSESSABLE"], s["counts"]["PASS"]))
    L.append("  语义项（UNKNOWN 不得视为 PASS）: {}".format(
        json.dumps(s["semantic_states"], ensure_ascii=False)))
    return "\n".join(L)


def _brief(k: str, m: dict) -> str:
    if k == "DQ-1":
        return "hook={} layers={} semantic={}".format(m.get("hook_scene"), m.get("layers"),
                                                      m.get("semantic"))
    if k == "DQ-2":
        return "unique_assets={} max_share={} scenes={}".format(
            m.get("unique_assets"), m.get("max_asset_share"), m.get("scenes"))
    if k == "DQ-3":
        return "mean_hold={}s max_hold={}s over={}/{} freeze={}".format(
            m.get("mean_hold_s"), m.get("max_hold_s"), m.get("holds_over_threshold"),
            m.get("scenes"), (m.get("freeze_profile") or {}).get("longest_s"))
    if k == "DQ-4":
        return "changes/min={} unique/min={} freeze_blocks/min={}".format(
            m.get("scene_changes_per_min"), m.get("unique_assets_per_min"),
            m.get("freeze_blocks_per_min"))
    if k == "DQ-5":
        return "core={} distinct_assets={} mean_hold={}s semantic={}".format(
            m.get("core_scenes"), m.get("distinct_assets_in_core"), m.get("mean_hold_in_core_s"),
            m.get("semantic_state"))
    if k == "DQ-6":
        return "outro_hits={} tail_silence={}s semantic={}".format(
            len(m.get("outro_keyword_hits") or []), m.get("tail_silence_s"),
            m.get("semantic_state"))
    if k == "DQ-8":
        return "scenes_with_evidence={}/{} match_share={} mismatch_scenes={} counts={}".format(
            m.get("scenes_with_evidence"), m.get("scenes"), m.get("match_share"),
            m.get("mismatch_scene_count"), m.get("layer_counts"))
    return ""
