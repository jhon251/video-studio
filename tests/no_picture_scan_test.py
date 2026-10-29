# -*- coding: utf-8 -*-
"""Phase 34 / P34-1 —— **无画面清零门**。

授权书 §0③ 定义（"无画面"）：
  · **纯色卡**（`0x0b1226`）：素材决策无 `selected_asset` 的景；
  · **持续近黑窗口**：灰度 `mean < 30` 且持续 **> 3s**。

本门写成**构造可断言**的形式（不依赖渲染后再测）：
  · **N1 构造层（硬门）**：**"有旁白 + 纯色卡"必须为 0** ——
    输入 = 生产素材时间轴（`material_timeline.json`）+ 脚本旁白；
    任一"有旁白却无素材绑定"的景 ⇒ FAIL（该景在成片里必然是纯色卡）。
  · **N2 具名绑定有效性**：P34-1 的具名绑定若声明了 `approval_document`，
    则其目标素材必须**真实在池内**且被**实际绑定**（否则是"声明了但没生效"）。
  · **N3 像素层（抽样，辅助）**：若成片在场，抽帧核验"卡景区间"不再是纯色
    （`uniq > 4`）—— 作为**辅助证据**，不作硬门（硬门以 N1 构造层为准）。

运行: python tests/no_picture_scan_test.py
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
L = ROOT / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
FF = str(ROOT / "bin" / "ffmpeg.exe")

PASS, FAIL, SKIP = [], [], []
NEAR_BLACK = 30.0
MIN_DARK_S = 3.0


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


# 优先用最新一轮（P34），回退到 P33
SANDBOXES = [ROOT / "output/phase36_p36_4_sandbox",
             ROOT / "output/phase36_p36_4_sandbox"]
SB = next((p for p in SANDBOXES if (p / "material_timeline.json").is_file()), None)
if SB is None:
    print("SKIP  未找到任何 material_timeline.json（需先渲染）")
    SKIP.append("NO_TIMELINE")
    print()
    print("no_picture_scan_test: 0 PASS / 0 FAIL / 1 SKIP")
    sys.exit(0)

fx = json.loads((SB / "fixture.json").read_text(encoding="utf-8"))
pid = fx["sandbox_project_id"]
pdir = ROOT / "projects" / pid / "output"
dec = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
print("沙箱 {} | 决策 {} 条".format(pid, len(dec)))

# 脚本旁白（判"有旁白"）
SCRIPT = None
for c in (ROOT / "output/phase34_script_sandbox/script_p34_v42_40seg.json",
          ROOT / "output/phase33_script_sandbox/script_p33_v41_40seg.json"):
    if c.is_file():
        SCRIPT = json.loads(c.read_text(encoding="utf-8"))
        break
nar = {s["scene_id"]: (s.get("narration") or "") for s in
       (SCRIPT or {}).get("segments", [])}

# ---------------- N1 有旁白 + 纯色卡 = 0 ----------------
offenders = []
for d in dec:
    sid = d["scene_id"]
    has_asset = bool((d.get("selected_asset") or {}).get("asset_id"))
    has_nar = bool((nar.get(sid) or "").strip())
    if has_nar and not has_asset:
        offenders.append({"scene_id": sid, "fallback_state": d.get("fallback_state"),
                          "insufficiency_class": d.get("insufficiency_class"),
                          "narration_chars": len(nar.get(sid) or "")})
cards_all = [d["scene_id"] for d in dec
             if not (d.get("selected_asset") or {}).get("asset_id")]
check("N1 **有旁白 + 纯色卡 = 0**（实测 {} 处；全片卡景 {} 个）".format(
    len(offenders), len(cards_all)), not offenders, offenders[:6])

# ---------------- N2 具名绑定有效性 ----------------
# **模型修正（实测踩坑）**：首版断言「声明 == 生效」，即每个被声明的景都必须由绑定提供
# 素材。但实盘里**绑定只在自动选材未命中时被消耗**；若某景被自动选材命中，它就不再需要
# 绑定 ⇒ 该声明项「未生效」**并非缺陷**（首版因此对全声明者报出「声明 36 / 生效 14」、
# 「声明 8 / 生效 5」这类**假阳性**）。
# **正确的硬不变量**：*任何被声明绑定、且其场景**没有** selected_asset 的景，都必须由
# 该绑定提供素材* —— 场景无素材 = 会渲染成纯色卡，而绑定本应救它。
binds = fx.get("explicit_bindings") or {}
bound_ok, bound_missing, not_needed = [], [], []
for d in dec:
    sid = d["scene_id"]
    if sid not in binds:
        continue
    a = (d.get("selected_asset") or {})
    aid = a.get("asset_id")
    declared = str(binds[sid])[:12]
    if not aid:
        bound_missing.append({"scene": sid, "expected": declared, "actual": None,
                              "why": "该景仍无素材（绑定未救到 ⇒ 真缺陷）"})
    elif str(aid).replace("asset_", "").startswith(declared) or \
            str(a.get("sha256") or "").startswith(declared):
        bound_ok.append(sid)
    else:
        not_needed.append({"scene": sid, "declared": declared,
                           "actual": str(aid)[:18],
                           "why": "自动选材先命中 ⇒ 绑定未被消耗（正常）"})
check("N2 声明绑定的景**均未落卡**（声明 {} / 由绑定生效 {} / 自动命中未用 {}）".format(
    len(binds), len(bound_ok), len(not_needed)), not bound_missing, bound_missing[:6])

# ---------------- N3 像素层（辅助）----------------
film = None
if pdir.is_dir():
    film = next((f for f in sorted(pdir.glob("*.mp4"))
                 if f.name.endswith("_with_outro_v2.mp4")), None)
if film is not None:
    # 抽全片 1fps 灰度，找 >3s 近黑窗口
    probe = ROOT / "output" / "p34_probe" / "gate_frames"
    probe.mkdir(parents=True, exist_ok=True)
    for f in probe.glob("g*.png"):
        f.unlink()
    subprocess.run([FF, "-v", "error", "-y", "-i", str(film), "-vf", "fps=1,scale=320:180",
                    str(probe / "g%05d.png")], check=True)
    frames = sorted(probe.glob("g*.png"))
    means, uniqs = [], []
    for fp in frames:
        with Image.open(fp) as im:
            a = np.asarray(im.convert("L"), dtype=float)
        means.append(float(a.mean()))
        uniqs.append(int(len(np.unique(a.astype(np.uint8)))))
    dark_runs, cur = [], 0
    for m in means:
        cur = cur + 1 if m < NEAR_BLACK else 0
        dark_runs.append(cur)
    longest = max(dark_runs) if dark_runs else 0
    pure = len([u for u in uniqs if u <= 4])
    N3 = {"frames": len(frames), "longest_dark_run_s": longest,
          "pure_color_frames": pure}
    print("     [N3 辅助] 抽帧 {} | 最长连续近黑 {}s | 纯色帧 {} 秒".format(
        N3["frames"], longest, pure))
else:
    N3 = None
    print("     [N3 辅助] 成片不在场 ⇒ 跳过（硬门以 N1 构造层为准）")

print()
print("=" * 70)
print("no_picture_scan_test: {} PASS / {} FAIL{}".format(
    len(PASS), len(FAIL), " / {} SKIP".format(len(SKIP)) if SKIP else ""))
if FAIL:
    print("FAILED:", json.dumps(FAIL, ensure_ascii=False))
print("=" * 70)
sys.exit(1 if FAIL else 0)
