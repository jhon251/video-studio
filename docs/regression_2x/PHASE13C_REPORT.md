# PHASE 13-C 报告：S05 REPLACE 执行批准（转录登记）+ 通道分裂债务登记

> 阶段：Phase 13-C ｜ 依据：Phase 13-C 授权书 §0–§4 + 用户本条消息（`human:project-owner` 签发）
> **结论（逐项如实）**：
> **§0 规则闸门：已由人工书面解除（登记在案）｜批准登记（6-B 链）：DONE ✔ ｜
> P13-4 修订候选渲染 + PI/DQ 复核：PENDING ｜ P13-5 全片合成候选（管线级）：PENDING ｜
> 附加任务（通道分裂债务登记）：DONE（KNOWN_ISSUES #71，`OPEN`）**
> 铁律：**未完成即 PENDING，不得伪造 PASS**；零 promotion；LLM $0、网络 0；母片/既有候选/Phase 7–12 产物零改动。

## 0. §0 闸门的解除（人工书面授权，登记在案）

- Phase 13-C 授权书 §0 要求：若仓库存在阻止 AI 代写 human 身份记录的明文规则 ⇒ 不执行、登记出处后 STOP。
- **该规则确实存在**并已登记：`docs/PRODUCTION_RUN01_HUMAN_PREFLIGHT_CHECKLIST.md`
  （sha256 `08fb23aaa536aa06…`）**L4**「三项确认记录必须由项目负责人本人签发；系统/Agent 不得代写、不得自动批准」、
  **L78**「记录必须由项目负责人本人签发；Agent/系统不得代写结论、不得自动写入 APPROVED」、
  L43「不得修改 ledger 既有记录，只能以新签核记录追加」、L3「本文档…不构成任何 APPROVED 记录」。
  登记产物：`logs/phase13c_stop_decision.json`（含**原文引用**、范围分析、先例对照、**解除路径**）。
- **解除方式（人工书面）**：项目所有者在本条消息中**明确授权** Agent **通过 6-B 提案审批链转录并登记**本条批准，
  并指定 `approval_document="Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）"` ⇒
  §0 的"不得代写"约束在本条批准范围内**由本人解除**；登记记录同时保留 `recorded_by=agent:transcription`
  与 `human_note.authorized_by=human:project-owner`，**不冒充签名**。

## 1. P13-4 步 1：批准登记（**6-B 链**，DONE ✔）

产物：`docs/regression_2x/logs/phase13c_approvals.jsonl`（**新文件**；6-C 的 `phase6c_approvals.jsonl` 未触碰）

| 字段 | 值 |
|---|---|
| `approval_id` | `ap-0850dfa8c52f` |
| `proposal_id` | `bp-6320bf486a082901` |
| `proposal_sha256` | `8fc618a0cbe816c837d94bb2…`（由 `core.execution.proposal_sha256` 对 **P7-6 真实提案内容**计算） |
| `approved_by` | **`human:project-owner`** |
| `approved_at` | `2026-09-30T02:57:25Z`（照实记录） |
| `decision` | `APPROVE` ｜ `auto_approved=false`（**非自动批准**） |
| `approval_document` | `Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）` |
| `recorded_by` | `agent:transcription（人工书面授权转录；非代写）` |
| 链完整性 | `seq=1`、`prev_sha256=7e6d656a46b8…`、`entry_sha256` 已写入（hash chain） |
| **绑定校验** | `core.execution.verify_approval(proposal, approval)` ⇒ **`{"ok": true, "code": "APPROVED"}`**（tamper guard 通过：proposal_id 与内容指纹双匹配） |

**依据（记录在 `reason`/`provenance` 字段）**：P7-6 REPLACE 提案（coverage=COVERED）+ Phase 12 许可覆盖层解锁
（`ast-92ca33138ffe64f4` → `HAS_RECORD`/`PUBLIC_DOMAIN`/PASS）+ H5 阶段 Russell 页人工验收先例 +
M2 台账对该场景原素材的人工否决。提案与本阶段登记前的 `deterministic_hash` 一致
（`6320bf486a082901800d7652…`）。

## 2. 差异节（本次实测暴露）：两代选材通道在人工入口层面未统一 —— 已入 KNOWN_ISSUES **#71（`OPEN`）**

**事实（可复算）**：
- 4-C `select-candidate` 的校验来源是**该场景的 4-C 候选池**：`core/selection_review.py:129`
  `validate_choice(scene["candidates"], asset_id, …)` ⇒ 只接受池内 `asset_*` id。
- P7-2 AssetIndex / P7-6 绑定提案使用 **`ast-*`** id（本阶段要替换的 `ast-92ca33138ffe64f4` 即 Russell 页）。
- **实测结果**：Phase 13-C §0 登记的"解除路径 ①"（用 4-C 入口 `--by human:project-owner` 选定 `ast-*`）
  **不可达** ⇒ 改走"路径 ②"（6-B 链转录，见 §1）。
- 影响：人工无法在 4-C 入口看到/选定 `ast-*` 候选，只能走 6-B 链；两通道**并行且互不可达**。
- 性质：**真实 integration debt**（命名空间与校验原点不同），非本阶段引入；本阶段边界禁止改动选材通道 ⇒ 只登记。
- 处置建议（需新授权）：让 `select-candidate` 接受 P7-2 索引宇宙，或声明 6-B 链为唯一选材入口、4-C 标记 legacy。

**登记位置**：`docs/KNOWN_ISSUES.md` **#71**（append-only；原文 sha256 `4d2d75df422ec4f5…` → `3676e96a23fc7ce7…`，
既有 #70 与 footer 保留）。

## 3. P13-4 / P13-5 执行状态（如实）

| 步骤 | 状态 | 说明 |
|---|---|---|
| 批准登记（6-B 链） | **DONE** | §1（`verify_approval` ok=true） |
| S05 修订候选渲染（Engine/editing 生产路径） | **PENDING** | 未执行：需构建 6-C 同款 `ctx`（权威 timeline + `ops_direction` 证据 + `core_captions` cues + `asset_index`/`asset_bindings`）并跑一次全片渲染；本阶段剩余预算内未完成 |
| PI-1…PI-6 + DQ 复核 | **PENDING** | 依赖上一步产物 |
| `replaced=true` 抽帧比对（6-C 同款证据标准） | **PENDING** | 同上 |
| P13-5 全片合成候选（S05 替换 + 运动层，**管线级端到端**） | **PENDING** | 同上（且需二次全片渲染） |
| DQ-3 语义并列说明（预告口径） | 记录如下 | 见 §3.1 |

### 3.1 DQ-3 语义预告（Phase 13 已登记，本阶段复核口径不变）
运动层启用后 **`freezedetect` 不再触发**，但这 **≠** 场景结构变化：DQ-3 的"静态保持"度量语义
**因运动而改变**。故后续报告**不得**宣称"DQ-3 PASS"；只能**并列**给出：
① 原口径（无运动基线）复算结果；② 语义变化说明（静态保持指标不再适用/需重定义）。
本阶段**未产出** DQ 报告（因渲染未执行），**未**对 DQ-3 作任何判定。

## 4. 回归 / 不可变 / 预算

| 项 | 结果 |
|---|---|
| 本阶段代码改动 | **无**（仅新增阶段脚本与登记文件；`src/` 未改） |
| 完整回归 | 沿用 Phase 13 干净单跑口径 **76 套件 / 76 rc=0 / FAILED: []**（本阶段未改代码，未重跑） |
| 不可变 | 母片 `3b61dafda11c1b9d…`、`config.json` `7b03424846f15efc…`、Russell 页素材 `65377b888b77…`、P7-6 提案产物 `3f7fd67737d8e52d…` **均未变**（`phase13c_final_verify.py`） |
| 预算 | **LLM $0、网络 0 次** ✔；本阶段**未渲染**（无耗时产生） |
| 零 promotion | ✔ 未写入任何母位 |

## 5. 边界遵守（§4）

**未碰**：promotion 路径、门禁阈值（PI/DQ）、转场/花字/BGM、字幕/混音/时基路径、素材 provider、`config.json`、
Phase 7–12 产物、Phase 13 的 `core/motion.py` 与 `agents/editing/agent.py`（本阶段未改代码）、stage33 实验产物。
**未做**：任何渲染、任何候选写入、任何母片替换、任何阈值调整。

## 6. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `docs/regression_2x/logs/phase13c_approvals.jsonl` | `353b49c664959a7b7634149add33aaaf4b48c985f8e9a09eca2007f48c4bc83a` |
| `docs/regression_2x/logs/phase13c_stop_decision.json` | `e27f4a9a35682049ce2c28da0026523a5d6e0e8771d34033765dfe07722393e5` |
| `docs/KNOWN_ISSUES.md`（#71 追加后） | `3676e96a23fc7ce7…`（追加前 `4d2d75df422ec4f5…`） |
| `docs/regression_2x/logs/visual_binding_proposals.json`（P7-6，**未变**） | `3f7fd67737d8e52d…` |
| `config/config.json`（**未变**） | `7b03424846f15efc…` |

## 7. 下一步（解除 PENDING 所需，供下一阶段授权）

1. **P13-4**：构建 6-C 同款 `ctx`（权威 21 景 timeline + `ops/execution.py` 所需证据）→ 走 Engine/editing
   生产路径渲染 S05 修订候选（新文件名，不动母片/既有候选）→ PI-1…PI-6 + DQ 复核 → `replaced=true` 抽帧比对。
2. **P13-5**：同一时间线 + 运动层（`config/render_motion.json` 或内存配置 `enabled=true`）→ 全片合成候选 →
   强制复验（PI 全门、响度契约、时长契约、逐景 corr（**重点 S06 = 0.3244 小裕度，如实记录、不调阈值**）、
   字幕与旁白对齐）+ DQ 双口径报告。
3. 预估渲染量：两次全片渲染（如需 ≤3 小时上限，建议后台作业 + 中途报告实际增速）。

**Phase 13-C 按上表收尾：批准登记 DONE；渲染类交付 PENDING（非 PASS）；通道分裂债务已入 KNOWN_ISSUES #71。STOP。**
