# -*- coding: utf-8 -*-
"""6-A / M1 —— Production Integrity **只读编排**（`run.py integrity`）。

只读保证：
  · DB 以 `mode=ro` + `PRAGMA query_only=ON` 打开；**不写库、不写项目目录、不写产物**；
  · 不调用 `build_engine()`（不建库/不建目录/不派发任务）；
  · 不修改渲染行为、apad 契约、素材选择、剪辑、TTS、字幕生成逻辑；
  · 报告默认打印到 stdout；仅当显式给 `out_path` 时才写**报告文件**（不是产物）。
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from ..core import integrity as core_integrity

SCHEMA = "production-integrity-v1"


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect("file:{}?mode=ro".format(Path(db_path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    return con


def build_integrity_report(project_id: str, db_path: Path, root: Path, config: dict,
                           film_task: str | None = None, film: str | None = None,
                           policy: dict | None = None) -> dict:
    """返回结构化只读报告（PI-1 … PI-6）。"""
    ff = ((config.get("tools") or {}).get("ffmpeg") or {})
    ffmpeg, ffprobe = ff.get("path"), ff.get("ffprobe")
    project_dir = Path(db_path).parent / project_id
    con = _connect_ro(db_path)
    try:
        recs = [dict(r) for r in con.execute(
            "select artifact_id, task_id, type, path, created_at from artifacts "
            "where project_id=? order by created_at", (project_id,))]
        tasks = [dict(r) for r in con.execute(
            "select task_id, task_type, version, status, created_at from tasks "
            "where project_id=? order by created_at", (project_id,))]
    finally:
        con.close()
    by_type: dict[str, list[dict]] = {}
    for r in recs:
        by_type.setdefault(r["type"], []).append(r)

    def newest(t):
        lst = by_type.get(t) or []
        return lst[-1] if lst else None

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

    voice, script, sub = payload(newest("voice_output")), payload(newest("script_output")), \
        payload(newest("subtitle"))
    # 成片：优先显式 --film / --film-task；否则取最近一次 SUCCEEDED 的 render_output
    render_rec = None
    if film_task:
        render_rec = next((r for r in (by_type.get("render_output") or [])
                           if r["task_id"] == film_task), None)
    if render_rec is None:
        ok_ids = {t["task_id"] for t in tasks if t["status"] == "SUCCEEDED"}
        render_rec = next((r for r in reversed(by_type.get("render_output") or [])
                           if r["task_id"] in ok_ids), None)
    render = payload(render_rec)
    timeline = render.get("material_timeline") or []
    timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s")
                           or (timeline[-1]["end_s"] if timeline else 0.0) or 0.0)
    narration_s = voice.get("narration_duration_s")
    voice_durs = [d.get("duration_s") for d in (voice.get("segment_details") or [])]
    script_segs = script.get("segments") or []
    film_path = film or render.get("output") or None

    probe = None
    if film_path and Path(film_path).is_file() and ffprobe:
        try:
            probe = core_integrity.probe_tracks(film_path, ffprobe)
        except Exception:                                        # noqa: BLE001
            probe = None

    metrics = {
        "PI-1": core_integrity.narration_coverage(narration_s, timeline_total, policy),
        "PI-2": core_integrity.duration_contract_dual(timeline_total, narration_s, policy),
        "PI-3": core_integrity.audio_silence_profile(film_path, ffmpeg, timeline_total, policy),
        "PI-4": core_integrity.av_track_consistency(probe, timeline_total, policy),
        "PI-5": core_integrity.subtitle_orphans(sub.get("srt") or [], narration_s,
                                                timeline_total, policy),
        "PI-6": core_integrity.segment_boundary_drift(script_segs, voice_durs, policy),
    }
    inputs = {
        "project_id": project_id, "db_path": str(db_path),
        "film": (str(film_path) if film_path else None),
        "film_task": (render.get("task_id") if render else None),
        "voice_task": (newest("voice_output") or {}).get("task_id"),
        "subtitle_artifact": (newest("subtitle") or {}).get("artifact_id"),
        "timeline_duration_s": timeline_total, "narration_duration_s": narration_s,
        "scenes": len(timeline), "script_segments": len(script_segs),
        "voice_segments": len(voice_durs),
        "policy": {**(core_integrity.DEFAULT_POLICY if policy is None else policy)},
    }
    return {"schema": SCHEMA, "kind": "production_integrity", "read_only": True,
            "enforced": False, "advisory": True, "mode": "M1（只读度量；不接线、不阻断）",
            "inputs": inputs, "metrics": metrics,
            "summary": core_integrity.summarize(metrics)}


def write_report(report: dict, out_path: str | Path) -> Path:
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def format_integrity(report: dict) -> str:
    L = ["Production Integrity（只读 / M1 不阻断）  project={} film={}".format(
        report["inputs"]["project_id"], report["inputs"]["film"]),
        "  narration={} s | timeline={} s | scenes={}".format(
            report["inputs"]["narration_duration_s"], report["inputs"]["timeline_duration_s"],
            report["inputs"]["scenes"])]
    for k in sorted(report["metrics"]):
        m = report["metrics"][k]
        L.append("  {:5s} {:14s} {}".format(k, m.get("state"), _brief(k, m)))
    s = report["summary"]
    L.append("  —— 汇总: {} | FAIL={} UNKNOWN={} NOT_ASSESSABLE={} PASS={} | UNKNOWN≠PASS".format(
        s["overall"], s["counts"]["FAIL"], s["counts"]["UNKNOWN"],
        s["counts"]["NOT_ASSESSABLE"], s["counts"]["PASS"]))
    return "\n".join(L)


def _brief(k: str, m: dict) -> str:
    if k == "PI-1":
        return "coverage={} shortfall={}s".format(m.get("coverage_ratio"), m.get("shortfall_s"))
    if k == "PI-2":
        return "shortfall={}s excess={}s within_tol={}".format(
            (m.get("contract") or {}).get("shortfall_s"), (m.get("contract") or {}).get("excess_s"),
            (m.get("contract") or {}).get("within_tolerance"))
    if k == "PI-3":
        return "blocks={} longest={}s ratio={} tail={}s".format(
            m.get("blocks"), m.get("longest_silence_s"), m.get("silence_ratio"),
            m.get("tail_silence_s"))
    if k == "PI-4":
        return "video={}s audio={}s delta={}s frames={}".format(
            (m.get("probe") or {}).get("video_s"), (m.get("probe") or {}).get("audio_s"),
            m.get("track_delta_s"), (m.get("probe") or {}).get("frames"))
    if k == "PI-5":
        return "cues={} orphan={} ({}) first={}s".format(
            m.get("cues"), m.get("orphan_cues"), m.get("orphan_share"), m.get("orphan_first_s"))
    if k == "PI-6":
        return "max_abs_drift={}s final={}s".format(m.get("max_abs_drift_s"),
                                                    m.get("final_drift_s"))
    return ""
