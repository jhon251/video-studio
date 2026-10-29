# -*- coding: utf-8 -*-
"""Phase 13-C：把「两代选材通道在人工入口层面未统一」登记为 KNOWN_ISSUES #71（append-only）。"""
import hashlib
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
KI = R / "docs" / "KNOWN_ISSUES.md"
sys.stdout.reconfigure(encoding="utf-8")
txt = KI.read_text(encoding="utf-8")
before = hashlib.sha256(KI.read_bytes()).hexdigest()

ENTRY = """## 71. 两代选材通道在**人工入口层面**尚未统一（4-C `asset_*` 旧命名空间 vs P7-2 `ast-*` 索引宇宙）—— `OPEN`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#71** | 4-C `select-candidate` 只接受**该场景 4-C 候选池内**的 `asset_*` id；P7-6 绑定提案与 P7-2 AssetIndex 使用 `ast-*` id ⇒ **人工无法用 4-C 入口选定 `ast-*` 素材**（Phase 13-C 实测尝试失败）。6-B 提案审批链（`core/execution.py`）可用 `ast-*`（经 `proposal_sha256` 绑定），两条通道**并行且互不可达** | `src/video_studio/core/selection_review.py:129`（`validate_choice(scene["candidates"], asset_id, …)`）；`docs/regression_2x/logs/phase13c_approvals.jsonl`（6-B 链登记 `bp-6320bf486a082901`，绑定 `ast-92ca33138ffe64f4`）；`docs/regression_2x/logs/phase13c_stop_decision.json`（§0 登记；其中"解除路径 ①"正是 4-C 入口，实测不可达 ⇒ 改走 ② 6-B 链转录） |

- **性质**：真实 **integration debt**（两代通道的 id 命名空间与校验来源不同），**非**本阶段引入。
- **为何本阶段不修**：Phase 13-C 边界明确禁止改动选材通道语义（"不碰门禁阈值/不做 promotion"），
  且修它需要统一两个命名空间的原点（4-A 素材池快照 vs P7-2 索引），属**跨阶段集成工作**。
- **影响**：人工在 4-C 入口看不到 `ast-*` 候选 ⇒ 只能走 6-B 链；反之 6-B 链也不产出 4-C 可选项。
  对"人工最终决定"这一契约**不构成放权风险**（两条通道都要求人工归属），但**增加操作摩擦与误用风险**。
- **建议处置**（择一，需新授权）：① 让 `select-candidate` 接受 P7-2 索引宇宙（把 `ast-*` 映射进候选视图）；
  ② 或声明 **6-B 链为唯一选材入口**并把 4-C 入口标注为 legacy（保留只读）。
"""

marker = "## 变更纪律"
i = txt.find(marker)
assert i > 0, "未找到 变更纪律 锚点"
# 在 footer 的 `---` 之前插入（保持 footer 原样）
j = txt.rfind("---", 0, i)
assert j > 0, "未找到 footer 分隔线"
new = txt[:j] + ENTRY + "\n" + txt[j:]
KI.write_text(new, encoding="utf-8")
after = hashlib.sha256(KI.read_bytes()).hexdigest()
print("KNOWN_ISSUES #71 已追加 | 原文 sha256:", before[:16], "-> 新:", after[:16])
print("行数:", len(txt.splitlines()), "->", len(new.splitlines()))
print("#71 在位:", "#71" in KI.read_text(encoding="utf-8"),
      "| 既有 #70 保留:", "**#70**" in KI.read_text(encoding="utf-8"),
      "| footer 保留:", "## 变更纪律" in KI.read_text(encoding="utf-8"))
