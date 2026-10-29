"""visual_qc（v3-mvp）：机器完整性审计（jitter=0 硬 Gate，三源分口径）+ A/B/C 对照。

jitter 口径（R2）：
  transform_delta —— executor 实际变换轨迹（spec 的 crop rect / anchor shift），
                     HOLD 必须全 0；运动必须整数/单调（motion.py 保证 + 此处复核）；
  content_delta   —— 视频素材自身帧内容变化（不判为 camera jitter）；
  alpha_delta     —— 淡入淡出/文字显隐（appearance change，不判为 geometric jitter）。
判定：
  HOLD + alpha fade = PASS；HOLD + 视频内容运动 = PASS；HOLD + 真实 transform 位移 = FAIL；
  运动 beat：出现 0↔N 交替 / 方向反转 / 尖峰 = FAIL。
分类（v3_gate.json）：REAL_RENDER_DEFECT / AUDIT_FALSE_POSITIVE / AUDIT_TRUE_POSITIVE。
"""
from __future__ import annotations

import json
import re
import subprocess
import unicodedata
from pathlib import Path

import numpy as np

from video_studio.stage33 import schemas

ROOT = Path(__file__).resolve().parents[3]
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FPS = 25


def _norm(s: str) -> str:
    """Unicode 归一 + 标点剥离（NFKC 会把全角标点转半角，须两者都剥）+ 空白归一。"""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[，。；！？、,.;!?\s\u3000]", "", s)
    return s


def _gray_frames(video: Path, fps: int, w: int = 480, h: int = 270) -> np.ndarray | None:
    r = subprocess.run(
        [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-i", str(video),
         "-vf", f"fps={fps},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    if r.returncode != 0 or not r.stdout:
        return None
    n = len(r.stdout) // (w * h)
    return np.frombuffer(r.stdout, dtype=np.uint8)[:n * w * h].reshape(n, h, w)


def _rgb_frame(video: Path, t: float) -> np.ndarray | None:
    r = subprocess.run(
        [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
         "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True)
    if r.returncode != 0 or len(r.stdout) != 1920 * 1080 * 3:
        return None
    return np.frombuffer(r.stdout, dtype=np.uint8).reshape(1080, 1920, 3)


def _text_pixels(img: np.ndarray | None) -> float:
    """调色板文字像素占比：白 #F4F8F9 或 高亮橙 #FFB74D（容差带）。"""
    if img is None:
        return 0.0
    r, g, b = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
    y = 0.299 * r + 0.587 * g + 0.114 * b
    white = y > 218
    orange = (r > 200) & (g > 130) & (g < 215) & (b < 130)
    return float((white | orange).mean())


def _transform_series(spec: dict, n: int) -> list[float]:
    """executor 实际变换轨迹（帧间几何位移）：material rects 或 anchor shift。"""
    series = [0.0] * max(n - 1, 0)
    for l in spec["layers"]:
        if l.get("rects"):
            rs = l["rects"][:n]
            for i in range(1, len(rs)):
                series[i - 1] += (abs(rs[i][0] - rs[i - 1][0]) +
                                  abs(rs[i][1] - rs[i - 1][1]) +
                                  abs(rs[i][2] - rs[i - 1][2]) // 2)
        elif l.get("shift_frames"):
            ss = l["shift_frames"][:n]
            for i in range(1, len(ss)):
                series[i - 1] += (abs(ss[i][0] - ss[i - 1][0]) +
                                  abs(ss[i][1] - ss[i - 1][1]))
    return series


def jitter_audit(beats_dir: Path, plan: dict) -> dict:
    rows, violations = [], []
    for b in plan["beats"]:
        clip = beats_dir / f"{b['beat_id']}.mp4"
        if not clip.exists():
            violations.append({"beat_id": b["beat_id"], "class": "REAL_RENDER_DEFECT",
                               "reason": "clip 缺失"})
            continue
        spec = b["spec"]
        actual = (b["statement"].get("motion") or {}).get("actual_behavior", "none")
        n = spec.get("_rendered_n_frames", None)
        frames = _gray_frames(clip, FPS)
        if frames is None or len(frames) < 3:
            violations.append({"beat_id": b["beat_id"], "class": "REAL_RENDER_DEFECT",
                               "reason": "帧提取失败"})
            continue
        nf = n if n is not None else len(frames)
        t_series = _transform_series(spec, nf)
        has_video = spec.get("_material_is_video", False)
        # appearance（alpha 显隐）判定以实际 alpha 变化为准（stage 名只是提示）
        alpha_change_idx = set()
        for l in spec["layers"]:
            a = l.get("alpha_frames") or []
            for i in range(1, len(a)):
                if a[i] != a[i - 1]:
                    alpha_change_idx.add(i)
        has_alpha = bool(alpha_change_idx)
        # 1) transform 检查（spec 轨迹，决定性）
        t_max = max(t_series) if t_series else 0.0
        if actual in ("HOLD", "none"):
            if t_max > 0:
                violations.append({"beat_id": b["beat_id"],
                                   "class": "REAL_RENDER_DEFECT",
                                   "reason": f"HOLD 却发生 transform 位移 max={t_max:.2f}"})
                continue
            deltas = np.array([float(np.abs(frames[i].astype(int) -
                                            frames[i - 1].astype(int)).mean())
                               for i in range(1, len(frames))])
            if not has_video and not has_alpha and float(deltas.max()) > 0.05:
                violations.append({"beat_id": b["beat_id"],
                                   "class": "REAL_RENDER_DEFECT",
                                   "reason": f"HOLD 纯静态帧差 max={float(deltas.max()):.3f}>0.05"})
                continue
            if has_video or has_alpha:
                ok, why = _no_alternation(deltas, alpha_change_idx)
                if not ok:
                    violations.append({"beat_id": b["beat_id"],
                                       "class": "REAL_RENDER_DEFECT", "reason": why})
            rows.append({"beat_id": b["beat_id"], "status": "HOLD_OK",
                         "transform_max": round(t_max, 3),
                         "content_or_alpha": has_video or has_alpha})
        else:
            deltas = np.array([float(np.abs(frames[i].astype(int) -
                                            frames[i - 1].astype(int)).mean())
                               for i in range(1, len(frames))])
            mono_ok = _monotonic_integer(t_series)
            alt_ok, why = _no_alternation(deltas, alpha_change_idx)
            if not mono_ok:
                violations.append({"beat_id": b["beat_id"],
                                   "class": "REAL_RENDER_DEFECT",
                                   "reason": "transform 轨迹非整数/非单调"})
            elif not alt_ok:
                violations.append({"beat_id": b["beat_id"],
                                   "class": "REAL_RENDER_DEFECT", "reason": why})
            rows.append({"beat_id": b["beat_id"], "status": "MOTION_OK" if
                         (mono_ok and alt_ok) else "VIOLATION",
                         "transform_max": round(t_max, 3),
                         "content_or_alpha": has_video or has_alpha})
    return {"rows": rows, "violations": violations,
            "jitter_gate": "PASS" if not violations else "FAIL"}


def _has_video(spec: dict) -> bool:
    return spec.get("_material_is_video", False)


def _no_alternation(deltas: np.ndarray, alpha_idx: set | None = None) -> tuple[bool, str]:
    """检测 0↔N 交替（步进闪烁）与异常尖峰。

    alpha_idx：alpha 渐变发生变化的帧下标集合——其相邻帧的台阶属 appearance
    量化（非 geometric jitter），尖峰检测排除这些位置。
    """
    if len(deltas) < 4:
        return True, ""
    nz = deltas[deltas > 0.05]
    if len(nz) == 0:
        return True, ""
    thr = max(0.15, float(np.median(nz)) * 0.5)
    big = deltas > thr
    for i in range(len(deltas) - 2):
        if big[i] and deltas[i + 1] < thr * 0.5 and big[i + 2]:
            return False, f"0↔N 交替（帧差 {deltas[i]:.2f}/{deltas[i+1]:.2f}/{deltas[i+2]:.2f}）"
    m = float(np.median(nz))
    if m > 0:
        boundary = (alpha_idx or set())
        for i in range(len(deltas)):
            if float(deltas[i]) > 6 * m:
                # 该帧是否与 alpha 渐变边界相邻（appearance 台阶）
                near = any(abs(i - j) <= 1 for j in boundary)
                if not near:
                    return False, (f"异常尖峰（max={float(deltas[i]):.2f} vs "
                                   f"median={m:.2f} @帧{i}）")
    return True, ""


def _monotonic_integer(series: list[float]) -> bool:
    """轨迹单调性/整数性复核（每帧步进为 0 或 ≥1 且方向不反转）。"""
    steps = [series[i] - series[i - 1] for i in range(1, len(series))]
    direction = 0
    for s in steps:
        if abs(s) < 1e-9:
            continue
        if abs(s - round(s)) > 0.01:
            return False
        d = 1 if s > 0 else -1
        if direction == 0:
            direction = d
        elif d != direction:
            return False
    return True


def statement_audit(plan: dict) -> dict:
    rows, violations = [], []
    for b in plan["beats"]:
        st = b["statement"]
        text = _norm(b["beat_text"])
        missing = [k for k in ("narrative_intent", "attention_target", "attention_path",
                               "visual_evidence", "shot_language", "audio_relationship",
                               "director_note") if not (st.get(k) or "").strip()]
        at_ok = _norm(st.get("attention_target") or "") in text if \
            st.get("attention_target") else False
        mn = (st.get("motion") or {}).get("necessity") or ""
        gl = st.get("graphic_layer") or {}
        gl_ok = (not gl.get("text")) or (
            len(gl["text"]) <= schemas.CAPS["GRAPHIC_TEXT_MAX"] and
            _norm(gl["text"]) in text)
        anchor_ok = bool(b["spec"]["anchor_text"]) and \
            _norm(b["spec"]["anchor_text"]) in text
        prob = []
        if missing:
            prob.append(f"缺失字段 {missing}")
        if not at_ok:
            prob.append("attention_target 非原文子串")
        if len(mn.strip()) < schemas.CAPS["MOTION_NECESSITY_MIN"]:
            prob.append("motion.necessity 过短")
        if not gl_ok:
            prob.append("graphic_layer 违规")
        if not anchor_ok:
            prob.append("锚点词缺失/非原文")
        cls = "REAL_RENDER_DEFECT" if (not anchor_ok) else "AUDIT_TRUE_POSITIVE"
        if prob:
            violations.append({"beat_id": b["beat_id"], "class": cls,
                               "reason": "; ".join(prob)})
        rows.append({"beat_id": b["beat_id"], "ok": not prob, "problems": prob})
    return {"rows": rows, "violations": violations,
            "statement_gate": "PASS" if not violations else "FAIL"}


def anti_template_audit(plan: dict) -> dict:
    hits = []
    for b in plan["beats"]:
        for k, v in (b["statement"] or {}).items():
            if isinstance(v, str):
                for bad in schemas.TEMPLATE_NAMES_BLACKLIST:
                    if bad in v:
                        hits.append(f"{b['beat_id']}.{k}: {bad}")
    return {"hits": hits, "gate": "PASS" if not hits else "FAIL"}


def statement_frame_consistency(plan: dict, exec_dir: Path) -> dict:
    """G7：全分辨率 + 调色板双色文本检测 + 素材纹理检测。"""
    rows, violations = [], []
    for b in plan["beats"]:
        spec = b["spec"]
        dur = b["duration"]
        clip = exec_dir / "build" / "beats" / f"{b['beat_id']}.mp4"
        if not clip.exists():
            violations.append({"beat_id": b["beat_id"],
                               "class": "REAL_RENDER_DEFECT", "reason": "clip 缺失"})
            continue
        mid = _rgb_frame(clip, dur * 0.6)
        early = _rgb_frame(clip, max(dur * 0.12, 0.2))
        if mid is None:
            violations.append({"beat_id": b["beat_id"],
                               "class": "REAL_RENDER_DEFECT", "reason": "帧提取失败"})
            continue
        has_anchor = any(l["kind"] == "anchor_text" for l in spec["layers"])
        has_material = any(l["kind"] == "material" for l in spec["layers"])
        stages = (b["statement"].get("temporal_behavior") or {}).get("stages", []) or []
        has_enter = any(s.get("name") == "enter" for s in stages)
        problems = []
        text_frac = _text_pixels(mid)
        if has_anchor and text_frac < 0.0015:
            problems.append(f"锚点词未见调色板文字像素（{text_frac:.5f}）")
        if has_anchor and has_enter and _text_pixels(early) >= text_frac and text_frac > 0:
            problems.append("enter 时序未见文字增长")
        y = 0.299 * mid[..., 0].astype(float) + 0.587 * mid[..., 1].astype(float) + \
            0.114 * mid[..., 2].astype(float)
        luma, std = float(y.mean()), float(y.std())
        if has_material and std < 30:
            problems.append(f"素材纹理疑似缺失（std={std:.1f}, luma={luma:.1f} ≈ 底色）")
        if problems:
            violations.append({"beat_id": b["beat_id"],
                               "class": "REAL_RENDER_DEFECT", "reason": "; ".join(problems)})
        rows.append({"beat_id": b["beat_id"], "ok": not problems, "problems": problems,
                     "mid": {"luma": round(luma, 1), "std": round(std, 1),
                             "text_frac": round(text_frac, 5)},
                     "has_anchor": has_anchor, "has_material": has_material,
                     "has_enter": has_enter, "n_layers": len(spec["layers"]),
                     "anchor_text": spec["anchor_text"],
                     "relation_to_prev": (b["statement"].get("relation_to_previous")
                                          or {}).get("type")})
    flow = (plan.get("narrative_arc") or {}).get("flow", []) or []
    handoff_rows = [{"shot_id": f.get("shot_id"), "focus_hint": f.get("focus_hint"),
                     "relation": f.get("relation_to_prev")} for f in flow]
    return {"rows": rows, "violations": violations,
            "gate": "PASS" if not violations else "FAIL",
            "handoff_rows": handoff_rows}


def make_contact_sheets(videos: dict, out_dir: Path) -> dict:
    sheets = {}
    for tag, video in videos.items():
        p = out_dir / f"sheet_{tag}_20shots.png"
        sel = "+".join(f"eq(n,{int((i * 5 + 2.5) / 20 * 102 * 25)})" for i in range(20))
        r = subprocess.run(
            [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error", "-i", str(video),
             "-vf", f"select='{sel}',scale=384:216,tile=5x4", "-frames:v", "1",
             str(p)], capture_output=True)
        sheets[tag] = str(p) if r.returncode == 0 else None
    return sheets


def run_gates(plan: dict, exec_dir: Path) -> dict:
    ja = jitter_audit(exec_dir / "build" / "beats", plan)
    sa = statement_audit(plan)
    ata = anti_template_audit(plan)
    g7 = statement_frame_consistency(plan, exec_dir)
    qc = json.loads((exec_dir / "qc" / "qc_report.json").read_text(encoding="utf-8"))
    out = {"jitter": ja, "statement": sa, "anti_template": ata, "g7": g7,
           "classification": {
               "REAL_RENDER_DEFECT": (ja["violations"] + g7["violations"]),
               "AUDIT_TRUE_POSITIVE": sa["violations"],
               "AUDIT_FALSE_POSITIVE": [],
           },
           "technical_qc": {k: qc.get(k) for k in ("probe", "filters", "shots_total",
                                                   "subtitle_vo_sync_bad", "subtitle_verbatim_ok",
                                                   "subtitle_overlap", "subtitle_bounds_ok")},
           "gates": {"jitter": ja["jitter_gate"], "statement": sa["statement_gate"],
                     "anti_template": ata["gate"], "g7": g7["gate"],
                     "technical": "PASS" if qc.get("output_sha_ok") else "FAIL"}}
    (ROOT / "output" / "stage33" / "coral" / "v3" / "v3_gate.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
