"""5.x Phase 5-B：多模态候选的**只读**编排（`run.py mm-review <pid>`）。

只读保证（与 4-G/5-A 同口径）：
  · 数据库以 `file:<path>?mode=ro` 打开（SQLite 层面禁止写入）；
  · 只读取既有产物（`render_output` / `retrieval_candidates` / `script_output`），不建任务、不改产物；
  · 抽帧/评分写系统临时目录；结果只打印（可选 `--out <path>` 由调用者显式指定）；
  · **绝不**调用 `select-candidate`、**绝不**触发 redo、**绝不**改选材/时间轴/BGM。
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..core.mm_candidates import (SCHEMA, build_report, mmc_settings,  # noqa: F401
                                 pool_from_retrievals, score_candidates)
from ..core.multimodal import mm_settings
from .multimodal import collect as _collect_mm
from .report import readonly_connection


def _load(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def collect_pool(con, pid: str) -> list:
    """读取该项目**全部** `retrieval_candidates` 产物（按时间排序）→ 候选池来源。"""
    rows = con.execute("select path from artifacts where project_id=? and "
                       "type='retrieval_candidates' order by created_at", (pid,)).fetchall()
    out = []
    for r in rows:
        payload = _load(r["path"])
        if payload:
            out.append(payload)
    return out


def mm_review_report(db_path, project_id: str, *, artifact_id: str | None = None,
                     config: dict | None = None, frames_dir: Path | None = None,
                     root: Path | None = None) -> dict:
    """只读：5-A 判定 → 候选池 → CLIP 打分 → 可解释候选清单（不写任何生产状态）。"""
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    con = readonly_connection(db_path)
    try:
        proj = con.execute("select * from projects where project_id=?",
                           (project_id,)).fetchone()
        if proj is None:
            return {"found": False, "project_id": project_id}
        mm_inputs = _collect_mm(con, project_id, artifact_id)      # 复用 5-A 的只读读取
        pools = collect_pool(con, project_id)
    finally:
        con.close()
    # 5-A 判定（只读；同一模型、同一抽帧口径）
    from ..core.multimodal import frame_plan, validate
    from .multimodal import extract_frames, labels_from_prompts
    ms = mm_settings(config)
    film = (mm_inputs["ro_payload"] or {}).get("output")
    ff = (((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("path")
    tmp = Path(frames_dir) if frames_dir else Path(tempfile.mkdtemp(prefix="vs_5b_frames_"))
    plan = frame_plan(mm_inputs["scenes"], int(ms["frames_per_scene"]))
    frames, _errs = extract_frames(film, plan, tmp, ffmpeg=ff) if film else ([], [])
    narration = {sid: {"text": (v or {}).get("text") or ""}
                 for sid, v in (mm_inputs["narration"] or {}).items()}
    mm_rep = validate(frames, labels_from_prompts(), root=root, settings=ms,
                      narration_by_scene=narration, film=film)
    project_dir = db_path.parent / project_id
    pool = pool_from_retrievals(pools, project_dir, mm_inputs["scenes"])
    cs = mmc_settings(config)
    scored = score_candidates(pool["pool"], None, root=root, settings=cs,
                              mm_settings_override=ms, workdir=tmp)
    rep = build_report(mm_rep, pool, scored, cs, project_id=project_id)
    rep["meta"] = {
        "project_id": project_id, "project": {"project_id": project_id, "name": proj["name"]},
        "render_artifact": ({"artifact_id": mm_inputs["render_output"]["artifact_id"],
                             "task_id": mm_inputs["render_output"]["task_id"]}
                            if mm_inputs["render_output"] else None),
        "film": film, "frame_plan": plan, "frames_extracted": len(frames),
        "pool_sources": len(pools), "scored_assets": len((scored.get("scores") or {})),
        "expected_domains": {s.get("scene_id"): s.get("expected_domain")
                             for s in (mm_rep.get("scenes") or [])}, "readonly": True, "db_writes": 0,
        "production_writes": 0, "redo_triggered": 0, "select_candidate_called": 0,
        "model": scored.get("model") or {}, "versions": scored.get("versions") or {},
        "worker_code": scored.get("worker_code"), "worker_detail": scored.get("detail"),
    }
    return rep


def format_mm_review(rep: dict) -> str:
    """人读输出：候选 + 证据 + 风险 + **人工确认命令**（只打印，不执行）。"""
    if not rep.get("found", True):
        return "项目不存在: {}".format(rep.get("project_id"))
    m, c = rep.get("meta") or {}, rep.get("counts") or {}
    lines = ["# 5-B 多模态候选（只生成候选；需人工确认后由人工 select-candidate + redo）",
             "项目 {} | 5-A 判定 {} | 待复核镜头 {} | 候选状态 {}".format(
                 m.get("project_id"), json.dumps(rep.get("mm_counts"), ensure_ascii=False),
                 rep.get("flagged_scenes"), json.dumps(c, ensure_ascii=False)),
             "视觉模型 {} | 候选池 {} 个已验证本地素材（不可用 {}）".format(
                 (rep.get("visual_model") or {}).get("snapshot"),
                 (rep.get("pool_summary") or {}).get("verified_local"),
                 (rep.get("pool_summary") or {}).get("unusable"))]
    for s in rep.get("scenes") or []:
        lines.append("")
        lines.append("## {} — 5-A 判定 {}（期望域 {}，Δ={}）".format(
            s.get("scene_id"), s.get("mm_verdict"), s.get("expected_domain"),
            (s.get("mm_evidence") or {}).get("delta")))
        lines.append("   依据：{}".format((s.get("mm_evidence") or {}).get("reason")))
        if s.get("current_asset"):
            lines.append("   当前素材：{}（{}）".format(
                (s["current_asset"] or {}).get("name"),
                (s["current_asset"] or {}).get("license_class")))
        lines.append("   状态：{} {}".format(s.get("status"), s.get("code") or ""))
        for i, cd in enumerate(s.get("candidates") or [], start=1):
            v = cd.get("visual_evidence") or {}
            lines.append("   [{}.] {}  score={} 视觉相似度={} 最像域={}({}) 许可={}({}) 来源={}/{}".format(
                i, cd.get("name"), cd.get("semantic_evidence", {}).get("keyword_match_score"),
                v.get("visual_sim_expected"), v.get("visual_best_domain"), v.get("visual_best_sim"),
                cd.get("license"), cd.get("license_class"),
                (cd.get("source") or {}).get("provider"), (cd.get("source") or {}).get("source_id")))
            for r in cd.get("risks") or []:
                lines.append("        · 风险：{}".format(r))
        for rj in (s.get("rejected") or [])[:5]:
            lines.append("   [排除] {} — {}".format(
                rj.get("name"), "; ".join(rj.get("excluded_reasons") or [])))
        if s.get("human_command"):
            lines.append("   人工确认命令（需人工执行；本命令不会自动运行）：")
            lines.append("     {}".format(s["human_command"]))
        if s.get("note"):
            lines.append("   说明：{}".format(s["note"]))
    lines.append("")
    lines.append("（只读：未写数据库/未写产物/未替换素材/未触发 redo；4-B 与 5-A 历史证据原样保留；"
                 "select-candidate 调用次数={}，redo 触发次数={}）".format(
                     m.get("select_candidate_called"), m.get("redo_triggered")))
    return "\n".join(lines)
