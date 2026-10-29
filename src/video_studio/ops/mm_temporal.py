"""5.x Phase 5-D：多帧/时序多模态验证的**只读**编排（`run.py mm-temporal <pid>`）。

只读保证（与 5-A 同口径，并在报告里机器可读地声明）：
  · 数据库以 `file:<path>?mode=ro` 打开（SQLite 层面禁止写入）；
  · 只读既有产物（`render_output` / `script_output`），不建任务、不改产物、不写库、不写生产决策；
  · 抽帧写进**临时目录**（`vs_mmt_frames_*`），可用 `--frames-dir` 指定；不在项目目录内落任何文件；
  · 结果只打印（可选 `--out <path>` 由调用者显式指定落盘），**不写任何生产产物**；
  · 5-A 的判定以**引用副本**并列展示（`five_a_reference`，由既有 5-A 只读命令对同一产物重跑得到），
    **不改写、不覆盖** 5-A 的报告与日志（5-A 模块 `core/multimodal.py` 一字未动）。
"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from ..core.mm_temporal import (MMT_DEFAULTS, SCHEMA, labels_from_prompts,  # noqa: F401
                                mmt_settings, validate_temporal)
from ..core.multimodal import frame_plan
from .multimodal import collect, extract_frames, multimodal_report
from .report import readonly_connection


def _sha256(p) -> str | None:
    try:
        h = hashlib.sha256()
        with Path(p).open("rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return None


def _ffmpeg_from_config(config: dict | None, root: Path) -> str | None:
    """解析 ffmpeg 可执行文件：显式配置优先，其次仓库 `config/config.json`（库调用与 CLI 同口径）。"""
    p = (((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("path")
    if p:
        return p
    cfg_p = Path(root) / "config" / "config.json"
    try:
        cfg = json.loads(cfg_p.read_text(encoding="utf-8-sig"))
        return (((cfg.get("tools") or {}).get("ffmpeg") or {}).get("path")) or None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def five_a_reference(db_path, project_id: str, *, artifact_id: str | None = None,
                     config: dict | None = None, root: Path | None = None,
                     frames_dir: Path | None = None) -> dict:
    """对**同一产物**重跑既有 5-A 只读命令，取其判定的**引用副本**（不做任何改写）。"""
    try:
        rep5 = multimodal_report(db_path, project_id, artifact_id=artifact_id, config=config,
                                 frames_dir=(Path(frames_dir) / "five_a") if frames_dir else None,
                                 root=root)
    except Exception as exc:                                  # noqa: BLE001
        return {"schema": "five-a-reference", "ok": False,
                "error": {"code": "MM_WORKER_FAILED",
                          "detail": "{}: {}".format(type(exc).__name__, str(exc)[:160])}}
    if not rep5.get("found", True):
        return {"schema": "five-a-reference", "ok": False,
                "error": {"code": "PROJECT_NOT_FOUND", "detail": project_id}}
    scenes = [{"scene_id": s.get("scene_id"), "verdict": s.get("verdict"), "code": s.get("code"),
               "confidence": s.get("confidence"), "expected_domain": s.get("expected_domain"),
               "expected_sim": s.get("expected_sim"), "best_other_domain": s.get("best_other_domain"),
               "best_other_sim": s.get("best_other_sim"), "delta": s.get("delta"),
               "frames_per_scene": len(s.get("frames") or []),
               "frame_times": [f.get("time_s") for f in (s.get("frames") or [])]}
              for s in rep5.get("scenes") or []]
    return {"schema": "five-a-reference", "ok": not bool(rep5.get("error")),
            "source": "run.py multimodal-check（同一 render_output 产物，只读重跑）",
            "artifact_id": (rep5.get("meta") or {}).get("render_artifact", {}).get("artifact_id")
            if isinstance((rep5.get("meta") or {}).get("render_artifact"), dict)
            else ((rep5.get("meta") or {}).get("artifact_id")),
            "film": rep5.get("film"), "counts": rep5.get("counts"),
            "settings": {"frames_per_scene": (rep5.get("settings") or {}).get("frames_per_scene"),
                         "min_sim": (rep5.get("settings") or {}).get("min_sim"),
                         "margin": (rep5.get("settings") or {}).get("margin")},
            "model_weights_sha256": (rep5.get("model") or {}).get("weights_sha256"),
            "error": rep5.get("error"), "scenes": scenes,
            "note": "引用副本：5-A 的原始报告/日志未被本层修改或覆盖"}


def temporal_report(db_path, project_id: str, *, artifact_id: str | None = None,
                    config: dict | None = None, settings: dict | None = None,
                    frames_dir: Path | None = None, ffmpeg: str | None = None,
                    root: Path | None = None, with_five_a: bool = True) -> dict:
    """只读时序验证：读库 → 加密抽帧 → CLIP（相似度 + 视觉嵌入）→ 时序三态报告。"""
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    con = readonly_connection(db_path)
    try:
        data = collect(con, project_id, artifact_id)
        proj = con.execute("select * from projects where project_id=?",
                           (project_id,)).fetchone()
    finally:
        con.close()
    if proj is None:
        return {"found": False, "project_id": project_id}
    s = settings or mmt_settings(config)
    film = (data["ro_payload"] or {}).get("output")
    plan = frame_plan(data["scenes"], int(s["frames_per_scene"]))
    ff = ffmpeg or _ffmpeg_from_config(config, root)
    tmp = Path(frames_dir) if frames_dir else Path(tempfile.mkdtemp(prefix="vs_mmt_frames_"))
    frames, errors = extract_frames(film, plan, tmp, ffmpeg=ff) if film else (
        [], [{"code": "MMT_NO_FRAMES", "detail": "render_output 未记录成片路径"}])
    labels = labels_from_prompts()
    narr_by_scene = {sid: {"text": (v or {}).get("text") or ""}
                     for sid, v in (data["narration"] or {}).items()}
    ref = (five_a_reference(db_path, project_id, artifact_id=artifact_id, config=config,
                            root=root, frames_dir=tmp) if with_five_a
           else {"schema": "five-a-reference", "ok": False, "skipped": True,
                 "note": "本次运行显式跳过 5-A 引用（--no-five-a）"})
    rep = validate_temporal(frames, labels, root=root, settings=s,
                            narration_by_scene=narr_by_scene, film=film,
                            five_a_reference=ref,
                            sources={"render_output":
                                     ({"artifact_id": data["render_output"]["artifact_id"],
                                       "sha256": _sha256(data["render_output"]["path"])}
                                      if data["render_output"] else None),
                                     "script_output":
                                     ({"artifact_id": data["script_output"]["artifact_id"],
                                       "sha256": _sha256(data["script_output"]["path"])}
                                      if data["script_output"] else None),
                                     "film_sha256": _sha256(film) if film else None})
    rep["meta"] = {
        "project_id": project_id,
        "project": {"project_id": project_id, "name": proj["name"], "status": proj["status"]},
        "render_artifact": ({"artifact_id": data["render_output"]["artifact_id"],
                             "task_id": data["render_output"]["task_id"]}
                            if data["render_output"] else None),
        "frame_plan": plan, "frames_extracted": len(frames), "frame_errors": errors,
        "frames_dir": str(tmp), "readonly": True, "db_writes": 0, "production_writes": 0,
        "labels": labels, "five_a_reference_ok": bool((ref or {}).get("ok")),
    }
    return rep


def format_mmt(rep: dict) -> str:
    """人读输出：显式标注"只读/未执行"，逐镜头给出时序证据与规则 ID。"""
    if not rep.get("found", True):
        return "项目不存在: {}".format(rep.get("project_id"))
    c, m = rep.get("counts") or {}, rep.get("meta") or {}
    lines = ["# 多帧/时序多模态验证（只读平行证据层；不覆盖 4-B / 5-A 结果、不执行任何改动）",
             "项目 {} | 成片 {} | 抽帧 {} 张 | 模型 {}（{}）".format(
                 m.get("project_id"), rep.get("film"), m.get("frames_extracted"),
                 (rep.get("model") or {}).get("snapshot"), (rep.get("versions") or {}).get("torch")),
             "每镜头帧数={} | 计数：MATCH={} MISMATCH={} UNKNOWN={}".format(
                 (rep.get("settings") or {}).get("frames_per_scene"), c.get("MATCH"),
                 c.get("MISMATCH"), c.get("UNKNOWN"))]
    if rep.get("error"):
        lines.append("错误：{} — {}".format(rep["error"].get("code"), rep["error"].get("detail")))
    ref5 = rep.get("five_a_reference") or {}
    lines.append("5-A 引用：{}（{}）| 计数 {} | 每镜头 {} 帧".format(
        ref5.get("source") or ref5.get("note"), ref5.get("ok"), ref5.get("counts"),
        (ref5.get("settings") or {}).get("frames_per_scene")))
    for sc in rep.get("scenes") or []:
        ag, st = sc.get("aggregate") or {}, sc.get("stability") or {}
        lines.append("· {} {:<9s} 规则={} 置信={} 期望域={}({}) 帧数={} | 5-A={}".format(
            sc.get("scene_id"), sc.get("verdict"), sc.get("rule_id"), sc.get("confidence"),
            sc.get("expected_domain"), sc.get("expected_domain_source"), sc.get("frame_count"),
            sc.get("five_a_verdict")))
        lines.append("    时序：一致性 mean={} min={} 类别={} split={} 散布={}".format(
            st.get("visual_stability_mean"), st.get("visual_stability_min"), st.get("class"),
            st.get("split"), st.get("dispersion")))
        lines.append("    聚合：期望相似度 中位数={} 最小={} | 边际中位数={} | 投票占比={} | "
                     "其它域占比={}（{}）".format(
                         ag.get("expected_sim_median"), ag.get("expected_sim_min"),
                         ag.get("median_margin"), ag.get("vote_expected"),
                         ag.get("other_vote_frac"), ag.get("other_vote_domain")))
        lines.append("    依据：{}".format(sc.get("reason")))
    lines.append("")
    lines.append("（只读：未写数据库/未写生产产物/未改选材·时间轴·旁白·BGM/未触发 redo；"
                 "4-B 与 5-A 结果原样保留，本层仅为新增平行证据）")
    return "\n".join(lines)
