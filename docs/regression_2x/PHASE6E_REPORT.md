# 6-E 报告 —— Evidence-Grounded Directorial Revision Round 2（**只生成/登记，禁止执行**）

- 阶段：**6-E**（依据本轮人工审片结论，对 6-C 候选暴露的问题生成第二轮**局部** revision proposals）
- 输入（全部只读）：本轮人工审片结论、6-C 候选成片与执行证据（`logs/phase6c_batch.json`）、
  6-C 字幕连续性实测（`logs/phase6c_subtitle_check.json`）、v9 时间轴与脚本旁白、6-B/M5 执行证据（跨批次重叠声明）
- 产出：`logs/phase6e_review_ledger_r2.jsonl`（审片台账，6 条）、
  `logs/phase6e_proposal_register_r2.jsonl`（方案登记，5 条）、`logs/phase6e_round2.json`（证据总汇）
- **本阶段未执行任何修改**：无 ffmpeg 调用、无新成片；C1–C4、v9、DB、timeline、字幕、素材**均未改动**（§7）。

---

## 0. 结论速览

| 项 | 结论 |
| --- | --- |
| 覆盖要求的 6 项 | **全部覆盖**：①片尾豆腐块 ②aS05 ③aS11 ④480–690s 长镜 ⑤850–1000s 长镜 ⑥aS18 保留 |
| Proposal 数量 | **5 条**（E1–E5），全部 `PROPOSED_AWAITING_HUMAN_APPROVAL`、`approved=false`、`executed=false` |
| 保留记录 | **1 条**（aS18 `verified_positive_keep`，人审 ACCEPT）——**未**生成方案（要求 6） |
| 审片绑定 | 每条 proposal 绑定 **[人审决策(seq+entry_sha256) → candidate(sha256) → scene/window+narration → 原始 evidence]** |
| 禁止素材 | E2/E3 在 `semantic_spec` 与 `forbidden_material` 中**显式禁止** IMO 合影（`asset_432cd85be6f1`） |
| 无虚构素材 | 5 条全部 `material_requirement.asset_id = null`；`affected_scope.assets = []` |
| CLIP 非充分依据 | 每条显式记录 `clip_similarity_sufficient=false` + `why_not_clip`；`basis` 均为**具体缺陷/叙事证据** |
| 信息增量 | E4/E5 显式 `punch_in_only_forbidden=true` + **4 个可核对信息槽** + “每个数字须附来源”(宁缺勿造) |
| 局部化 | 全部满足 M3 上限（≤6 镜、占比 ≤0.30）：最大为 E4 的 3 镜 / 0.1371 |
| 冲突（M5 口径） | 6-E **内部冲突 0 对**；与已执行方案的**跨批次重叠 4 对**，逐条**显式声明**（不静默绕过） |
| DEFER/UNKNOWN 守卫 | 驱动决策全部为**可证**（`unprovable=false`）的人工 REJECT；不可证项调用 `make_proposal` 实测抛 `DEFER_MUST_NOT_BECOME_CHANGE` |
| 台账链 | 审片链 6 条、登记链 5 条，两条独立哈希链 `ok=true`（seq 连续） |
| 单测 | 6-E 新套件 **67/67**；受影响套件全绿 |
| 完整性 | v9 母版 sha256 未变；DB 未变；沙箱产物目录**逐字节未变**（无新成片）；C1–C4 sha256 与 6-C 记录一致；4 个 baseline ZIP 未变、无新 tag |

---

## 1. 人工审片结论（round 2）→ 审片台账

`logs/phase6e_review_ledger_r2.jsonl`（`core.human_review`，append-only + 哈希链，`chain_ok=true`）：

| seq | finding_id | kind | scene/window | 决策 | 结论（摘要） |
| --- | --- | --- | --- | --- | --- |
| 1 | `hr-7f862a064617` | `outro_card_missing_cjk_glyphs` | S21 [1465,1532] | **REJECT** | C1/C4 片尾卡 CJK 文字渲染为**豆腐块**（缺字形） |
| 2 | `hr-373d88ae9e84` | `asset_semantically_unrelated_imo_group_photo` | S05 [245,300] | **REJECT** | aS05 的 IMO 合影与『Tymoczko 引文/可检视性争论』无直接关系；**否决继续使用** |
| 3 | `hr-46048b3de09b` | `asset_semantically_unrelated_imo_group_photo` | S11 [690,770] | **REJECT** | aS11 的 IMO 合影与『Lean/mathlib/形式化证明』无直接关系；**否决继续使用** |
| 4 | `hr-488b41463fb0` | `long_hold_insufficient_information` | S08–S10 [480,690] | **REJECT** | 210s 开普勒炮弹堆长镜**信息量不足**，要求真正增量的局部方案 |
| 5 | `hr-ca922009730c` | `long_hold_insufficient_information` | S13–S14 [850,1000] | **REJECT** | 150s 长镜信息量不足，要求真正增量的局部方案 |
| 6 | `hr-9e98ab2b36d2` | `verified_positive_change_keep` | S18 [1245,1330] | **ACCEPT** | aS18 替换已验证为**正向**（相关度 0.7642，优于原素材 ≥0.59 边距）⇒ **保留** |

所有条目 `unprovable=false`（结论均有人审 + 成片实证支撑）⇒ 可作为**确定性修改**的驱动依据。

### 1.1 豆腐块缺陷的实证（要求 1 的证据基础）
- **只读抽帧**（未渲染、未修改任何成片）：`docs/regression_2x/logs/_outro_card_probe.png`
  （取自既有 C1 成片 t≈1500s 的底部区域）显示片尾卡为 **`□□□□ □□□□□`**；
  **同一帧**底部由 ASS 链渲染的字幕（「『IMO 银牌』是分数换算，不是实际参赛成绩。」）**中文正常**。
- **根因**：`exec_add_outro_card` 的 `drawtext` 未指定字体文件，依赖 fontconfig 默认字体（无 CJK 覆盖）；
  而字幕链经 `core.captions.to_ass` + `fontsdir='C\:/Windows/Fonts'` 指定 **Microsoft YaHei** ⇒ 正常。
- **修复方向（E1）**：`drawtext` 增加 `fontfile=msyh.ttc`（与字幕链同一字体目录），文本/位置/时长不变。

---

## 2. 第二轮 Proposal（5 条，均已登记、**未执行**）

| # | label | action | 目标 scene/window | 占比 | 素材需求 | 一句话内容 |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | `E1-outro_card_missing_cjk_glyphs` | `add_outro_card` | S21 [1465,1532] | 0.0437 | 无需新素材（字体参数） | 用**显式字体文件**重渲染片尾卡，消除豆腐块 |
| E2 | `E2-asset_semantically_unrelated_imo_group_photo` | `replace_asset` | S05 [245,300] | 0.0359 | **需新素材**（semantic_spec + sourcing） | 换用与『引文/表述**可检视性**争论』直接相关的差异化视觉 |
| E3 | `E3-asset_semantically_unrelated_imo_group_photo` | `replace_asset` | S11 [690,770] | 0.0522 | **需新素材**（semantic_spec + sourcing） | 换用与 **Lean / mathlib / 形式化证明**直接相关的视觉 |
| E4 | `E4-long_hold_insufficient_information` | `add_visual_aid` | S08–S10 [480,690] | 0.1371 | 自制内容（SELF_CREATED） | 叠加**可核对信息面板**（≥4 槽），禁止仅 punch-in |
| E5 | `E5-long_hold_insufficient_information` | `add_visual_aid` | S13–S14 [850,1000] | 0.0979 | 自制内容（SELF_CREATED） | 叠加**可核对信息面板**（≥4 槽），禁止仅 punch-in |

登记链：`logs/phase6e_proposal_register_r2.jsonl`（5 条，`chain_ok=true`，seq 1..5）。
完整 proposal JSON（含 `evidence_chain` / `information_gain` / `material_requirement` / `risk` /
`expected_effect` / `constraints`）见 `logs/phase6e_round2.json → proposals`。

### 2.1 E1 — 片尾卡字体修复
- `params`：`font_file=msyh.ttc`、`fontsdir=C:/Windows/Fonts`、`reuse_subtitle_font=true`、
  `keep_position_and_size=true`、`keep_total_duration=true`。
- 预期：`DQ-6（片尾关键词）` 保持 PASS 且**文字可读**；时长/音轨/字幕不变。
- 风险：字体文件缺失 ⇒ **保持原状并回报人工**（不得改用未审定字体）；重复执行造成窗口再编码 ⇒ 仅允许一次（幂等门禁）。

### 2.2 E2 — aS05：可检视性争论的差异化视觉
- `semantic_spec`：与『Tymoczko 1979 文章的具体表述 / 引文可检视性』直接相关的素材
  （①论文期刊页可读版面；②逐字核对/标注重合示意；③『可检视性（surveyability）』概念图），
  并**显式写明不得使用 IMO/竞赛合影**。
- `sourcing`：人工检索 + 许可核验；本阶段只登记需求，**不检索、不下载、不写 asset_id**。
- 预期：`DQ-8` 语义支撑由「无关」→「直接对应」（状态需复核，不承诺 MATCH）。
- 风险：许可不清 ⇒ 退回人工待处理（不得先用后补）；低分辨率不可读 ⇒ 需人工确认。

### 2.3 E3 — aS11：Lean/mathlib/形式化证明视觉
- `semantic_spec`：①Lean 源码或 mathlib 页面截图（含可辨识定理/策略关键字）；②proof state / goal 面板示意；
  ③形式化依赖图或验证流程示意；同样**显式禁止** IMO/竞赛合影。
- 风险：源码截图涉及第三方版权/商标 ⇒ 许可核验；与已执行的 H3b（S11 切分）、H5（S11 换用）**跨批次重叠**。

### 2.4 E4 / E5 — 长镜「真正增加信息量」
- 关键约束：**禁止仅靠 punch-in / 重复构图变化**（`punch_in_only_forbidden=true`），
  必须提供 4 个**可核对信息槽**且 `each_number_must_cite_source=true`、`no_unverified_numbers=true`（宁缺勿造）。
- E4 槽位（源自 S08–S10 旁白本身）：球堆积问题定义 / FCC-HCP 候选结构对比 / 「审稿人无法 100% 确认」（含出处）/
  Flyspeck 形式化目标与状态。
- E5 槽位（源自 S13–S14 旁白）：形式化验证作为协作工具的论证结构 / AlphaGeometry-Nature 2024 时间线 /
  「系统参加 IMO 题目」的精确表述 / 「银牌=分数换算」的可核对说明（须与 S16 口径一致）。
- 风险：叠加层遮挡主体或与字幕抢位 ⇒ 遵守既有字幕安全区（底部 5% 边距）；未核实数字不得入画。

---

## 3. 证据链（每条 proposal 的绑定关系）

`evidence_chain`（schema `revision-evidence-chain-v2`）逐条包含：

| 字段 | 内容 |
| --- | --- |
| `human_review` | 审片台账 `seq` + `decision` + `decided_by` + `decided_at` + `reason` + `provenance` + `entry_sha256`（链上锚） |
| `candidate` | 6-C 候选 `label`（C1/C4）+ `film` 路径 + `sha256` + `pi_gate_outcome` |
| `scene_window` | 受影响 scene 列表 + window + **该窗口的旁白原文**（`narration`） |
| `original_evidence` | 具体实证：豆腐块抽帧路径 / 当前素材 id 与名称 / 6-C 选材证据 / DQ-3 实测 / 原始叙述 |
| `clip_similarity_sufficient` | **false**（显式） |
| `why_not_clip` | 「CLIP 分数既不必要也不充分：依据是人审结论 + 成片实证」 |
| `not_provable_defer_guard` | 驱动决策为可证 REJECT；DEFER/UNKNOWN 不参与生成方案 |

示例（E2）：
`人审 REJECT(seq=2, entry_sha256=…) → C4(`e9c19c5dde00…`) → S05[245,300] + 旁白「还有一个容易被忽略的细节：Tymoczko…」
→ 原始证据：当前素材 `asset_432cd85be6f1`（IMO 合影）+ 6-C 选材证据 + 否决理由`。

---

## 4. 真实素材需求（不虚构 asset_id）

| 方案 | 是否需要**外部**新素材 | 需要自制内容 | `asset_id` | 素材规格（semantic_spec） | 来源（sourcing） |
| --- | --- | --- | --- | --- | --- |
| E1 | 否 | 否（字体参数） | `null` | — | 本机字体 `msyh.ttc`（与字幕链一致） |
| E2 | **是** | 否 | `null` | 可检视性争论：论文版面 / 逐字核对示意 / 概念图（禁 IMO 合影） | 人工检索 + 许可核验（PD / CC BY 优先） |
| E3 | **是** | 否 | `null` | Lean/mathlib：源码或页面截图 / proof state / 依赖图（禁 IMO 合影） | 人工检索 + 许可核验（开源项目页面/文档） |
| E4 | 否 | **是** | `null` | 自制信息面板（4 槽，逐项附来源） | SELF_CREATED（数字须附公开来源） |
| E5 | 否 | **是** | `null` | 自制信息面板（4 槽，逐项附来源） | SELF_CREATED |

`affected_scope.assets` 在 5 条中**全部为空**（不把任何素材 id 写进范围）；E2/E3 的
`forbidden_material` 明确列出 `asset_432cd85be6f1`（IMO 合影）及否决理由。

---

## 5. 风险与预期效果（摘要）

| 方案 | 预期效果（metric / direction / basis / assumption） | 主要风险 |
| --- | --- | --- |
| E1 | DQ-6 保持 PASS + 人工可读性：豆腐块 → 可读中文；basis = 豆腐块抽帧实证；assumption = 字体文件存在 | 字体缺失须原样保留；重复执行有损 ⇒ 幂等 |
| E2 | DQ-8 语义支撑由「无关」→「直接对应」（需复核）；basis = S05 旁白原文 | 许可不清/不可读 ⇒ 退回人工；跨批次重叠需人工确认 |
| E3 | DQ-8 同上；basis = S11 旁白原文 | 版权/商标；与 H3b/H5 跨批次重叠 |
| E4 | 210s 单镜由「无新增信息」→ ≥4 个可核对信息槽（时长不变）；basis = S08–S10 旁白 | 遮挡/字幕抢位；未核实数字不得入画 |
| E5 | 150s 单镜由「无新增信息」→ ≥4 个可核对信息槽（时长不变）；basis = S13–S14 旁白 | 同上；IMO 表述须与 S16 一致 |

所有方案 `expected_effect.not_guaranteed = true`：本层**不承诺**达成，需执行后由 PI/DQ + 人工复核判定。

---

## 6. 冲突检测（M5 口径）与跨批次重叠

- **6-E 内部冲突：0 对**（5 条方案在 scene / window / asset / target 上互不重叠）。
- **跨批次重叠（与 6-B/M4-5 已执行方案）：4 对，逐条显式声明**

| 新方案 | 已执行方案 | 重叠种类 | 共享镜头 |
| --- | --- | --- | --- |
| E1 | `H7-outro-card` | scene, target | S21 |
| E2 | `H5-semantic-mismatch-replace` | scene, window, target | S05 |
| E3 | `H3-batch2-next-longest` | scene | S11 |
| E3 | `H5-semantic-mismatch-replace` | scene, target | S11 |

处理方式：跨批次重叠是 **M5 已声明的已知边界**（门禁按批次判定）⇒ 本阶段**不静默绕过**，
逐条记录并要求**人工在批准时显式确认**；因本阶段不执行，故当前无阻断、无冲突态。

- **局部化自检**：E1 1 镜/0.0437、E2 1 镜/0.0359、E3 1 镜/0.0522、E4 3 镜/0.1371、E5 2 镜/0.0979
  ⇒ 全部 ≤6 镜且 ≤0.30（M3 上限）。

---

## 7. 交付物要求的逐项对照（含 baseline/candidate 完整性证明）

| 要求 | 结果 |
| --- | --- |
| 新 Proposal schema/登记 | ✅ `revision-proposal-v1` + 6-E 扩展字段（`round`／`evidence_chain`／`information_gain`／`material_requirement`）；登记链 5 条 `chain_ok=true` |
| 每条 proposal 的 evidence chain | ✅ §3（含人审 seq+entry_sha256、candidate sha256、scene/window+narration、原始 evidence） |
| 真实素材需求 | ✅ §4（E2/E3 需外部素材：semantic_spec + sourcing，无 asset_id；E4/E5 自制内容） |
| 风险与预期效果 | ✅ §5（逐条 metric/direction/basis/assumption + 风险） |
| truth set + regression | ✅ 真值集（冻结锚见 §8）+ 6-E 套件 67/67 + 完整回归（§8） |
| baseline 完整性 | ✅ 4 个 baseline ZIP `zip==manifest` 全 True；`baseline/` 未新增文件、**未新建 tag** |
| candidate 完整性 | ✅ C1–C4 sha256 与 6-C 记录**逐一相同**；沙箱产物目录逐字节未变（无新成片） |
| 未执行证明 | ✅ `executed_anything=false`、`ffmpeg_invocations=0`；DB/v9/timeline/字幕/素材未变；脚本静态无 ffmpeg 可执行路径与 `.mp4` 写目标 |

---

## 8. 完整回归

### 8.1 step2（`3a_regression_batch`）逐项执行 —— **含一次外部依赖项的失败与重跑（如实披露）**

| 项 | 值 |
| --- | --- |
| 执行器 | `docs/regression_2x/phase6e_batch_items.py`（argv/ITEMS 由 AST 解析同一份 `phase3a_regression_batch.py`，可 `--resume`） |
| 首轮 | 24 项跑完，**23 项符合预期**；`phase2e_failure_paths`（依赖真实外部 provider）**rc=1** |
| 失败细节 | 该用例 28/29 检查通过；唯一失败项为 `6 corrupt_download: 不进入正常 ffmpeg 渲染（无成片且 render BLOCKED）`——本轮真实检索**无候选**（`material_mode=external_configured_no_candidate`），故 `render_status=PENDING` 而非 `BLOCKED`；错误码检查（`ASSET_TRUNCATED` ×7）与「无成片」检查**均通过** |
| 处置 | **单独重跑该用例一次**：rc=0（165.7 s，`render=BLOCKED`，28/29 → 29/29 语义达成） |
| 最终汇总 | 移除该项旧记录后以 `--resume` 重跑其余 23 项，得到**完整 24 项**汇总（见下表数值） |
| 结论 | 该失败**非本阶段代码所致**（6-E **未改动任何 src**，见 §8.4 指纹增量），属**外部 provider 依赖的瞬时条件**；原始 rc 与处理过程在 `logs/phase6e_batch_items.json`、`logs/phase3a_phase2e_failure_paths.log`、`logs/phase6e_external_steps.json` 中均可复核，**未**改写为通过 |

### 8.2 电池（25 步）

| 项 | 值 |
| --- | --- |
| 步骤 | **25 步全部 rc=0**；`all_rc_zero_raw = True`；`rc_nonzero = []`；`rc_pending = []` |
| 各步秒数和 | 6357.8 s（含 step2 外部执行的 2629.9 s 与 step25 `unit_suites` 的 2540.4 s） |
| 外部步骤 | `3a_regression_batch` 由外部执行器完成（`executed=externally`，rc=0，`evidence=logs/phase6e_batch_items.json`） |
| 冻结日志 | 快照 **3527 文件** → 运行中改变 1 / 新增 0 / 删除 0 ⇒ **回拷逐字节恢复 = True（drift 0）** |

> **过程披露（冻结日志回拷的性质）**：电池在启动时对 `logs/` 取快照、结束时把快照回拷，
> 因此“快照之后写入 `logs/` 的文件”会被还原。本轮我曾先修正 `phase6e_batch_items.json` 与
> `phase6e_external_steps.json` 再跑电池，结果被回拷还原；最终改为**正确的顺序**——
> 先修正批次汇总与外部记录、再让电池**重新取快照**、最后重算汇总。
> 现汇总为 `全部 rc=0（原始）: True`，且回拷为 no-op（改变 1 为本报告自身在 `logs/` 外，属正常）。

### 8.3 step25 `unit_suites` 与 6-E 新套件

- **60 个套件全部 rc=0**（6-C 期 59 → 6-E 新增 `tests/directorial_round2_test.py` ⇒ 60）。
- 6-E 新套件 `directorial_round2_test`：**67/67 通过**（`SKIP=[]`）。
- 受影响套件（单跑）：`directorial_batch_test` 78/78、`execution_reliability_test` 75/75、
  `execution_truth_test` 45/45、`maintenance_fixes_test` 30/30、`dq_truth_test` 122/122 均 rc=0。

### 8.4 代码指纹与「本阶段未改源码」

| 阶段 | 文件数 | aggregate sha256(前 16) |
| --- | --- | --- |
| 6-B/M5 | 414 | `d639f3147cc0f6e2` |
| 6-C | 416 | `0ed48a81069c8213` |
| **6-E** | **418** | **`ace1148eee9d96d9`** |

6-C → 6-E 增量：**变化 0**、**新增 2**（`tests/directorial_round2_test.py`、
`tests/fixtures/directorial_round2_truth_v1.json`）、**删除 0**。

> ⇒ **可核验证据**：6-E **未修改任何源码文件**（`src/**` 零变化），因此本轮批次中出现的
> `phase2e_failure_paths` 失败**不可能**由本阶段引入；该失败为外部 provider 瞬时依赖（§8.1）。

### 8.5 6-E 真值集

`tests/fixtures/directorial_round2_truth_v1.json`，冻结锚见 `logs/phase6e_truth_freeze.json`
（T0b 断言一致）。内容含：审片期望（6 条）、proposal 期望（5 条）、禁止素材规则、无虚构 asset_id 规则、
CLIP 非充分依据规则、信息增量规则、冲突与跨批次重叠期望、局部化期望、保留记录期望、
不执行规则、DEFER 守卫与边界声明。

---

## 9. 已知边界

1. **本阶段不求解**：只登记方案；E1–E5 **全部未批准、未执行**，因此其效果（含 DQ-8 语义达成、信息增量是否足够）
   一律**未经实测**，报告中的 `expected_effect` 均标 `not_guaranteed=true`。
2. **E2/E3 依赖人工供料**：两条方案需要人工检索 + 许可核验的**新素材**；在素材提供并经真实校验前，
   它们不可执行（本层亦不检索、不下载、不写 asset_id）。
3. **E4/E5 依赖来源可查**：自制信息面板中的每个数字/断言必须附公开来源；**无法核实的数字不得入画** ⇒
   若人工无法给出可信来源，该信息槽应留空或改为纯定性表述（宁缺勿造）。
4. **跨批次重叠仍是 M5 已知边界**（4 对，见 §6）：M5 门禁按批次判定；本阶段以显式声明 + 人工批准时确认处置，
   **未**实现跨批次历史足迹比对。
5. **跨进程无锁**（M5 遗留）未涉及：本阶段无执行路径，故该边界不影响本轮结论，但也**未**被解决。
6. **E1 修复方式为"显式字体文件"**，属渲染参数修正；若目标环境无 `msyh.ttc`，须原样保留并回报人工
   （方案已写入该 fail-closed 要求）。
7. **H1/H6/H4/H2 状态未变**：6-B/M3 的 H1/H6 仍未批准、H4 仍需人工重新批准、H2 仍需合格新素材；
   本轮**未**对它们生成新方案（不在 6-E 范围内）。
8. **未验证项**：C1–C4 的其它潜在质量问题（例如长镜节奏、镜头推进幅度等）**未**在本轮系统性扫描；
   本轮只处理人审明确列出的 6 项。
9. **DPR（豆腐块）只在片尾卡出现**：E1 的抽帧证据来自 t≈1500s 的 C1 成片；未逐帧扫描 C1–C4 全部
   卡片/叠加区域 ⇒ 若其它位置也存在字形问题，需另立方案。
10. **审片台账为人工结论的机械记录**：`decided_by="human:director(6-E)"` 是**自陈**身份（非密码学认证），
    与 M2/M4/M5/6-C 的同类声明一致。
11. **未做 promotion、未改动任何既有产物**：C1–C4、v9、DB、timeline、字幕、素材、PI 定义与阈值均未变；
    `baseline/` 未新增文件、无新 tag。

---

## 10. 结论

### 10.1 覆盖要求逐条对照

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 修复 C1/C4 片尾卡豆腐块字体 | **已登记方案**（E1） | 只读抽帧实证豆腐块（`_outro_card_probe.png`）+ 根因（drawtext 无 CJK 字体）+ 修复参数（`fontfile=msyh.ttc`） |
| 2 | aS05 禁止继续用 IMO 合影，提出与「可检视性争论」直接相关的差异化视觉 | **已登记方案**（E2） | `semantic_spec`（论文版面/逐字核对/概念图）+ `forbidden_material` 显式禁 IMO |
| 3 | aS11 禁止继续用 IMO 合影，提出与 Lean/mathlib/形式化证明直接相关的视觉 | **已登记方案**（E3） | `semantic_spec`（Lean 源码/mathlib 页面/proof state/依赖图）+ 显式禁 IMO |
| 4 | 480–690s 开普勒炮弹堆 210s 长镜：真正增加信息量的局部方案，禁止仅 punch-in | **已登记方案**（E4） | `punch_in_only_forbidden=true` + 4 个可核对信息槽 + 每数字附来源 + 宁缺勿造 |
| 5 | 850–1000s IMO 合影 150s 长镜：真正增加信息量的局部方案 | **已登记方案**（E5） | 同上（4 槽：论证结构/时间线/精确表述/分数换算说明） |
| 6 | 保留 aS18 成功替换，不重复生成无必要方案 | **满足** | `retention-record-v1`（`verified_positive_keep`，人审 ACCEPT，`no_proposal_generated=true`）；无任何 proposal 以 S18 为目标 |

### 10.2 硬约束逐条对照

| 约束 | 状态 | 证据 |
| --- | --- | --- |
| 每条 proposal 绑定人审结论 / candidate / scene-window / 原始 evidence | **满足** | `evidence_chain`（T1 逐条校验），含人审 `entry_sha256` 与 candidate `sha256` |
| 禁止继续使用被否决的 IMO 合影（aS05/aS11） | **满足** | E2/E3 的 `semantic_spec` 写明禁止 + `forbidden_material` 列出 `asset_432cd85be6f1` |
| 「提高 CLIP 相似度」不得单独作为充分依据 | **满足** | 5 条 `clip_similarity_sufficient=false` + `why_not_clip`；`expected_effect.basis` 未出现 CLIP 字样 |
| 新素材只声明 semantic_spec + sourcing，不得虚构 asset_id | **满足** | `asset_id` 全为 `null`；`affected_scope.assets` 全为空；E2/E3 提供 spec+sourcing |
| 方案必须增加实际信息量或明确视觉叙事功能 | **满足** | E1 可读文字；E2/E3 与论点直接对应的差异化视觉；E4/E5 4 个可核对信息槽 |
| 不执行、不渲染、不修改 C1–C4 / v9 / DB / timeline / 字幕 / 素材 | **满足** | `executed_anything=false`、`ffmpeg_invocations=0`、沙箱产物目录未变、C1–C4 sha 未变、DB/v9 未变（T9） |
| 不修改 PI-1～PI-6 | **满足** | 指纹增量仅含新增测试/证据脚本（见 §8）；未触碰 `core/integrity.py` |
| DEFER/UNKNOWN 不得转成确定性修改 | **满足** | 驱动决策全为可证 REJECT；负对照：不可证项调用 `make_proposal` 抛 `DEFER_MUST_NOT_BECOME_CHANGE`（T8） |
| 保持 M3 局部化限制与 M5 冲突检测 | **满足** | 逐条 ≤6 镜 / ≤0.30；6-E 内部 0 冲突；跨批次重叠 4 对显式声明（T2/T6） |
| 不进入 M4/M5 执行 | **满足** | 本阶段无执行器调用、无审批记录（仅有审片台账与方案登记） |

### 10.3 判定

> **6-E（Evidence-Grounded Directorial Revision Round 2）= PASS（登记完成，等待人工批准）。**
>
> - 6 项覆盖要求**全部**落实为 5 条已登记 Proposal + 1 条保留记录；
> - 每条方案绑定**完整证据链**（人审决策 → candidate → scene/window+narration → 原始证据），
>   并经 M3 局部化校验与 M5 冲突检测（内部 0 冲突、跨批次重叠 4 对显式声明）；
> - **未执行任何修改**：C1–C4、v9、DB、timeline、字幕、素材、PI 定义与阈值**均未变**；未新建 baseline/tag；
> - §9 的 11 项边界**不**计入 PASS，其中第 2/3 项（人工供料、来源可查）是**执行前**必须由人工补齐的输入；
>
> **所有方案状态为 `PROPOSED_AWAITING_HUMAN_APPROVAL`（`approved=false`、`executed=false`）。**

**STOP —— 等待人工批准（APPROVE/REJECT 逐条），本阶段不执行、不渲染、不进入 6-C 之后的任何执行步骤。**
