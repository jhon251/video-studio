# -*- coding: utf-8 -*-
"""校正已登记的 Phase 14 数字（末次实测）：agreement 与成本合计。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

REPL = [
    ("`agreement = 3/27 = 11.11%`（**FAIL**）",
     "`agreement = 4/27 = 14.81%`（**FAIL**；首次独立运行 3/27 = 11.11%，同样 FAIL）"),
    ("**实测结果**：`agreement = 3/27 = 11.11%`（**FAIL**）",
     "**实测结果**：`agreement = 4/27 = 14.81%`（**FAIL**；首次 11.11%）"),
    ("正例误判 16；非二值 8。**成本 $0.0201**（上限 $2）",
     "正例误判 13；非二值 10。**成本 $0.0202**（上限 $2）"),
    ("正例误判 RELEVANT→IRRELEVANT 16；非二值 8。成本 **$0.0201**（上限 $2）",
     "正例误判 RELEVANT→IRRELEVANT 13；非二值 10。成本 **$0.0202**（上限 $2）"),
    ("仅把一致率提到 25.93% ⇒ **不是提示词措辞问题**",
     "首测 25.93%、末测与门禁口径同为 14.81%（端点非确定性）⇒ **不是提示词措辞问题**"),
    ("仅把一致率从 11.11% 提到 **25.93%**（`logs/phase14_eval_diag_anchor.json`）。",
     "首测到 **25.93%**、末测 14.81%（`logs/phase14_eval_diag_anchor.json`）。"),
    ("**总 API 花费 $0.0368**（门禁 27 对 $0.0201 + 诊断 27 对 $0.0167 + 连通性探针 $0.0006）",
     "**总 API 花费 $0.0375**（门禁 27 对 $0.0202 + 诊断 27 对 $0.0167 + 连通性探针 $0.0006）"),
    ("成本台账：门禁 $0.0201 + 诊断变体 $0.0167 + 连通性探针 $0.0006 = **$0.0368**（上限 $2）；",
     "成本台账：门禁 $0.0202 + 诊断变体 $0.0167 + 连通性探针 $0.0006 = **$0.0375**（上限 $2）；"),
    ("`overall agreement = 3/27 = 11.11%`（阈值 90%）",
     "`overall agreement = 4/27 = 14.81%`（阈值 90%；首次独立运行 11.11%）"),
]

for name in ("STATUS.md", "CHANGELOG.md", "docs/KNOWN_ISSUES.md"):
    p = R / name
    t = p.read_text(encoding="utf-8")
    n = 0
    for a, b in REPL:
        if a in t:
            t = t.replace(a, b)
            n += 1
    if n:
        p.write_text(t, encoding="utf-8")
    print("{:24s} 替换 {} 处".format(name, n))

# 追加"端点非确定性"说明到 KNOWN_ISSUES #73（仅一次）
p = R / "docs" / "KNOWN_ISSUES.md"
t = p.read_text(encoding="utf-8")
add = ("- **端点非确定性（实测）**：设计假定 `temperature=0` ⇒ 同输入同判定，实测**不成立** —— "
       "清空缓存后两次独立运行有 2 对标签改变（S04 `PARTIAL→RELEVANT`、S07 `IRRELEVANT→PARTIAL`），"
       "一致率 11.11%→14.81%。**文件缓存内一致**（同键同字节，已验证），**跨键/跨版本不保证复现**；"
       "该不确定性不改变门禁结论（两次均远低于 90%）。\n")
if "端点非确定性" not in t:
    anchor = "### 真值集规模不足（连带登记）"
    i = t.find(anchor)
    t = (t[:i] + add + "\n" + t[i:]) if i >= 0 else (t.rstrip() + "\n" + add)
    p.write_text(t, encoding="utf-8")
    print("KNOWN_ISSUES.md 已追加端点非确定性说明")
else:
    print("KNOWN_ISSUES.md 已含端点非确定性说明")
