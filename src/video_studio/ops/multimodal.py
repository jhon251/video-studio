"""5.x Phase 5-A：多模态语义验证的**只读**编排（`run.py multimodal-check <pid>`）。

只读保证：
  · 数据库以 `file:<path>?mode=ro` 打开（SQLite 层面禁止写入）；
  · 只读取既有产物（`render_output` / `script_output`），不建任务、不改产物、不写库、不写生产决策；
  · 抽帧写进**临时目录**（`vs_mm_*`），可用 `--frames-dir` 指定；不在项目目录内落任何文件；
  · 结果只打印（可选 `--out <path>` 由调用者显式指定落盘），**不写任何生产产物**。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from ..core.multimodal import (DOMAIN_PROMPTS, SCHEMA, frame_plan, mm_settings,  # noqa: F401
                               validate)
from .report import readonly_connection


def labels_from_prompts(prompts: dict | None = None) -> list:
    """把"域 → 英文提示词"展开成 worker 标签表（确定性顺序）。"""
    src = prompts or DOMAIN_PROMPTS
    out = []
    for dom in sorted(src):
        for i, text in enumerate(src[dom]):
            out.append({"id": "{}#{}".format(dom, i), "text": text, "domain": dom})
    return out


def _load(path: str | None) -> dict | None:
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


def collect(con, pid: str, artifact_id: str | None = None) -> dict:
    """读取只读输入：成片路径、镜头窗口、每镜头旁白文本（来自 script_output）。"""
    ro = _latest(con, pid, "render_output", artifact_id)
    so = _latest(con, pid, "script_output")
    ro_payload = _load(ro["path"]) if ro else None
    script = _load(so["path"]) if so else None
    segs = list((script or {}).get("segments") or [])
    scenes = list((ro_payload or {}).get("material_timeline") or [])
    narration = {}
    for sc in scenes:
        sid = sc.get("scene_id")
        idx = sc.get("segment_index")
        text = ""
        if isinstance(idx, int) and 0 <= idx < len(segs):
            text = str(segs[idx].get("narration") or "")
        narration[sid] = {"text": text, "segment_index": idx,
                          "chapter": (segs[idx].get("chapter") if isinstance(idx, int)
                                      and 0 <= idx < len(segs) else None)}
    return {"render_output": ro, "script_output": so, "ro_payload": ro_payload,
            "script": script, "scenes": scenes, "narration": narration}


def extract_frames(film: str | Path, plan: list, out_dir: Path, *, ffmpeg: str | None = None,
                   quality: int = 2) -> tuple[list, list]:
    """按计划抽帧（ffmpeg，确定性参数）。返回 (frames, errors)。"""
    frames, errors = [], []
    film = Path(film)
    if not film.is_file():
        return [], [{"code": "MM_NO_FRAMES", "detail": "成片不存在: {}".format(film)}]
    out_dir.mkdir(parents=True, exist_ok=True)
    for sc in plan:
        for i, t in enumerate(sc.get("times") or []):
            fid = "{}#{}".format(sc.get("scene_id"), i)
            dst = out_dir / "{}.jpg".format(fid.replace("#", "_"))
            cmd = [ffmpeg or "ffmpeg", "-y", "-hide_banner", "-nostats", "-ss", "{:.3f}".format(t),
                   "-i", str(film), "-frames:v", "1", "-q:v", str(int(quality)), str(dst)]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", timeout=300)
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append({"code": "MM_NO_FRAMES", "detail": "{}: {}".format(
                    type(exc).__name__, str(exc)[:120]), "scene_id": sc.get("scene_id")})
                continue
            if r.returncode != 0 or not dst.is_file():
                errors.append({"code": "MM_NO_FRAMES",
                               "detail": "ffmpeg rc={} @t={}".format(r.returncode, t),
                               "scene_id": sc.get("scene_id")})
                continue
            frames.append({"id": fid, "path": str(dst), "scene_id": sc.get("scene_id"),
                           "time_s": t, "sha256": _sha256(dst)})
    return frames, errors


def _sha256(p: Path) -> str | None:
    import hashlib
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for c in iter(lambda: fh.read(1 << 20), b""):
                h.update(c)
        return h.hexdigest()
    except OSError:
        return None


def multimodal_report(db_path, project_id: str, *, artifact_id: str | None = None,
                      config: dict | None = None, settings: dict | None = None,
                      frames_dir: Path | None = None, ffmpeg: str | None = None,
                      root: Path | None = None) -> dict:
    """只读多模态验证：读库 → 抽帧 → CLIP → 三态报告（不写库、不写生产产物）。"""
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
    s = settings or mm_settings(config)
    film = (data["ro_payload"] or {}).get("output")
    plan = frame_plan(data["scenes"], int(s["frames_per_scene"]))
    ff = ffmpeg or (((config or {}).get("tools") or {}).get("ffmpeg") or {}).get("path")
    tmp = Path(frames_dir) if frames_dir else Path(tempfile.mkdtemp(prefix="vs_mm_frames_"))
    frames, errors = extract_frames(film, plan, tmp, ffmpeg=ff) if film else (
        [], [{"code": "MM_NO_FRAMES", "detail": "render_output 未记录成片路径"}])
    labels = labels_from_prompts()
    narr_by_scene = {sid: {"text": (v or {}).get("text") or ""}
                     for sid, v in (data["narration"] or {}).items()}
    rep = validate(frames, labels, root=root, settings=s, narration_by_scene=narr_by_scene,
                   film=film,
                   sources={"render_output": ({"artifact_id": data["render_output"]["artifact_id"],
                                               "sha256": _sha256(Path(data["render_output"]["path"]))}
                                              if data["render_output"] else None),
                            "script_output": ({"artifact_id": data["script_output"]["artifact_id"],
                                               "sha256": _sha256(Path(data["script_output"]["path"]))}
                                              if data["script_output"] else None),
                            "film_sha256": _sha256(Path(film)) if film else None})
    rep["meta"] = {
        "project_id": project_id,
        "project": {"project_id": project_id, "name": proj["name"], "status": proj["status"]},
        "render_artifact": ({"artifact_id": data["render_output"]["artifact_id"],
                             "task_id": data["render_output"]["task_id"]}
                            if data["render_output"] else None),
        "frame_plan": plan, "frames_extracted": len(frames), "frame_errors": errors,
        "frames_dir": str(tmp), "readonly": True, "db_writes": 0, "production_writes": 0,
        "labels": labels,
    }
    return rep


def format_mm(rep: dict) -> str:
    """人读输出：显式标注"只读/未执行"。"""
    if not rep.get("found", True):
        return "项目不存在: {}".format(rep.get("project_id"))
    c, m = rep.get("counts") or {}, rep.get("meta") or {}
    lines = ["# 多模态语义验证（只读证据层；不覆盖 4-B 结果、不执行任何改动）",
             "项目 {} | 成片 {} | 抽帧 {} 张 | 模型 {}（{}）".format(
                 m.get("project_id"), rep.get("film"), m.get("frames_extracted"),
                 (rep.get("model") or {}).get("snapshot"), (rep.get("versions") or {}).get("torch")),
             "计数：MATCH={} MISMATCH={} UNKNOWN={}".format(
                 c.get("MATCH"), c.get("MISMATCH"), c.get("UNKNOWN"))]
    if rep.get("error"):
        lines.append("错误：{} — {}".format(rep["error"].get("code"), rep["error"].get("detail")))
    for sc in rep.get("scenes") or []:
        lines.append("· {} {:<9s} 期望域={} 期望相似度={} 最强其它域={}({}) Δ={} 置信={}".format(
            sc.get("scene_id"), sc.get("verdict"), sc.get("expected_domain"),
            sc.get("expected_sim"), sc.get("best_other_domain"), sc.get("best_other_sim"),
            sc.get("delta"), sc.get("confidence")))
        lines.append("    旁白: {}".format((sc.get("narration_text") or "")[:80]))
        lines.append("    依据: {}".format(sc.get("reason")))
        if sc.get("top_k"):
            lines.append("    画面最像的域: {}".format(
                ", ".join("{}({})".format(x["domain"], x["sim"]) for x in sc["top_k"])))
    lines.append("")
    lines.append("（只读：未写数据库/未写生产产物/未改选材·时间轴·旁白·BGM/未触发 redo；"
                 "4-B 结果原样保留，本层仅为新增证据）")
    return "\n".join(lines)
