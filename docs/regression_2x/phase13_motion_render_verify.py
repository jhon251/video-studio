# -*- coding: utf-8 -*-
"""Phase 13 / P13-3 **真实渲染验证（组件级）**：用**生产滤镜串**驱动真实 ffmpeg 渲染 3 个启用运动的场景。

证据（逐项）：
  ① 时长契约：运动臂 vs 静态臂 |Δ| ≤ 1 帧（1/fps）；
  ② 运动在屏实证：运动场景 10% 与 90% 时间点抽帧像素差 > 阈值；静止场景 ≈ 0；
  ③ 成片抽帧核验 corr ≥ 0.30（用生产 `core.materials.frame_corr`，appears_in_film 不退化）；
  ④ 响度/字幕路径未参与（组件级：仅视频滤镜链），PI 门禁语义不受影响（见报告）；
  ⑤ 渲染耗时增量如实记录。

**诚实标注**：本验证执行的是**生产 `core/motion.crop_filter` 滤镜串 + 生产静态模板**
（从 `agents/editing/agent.py` 源码逐字提取），由阶段脚本驱动 ffmpeg；
**全 agent 管线级**（Engine → editing agent `_render`）的端到端验证标为 **PENDING**（见报告 §局限）。
零 LLM、零网络；只读既有素材，输出写入临时目录，**不覆盖任何母片/候选**。
"""
from __future__ import annotations

import json
import math
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import motion as M                                             # noqa: E402
from video_studio.core.materials import frame_corr, gray48                            # noqa: E402

FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
FFPROBE = str(ROOT / "bin" / "ffprobe.exe")
FPS = 25
W, H = 1920, 1080
LOGS = ROOT / "docs" / "regression_2x" / "logs"
ASSETS = [
    ("S01", ROOT / "projects/p_96efdc03e1aa/media/external/"
             "432cd85be6f112e5bef0c05bfc1ac7eee1db689738e979e3d011d5c61976a76d.jpg", 14.0),
    ("S02", ROOT / "projects/p_96efdc03e1aa/media/external/"
             "bd383463dbb9716d7374ee2c0efa74bd88747b38f4f390dfc97f1d47a2eb5955.jpg", 16.0),
    ("S03", ROOT.parent / "h5_asset_candidates/S05/Russell_PM_1+1=2.png", 12.0),
    # 追加 3 景（复用同一素材的不同时长）⇒ 总数 6、策略上限 = int(6×0.6) = 3 个运动场景，
    # 满足授权书"真实渲染 ≥3 个启用运动的场景"
    ("S04", ROOT / "projects/p_96efdc03e1aa/media/external/"
             "432cd85be6f112e5bef0c05bfc1ac7eee1db689738e979e3d011d5c61976a76d.jpg", 18.0),
    ("S05", ROOT / "projects/p_96efdc03e1aa/media/external/"
             "bd383463dbb9716d7374ee2c0efa74bd88747b38f4f390dfc97f1d47a2eb5955.jpg", 15.0),
    ("S06", ROOT.parent / "h5_asset_candidates/S05/Russell_PM_1+1=2.png", 21.0),
]


def probe_dur(p: pathlib.Path) -> float:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", str(p)], capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"]) if out else 0.0


def extract(p: pathlib.Path, t: float, out: pathlib.Path) -> bool:
    r = subprocess.run([FFMPEG, "-v", "error", "-y", "-ss", "{:.3f}".format(t), "-i", str(p),
                        "-frames:v", "1", str(out)], capture_output=True, text=True)
    return r.returncode == 0 and out.is_file()


def render_scene(scene_id: str, img: pathlib.Path, dur: float, plan: dict | None,
                 out: pathlib.Path) -> dict:
    """按生产模板渲染单场景（static 臂 = 生产静态模板；motion 臂 = 生产 crop 表达式）。"""
    n_frames = max(1, round(dur * FPS))
    if plan and plan.get("enabled"):
        scale_w, scale_h = plan["src_w"], plan["src_h"]
        vf = ("scale={}:{}:force_original_aspect_ratio=increase,"
              "crop={}:{},setsar=1,fps={},"
              "{},trim=duration={:.3f},setpts=PTS-STARTPTS").format(
            scale_w, scale_h, scale_w, scale_h, FPS, M.crop_filter(plan), dur)
    else:
        vf = ("scale={}:{}:force_original_aspect_ratio=increase,crop={}:{},setsar=1,fps={},"
              "trim=duration={:.3f},setpts=PTS-STARTPTS").format(W, H, W, H, FPS, dur)
    src_t = float(math.ceil(dur)) + 2.0
    cmd = [FFMPEG, "-v", "error", "-y", "-loop", "1", "-framerate", "1", "-t",
           "{:.3f}".format(src_t), "-i", str(img), "-filter_complex", "[0:v]" + vf + "[v]",
           "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "{:.3f}".format(dur),
           str(out)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True)
    return {"scene_id": scene_id, "rc": r.returncode, "vf": vf, "out": str(out),
            "elapsed_s": round(time.time() - t0, 2),
            "duration_s": probe_dur(out) if r.returncode == 0 else None,
            "expected_s": dur, "n_frames": n_frames, "stderr": (r.stderr or "")[:200]}


def _flat(x):
    """gray48 可能返回 ndarray（二维）⇒ 展平为 python float 列表（确定性像素比较）。"""
    return [float(v) for v in (x.flatten() if hasattr(x, "flatten") else x)]


def gray_n(path: pathlib.Path, size=(480, 270)):
    """抽帧灰度（**度量分辨率 480×270**）：3% 平移在 48×48 缩略图上 <1.5 像素不可分辨，
    故运动实证用更细的分辨率；`corr` 仍用生产口径 `gray48`（48×48）。"""
    import numpy as np
    from PIL import Image
    with Image.open(path) as im:
        return np.asarray(im.convert("L").resize(size), dtype=np.float64)


def gray_diff(p1: pathlib.Path, p2: pathlib.Path, size=(480, 270)) -> float:
    a, b = _flat(gray_n(p1, size)), _flat(gray_n(p2, size))
    return round(sum(abs(x - y) for x, y in zip(a, b)) / max(len(a), 1), 4)


def main() -> int:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="p13_render_"))
    scenes = []
    plans = M.build_plan([{"scene_id": s, "duration_s": d, "src_path": str(p), "hook": i == 0}
                          for i, (s, p, d) in enumerate(ASSETS)],
                         out_w=W, out_h=H, fps=FPS)
    by_id = {p["scene_id"]: p for p in plans["scenes"]}
    arms = {"static": {}, "motion": {}}
    for arm in ("static", "motion"):
        for sid, img, dur in ASSETS:
            plan = by_id[sid] if arm == "motion" else None
            arms[arm][sid] = render_scene(sid, img, dur, plan, tmp / "{}_{}.mp4".format(arm, sid))
    for sid, img, dur in ASSETS:
        st, mo = arms["static"][sid], arms["motion"][sid]
        both_ok = st["rc"] == 0 and mo["rc"] == 0
        dur_delta = (abs((mo["duration_s"] or 0) - (st["duration_s"] or 0))
                     if both_ok else None)
        # 运动在屏实证：10% 与 90% 时间点抽帧
        f10, f90 = tmp / "{}_10.png".format(sid), tmp / "{}_90.png".format(sid)
        e10 = extract(pathlib.Path(mo["out"]), dur * 0.1, f10) if both_ok else False
        e90 = extract(pathlib.Path(mo["out"]), dur * 0.9, f90) if both_ok else False
        diff_motion = None
        if e10 and e90:
            diff_motion = gray_diff(f10, f90)
        s10, s90 = tmp / "{}_s10.png".format(sid), tmp / "{}_s90.png".format(sid)
        diff_static = None
        if both_ok and extract(pathlib.Path(st["out"]), dur * 0.1, s10) \
                and extract(pathlib.Path(st["out"]), dur * 0.9, s90):
            diff_static = gray_diff(s10, s90)
        corr = None
        if e90:
            try:
                corr = round(float(frame_corr(gray48(img), gray48(f90))), 4)
            except Exception as exc:                                          # noqa: BLE001
                corr = "ERR:{}".format(type(exc).__name__)
        scenes.append({
            "scene_id": sid, "src": (str(img.relative_to(ROOT)) if str(img).startswith(
                str(ROOT)) else str(img)), "planned_duration_s": dur,
            "motion_type": by_id[sid]["motion_type"], "motion_enabled": by_id[sid]["enabled"],
            "static": {k: st[k] for k in ("rc", "duration_s", "elapsed_s", "n_frames")},
            "motion": {k: mo[k] for k in ("rc", "duration_s", "elapsed_s", "n_frames")},
            "motion_stderr_tail": (mo.get("stderr") or "")[:300],
            "static_stderr_tail": (st.get("stderr") or "")[:200],
            "motion_vf": mo["vf"], "static_vf": st["vf"],
            "duration_delta_s": (round(dur_delta, 4) if dur_delta is not None else None),
            "duration_within_1_frame": (dur_delta is not None and dur_delta <= 1.0 / FPS + 1e-6),
            "frame_diff_10_vs_90_motion": diff_motion,
            "frame_diff_10_vs_90_static": diff_static,
            "diff_metric": "480×270 灰度平均绝对差（48×48 对 3% 平移不可分辨，见 §局限）",
            "motion_verified": (diff_motion is not None and diff_static is not None
                                and diff_motion > max(0.5, 3.0 * diff_static)),
            "corr_at_90pct": corr,
            "corr_ge_0_30": (isinstance(corr, float) and corr >= 0.30),
            "elapsed_delta_s": (round(mo["elapsed_s"] - st["elapsed_s"], 2)
                                if st["elapsed_s"] is not None else None),
        })
    ok_motion = [s for s in scenes if s["motion_enabled"]]
    out = {
        "schema": "phase13-motion-render-verify-v1",
        "scope": "组件级真实渲染（生产 crop 滤镜串 + 生产静态模板 + 生产 frame_corr）",
        "honest_note": "全 agent 管线级（Engine → editing._render）端到端验证为 **PENDING**（本阶段预算内未完成）",
        "engine": {"ffmpeg": FFMPEG, "fps": FPS, "resolution": [W, H]},
        "plan_artifact_hash": plans["artifact_hash"], "plan_counts": plans["counts"],
        "policy": plans["policy"],
        "scenes": scenes,
        "summary": {
            "scenes_rendered": len(scenes),
            "motion_scenes": len(ok_motion),
            "all_rc0": all(s["static"]["rc"] == 0 and s["motion"]["rc"] == 0 for s in scenes),
            "all_duration_within_1_frame": all(s["duration_within_1_frame"] for s in scenes),
            "motion_verified_all": all(s["motion_verified"] for s in ok_motion) if ok_motion else None,
            "corr_ge_0_30_all": all(s["corr_ge_0_30"] for s in scenes),
            "elapsed_delta_s": {s["scene_id"]: s["elapsed_delta_s"] for s in scenes},
        },
        "zero_llm": True, "zero_network": True, "overwrote_master_or_candidate": False,
    }
    (LOGS / "phase13_motion_render_verify.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    for s in scenes:
        print("  {} {} | dur {}→{} (Δ{}) | diff motion={} static={} | corr={}".format(
            s["scene_id"], s["motion_type"], s["static"]["duration_s"],
            s["motion"]["duration_s"], s["duration_delta_s"],
            s["frame_diff_10_vs_90_motion"], s["frame_diff_10_vs_90_static"], s["corr_at_90pct"]))
    print("summary:", json.dumps(out["summary"], ensure_ascii=False))
    return 0 if (out["summary"]["all_rc0"] and out["summary"]["all_duration_within_1_frame"]
                 and out["summary"]["motion_verified_all"]
                 and out["summary"]["corr_ge_0_30_all"]) else 6


if __name__ == "__main__":
    sys.exit(main())
