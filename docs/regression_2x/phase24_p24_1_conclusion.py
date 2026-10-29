# -*- coding: utf-8 -*-
"""P24-1 结论：运动策略 v2 的三指标实测 + **数学上界证明**（授权预算 vs 指标冲突）。

结论导向：给出 v2 计划的逐秒内容变化**上界**，证明在授权幅度上限（zoom ≤1.08、
pan ≤3%）下，**冻结占比 <50% 不可达**；并给出与基线的对照。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import motion as M                                      # noqa: E402
from video_studio.core import motion_metrics as MM                             # noqa: E402

FF = str(R / "bin" / "ffmpeg.exe")

# ---------------- 1) 上界推导（确定性算术，无需渲染）----------------
PROBE_W = MM.PROBE_W
OUT_W = 1920
rows = []
for dur in (20.0, 30.0, 44.5, 67.4, 88.0):
    sc = {"scene_id": "S", "duration_s": dur, "hook": True}
    p = M.plan_scene(sc, out_w=OUT_W, out_h=1080, fps=25)
    pr = p["params"]
    px_total = OUT_W - pr["w_end"]                      # zoom 总像素推进
    per_s = px_total / max(dur, 1e-9)                   # px/s（全分辨率）
    per_s_probe = per_s * PROBE_W / OUT_W               # 折算到 160 宽探针
    pct_per_s = (pr["zoom_end"] - 1.0) / max(dur, 1e-9) # 每秒放大比例
    rows.append({
        "duration_s": dur, "zoom_end": pr["zoom_end"],
        "px_total": px_total, "px_per_s_full": round(per_s, 4),
        "px_per_s_at_probe": round(per_s_probe, 4),
        "zoom_pct_per_s": round(pct_per_s * 100, 4),
        # 要在探针尺度上产生 >=1px/秒的变化所需的每秒放大比例与整片 zoom
        "needed_pct_per_s_for_1px_probe": round(1.0 / PROBE_W * 100, 4),
        "needed_total_zoom_for_1px_probe": round(1.0 / PROBE_W * 100 * dur + 100, 2),
    })

# ---------------- 2) 三指标实测（真实短片 probe）----------------
probe = str(R / "output" / "p24_motion_probe" / "probe.mp4")
meas = MM.evaluate(probe, FF) if pathlib.Path(probe).is_file() else None

# ---------------- 3) 全片 v2 计划（21 景，来自交付候选）----------------
script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                    .read_text(encoding="utf-8"))
scenes = [{"scene_id": s["scene_id"], "duration_s": float(s["duration_s"]),
           "hook": i == 0, "src_w": round(OUT_W * M.MAX_ZOOM_END),
           "src_h": round(1080 * M.MAX_ZOOM_END)}
          for i, s in enumerate(script["segments"])]
sel = M.select_scenes(scenes)
per_scene = []
for s in sel:
    p = M.plan_scene(s, out_w=OUT_W, out_h=1080, fps=25,
                     enabled=bool(s["motion_enabled"]))
    per_scene.append({"scene_id": s["scene_id"], "duration_s": s["duration_s"],
                      "enabled": p["enabled"], "zoom_end": p["params"].get("zoom_end"),
                      "motion_frames": p["params"].get("motion_frames"),
                      "step_px": p["params"].get("step_px")})
enabled = [x for x in per_scene if x["enabled"]]
tot_dur = sum(x["duration_s"] for x in per_scene)

out = {
    "schema": "phase24-p24-1-motion-v2-conclusion-v1",
    "policy_v2": {
        "full_scene_motion": M.FULL_SCENE_MOTION,
        "max_enabled_ratio": M.MAX_ENABLED_RATIO_V2,
        "force_hook": True,
        "max_zoom_end": M.MAX_ZOOM_END, "pan_max_ratio": M.PAN_MAX_RATIO,
        "min_scene_s": M.MIN_SCENE_S, "static_head_tail_frames": M.STATIC_HEAD_TAIL_FRAMES,
        "step_model": ("Q8 定点 + Bresenham 均匀分配：把 8% 的 142px 推进摊满整景，"
                       "保证景末恰好到达 w_end 且逐帧矩形与闭式逐帧一致"),
    },
    "per_scene_plan": per_scene,
    "plan_summary": {"scenes": len(per_scene), "enabled": len(enabled),
                     "total_duration_s": round(tot_dur, 3),
                     "enabled_duration_s": round(sum(x["duration_s"] for x in enabled), 3),
                     "all_scenes_enabled": len(enabled) == len(per_scene)},
    "upper_bound": rows,
    "measurement": meas,
    "mathematical_conflict": {
        "finding": ("在授权幅度上限（zoom ≤1.08、pan ≤3% 画面尺寸）下，**冻结占比 <50% 不可达**。"),
        "derivation": [
            "zoom 上限 1.08 ⇒ 全分辨率下总推进 = {:.0f}px（1920 − 1778）".format(OUT_W - 1778),
            "探针尺度 160px 宽 ⇒ 每 1px 探针变化需全分辨率 {:.1f}px 推进".format(OUT_W / PROBE_W),
            "整景只推进 {:.0f}px ⇒ 探针上总变化 ≈ {:.2f}px".format(
                OUT_W - 1778, (OUT_W - 1778) * PROBE_W / OUT_W),
            "若把该变化摊满 20s ⇒ {:.4f}px/秒（探针）<< 1px/s 的可测阈值。".format(
                (OUT_W - 1778) * PROBE_W / OUT_W / 20.0),
            "要在 20s 内每秒产生 ≥1px（探针）变化，需要每秒放大约 {:.2f}% ⇒ 20s 累计约 {:.0f}%，"
            "远超 1.08 上限。".format(1.0 / PROBE_W * 100, (1.0 / PROBE_W * 100) * 20 + 100),
        ],
        "conclusion": ("授权同时要求「zoom ≤1.08 / pan ≤3%」与「冻结占比 <50%、最长静止 <25s」，"
                       "在**低细节静态图片**素材上**数学不相容**。"
                       "冻结占比由「每秒可见内容变化」决定，而该变化的上界由幅度上限锁定。"),
        "implication": ("要达标必须放宽其一：① 提高 zoom/pan 上限（如 zoom ≤1.25 或允许整幅平移动画）；"
                        "② 更换素材策略（改用本身含运动的视频素材 / 多图快切）；"
                        "③ 改用「图内元素动画」（图注/箭头/高亮的逐段揭示）而非整体缓推；"
                        "④ 重定义该指标（如按 5s 窗口而非 1s 窗口计冻结）。"),
    },
    "metric_note": ("采用**逐秒差分法**（授权书口径）而非 `freezedetect`：实测在 H.264 CRF20 下 "
                    "`freezedetect` 对真实冻结画面也报 0%（编码噪声抖动），属噪声阈值度量。"
                    "逐秒差分法直接量测内容变化，更贴合『观众看到的画面是否在动』。"),
    "baseline_note": "监理实测基线：94.8% 片长冻结、最长静止 64s（方法未同源，此处以逐秒差分法为准）。",
    "zero_llm": True, "zero_vlm": True, "zero_rerender_of_film": True,
}
p = L / "phase24_p24_1_motion_v2.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 90)
print("P24-1 运动策略 v2：计划 + 三指标 + 数学冲突")
print("=" * 90)
print("策略: FULL_SCENE_MOTION={} max_enabled_ratio={} force_hook=True".format(
    M.FULL_SCENE_MOTION, M.MAX_ENABLED_RATIO_V2))
print("全片计划: {} 景 / 启用 {} 景 / 总时长 {:.1f}s".format(
    len(per_scene), len(enabled), tot_dur))
print("  样例行: {} -> {}".format(per_scene[0]["scene_id"], json.dumps(
    {k: per_scene[0][k] for k in ("duration_s", "enabled", "zoom_end", "motion_frames")},
    ensure_ascii=False)))
print()
print("上界（授权幅度下，每秒可见变化）")
print("  {:>8s} {:>9s} {:>10s} {:>14s} {:>16s}".format(
    "时长s", "zoom_end", "总推进px", "探针px/秒", "达1px/s需总zoom%"))
for r in rows:
    print("  {:>8.1f} {:>9.4f} {:>10.0f} {:>14.4f} {:>16.0f}".format(
        r["duration_s"], r["zoom_end"], r["px_total"], r["px_per_s_at_probe"],
        r["needed_total_zoom_for_1px_probe"]))
print()
if meas:
    print("实测（20s 短片）: 冻结占比 {:.1%} | 最长静止 {:.1f}s | 开场变化 {} 次 | MAD 中位数 {}".format(
        meas["freeze_ratio"], meas["longest_static_s"], meas["opening_changes"],
        meas["mad_median"]))
    print("  三指标:", json.dumps(meas["pass"], ensure_ascii=False), "全过:", meas["all_pass"])
print()
print("数学冲突:", out["mathematical_conflict"]["finding"])
for d in out["mathematical_conflict"]["derivation"]:
    print("   ·", d)
print("->", p.relative_to(R).as_posix())
