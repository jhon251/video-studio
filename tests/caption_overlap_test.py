# -*- coding: utf-8 -*-
"""Phase 51 / P51-1：**重叠不变量门**（新，阈值运行前写死）。

授权书 §1 要求：对**最终烧录的 ASS** 以 **0.1s 步进**扫描，
**同时活跃 cue 数 >1 的时刻 = 0**。
F7.1 的 **41 条重叠**作为 **before 夹具**留档。

判据（**运行前写死**）：
  · **O1** `max_concurrent == 1`（严格互斥）；
  · **O2** 同时活跃 >1 的采样时刻数 `== 0`；
  · **O3** 相对 F7.1 before 夹具**必须改善**（41 → 1）。

运行: python tests/caption_overlap_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "docs" / "regression_2x"))
sys.stdout.reconfigure(encoding="utf-8")
from ass_overlap_scan import parse_ass, scan                                  # noqa: E402

PASS, FAIL = [], []
STEP = 0.1
BEFORE_FIXTURE = {"label": "F7.1", "max_concurrent": 41, "overlap_moments": 1033,
                  "ass": "projects/p_06e490c43f6f/artifacts/_captions_t_b4b8433327d4.ass"}
SB = R / "output" / "phase36_p36_4_sandbox" / "fixture.json"
LOGS = R / "docs" / "regression_2x" / "logs"


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:280]))
    return bool(ok)


def latest_ass():
    """取**当前沙箱**最新烧录的 ASS。

    **踩坑（P53）**：原实现先按 `fixture.sandbox_project_id` 找，失败才 glob 全库。
    但**回归运行中**该测试曾读到**别的工程的 ASS**（表现为同一文件独立复跑 3/3 PASS、
    回归内 1/3 FAIL）—— 因为 glob 会命中任何“更新”的产物。
    ⇒ 现改为**只认 fixture 指定的工程**，并把读数**显式打印**（可审计）；
    仅当该工程无产物时才回退 glob（并标注 fallback）。
    这正是 P53 新规则「验证必须穿透生产入口、禁止平行构造」的落地。
    """
    pid = None
    try:
        pid = json.loads(SB.read_text(encoding="utf-8"))["sandbox_project_id"]
    except Exception:                                                           # noqa: BLE001
        pid = None
    if pid:
        d = R / "projects" / str(pid) / "artifacts"
        cands = sorted(d.glob("_captions_*.ass")) if d.is_dir() else []
        if cands:
            return cands[-1], "fixture:" + str(pid)
    cands = sorted(R.glob("projects/*/artifacts/_captions_*.ass"),
                   key=lambda p: p.stat().st_mtime)
    return ((cands[-1], "fallback:glob") if cands else (None, "none"))


def main() -> int:
    ass, how = latest_ass()
    if not ass:
        print("SKIP  未找到烧录 ASS")
        sys.exit(0)
    cues = parse_ass(ass)
    res = scan(cues, step=STEP)
    print("ASS: {}（来源 {}）".format(ass.relative_to(R).as_posix(), how))
    print("cue 数 {} | **max_concurrent {}** | 重叠时刻 {} / {} 采样".format(
        res["cues"], res["max_concurrent"], res["overlap_moments"], res["samples"]))
    print("最长重叠区间 {:.2f}s".format(res["longest_overlap_s"]))
    print("before 夹具（F7.1）：max_concurrent {} | 重叠时刻 {}".format(
        BEFORE_FIXTURE["max_concurrent"], BEFORE_FIXTURE["overlap_moments"]))
    if res["examples"]:
        print("重叠样例（前 2）:")
        for e in res["examples"][:2]:
            print("   t={} 同时 {} 条: {}".format(e["t"], e["concurrent"],
                                                  " | ".join(e["texts"])[:80]))
    print()
    check("O1 同时活跃 cue 数 == 1（实测 {}）".format(res["max_concurrent"]),
          res["max_concurrent"] == 1, res)
    check("O2 同时活跃 >1 的采样时刻 == 0（实测 {}）".format(res["overlap_moments"]),
          res["overlap_moments"] == 0, res)
    check("O3 相对 F7.1 夹具改善（{} → {}）".format(
        BEFORE_FIXTURE["max_concurrent"], res["max_concurrent"]),
        res["max_concurrent"] < BEFORE_FIXTURE["max_concurrent"], res)
    print()
    print("=" * 76)
    print("caption_overlap_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 76)
    (LOGS / "p51_1_overlap_invariant.json").write_text(
        json.dumps({"schema": "p51-1-overlap-invariant-v1",
                    "method": "对最终烧录 ASS 以 {}s 步进扫描同时活跃 cue 数".format(STEP),
                    "ass": ass.relative_to(R).as_posix(),
                    "step_s": STEP, "thresholds": {"max_concurrent": 1,
                                                   "overlap_moments": 0},
                    "before_fixture": BEFORE_FIXTURE,
                    "after": {k: res[k] for k in
                              ("cues", "max_concurrent", "overlap_moments",
                               "samples", "longest_overlap_s")},
                    "examples": res["examples"],
                    "pass": len(PASS), "fail": len(FAIL)},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
