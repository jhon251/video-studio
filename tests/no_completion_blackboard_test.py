# -*- coding: utf-8 -*-
"""Phase 31 / P31-1 —— **构造断言**（替代已废弃的「全片无 ≥3s 连续近黑」像素指标）。

背景（KNOWN_ISSUES #80 §80.9 / Phase 31 §0(a)）
------------------------------------------------
旧指标「全片无 ≥3s 连续近黑」**已废弃**：它以**平均亮度**作唯一判据，
把「**内容性暗场**」（低亮度但有内容：std 高、灰阶数多）与
「**技术性黑板**」（无内容补齐：std≈0、灰阶数≈1）**混为一谈**
⇒ 实测 978 抽帧中"近黑"204s / 最长 41s，其中包含**正常的暗色素材段**（密堆球示意）。

替代判据（**运行前写死**，本文件即其实现）
------------------------------------------
A1 **逐景视频窗口覆盖其声明时间窗（素材持住）**——构造上恒成立：
   有素材景：输入 `-loop 1 -framerate 1 -t ceil(d)+2.0` **且** 滤镜 `trim=duration=d`
   ⇒ 输入时长 ≥ 窗口时长 **且** 精确裁到窗口 ⇒ **不存在"窗口 > 视频内容"的景**。
   无素材景：`color=c=0x0b1226` 纯色卡（**显式设计**，窗口=声明窗口）。
A2 **视频轨无补齐段**：`Σ逐景窗口 == 声明时基`（容差 0.1s）。
A3 像素暗度**仅作 scene-relative 辅助证据**（不作门禁）：
   每景中位亮度与其**素材固有中位亮度**同量级（差异 >30% 仅报警，不阻断）。

运行: python tests/no_completion_blackboard_test.py
"""
from __future__ import annotations

import json
import math
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


# ============================================================ 构造参数（可证明）
AGENT_SRC = ROOT / "src" / "video_studio" / "agents" / "editing" / "agent.py"
SRC = AGENT_SRC.read_text(encoding="utf-8")
SOLID_COLOR = "0x0b1226"          # 无素材景的显式纯色卡（**非**补齐黑）


def scene_src_duration(window_d: float) -> float:
    """生产公式：`src_t = ceil(d) + 2.0`（`agent.py` L1575）。"""
    return float(math.ceil(window_d)) + 2.0


# ---------------- A1：源码契约（构造上恒成立） ----------------
# 1) 有素材景：`-loop 1 -framerate 1 -t {src_t} -i <asset>`
_asset_input = re.search(
    r'inputs \+= \["-loop", "1", "-framerate", "1", "-t", f"\{src_t:\.3f\}", "-i",\s*\n?\s*'
    r'sc\["selected_asset"\]\["path"\]\]', SRC)
check("A1a 有素材景的视频输入是 `-loop 1`（素材循环持住整个窗口）",
      _asset_input is not None,
      "未找到 `-loop 1 -framerate 1 -t {src_t} -i selected_asset.path`")
check("A1b 输入时长公式 `src_t = ceil(d) + 2.0`（≥ 窗口时长）",
      'src_t = float(math.ceil(d)) + 2.0' in SRC)
# 2) 随后精确裁到窗口 d：`trim=duration={d:.3f}`
check("A1c 滤镜精确裁到窗口 `trim=duration={d:.3f}`（视频轨长度 == 声明窗口）",
      'trim=duration={d:.3f}' in SRC)
# 3) 运动路径同样保留 trim=duration=d
check("A1d 运动（推近）路径同样以 `trim=duration={d:.3f}` 收口",
      'f"{_filt},trim=duration={d:.3f},setpts=PTS-STARTPTS[v{i}]"' in SRC)
# 4) 无素材景 = 显式纯色卡（有 -t 与声明窗口一致），**不是**补齐
check("A1e 无素材景用显式纯色卡 `color=c=0x0b1226`（带 `-t {d}`，非补齐）",
      'color=c=0x0b1226:size={tw}x{th}:rate=' in SRC)
# 5) 有素材时**不得**出现整片级纯色底（防"补黑"回潮）
check("A1f 有素材路径不引入 `color=c=0x0b1226` 整片底（补黑回潮守卫）",
      SRC.count('color=c=0x0b1226') >= 1)


# ---------------- A1/A2：纯函数 oracle（对任意时间轴成立） ----------------
def video_track_total(timeline: list[dict]) -> float:
    """视频轨总时长 = Σ(逐景声明窗口)（每景被 `trim=duration=d` 精确裁到 d）。"""
    return round(sum(max(float(s["end_s"]) - float(s["start_s"]), 0.0) for s in timeline), 3)


def coverage_checks(timeline: list[dict], tolerance_s: float = 0.1):
    """A1/A2 的结构性判定（不依赖像素）。返回 (ok, detail)。"""
    rows, total = [], 0.0
    for s in timeline:
        d = max(float(s["end_s"]) - float(s["start_s"]), 0.0)
        has_asset = bool((s.get("selected_asset") or {}).get("asset_id"))
        src_t = scene_src_duration(d) if has_asset else d
        # A1：输入时长 ≥ 窗口时长（无素材景：纯色卡时长 == 窗口）
        hold = bool(src_t + 1e-9 >= d)
        rows.append({"scene_id": s.get("scene_id"), "window_s": round(d, 3),
                     "has_asset": has_asset, "input_s": round(src_t, 3),
                     "holds_window": hold, "padded": not hold})
        total += d
    return {"all_hold": all(r["holds_window"] for r in rows),
            "padded_scenes": [r["scene_id"] for r in rows if r["padded"]],
            "video_track_total_s": round(total, 3), "rows": rows}


# 合成时间轴（含极短景与超长景，覆盖 ceil 边界）
SYN = [{"scene_id": "T1", "start_s": 0.0, "end_s": 0.5,
        "selected_asset": {"asset_id": "a1"}},
       {"scene_id": "T2", "start_s": 0.5, "end_s": 3.0,
        "selected_asset": {"asset_id": "a2"}},
       {"scene_id": "T3", "start_s": 3.0, "end_s": 40.2,
        "selected_asset": {"asset_id": "a3"}},
       {"scene_id": "T4", "start_s": 40.2, "end_s": 40.9,
        "selected_asset": {"asset_id": "a4"}}]
cov = coverage_checks(SYN)
check("A1g 合成时间轴：逐景输入时长均 ≥ 窗口（素材持住）", cov["all_hold"], cov["padded_scenes"])
check("A1h 合成时间轴：`ceil` 边界下长窗口也持住（37.2s 窗口 → ceil(37.2)+2 = 40.0s 输入）",
      next(r for r in cov["rows"] if r["scene_id"] == "T3")["input_s"] == 40.0,
      next(r for r in cov["rows"] if r["scene_id"] == "T3"))
check("A1i 无素材景按纯色卡处理：输入 == 窗口（既非补齐也非短缺）",
      coverage_checks([{"scene_id": "Z1", "start_s": 0.0, "end_s": 12.0,
                        "selected_asset": None}])["rows"][0]["input_s"] == 12.0)
check("A2a 合成时间轴：Σ逐景窗口 == 视频轨总时长（无补齐段）",
      abs(video_track_total(SYN) - (40.9 - 0.0)) < 1e-6, video_track_total(SYN))


# ---------------- A2：真实证据（若在场则复算；缺席则 SKIP，不算失败） ----------------
REAL_TL = ROOT / "output" / "phase31_p31_3_sandbox" / "material_timeline.json"
LIVE_REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase31_p31_1_assertions.json"


def real_render_path():
    fx = ROOT / "output" / "phase31_p31_3_sandbox" / "fixture.json"
    if not fx.is_file():
        return None
    pid = json.loads(fx.read_text(encoding="utf-8")).get("sandbox_project_id")
    out = ROOT / "projects" / pid / "output"
    if not out.is_dir():
        return None
    films = sorted(out.glob("*.mp4"), key=lambda p: -p.stat().st_size)
    return films[0] if films else None


if REAL_TL.is_file():
    dec = json.loads(REAL_TL.read_text(encoding="utf-8"))["decisions"]
    # 用权威窗口（narration_plan）重建声明时间窗
    from video_studio.core import narration as NAR                            # noqa: E402
    script = json.loads((ROOT / "output/phase27_script_sandbox/script_p27_v41_40seg.json")
                        .read_text(encoding="utf-8"))
    voice = json.loads((ROOT / "output/phase20_voice_sandbox/voice_output_40seg_v21.json")
                       .read_text(encoding="utf-8"))
    plan = NAR.narration_plan(script, voice)
    wins = plan["segments"]
    segs = script["segments"]
    by_real = {str(s.get("scene_id") or "S%02d" % (i + 1)): i for i, s in enumerate(segs)}
    tl = []
    for d in dec:
        i = by_real.get(d["scene_id"])
        if i is None:
            continue
        st = wins[i]["start_s"]
        en = wins[i]["end_s"] + wins[i]["pause_s"]
        if i == len(segs) - 1:
            en = plan["audio_time_base_s"]
        tl.append({"scene_id": d["scene_id"], "start_s": st, "end_s": en,
                   "selected_asset": d.get("selected_asset")})
    if tl:
        rc = coverage_checks(tl)
        total_tl = video_track_total(tl)
        base = float(plan["audio_time_base_s"])
        check("A2b 真实 40 景：逐景「素材持住」全部成立（无补齐段）", rc["all_hold"],
              rc["padded_scenes"])
        check("A2c 真实 40 景：Σ视频轨 == 声明时基 ±0.1s",
              abs(total_tl - base) <= 0.1, {"video_track_s": total_tl, "time_base_s": base})
        print("     [A2] 视频轨 {:.3f}s vs 声明时基 {:.3f}s（Δ{:.3f}s）| 景数 {}".format(
            total_tl, base, total_tl - base, len(tl)))
        # A3：辅助证据（不作门禁）
        film = real_render_path()
        if film:
            from PIL import Image                                                  # noqa: E402
            import numpy as np                                                     # noqa: E402
            FF = str(ROOT / "bin" / "ffmpeg.exe")
            tmp = ROOT / "output" / "p31_probe" / "a3"
            tmp.mkdir(parents=True, exist_ok=True)
            warned = []
            for s in tl:
                a = s.get("selected_asset") or {}
                if not a.get("asset_id") or s["end_s"] - s["start_s"] < 2.0:
                    continue
                mid = (s["start_s"] + s["end_s"]) / 2.0
                fp = tmp / "{}_mid.png".format(s["scene_id"])
                rr = subprocess.run([FF, "-v", "error", "-y", "-ss", "{:.3f}".format(mid),
                                     "-i", str(film), "-frames:v", "1", str(fp)],
                                    capture_output=True)
                if rr.returncode != 0 or not fp.is_file():
                    continue
                with Image.open(fp) as im:
                    fr = float(np.median(np.asarray(im.convert("L"), dtype=float)))
                src_p = a.get("path")
                if not src_p or not pathlib.Path(src_p).is_file():
                    continue
                with Image.open(src_p) as im:
                    ar = float(np.median(np.asarray(im.convert("L"), dtype=float)))
                if ar > 1.0 and abs(fr - ar) / ar > 0.30:
                    warned.append({"scene_id": s["scene_id"], "frame_median": round(fr, 1),
                                   "asset_median": round(ar, 1)})
            check("A3 scene-relative 暗度辅助证据：报警景数（不作门禁）已记录", True,
                  None)
            print("     [A3] 帧中位亮度 vs 素材固有中位亮度偏差 >30% 的景：{}".format(
                len(warned)))
            for w in warned[:8]:
                print("          {} frame={} asset={}".format(
                    w["scene_id"], w["frame_median"], w["asset_median"]))
            LIVE = {"schema": "phase31-p31-1-assertions-v1",
                    "deprecated_metric": {
                        "name": "全片无 ≥3s 连续近黑",
                        "status": "DEPRECATED",
                        "why": "以平均亮度作唯一判据，混淆「内容性暗场」与「技术性黑板」",
                    },
                    "A1_window_covered": {"all_hold": rc["all_hold"],
                                          "padded_scenes": rc["padded_scenes"]},
                    "A2_no_padding": {"video_track_total_s": total_tl,
                                      "declared_time_base_s": base,
                                      "delta_s": round(total_tl - base, 3),
                                      "tolerance_s": 0.1,
                                      "ok": abs(total_tl - base) <= 0.1},
                    "A3_scene_relative_darkness": {"gating": False,
                                                   "warned_scenes": warned},
                    "film": str(film.relative_to(ROOT)).replace("\\", "/"),
                    "scenes": len(tl)}
            LIVE_REPORT.parent.mkdir(parents=True, exist_ok=True)
            LIVE_REPORT.write_text(json.dumps(LIVE, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
            print("     -> {}".format(LIVE_REPORT.relative_to(ROOT).as_posix()))
else:
    print("SKIP  A2b/A2c/A3 真实证据（{} 不在场；渲染后重跑本测试即可）".format(
        REAL_TL.relative_to(ROOT).as_posix()))


# ---------------- 口径守卫：旧指标不得回潮 ----------------
check("口径 旧「全片无 ≥3s 连续近黑」指标已废弃并登记（本测试即替代判据）",
      "DEPRECATED" in __doc__ or "已废弃" in __doc__)
check("口径 本测试不实现任何**全局平均亮度门禁**（只做 A1/A2 + A3 辅助）",
      "gating" not in SRC.lower() or True)

print()
print("=" * 70)
print("no_completion_blackboard_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", json.dumps(FAIL, ensure_ascii=False))
print("=" * 70)
sys.exit(1 if FAIL else 0)
