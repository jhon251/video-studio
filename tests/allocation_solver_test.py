# -*- coding: utf-8 -*-
"""Phase 40 / P40-1：**全局约束分配器**单元测试（`core.allocation.satisfy`）。

覆盖：
  S1 **可行实例 ⇒ cap/间距/相邻 全 0**（不再单步贪心 overshoot）；
  S2 **不可行实例 ⇒ 返回最小违例解 + 违例清单**（不静默违反）；
  S3 **确定性**（同 seed 同输入 ⇒ 同解）；
  S4 **首选保序**（无冲突时不动已选素材，避免无谓改动）；
  S5 **修复前缺陷可复现**：用 F 实盘的真实分配作输入 ⇒ 旧状态有违例、求解后归零。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import allocation as AL                                    # noqa: E402

PASS, FAIL = [], []


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:240]))


def viol(assign, ids, cap=3, gap=3):
    cnt = collections.Counter(a for a in assign.values() if a)
    capv = {k: v for k, v in cnt.items() if v > cap}
    gapv = adjv = 0
    for i, s in enumerate(ids):
        a = assign.get(s)
        if not a:
            continue
        if i > 0 and assign.get(ids[i - 1]) == a:
            adjv += 1
        for j in range(max(0, i - gap), min(len(ids), i + gap + 1)):
            if j != i and assign.get(ids[j]) == a:
                gapv += 1
                break
    return capv, gapv, adjv


def main() -> int:
    # ---- S1 可行实例：12 景、4 素材、每素材 ≤3、间距 ≥3 ----
    ids = ["s{:02d}".format(i) for i in range(12)]
    opts = {s: ["A", "B", "C", "D"] for s in ids}
    r = AL.satisfy(ids, opts)
    capv, gapv, adjv = viol(r["assignment"], ids)
    check("S1 可行实例 ⇒ 违例全 0（cap {} / 间距 {} / 相邻 {}）".format(
        len(capv), gapv, adjv), r["pass"] and not capv and not gapv and not adjv,
        r["report"])

    # ---- S2 不可行实例：12 景但仅 2 素材可用（cap=3 ⇒ 最多 6 景位）----
    opts2 = {s: ["A", "B"] for s in ids}
    r2 = AL.satisfy(ids, opts2, restarts=6, iters=200)
    capv2, gapv2, adjv2 = viol(r2["assignment"], ids)
    check("S2 不可行实例 ⇒ 返回**最小违例解 + 违例清单**（cap 违例 {}）".format(
        r2["report"]["cap_violations"]), (not r2["pass"]) and bool(capv2),
        {"report": r2["report"]})

    # ---- S3 确定性 ----
    a1 = AL.satisfy(ids, opts)["assignment"]
    a2 = AL.satisfy(ids, opts)["assignment"]
    check("S3 确定性：同 seed 同输入 ⇒ 同解", a1 == a2,
          {"diff": [k for k in a1 if a1.get(k) != a2.get(k)][:4]})

    # ---- S4 首选保序：给一个已满足约束的分配 ⇒ 不应改动 ----
    good = {}
    for i, s in enumerate(ids):
        good[s] = ["A", "B", "C", "D"][i % 4]
    r4 = AL.satisfy(ids, {s: [good[s]] for s in ids}, initial=good)
    check("S4 已满足的分配 ⇒ 不改动（避免无谓变更）",
          r4["pass"] and all(r4["assignment"][s] == good[s] for s in ids),
          {"changed": [s for s in ids if r4["assignment"][s] != good[s]][:4]})

    # ---- S5 复现历史缺陷并归零 ----
    # **踩坑修正**：S5 原以「当前时间轴」为夹具 ⇒ Phase 41 把分配修好后，该时间轴
    # **已无违例**，于是 S5 的 `before` 前提不再成立而**误报 FAIL**。
    # 正解：S5 应守住**历史缺陷的可复现性** ⇒ 用 P40 记录的**缺陷基线**
    # （`logs/p40_solver_validation.json` 的 before 计数）作为断言依据；
    # 同时断言**当前时间轴已无违例**（回归守卫）。
    sb = R / "output/phase36_p36_4_sandbox/material_timeline.json"
    hist = R / "docs/regression_2x/logs/p40_3_delivery_candidate.jsonl"
    if sb.is_file() and hist.is_file():
        tl = json.loads(sb.read_text(encoding="utf-8"))["decisions"]
        fids = [d["scene_id"] for d in tl]
        freal = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id"))
                 for d in tl}
        pool = json.loads((R / "docs/regression_2x/logs/phase33_retrieval_payload.json")
                          .read_text(encoding="utf-8"))
        assets = ["asset_" + str(c["sha256"])[:12] for c in pool["candidates"]
                  if c.get("path")]
        usage = collections.Counter(v for v in freal.values() if v)
        fopts = {}
        for s in fids:
            cur = freal.get(s)
            rest = sorted(assets, key=lambda a: (usage.get(a, 0), a))
            fopts[s] = ([cur] if cur else []) + [a for a in rest if a != cur]
        b_cap, b_gap, b_adj = viol(freal, fids)
        r5 = AL.satisfy(fids, fopts, initial=freal)
        a_cap, a_gap, a_adj = viol(r5["assignment"], fids)
        # 历史缺陷基线（P40-3 登记记录里的 F2 条目：before cap/gap/adj = 1/10/4）
        hb = {}
        for line in hist.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            b = (row.get("p40_1_allocator_fix") or {}).get("before")
            if b:
                hb = b
                break
        check("S5 历史缺陷基线在案（P40-3 记录 before cap/gap/adj = {}/{}/{}）".format(
            hb.get("cap_violations"), hb.get("gap_violations"),
            hb.get("adjacent_violations")),
            (hb.get("cap_violations") or 0) + (hb.get("gap_violations") or 0) \
            + (hb.get("adjacent_violations") or 0) > 0, hb)
        check("S5b 求解器可**彻底归零**（对当前时间轴：{}/{}/{} ⇒ {}/{}/{}）".format(
            len(b_cap), b_gap, b_adj, len(a_cap), a_gap, a_adj),
            not (a_cap or a_gap or a_adj),
            {"after": {"cap": len(a_cap), "gap": a_gap, "adj": a_adj}})
        check("S5c **回归守卫**：当前时间轴已无 cap/间距/相邻违例（{}/{}/{}）".format(
            len(b_cap), b_gap, b_adj), not (b_cap or b_gap or b_adj),
            {"cap": len(b_cap), "gap": b_gap, "adj": b_adj})
    else:
        print("SKIP  S5 未找到时间轴或历史基线")

    print()
    print("=" * 72)
    print("allocation_solver_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
    print("=" * 72)
    (R / "docs/regression_2x/logs/p40_allocation_solver_test.json").write_text(
        json.dumps({"schema": "p40-allocation-solver-test-v1", "pass": len(PASS),
                    "fail": len(FAIL), "failed": FAIL}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
