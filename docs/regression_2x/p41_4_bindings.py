# -*- coding: utf-8 -*-
"""Phase 36 / P36-4 前置：**逐景具名绑定方案**（P34-1 机制的 36 景版）。

为什么要重做：P36 把 9 段切成 36 景 ⇒
  · 旧绑定键为 v4.1 的景号（S03p1…），在新景号（P01_1…）下**全部失配**（实测 bindings=0）；
  · 实测残留卡景 `P09_1`。
本脚本：按**逐景旁白语义**从池（17 张）中挑语义相配素材，产出绑定表，
并**预检约束**（每素材 ≤3 景、相邻禁同、间距 ≥3）——不合格则报告而非静默。
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
POOL = L / "phase33_retrieval_payload.json"
OUT = R / "output" / "phase36_voice" / "bindings_proposal.json"

# 池内可用素材（按名称/主题），来自 phase33_retrieval_payload.json 的 17 张
# 语义关键词 → 首选素材（按旁白主题）
TOPIC = [
    # (关键词组, 首选 sha 前缀, 说明)
    (["四色", "地图", "上色", "区域"], "301ff850be9c", "mathmap 结构图"),
    (["归约", "构型", "有限多种", "无穷多"], "1d2fe4b325bd", "黑板公式（形式化意象）"),
    (["证明", "读完", "读一遍", "行"], "a3aff2f300eb", "人手书写证明（规模意象）"),
    (["审稿", "期刊", "背书", "拖"], "f0cd2a28016d", "历史文献页（审稿意象）"),
    (["Tymoczko", "哲学家", "哲学", "认识论", "地基"], "65377b888b77",
     "罗素《数学原理》（严谨/证据意象）"),
    (["Detlefsen", "Luker", "反驳", "定义", "共同体"], "acaa16094c3b", "图论示例（结构意象）"),
    (["单群", "几百位", "接力", "分工"], "23e71bc8a864", "证明链（分工意象）"),
    (["开普勒", "球", "堆", "橘子", "最密"], "a3f0e27204cd", "堆叠/密排意象"),
    (["Hales", "99", "审稿人", "没有洞"], "bd383463dbb9", "计算/表格意象"),
    (["Flyspeck", "形式化", "十六年", "改写", "编译器"], "1e9d2ab4e64e",
     "Lean 界面（人→机翻译意象）"),
    (["Lean", "mathlib", "代码", "标准件", "库"], "1e9d2ab4e64e", "Lean 界面"),
    (["Scholze", "菲尔兹", "挑战", "Liquid", "挑刺"], "33b360a5363c",
     "顶尖数学工作场景意象"),
    (["AlphaGeometry", "IMO", "几何", "辅助线", "银牌", "奖牌"], "432cd85be6f1",
     "几何图形意象"),
    (["机器", "AI", "出题", "自己写", "三代", "封条"], "cfae038f6106",
     "机器/计算意象"),
    (["数学", "定理", "结果"], "5144139591a0", "数学文档意象"),
]
FALLBACK = ["301ff850be9c", "1d2fe4b325bd", "a3aff2f300eb", "f0cd2a28016d",
            "65377b888b77", "acaa16094c3b", "23e71bc8a864", "a3f0e27204cd",
            "bd383463dbb9", "1e9d2ab4e64e", "33b360a5363c", "432cd85be6f1",
            "cfae038f6106", "5144139591a0"]


def main() -> int:
    script = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                        .read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    cands = {str(c["sha256"]): c for c in pool["candidates"] if c.get("path")}
    segs = script["segments"]
    binds, used, reasons = {}, {}, {}
    fi = 0
    for s in segs:
        text = s["narration"]
        pick = None
        for kws, pre, why in TOPIC:
            if any(k in text for k in kws):
                hit = next((h for h in cands if h.startswith(pre)), None)
                if hit:
                    pick, why_txt = hit, why
                    break
        if pick is None:
            # 兜底：取**当前使用次数最少**的池素材（保证分布均匀）
            order = sorted(cands, key=lambda h: (used.get(h, 0), h))
            pick, why_txt = order[0], "兜底（当前用量最少）"
            fi += 1
        # 约束回避：每素材 ≤3、相邻禁同、间距 ≥3 ⇒ 选最合适的合规者
        def ok(h, idx):
            if used.get(h, 0) >= 3:
                return False
            for j in range(max(0, idx - 3), min(len(segs), idx + 4)):
                if j != idx and binds.get(segs[j]["scene_id"]) == h:
                    return False
            return True
        idx = s["index"]
        if not ok(pick, idx):
            alt = [h for h in sorted(cands, key=lambda h: (used.get(h, 0), h)) if ok(h, idx)]
            if alt:
                pick, why_txt = alt[0], why_txt + "（约束改选）"
            else:
                print("  !! {} 无合规素材（保持自动选材）".format(s["scene_id"]))
                continue
        binds[s["scene_id"]] = pick
        used[pick] = used.get(pick, 0) + 1
        reasons[s["scene_id"]] = why_txt
    # ---- 预检 ----
    ids = [s["scene_id"] for s in segs]
    seq = [binds.get(i) for i in ids]
    viol_cap = {h: n for h, n in used.items() if n > 3}
    viol_gap = []
    for i, a in enumerate(seq):
        if not a:
            continue
        for j in range(max(0, i - 3), min(len(seq), i + 4)):
            if j != i and seq[j] == a:
                viol_gap.append((ids[i], ids[j]))
                break
    print("逐景绑定 {} / {} 景 | 兜底 {} 景".format(len(binds), len(segs), fi))
    print("素材用量: {}".format(json.dumps(
        {h[:12]: n for h, n in sorted(used.items(), key=lambda x: -x[1])},
        ensure_ascii=False)))
    print("预检：每素材 ≤3 ⇒ {} | 间距 ≥3 ⇒ {}".format(
        viol_cap or "OK", "OK" if not viol_gap else viol_gap[:5]))
    detail = {sid: {"sha256": h, "name": cands[h].get("name"), "reason": reasons[sid],
                    "approval_document": "Phase 34 授权书 §1(a)（P36 逐景重映射）"}
              for sid, h in binds.items()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"schema": "p36-per-scene-bindings-v1",
                               "scene_count": len(segs), "bound": len(binds),
                               "usage": used, "violations": {"cap": viol_cap,
                                                             "gap": viol_gap[:10]},
                               "bindings": detail},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> " + str(OUT.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
