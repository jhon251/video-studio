# -*- coding: utf-8 -*-
"""Phase 40 / P40-2：**DQ-3e 有效静止门**（合并相邻同素材后的有效保持）。

定义（**运行前写死**）：
  · 逐景窗口按时间轴顺序排列；
  · 把**相邻且使用同一素材**（或无素材纯色卡）的景**合并**为一段「有效静止段」；
  · 段长 = 合并区间的总时长；**DQ-3e 断言：任一有效静止段 ≤ 25.0s**。
  · 与逐景 DQ-3（单景 ≤25s）并存：**DQ-3 是诊断层、DQ-3e 才是交付门**
    —— 因为「相邻同素材」在观感上就是连续同一画面，逐景门会漏掉它（本阶段发现的门盲区）。

为什么需要：F 候选逐景门全绿，但合并后出现 4 处 >25s（45.8/45.5/39.3/26.5s）⇒ 盲区。

运行: python tests/dq3e_effective_hold_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
PASS, FAIL = [], []
MAX_EFFECTIVE_S = 25.0          # **运行前写死**
TB_CANDIDATES = [
    ROOT / "output/phase36_voice/timebase_v65.json",
    ROOT / "output/phase34_voice/timebase_v42.json",
]
SB_CANDIDATES = [
    ROOT / "output/phase36_p36_4_sandbox/material_timeline.json",
    ROOT / "output/phase34_p34_4_sandbox/material_timeline.json",
]


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


def effective_runs(windows, decisions):
    """返回合并后的有效静止段列表（相邻同素材/同纯色卡 ⇒ 合并）。"""
    asset = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id") or "CARD")
             for d in decisions}
    runs, cur = [], None
    for w in windows:
        sid = w["scene_id"]
        a = asset.get(sid, "CARD")
        if cur and cur["asset"] == a:
            cur["scene_ids"].append(sid)
            cur["end_s"] = w["end_s"]
            cur["duration_s"] = round(cur["end_s"] - cur["start_s"], 3)
        else:
            if cur:
                runs.append(cur)
            cur = {"asset": a, "scene_ids": [sid], "start_s": w["start_s"],
                   "end_s": w["end_s"],
                   "duration_s": round(w["end_s"] - w["start_s"], 3)}
    if cur:
        runs.append(cur)
    return runs


def main() -> int:
    tb = next((p for p in TB_CANDIDATES if p.is_file()), None)
    sb = next((p for p in SB_CANDIDATES if p.is_file()), None)
    if tb is None or sb is None:
        print("SKIP  未找到时间轴/时间轴决策文件")
        sys.exit(0)
    windows = json.loads(tb.read_text(encoding="utf-8"))["windows"]
    decisions = json.loads(sb.read_text(encoding="utf-8"))["decisions"]
    runs = effective_runs(windows, decisions)
    over = [r for r in runs if r["duration_s"] > MAX_EFFECTIVE_S]
    print("时间轴: {}".format(tb.name))
    print("景 {} ⇒ 合并为 {} 个有效静止段 | 阈值 {:.1f}s".format(
        len(windows), len(runs), MAX_EFFECTIVE_S))
    print()
    print("合并后 >{:.0f}s 的段（{} 处）:".format(MAX_EFFECTIVE_S, len(over)))
    for r in sorted(over, key=lambda x: -x["duration_s"]):
        print("   {:.1f}s | {} 景 | {} | {}".format(
            r["duration_s"], len(r["scene_ids"]), r["asset"][:20],
            ",".join(r["scene_ids"][:5])))
    print()
    check("E1 **DQ-3e：任一有效静止段 ≤ {:.0f}s**（实测最长 {:.1f}s）".format(
        MAX_EFFECTIVE_S, max(r["duration_s"] for r in runs)),
        not over, over[:6])
    # 诊断层：逐景 DQ-3
    sover = [w for w in windows if w["window_s"] > MAX_EFFECTIVE_S + 0.01]
    check("E2 对照：逐景 DQ-3 单景 ≤ {:.0f}s（实测最长 {:.2f}s）".format(
        MAX_EFFECTIVE_S, max(w["window_s"] for w in windows)), not sover, sover[:4])
    rep = {"schema": "p40-dq3e-v1", "max_effective_s": MAX_EFFECTIVE_S,
           "windows": len(windows), "runs": len(runs),
           "over": [{"duration_s": r["duration_s"], "asset": r["asset"],
                     "scene_ids": r["scene_ids"]} for r in over],
           "max_effective_actual_s": max(r["duration_s"] for r in runs),
           "scenes_over": [w["scene_id"] for w in sover],
           "pass": not over, "source_timebase": tb.name}
    (ROOT / "docs/regression_2x/logs/p40_dq3e.json").write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("=" * 72)
    print("dq3e_effective_hold_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
