# Visual Orchestration Layer 正式实现报告

- 日期: 2026-09-10 · 授权: EXP-VG=PARTIAL 但满足正式开发条件 → 正式工程实现
- 状态: **Visual Orchestration Layer Ready（不代表 Production PASS，不触碰任何成片）**
- 实现产物: `src/video_studio/orchestration/`（新增包，stage33 冻结 14 件零触碰）· 测试与影子重放产物: `output/audit_20260910_vg/impl/` 与 `src/video_studio/orchestration/tests/`

## 1. 正式架构（链序固定）

```
Retrieval → Gate → CV2 → Assignment → Global Reuse Policy
→ Pre-render Visual Integrity Gate → Crop/Layout → Crop-aware Recheck → Render → QA
```

**先质量 Gate 后 Reuse Policy** 已作为类型签名固化：`run_reuse_policy(beats)` 的输入 `BeatSpec.candidates` 只能由上游（候选阶段确定性 Gate + CV2 判定）构造，policy 不接触未过滤资产。顺序为 `candidate → quality eligible pool → reuse selection`。

## 2. 模块清单（全部确定性 + schema + audit log）

| 模块 | 文件 | 职责 |
|---|---|---|
| schemas | `orchestration/schemas.py` | AssetRef/Candidate/BeatSpec/GateResult/IntegrityReport/Decision/LedgerEntry/CropRisk 输入输出类型 |
| content_identity | `orchestration/content_identity.py` | MD5→dHash 内容聚类（≤6 判同；7–10 suspect **默认不合并**仅记录）；身份永不使用 material_id/路径 |
| global_reuse_ledger | `orchestration/global_reuse_ledger.py` | 按**内容**记账：次数/位置/功能/借用数/首末次；可回答"该内容全片出现几次、在哪里、什么功能" |
| global_reuse_policy | `orchestration/global_reuse_policy.py` | 纯函数三段式（EVIDENCE/VIZ/借用账本），级联 换池→HN→空位卡，禁止静默重复 |
| visual_integrity_gate | `orchestration/visual_integrity_gate.py` | G0–G9；**确定性门（G0-G4,G8,G9）才可 BLOCK**；G5/G7 仅 ADVISORY |
| crop_recheck | `orchestration/crop_recheck.py` | 裁切后语义复核：vis 比例 / dHash 位移 / 位移量 / 纵横变换 / 文字碰撞；高风险 DEMOTE→contain |
| namespace_guard | `orchestration/namespace_guard.py` | stage22/exp225/experimental/audit/pilot 硬 BLOCK（非 warning）；allow_registry 仅限签核资产 |

## 3. 验收 A：单元测试 — 12/12 PASS

内容身份合并/区分 · ledger 计数与查询 · 策略唯一选择与相邻禁止 · 级联借用 · 60s 间隔强制 · 注册回调恰好 +1 · G3/G5-G7 门行为（advisory 永不单独 BLOCK）· crop recheck S10 fixture/横构图对照 · namespace 守卫四种情形。运行：`python -m video_studio.orchestration.tests.run_all`。

## 4. 验收 B：回归 fixtures R1–R8 — 8/8 PASS

| # | fixture | 结果 |
|---|---|---|
| R1 | S10-B02 裁切失败 | DEMOTE（vis=0.387, shift=25）✅ |
| R2 | viz3 坏图表 | G2(1011×512)+G8(experiment) BLOCK ✅ |
| R3 | NullSpace 极端纵横比 | G3 DEMOTE→contain（AR 0.688）✅ |
| R4 | 3 对字节全同素材 | 聚为 3 内容；候选级 advisory；展示级安全网 3×BLOCK ✅ |
| R5 | S29 A?A 模式 | 决策序列 A?A=0、adjacent=0 ✅ |
| R6 | Run02 ABAB 窗口 | 不再复现 ABAB，同章节图表级联换池 ✅ |
| R7 | exp225 命名空间泄漏 | 硬 BLOCK（非 warning）✅ |
| R8 | S33B 叙事锚点回调 | 无注册→级联不静默重复；注册→合法 +1（ledger=2）✅ |

## 5. 验收 C/D：Run02 影子重放 + 策略指标（`impl/acceptance_summary.json`）

**Config A = 策略层验收**（与封存 EXP-VG1 同资产基线，策略效果 like-for-like）：

| 指标 | Run02 现状 | 正式层 A | 验收 |
|---|---|---|---|
| ABAB / ABA / A?A / adjacent | 12 / 32 / 34 / 7 | **0 / 0 / 0 / 0** | ✅ |
| CORRESPONDING | 51 | **51**（VISUALIZATION 11, HN 26, FALLBACK 13） | ≥51 ✅ |
| HN/FALLBACK rate | 38.6% | **38.6%（+0.0pp）** | ≤+5pp ✅ |
| policy violations | — | **0** | ✅ |
| max reuse / ledger | 5 | **2**（57 内容: 1×13, 2×44；借用 39） | ✅ |

**Config B = 全严格生产行为**（实验图表不得入场）：CORRESPONDING 51 保持（低清/重复候选全部换池成功），11 个 VIZ 拍被 G2(1011×512)+G8(实验)+G9(无出处链) 确定性阻断，按授权级联转入借用 → HN/FB 49.5%（**+10.9pp 为治理代价而非策略缺陷**：VIZ Production Rollout 未授权时生产路由本不应存在 VIZ 拍——Run 03 生产指派即无 VIZ 路由）；空位卡 0；模式全零；violations 0。此代价为命名空间硬门槛的直接计量，已在报告中显式入账。

## 6. 验收 E：Integrity 指标

- 已知异常 **100% 捕获**（两配置一致）：viz3→G2+G8+G9；NullSpace→G3(+G4 内容重复)；3 对字节重复→内容身份合并+展示级 G4；UI 截图(408px)→G2；316px 横幅/288px→G2
- pre-render 决策分布：A=37 PASS / 14 DEMOTE（contain+上采样标注）/ 11 BLOCK(图表)；B=37/14/0
- **G5/G7 仅 advisory**：正式实现中二者不可能产生 BLOCK（代码路径+单测+重放三重验证）；chosen displays 上 10 个 advisory 信号全部只记录不处置
- crop recheck：51 个照片展示中 16 个高风险 DEMOTE（含 R1 fixture），建议 contain 重排——无静默进入 render 路径

## 7. 验收 F：Namespace 隔离

Config B 全片 0 个实验资产进入渲染决策（11 图表全部候选阶段阻断）；R7 单元级 BLOCK 验证通过；production→experimental 方向为硬 BLOCK。

## 8. 实现中的设计决策（与 EXP-VG 实验版的差异，全部有依据）

1. **suspect 带（dHash 7–10）默认不合并**：全候选池规模上 7–10 合并产生假簇（不同纵横比图像被并簇，曾致 5 拍候选池被清空）。正式版只记录 suspect 链接供人工/更强模型复核。
2. **G4 改为展示级安全网**：候选阶段的文件级"首现封杀"违反分层（内容唯一性是 policy 的职责）且误杀孪生池；正式版候选级 G4 只做 advisory 标注，展示级（pre-render）对照已展示内容集 BLOCK。
3. **G2 照片双阈值**：<480 BLOCK（不可用），480–719 DEMOTE（上采样标注）——已知异常集不含 627px 合法照片，一刀切 720 会无对应收益地损失 CORRESPONDING；图表阈值不变（viz3 仍被捕获）。
4. **G9 图表无照片出处链 → BLOCK**：与命名空间守卫一致，实验图表双路拦截。
5. **allow_registry（签核注册表）**：G8/G9 可被显式签核覆盖，仅用于未来经人工批准的资产；本轮 Config A 的"测试授权"仅用于策略层计量，不构成生产签核。

## 9. 冻结完整性复验（实现后）

- stage19_8 冻结指纹 **14/14 SHA256 一致**（CHANGED 0 / MISSING 0）
- Run02 母片 `ad52a0c0eb9a4491` 不变，mtime 仍为 2026-09-07 16:43（原始渲染时刻）
- Retrieval/CV2/Run01/Run03/EXP-A/B/VIZ Rollout/P-2 seal：零触碰；本轮未重跑任何昂贵链路（Retrieval/CV2 均未调用）

## 10. 未尽事项（不阻塞本层 Ready）

1. **CV2 裁切带实判复核**：被 API 402（额度耗尽）阻塞，确定性模拟层已覆盖 R1；额度恢复后补 3 次调用验证
2. **人工盲测**：等待评分者；VG3 contact-sheet 与客观指标已交付
3. **G5/G7 独立校准**：保持 advisory 直至完成（本实现已从结构上禁止其 BLOCK）
4. **生产接线**：本层模块尚需由未来生产 render 脚本按 §1 链序调用（本轮按授权不修改任何生产脚本）

## 11. 验收清单对照

| 要求 | 结果 |
|---|---|
| A. Unit tests | 12/12 PASS |
| B. Regression fixtures R1–R8 | 8/8 PASS |
| C. Run02 shadow replay | Config A/B 完成（`impl/shadow_replay_A/B.json`） |
| D. Policy metrics | §5：四类模式全部归零，+0.0pp，CORR 51 |
| E. Integrity metrics | §6：已知异常 100%，G5/G7 advisory-only |
| F. Namespace isolation | 0 泄漏（Config B 全片无实验资产） |
| crop regression S10-B02 | R1 + 重放双捕获 |
| 冻结完整性 | 14/14 指纹一致，母片哈希不变 |

```
IMPLEMENTATION = PASS
状态 = Visual Orchestration Layer Ready
边界 = 不自动修改 Run02 成片 · 不自动重启 Run03 · 不代表 Production PASS
待外部条件 = CV2 API 额度（裁切实判+盲评） · 人工评分者 · 生产 render 接线授权
STOP——等待授权
```
