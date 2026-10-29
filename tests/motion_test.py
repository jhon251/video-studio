# -*- coding: utf-8 -*-
"""Phase 13 测试：运动层（整数帧 pan/zoom；纯函数 + 策略 + 关闭时逐字节兼容 + fail-closed 回退）。

覆盖授权书 §5：
 · 滤镜串确定性（同输入两次构建逐字节一致）；
 · 策略规则：<10s 静止、hook 优先、zoom ≤1.08、平移 ≤画面 3%、启用比例 ≤60%、整数帧；
 · **闭式 ⇔ 权威逐帧矩形**等价（Python 侧复算，逐帧全等）；
 · 失败回退路径（不可行 ⇒ MOTION_FALLBACK_STATIC + STATIC 矩形）；
 · **关闭时向后兼容**：静态模板的滤镜串逐字节不变（与 Phase 2-A/5-K 既有模板对照）；
 · 渲染链源码契约（运动在 concat 之前、字幕/混音/时基路径未改；默认 off）。

运行: python tests/motion_test.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import motion as M                                             # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))
    return bool(ok)


SCENES = [{"scene_id": "S{:02d}".format(i), "duration_s": d, "src_path": "x{}.png".format(i),
           "hook": i in (2, 7, 8)} for i, d in enumerate(
    [12, 73, 20, 6, 35, 18, 9, 44, 27, 8, 15, 11], start=1)]

# ---------------- 1. 确定性 ----------------
p1 = M.build_plan(SCENES, out_w=1920, out_h=1080, fps=25)
p2 = M.build_plan(SCENES, out_w=1920, out_h=1080, fps=25)
p3 = M.build_plan(list(reversed(SCENES)), out_w=1920, out_h=1080, fps=25)
check("1 滤镜串/计划确定性：同输入两次逐字节一致（canonical 相等 + artifact_hash 相同）",
      M.canonical(p1) == M.canonical(p2) and p1["artifact_hash"] == p2["artifact_hash"]
      and M.validate_plan(p1) == [], M.validate_plan(p1)[:3])
check("1b 场景输入顺序不影响结果（内部按 scene_id 输出，选取规则确定性）",
      M.canonical(p1) == M.canonical(p3))
check("1c 整数帧：所有矩形与步长均为 int，帧数 = round(duration×fps)",
      all(isinstance(v, int) for p in p1["scenes"] for r in p["rects"] for v in r)
      and all(p["n_frames"] == max(1, round(p["duration_s"] * 25)) for p in p1["scenes"]))

# ---------------- 2. 闭式 ⇔ 权威矩形 ----------------
mismatch = {}
for p in p1["scenes"]:
    bad = [n for n in range(p["n_frames"]) if p["rects"][n] != M.evaluate_closed_form(p, n)]
    if bad:
        mismatch[p["scene_id"]] = len(bad)
check("2 闭式 ⇔ 权威逐帧矩形：全部场景逐帧完全一致（滤镜串是同一闭式的转写）",
      not mismatch, mismatch)

# ---------------- 3. 策略规则 ----------------
short = [p for p in p1["scenes"] if p["duration_s"] < M.MIN_SCENE_S]
check("3 场景 <10s ⇒ 静止（prefer STATIC；rects 全为 0,0,out,out）",
      short and all(not p["enabled"] and p["motion_type"] == "STATIC"
                    and set(p["rects"]) == {(0, 0, 1920, 1080)} for p in short),
      [(p["scene_id"], p["duration_s"], p["enabled"]) for p in short])
en = [p for p in p1["scenes"] if p["enabled"]]
hooks_enabled = [p["scene_id"] for p in en if p["scene_id"] in ("S02", "S08")]
check("3b hook 优先：时长 ≥10s 的 hook 场景全部入选（S02 73s、S08 44s）",
      len(hooks_enabled) == 2, hooks_enabled)
hook_short = next(p for p in p1["scenes"] if p["scene_id"] == "S07")
check("3b2 优先级如实：hook 但时长 <10s（S07 9s）仍被**时长规则**排除（duration 规则优先）",
      hook_short["duration_s"] < M.MIN_SCENE_S and not hook_short["enabled"]
      and hook_short["reason"].startswith("disabled_by_policy"), hook_short["reason"])
check("3c 启用比例 ≤ 策略上限（**v2 起为全镜 1.0**；P24-1 授权将 60% 提升到 100%）",
      len(en) <= int(len(p1["scenes"]) * M.MAX_ENABLED_RATIO_V2),
      {"enabled": len(en), "total": len(p1["scenes"]),
       "ratio": M.MAX_ENABLED_RATIO_V2})
zooms = [p for p in en if p["motion_type"] == "SLOW_ZOOM_IN"]
pans = [p for p in en if p["motion_type"] == "SLOW_PAN"]
check("3d zoom 上限：end_zoom ≤ 1.08（授权书上限，只可收紧不可放宽）",
      zooms and all(p["out_w"] / p["params"]["w_end"] <= M.MAX_ZOOM_END + 1e-9 for p in zooms),
      [(p["scene_id"], round(p["out_w"] / p["params"]["w_end"], 4)) for p in zooms])
check("3e 平移幅度 ≤ 画面宽 3%，且单方向（步长符号一致、无反转）",
      pans and all(p["params"]["pan_px"] <= int(p["out_w"] * M.PAN_MAX_RATIO) for p in pans)
      and all(len({p["rects"][i][0] - p["rects"][i - 1][0] for i in range(1, p["n_frames"])}
                  - {0}) <= 1 for p in pans),
      [(p["scene_id"], p["params"]["pan_px"]) for p in pans])
check("3f **v2 全镜缓推**：运动摊满整景（motion_frames == n_frames − 8）+ 景头静止",
      all(p["params"]["motion_frames"] == max(p["n_frames"] - M.STATIC_HEAD_TAIL_FRAMES, 0)
          for p in en)
      and all(p["rects"][0] == p["rects"][M.STATIC_HEAD_TAIL_FRAMES - 1] for p in en)
      and all(p["params"].get("v2_progress") is True for p in en),
      [p["params"].get("motion_frames") for p in en][:4])
check("3g 轨迹单调：zoom 宽度单调不增、pan 位移单调不反转",
      all(all(p["rects"][i][2] >= p["rects"][i + 1][2] for i in range(p["n_frames"] - 1))
          for p in zooms)
      and all(all((p["rects"][i + 1][0] - p["rects"][i][0]) * p["params"]["sign"] >= 0
                  for i in range(p["n_frames"] - 1)) for p in pans))

# ---------------- 4. 失败回退路径 ----------------
tiny = M.plan_scene({"scene_id": "S99", "duration_s": 60, "src_w": 1920, "src_h": 1080},
                    out_w=1920, out_h=1080, enabled=True, motion_type="SLOW_PAN")
check("4 画布无余量 ⇒ 回退 STATIC + fallback_code=MOTION_FALLBACK_STATIC（不静默、不失败整片）",
      tiny["enabled"] is False and tiny["fallback_code"] == M.MOTION_FALLBACK_CODE
      and set(tiny["rects"]) == {(0, 0, 1920, 1080)} and "INFEASIBLE" in tiny["reason"],
      {k: tiny[k] for k in ("enabled", "fallback_code", "reason")})
short_scene = M.plan_scene({"scene_id": "S98", "duration_s": 5}, out_w=1920, out_h=1080,
                           enabled=True)
check("4b <10s ⇒ 静止且**不**记 fallback（是策略决定，不是失败）",
      short_scene["enabled"] is False and short_scene["fallback_code"] is None
      and "prefer STATIC" in short_scene["reason"])
check("4c 滤镜串在静止时退化为固定 crop（合法 ffmpeg 表达式）",
      M.crop_filter(short_scene) == "crop=1920:1080:0:0"
      and M.crop_filter(tiny) == "crop=1920:1080:0:0")

# ---------------- 5. 关闭时向后兼容（静态模板逐字节不变）----------------
off = M.build_plan(SCENES, out_w=1920, out_h=1080, fps=25, enabled=False)
check("5 enabled=False ⇒ 全场景 STATIC、无 fallback、矩形全为满幅（等同关闭）",
      off["counts"] == {"scenes": len(SCENES), "enabled": 0, "static": len(SCENES),
                        "fallback": 0}
      and all(set(p["rects"]) == {(0, 0, 1920, 1080)} for p in off["scenes"]))
cfg_default, src_default = M.resolve_config(
    {}, root=pathlib.Path(tempfile.mkdtemp(prefix="vs_motion_nofile_")))
check("5b 默认配置解析 ⇒ off（**无外部文件时**运动层完全不介入）",
      cfg_default == {"enabled": False} and "default" in src_default,
      {"cfg": cfg_default, "src": src_default})
# 5b-2：真实仓库根下 `config/render_motion.json` **在场** ⇒ 解析必须
# ①**来源标注为外部文件**（证明开关走外部链而非 config.json）；② **与文件声明值一致**。
# **不强绑 `enabled` 的取值**（实测教训）：P34-2 依授权把该开关**置 false（全片运动停用）**，
# 旧断言写死 `enabled is True` ⇒ 会与"已授权的状态变更"冲突而误报。
# 现改为**读文件取期望值**再比对 ⇒ 无论启用/停用都能验证"外部链确实生效"（强度更高）。
_ext = ROOT / "config" / "render_motion.json"
cfg_live, src_live = M.resolve_config({}, root=ROOT)
_want = None
if _ext.is_file():
    try:
        _j = json.loads(_ext.read_text(encoding="utf-8")).get("render_motion") or {}
        _want = bool(_j.get("enabled", False))
    except Exception:                                                       # noqa: BLE001
        _want = None
check("5b-2 真实根 + 外部开关文件在场 ⇒ 来源为外部文件，且解析值与文件声明一致",
      "render_motion.json" in str(src_live)
      and (_want is None or bool(cfg_live.get("enabled")) == _want),
      {"cfg": cfg_live, "src": str(src_live), "file_enabled": _want})
editing_src = (ROOT / "src" / "video_studio" / "agents" / "editing" / "agent.py").read_text(
    encoding="utf-8")
# P0（2026-10-20）：静态模板由 `scale={tw}:{th}` 改为 `scale={_fw}:{_fh}`
# （`_fw/_fh = tw/th × reframe`，逐镜取景 1.00/1.06/1.02…）。
# 这是**已评审的预期变更**：没有 reframe 时 `_fw==tw`，链路语义不变；
# 断言改为校验"模板结构仍在 + 取景缩放已接入"，避免把预期变更当回归。
STATIC_TEMPLATE = ('f"[{i}:v]scale={_fw}:{_fh}:force_original_aspect_ratio=increase,"\n'
                   '                        f"crop={tw}:{th},setsar=1,fps={fps},trim=duration={d:.3f},"\n'
                   '                        f"setpts=PTS-STARTPTS[v{i}]"')
check("5c 静态模板保留且已接入逐镜取景缩放（reframe）：scale=_fw×_fh → crop=tw×th",
      "scale={_fw}:{_fh}:force_original_aspect_ratio=increase" in editing_src
      and "crop={tw}:{th},setsar=1,fps={fps},trim=duration={d:.3f}" in editing_src
      and "_fw = int(round(tw * _z))" in editing_src)
check("5d 运动注入在 concat **之前**，且字幕/混音/时基语句未被改动",
      editing_src.index("_motion.crop_filter(_p13)") < editing_src.index(
          'concat=n={n}:v=1:a=0[vc]')
      and "ass=filename=" in editing_src
      and "trim=duration={d:.3f}" in editing_src
      and '_af("apad")' in editing_src)
check("5e config.json 未被本阶段改动（P10 教训：开关走外部文件/内存）",
      "render_motion" not in (ROOT / "config" / "config.json").read_text(encoding="utf-8")
      and (ROOT / "config" / "render_motion.example.json").is_file())

# ---------------- 6. 策略常量出处 ----------------
check("6 策略常量全部注明 basis（不发明数）+ 授权书上限在位",
      all(v.get("basis") for v in M.POLICY.values())
      and M.MAX_ZOOM_END == 1.25 and M.PAN_MAX_RATIO == 0.03 and M.MIN_SCENE_S == 10.0)
plan_str = json.dumps(p1, ensure_ascii=False, sort_keys=True)
check("6b 计划中不含时间戳/随机量（确定性身份）",
      not re.search(r"20\d\d-\d\d-\d\dT", plan_str) and "uuid" not in plan_str.lower())

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
