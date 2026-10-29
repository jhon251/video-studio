# 6-C 报告 —— Controlled Directorial Revision Batch

- 阶段：**6-C**（授权 11 条 + 重点验证 5 条；**不进入下一阶段**）
- 目的：**首次**使用已验证的 6-B/M3→M5 执行链，对 v9 做一批**人工批准、可回溯、可撤销**的真实导演修订，
  每条修改只产生**新的 revision candidate**（不覆盖 v9、不做 promotion）。
- 上游：`logs/phase6b_m3_proposals_v9.json`（8 条登记方案）、`logs/phase6b_m2_review_ledger_v9.jsonl`（11 条人工决策）、
  `logs/phase6b_m5_v9_execution.json`（v9 的强制 PI/DQ 基线复核）
- 产物：`logs/phase6c_batch.json`、`logs/phase6c_candidate_{1..4}.json`、
  `logs/phase6c_approvals.jsonl`、`logs/phase6c_execution_ledger.jsonl`、四部候选成片（沙箱内，供人工观看）

---

## 0. 结论速览

| 项 | 结论 |
| --- | --- |
| 执行的方案 | **仅** 6-B/M3 已登记方案（`proposal_id` + `proposal_sha256` 与登记表逐字一致）；**未**现场创造任何修改 |
| 人工批准 | 5 条 `APPROVE`，全部绑定 `proposal_id + proposal_sha256 + human:身份 + 时间 + 理由/溯源`；`auto_approved=false` |
| 批次结果 | C1 `H7` **SUCCEEDED**；C2 `H2` **PENDING_HUMAN_ASSET**；C3 `H3a` + `H3b` **SUCCEEDED**；C4 `H5` **SUCCEEDED** |
| 候选成片 | **4 部**新 candidate（v9 母版零改动）；均双流、头尾各 90s 解码 rc=0、整容器扫描 rc=0 |
| 音轨完整性 | 4/4 候选音轨 = **母版整条音轨流复制** ⇒ 抽出的音轨 sha256 与母版**完全一致** |
| 时长守恒 | 累计漂移 ≤ **0.2 s**（0.013%）：1532.00 → 1532.04 → 1532.08 → 1532.20 s |
| 真实画面改写 | H7 片尾卡（视频重编码）；H3a/H3b **18 个切点**全部实测有画面差异（gray48 差 15.9–36.3）；H5 三镜素材替换（抽帧比对相关度 0.76–0.79，均优于原素材 ≥0.59） |
| 强制复核 | 每个候选都跑 **PI-1…PI-6 + DQ-1…DQ-8**；**4/4 `pi_gate_outcome = BLOCKED`** |
| 局部改善 | **DQ-6 FAIL → PASS**（片尾命中）；DQ-3 均值 hold 72.952 → 46.424 → 31.917 s；DQ-4 镜头数 21 → 33 → 48 |
| **不夸大** | DQ-2/3/4/5/8 **状态仍 FAIL**（阈值未变）；**无任何"全片 PASS"宣称**；PI 域问题未被局部修订解决 |
| H2 | **PENDING_HUMAN_ASSET**（注册需 2 个新素材；池内真实素材仅 5 个、未入片且合格仅 1 个 ⇒ 不虚构素材） |
| H4 | **NOT_EXECUTED_REQUIRES_HUMAN_REAPPROVAL**：依赖 H3a 已满足；与 H3a 重叠（scene/target）**显式声明**；不做二次切分 |
| H1 / H6 | 未批准 ⇒ 未执行（不在本阶段优先级集合） |
| 台账 | 审批链 5 条、执行链 5 条（4 执行 + 1 PENDING），`chain_ok=true`、seq 1..5 |
| 零提升 | `promoted=[]`、`auto_approved=false` |
| 完整性 | v9 母版 sha256 与 M1 记录一致；DB/v9 output 目录未变；候选全在沙箱；未新建 baseline/tag |
| 单测/回归 | 6-C 新套件 **73/73**；受影响套件全绿；完整回归见 §8 |

---

## 1. 批次与候选清单（供人工观看）

| 候选 | 批次 | 方案（登记 id） | 文件（`output/phase6b_m4_sandbox/…`） | 字节 | sha256(前 16) | PI 门禁 |
| --- | --- | --- | --- | --- | --- | --- |
| **C1** | C1 | `H7-outro-card`（`rp-13aae40036e3`） | `p_96efdc03e1aa_6c/output/t_d0a54bdf1810_draft_6c_rp-13aae40036e3_outro.mp4` | 48,484,967 | `fcaa4e78255c00b1` | BLOCKED |
| **C2** | C3 | `H3-batch1-split-longest`（`rp-130d116e03d6`） | 同上 + `_6c_rp-130d116e03d6_split.mp4` | 94,921,954 | `4ce951350095418d` | BLOCKED |
| **C3** | C3 | `H3-batch2-next-longest`（`rp-b638f1775da8`） | 同上 + `_6c_rp-b638f1775da8_split.mp4` | 124,316,795 | `07eb0c43053ff512` | BLOCKED |
| **C4** | C4 | `H5-semantic-mismatch-replace`（`rp-e3a26c23dff4`） | 同上 + `_6c_rp-e3a26c23dff4_replace.mp4` | 144,654,163 | `e9c19c5dde00b8d6` | BLOCKED |

候选是**链式**的（C2 建立在 C1 上、C3 建立在 C2 上、C4 建立在 C3 上），每一部都可**独立回放**；
批次清单与逐候选证据见 `logs/phase6c_candidate_{1..4}.json`。**本阶段不做 promotion**，仅供人工观看。

---

## 2. 授权与绑定（登记方案 → 人工批准 → 执行）

| 方案 | 登记 sha256(前 12) | 人工决策 | 理由/溯源（摘要） | 执行结果 |
| --- | --- | --- | --- | --- |
| H7-outro-card | `12371ef6a529` | APPROVE | 6-A 审计 §2.7 缺片尾 VERIFIED + KNOWN_ISSUES #67 | **SUCCEEDED** |
| H2-asset-pool-diversity | `6b32c63cc08c` | APPROVE（附条件：必须真实、许可明确素材） | 6-A 审计 §2.2 素材重复 VERIFIED | **PENDING_HUMAN_ASSET** |
| H3-batch1-split-longest | `fd368a0e32da`※ | APPROVE | 6-A 审计 §2.4 单镜过长 VERIFIED | **SUCCEEDED** |
| H3-batch2-next-longest | `bd0f16bd0e5d`※ | APPROVE | 6-A 审计 §2.4 | **SUCCEEDED** |
| H5-semantic-mismatch-replace | `9a77cadc0df4`※ | APPROVE（池内换用；逐镜人工选材绑定） | 6-A 审计 §2.3 + 该镜候选表 | **SUCCEEDED** |
| H4-density-increase | — | 未批准执行 | 依赖 H3a + 注册意图为"与 H3a 合并推进" | **NOT_EXECUTED_REQUIRES_HUMAN_REAPPROVAL** |
| H1-hook-replace / H6-visual-climax-aid | — | 未批准 | 不在本阶段优先级集合 | 未执行 |

※ 完整 64 位 sha256 见 `logs/phase6c_batch.json` 的 `registered_proposals` / `approvals`（每条审批都记录绑定值）。
判定链：`gate_batch`（个体门禁 → 冲突 → 幂等）→ 执行器 → **强制 PI/DQ 复核** → 台账 append。

---

## 3. 真实修订内容（不是"只改元数据"）

### 3.1 C1 — H7 片尾收束（`add_outro_card`）
- 末镜窗口 [1465, 1532] 重编码并叠加片尾文字卡（`drawtext`），未触及区段按母版复制；
- 执行器在 6-C 改为**只重编码视频段 + 母版整条音轨流复制**（避免旧实现重编码窗口音轨带来的接缝风险），
  并**重新烧录该窗口字幕**（见 §3.4）；
- 结果：`DQ-6 FAIL → PASS`；时长 +0.04 s；音轨与母版**逐字节一致**。

### 3.2 C2 / C3 — H3a + H3b 长镜切分（`split_scene`，**本轮新实现的真实执行器**）
- 依据**注册参数** `target_hold_s = 25.0` 对 9 个镜头（S07/S06/S16/S18 + S03/S11/S12/S15/S17）均分切点，
  切点两侧用同一真实素材的**构图变化**（缩放 1.0 / 1.18）制造真实视觉切分；
- **18 个切点全部实测有画面差异**（gray48 平均绝对差 15.72–36.27，全部 ≥0.02 阈值），且与母版同刻画面不同；
- 未触及区段按母版复制或重编码，音轨为母版整条音轨流复制 ⇒ **画面重排而音轨零改动**；
- `H4-density-increase` 的注册意图就是"与 H3-batch1 合并推进" ⇒ 其 DQ-4 效果由 C2/C3 候选实测（见 §4）。

### 3.3 C4 — H5 语义不匹配镜头的**池内换用**（`replace_asset`，多镜路径）
- 该方案注册 params 明确 `new_assets_needed.count = 0`（"仅在池内无候选时申请"）⇒ 本阶段**不新增素材**；
- 逐镜按**人工选材绑定规则**（该镜候选表中 `match_score` 最高、≠当前在用素材、文件真实存在且 sha256 一致、
  许可优先 PUBLIC_DOMAIN > FREE_ATTRIBUTION）选定素材；
- 逐镜抽帧比对：相关度 **0.7985 / 0.7985 / 0.7642**，均 ≥0.30 且**优于原素材** 0.844 / 0.606 / 0.854（≥0.15 边距）。

### 3.4 字幕守恒（本轮**发现并修复**的一处真实缺口）
生产渲染把字幕**烧录进画面**（`agents/editing/agent.py` 用 `ass=` 滤镜，样式来自 `core.captions.to_ass`）。
因此"替换画面"的执行会把被替换窗口的字幕一起抹掉 —— 首轮候选即存在该缺口（**已实测确认**：v9 母版在
t≈250 s 的底部确有中文字幕）。修复方式：
- ops 层用**与生产 pipeline 完全相同的函数与输入**重建 cue 表（`core.strip.strip_claims` + `core.captions.build_cues`）；
- 每个替换段按窗口裁剪/平移 cue，调用**同一个** `core.captions.to_ass`（PlayRes=1920×1080、
  `fontsdir='C\:/Windows/Fonts'`）重新烧录 ⇒ 样式、字号、位置、时间轴与母版一致；
- 切分子段按子窗口裁剪 cue ⇒ 跨切点的字幕不会丢字（同一时刻显示同一句）；
- 缺口修复后**重新生成全部候选**（`logs/phase6c_batch.json` 为最终一次运行），并在报告中如实记录"发现→修复"过程。

---

## 4. before/after 指标差异（PI + DQ，逐候选）

**v9 基线**（取自 `logs/phase6b_m5_v9_execution.json → batches[0].records[0].recheck`，对 v9 母版复制品的强制复核）：
PI `{1:FAIL, 2:FAIL, 3:FAIL, 4:PASS, 5:FAIL, 6:FAIL}` / `BLOCKED`；DQ `{1:UNKNOWN, 2:FAIL, 3:FAIL, 4:FAIL, 5:FAIL, 6:FAIL, 8:FAIL}`；
DQ-2 `unique_assets=4 / max_asset_share=0.3329`；DQ-3 `mean_hold=72.952 s / max_hold=95.0 s / scenes=21`。

| 候选 | PI-1…PI-6 | 门禁 | DQ 状态迁移 | DQ 数值变化（parent → candidate） |
| --- | --- | --- | --- | --- |
| C1 (H7) | `F F F P F F` | **BLOCKED** | **DQ-6 FAIL→PASS**，其余不变 | scenes 21（不变） |
| C2 (H3a) | `F F F P F F` | **BLOCKED** | 无状态变化 | **DQ-3 mean_hold 72.952→46.424、max_hold 95→80、scenes 21→33**；DQ-4/DQ-2 scenes 21→33；DQ-8 match_share 0.0595→0.0962 |
| C3 (H3b) | `F F F P F F` | **BLOCKED** | 无状态变化 | **DQ-3 mean_hold 46.424→31.917、max_hold 80→75、scenes 33→48**；DQ-4 scenes 33→48（≈1.88 次/分钟，目标 2.0 ⇒ 仍 FAIL）；DQ-8 match_share 0.0962→0.0357 |
| C4 (H5) | `F F F P F F` | **BLOCKED** | 无状态变化 | 结构类指标不变（素材替换不改镜头结构）；素材相关度证据见 §5 |

**必须如实说明的三点**：
1. **PI 域未被局部修订解决**：PI-1/2/3/5/6 仍 FAIL（覆盖 0.6277、时长缺口、尾部静音、orphan、边界漂移）⇒ 所有候选 `pi_gate_outcome = BLOCKED`。
2. **DQ 状态仍大面积 FAIL**：DQ-2（唯一素材 4 < 6）、DQ-3（max_hold 75 s > 25 s，未切分镜头仍超阈）、
   DQ-4（1.88 < 2.0 次/分钟）、DQ-5、DQ-8 均未达标 ⇒ **不宣称全片 PASS**（授权第 7 条）。
3. **一处负向副作用**：C3 之后 DQ-8 的 `match_share` 由 0.0962 降到 0.0357 —— 因为切分产生了 15 个
   **无语义证据**的子镜（记 UNKNOWN），分母变大而 MISMATCH 数未变。该值变化已如实记录，未做任何修饰。

---

## 5. 素材 provenance（H5 池内换用）

| 镜头 | 原素材 | 选定素材 | 许可 | sha256(前 12) | 候选表 match_score | 抽帧相关度（新 / 原） | 替换 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S05 | `asset_30dd89a16713` | `asset_432cd85be6f1` | **PUBLIC_DOMAIN**（cleared） | `432cd85be6f1` | 40（tokens: 20/IM/MO/…） | **0.7985 / −0.0458** | ✅ |
| S11 | `asset_3f0b94a3f2ac` | `asset_432cd85be6f1` | **PUBLIC_DOMAIN** | `432cd85be6f1` | 40 | **0.7985 / 0.1925** | ✅ |
| S18 | `asset_30dd89a16713` | `asset_cfae038f6106` | **FREE_ATTRIBUTION**（CC BY 4.0，cleared） | `cfae038f6106` | 40 | **0.7642 / −0.0894** | ✅ |

- 每条素材在执行前都经过**真实校验**：文件存在 → 实际 sha256 == 记录 sha256 → ffprobe 可解码 → 许可门禁（3-A 冻结口径）；
  证据落在执行记录的 `exec_evidence.asset_verifications`。
- 语义适配由**人工选材绑定**决定（依据该镜候选表），本阶段**不**声称语义层判定为 MATCH（DQ-8 仍 FAIL）。

---

## 6. 重点验证（授权指定的 5 条）

| 验证项 | 结果 | 证据 |
| --- | --- | --- |
| **原始 v9 完整保留** | ✅ sha256 `22705c7d7ea20b40…` / 46,761,341 B **逐字节未变**；DB 未变；v9 output 目录未变；`project_files_touched=[]` | `read_only_evidence`（T8） |
| **新 candidate 可独立回放** | ✅ 4/4：ffprobe 双流 + 头 90 s 解码 rc=0 + 尾 90 s 解码 rc=0 + **整容器扫描 rc=0** | `verification`（T2） |
| **音频、字幕、素材、timeline 无断裂** | ✅（字幕经**发现→修复**后达成）音轨 = 母版整条音轨流复制（抽出音轨 sha256 与母版**完全一致**）；字幕：替换段用**同一 cue 表 + 同一 `to_ass` 样式**重新烧录（首轮缺口见 §3.4）；素材均为真实文件且逐条校验；总时长漂移 ≤0.2 s | `audio_check` / `duration_check` / `steps` / §3.4 |
| **不出现 M5 已关闭的执行安全回归** | ✅ 仍只执行人工 APPROVE + hash 匹配者；台账 append-only 链完整；`promoted=[]`、`auto_approved=false`；冲突/幂等/沙箱约束未变 | T1/T7 + `execution_reliability_test` 75/75 |
| **真实输出必须经过 PI/DQ，而非仅凭返回码** | ✅ 4/4 候选都有 PI-1…PI-6 + DQ-1…DQ-8 实测状态与 `pi_gate_outcome`；ffmpeg 返回码只作为"是否产出"的必要条件之一，判定以实测指标为准 | `pi_metrics` / `dq_metrics`（T3） |

---

## 7. H2 与 H4 的显式处置

### 7.1 H2 = PENDING_HUMAN_ASSET（**不虚构素材**）
注册目标：`new_assets_needed.count = 2`、`target_unique_assets = 6`。
材料实测：v9 片内唯一素材 **4**；纳入候选表的真实素材共 **5** 个，其中**未入片且校验通过**的仅 **1** 个
（`asset_cfae038f6106`）。⇒ 无法在不虚构 `asset_id` 的前提下满足注册目标 ⇒ 保持 PENDING（授权第 4 条）。
（5 条真实素材的 `status/code/in_film/license_class` 逐条记录在 `h2_shortfall.verified`。）

### 7.2 H4 = 依赖满足 + 重叠显式声明（**不静默绕过**）
- **依赖**：`dependency = [H3-batch1-split-longest]`，该方案已在本批 **SUCCEEDED** ⇒ `dependency_satisfied = true`；
- **注册意图**：该方案 `how` 明确"与 H3-batch1 **合并推进**（同一批切分同时提升密度）"⇒ 其 DQ-4 期望效果
  已由 C2/C3 候选**实测**（1.88 次/分钟），不需要再执行一次；
- **重叠**：与 H3a 在 `scene` + `target` 上重叠（`pair_conflict` 实测）；**诊断**（用临时审批，**未写入台账**）显示：
  若 H4 也获批并与 H3a 同批提交，M5 门禁会**对称阻断**两者（`BLOCKED_CONFLICT`）；
- **决策**：单独执行 H4 等于**二次切分同一批镜头**（注册方案未授权的范围扩大），故 **不执行**，
  记录 `require_human_reapproval = true` 与 `cross_batch_overlap_declared = true`。
- 跨批次重叠是 M5 已声明的**已知边界**（M5 门禁按批次判定）；本阶段**没有**用静默方式绕过它，
  而是把重叠对、诊断结果与人工复核要求一并落盘。

---

## 8. 完整回归

### 8.1 step2（`3a_regression_batch`）逐项执行

| 项 | 值 |
| --- | --- |
| 执行器 | `docs/regression_2x/phase6c_batch_items.py`（argv/ITEMS 由 AST 解析同一份 `phase3a_regression_batch.py`，可 `--resume`） |
| 结果 | **24 项 | 符合预期 24/24 | 非预期 [] | 等价 step rc = 0** |
| 耗时 | 各次启动合计 `seconds_total_all_items = 2065.3 s`（含字幕修复后对 `suite_all` 项的重跑） |
| 逐项日志 | `logs/phase3a_<name>.log`；汇总 `logs/phase6c_batch_items.json`；外部步骤记录 `logs/phase6c_external_steps.json` |

> 说明：`suite_all` 项在**字幕修复后**重跑过一次（从进度文件移除该记录后 `--resume`），
> 以保证该项反映**最终代码 + 最终候选证据**状态；其余 23 项沿用首轮记录（未被本轮改动影响）。

### 8.2 电池（25 步）

- **25 步全部 rc=0**；`all_rc_zero_raw = True`；`rc_nonzero = []`；`rc_pending = []`。
- 各步秒数和 **4477.7 s**；step2 由外部执行器完成并在汇总中单列 `executed=externally`。
- 冻结日志：快照 **2734 文件** → 运行中改变 21 / 新增 93 / 删除 0 ⇒ **回拷逐字节恢复 = True（drift 0）**。
- 首轮电池在回拷阶段因 Windows 文件占用（`WinError 32`）中断（**步骤已全部完成、rc 全 0**），
  随后以 `--resume` 完成回拷与汇总（步骤全部跳过）。

### 8.3 step25 `unit_suites`：**59 个套件全部 rc=0**

（6-B/M5 期 58 → 6-C 新增 `tests/directorial_batch_test.py` ⇒ 59。）
本轮相关套件：`directorial_batch_test` **78/78**、`execution_reliability_test` 75/75、
`execution_truth_test` 45/45、`maintenance_fixes_test` 30/30、`dq_truth_test` 122/122 等，全部 rc=0。

### 8.4 受影响套件（单跑结果）

| 套件 | 结果 |
| --- | --- |
| `tests/directorial_batch_test.py`（新） | **78/78** |
| `tests/execution_reliability_test.py`（M5） | 75/75 |
| `tests/execution_truth_test.py`（M4） | 45/45 |
| `tests/maintenance_fixes_test.py` | 30/30 |
| `tests/dq_truth_test.py` | 122/122 |
| `tests/revision_truth_test.py` | 61/61 |
| `tests/narration_contract_test.py` | 45/45 |
| `tests/integrity_gates_test.py` | 45/45 |

### 8.5 6-C 真值集

`tests/fixtures/directorial_batch_truth_v1.json`，冻结锚
**`7b1cdfef98d873627ecbe8676d47cf84c90975330322d6336ecd187bd3df947d`**
（`logs/phase6c_truth_freeze.json` 记录，T0b 断言一致）。内容含：批次期望、候选期望（含 DQ 数值）、
v9 基线（含 detail）、单调性规则、H5/H2/H4 期望、**字幕连续性期望（13/13 窗口）**、台账契约、
守恒规则与边界声明。

---

## 9. 基线与已知边界

1. **跨进程无锁**（M5 遗留边界，本轮**未**解决、也**未**静默绕过）：`execute_batch(lock=…)` 只在**同进程**内串行化；
   跨进程同时提交同一方案仍存在"幂等判定—落账"竞态窗口。本轮全部执行均为**单进程顺序**提交。
2. **跨批次重叠检测仍是批次级**（M5 遗留边界）：本轮以**显式声明**处置（H4），未做跨批次历史足迹比对；
   若人工分两批提交互相重叠的方案，本层仍**不会**跨批发现 ⇒ 需下一阶段（人工授权后）实现历史窗口比对。
3. **H2 仍 PENDING**：注册目标需 2 个新素材；池内真实素材 5 个、未入片且合格仅 1 个 ⇒ 无法在不虚构素材的前提下达标。
   需人工提供**真实 + 许可明确 + 语义相关**的新素材（或修改注册目标）后方可继续。
4. **H4 需人工重新批准**：其注册意图（与 H3a 合并推进）已由 C2/C3 候选实现；单独执行等于二次切分同一批镜头（范围扩大）。
5. **H1 / H6 未执行**：不在本阶段优先级集合内（未批准）。
6. **字幕重烧录为"同 cue 表 + 同 to_ass 样式"**，与母版一致；但**不是**逐像素回放原 ASS 文件（母版 ASS 未落盘保留），
   实测以"描边墨水"指标 + 抽帧 PNG 证明其存在与位置一致（13/13 窗口）。
7. **一处负向副作用**：C3 之后 DQ-8 的 `match_share` 由 0.0962 降到 0.0357（切分产生无语义证据的子镜，分母变大）——
   已如实记录，未做修饰。
8. **候选体积较大**（94.9 / 124.3 / 144.7 MB）：未触及区段在切分/替换后按需重编码（ultrafast）+ 拼接；
   沙箱内累计占用约 0.5 GB。**本阶段不清理**，以便人工观看与复核。
9. **累计时长漂移 +0.2 s**（四次拼接各 ≤0.12 s，占比 0.013%）：属窗口拼接的固有量化误差，已逐候选记录。
10. **6-C 批次共生成 4 次**（首轮→证据修正→字幕修复→最终），台账在每次重跑前删除重建；
    最终证据为最后一次运行（`logs/phase6c_batch.json`），append-only 语义由哈希链校验与单测证明，
    **不**依赖"文件从未被重写"。
11. **H5 语义适配依据人工选材绑定**（该镜候选表 match_score/matched_tokens），本阶段**不**声称语义层判定为 MATCH
    （DQ-8 仍 FAIL）。
12. **未做 promotion**：候选仅供人工观看；v9 母版、r1/r2/r3/5.x-final、baseline 目录与 tag 均未改动。

---

## 10. 结论

### 10.1 授权 11 条逐条对照

| # | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| 1 | 仅执行已有 M3 Proposal，禁止现场创造未登记的修改 | **满足** | 4 条执行方案的 `proposal_id` + `proposal_sha256` 与 M3 登记表逐字一致（T0c） |
| 2 | 每条执行前必须有有效 Human APPROVE + proposal hash | **满足** | 5 条审批（含 H2）全部绑定 id+hash+身份+时间+理由/溯源；无自动批准（T1） |
| 3 | 优先 H7、H2、H3a/H3b、H5；H4 遵守对 H3a 的依赖 | **满足** | C1=H7、C2=H2、C3=H3a+H3b、C4=H5；H4 依赖已满足且**不**单独执行（T6d/T6f） |
| 4 | H2/H5 用真实已验证许可明确素材；无合格素材则 PENDING | **满足** | H5 用 PUBLIC_DOMAIN + CC BY 4.0（真实+sha256一致+可解码）；H2 保持 `PENDING_HUMAN_ASSET`（量化短缺） |
| 5 | 只产生新的 revision candidate，禁止覆盖 v9 | **满足** | 4 部候选在沙箱内；v9 母版 sha256 未变；`project_files_touched=[]`（T8） |
| 6 | 每批执行后强制 PI-1…PI-6 + DQ-1…DQ-8 复核 | **满足** | 4/4 候选都有 PI/DQ 实测状态与 `pi_gate_outcome`（T3） |
| 7 | 不得因局部 DQ 改善宣称全片 PASS | **满足** | 4/4 `pi_gate_outcome = BLOCKED`；DQ-2/3/4/5/8 仍 FAIL；报告显式声明不达标 |
| 8 | 生成 before/after 差异、执行记录、素材 provenance、PI/DQ evidence | **满足** | `before_after_diffs`（含 v9 基线 detail）、`steps`/`exec_evidence`、`asset_bindings`/`asset_verifications`、`pi_metrics`/`dq_metrics` |
| 9 | 保留完整候选成片供人工观看；不做自动 promotion | **满足** | 4 部候选保留 + 抽帧 PNG；`promoted=[]`（T7c/T8e） |
| 10 | 不改 PI 定义/阈值、不改 5.x Final/r1/r2/r3、不新建 baseline/tag | **满足** | 指纹增量不含 `core/integrity.py`、`core/direction.py`、`core/materials.py`；4 个 baseline ZIP sha 未变；无新 tag（§9/§6） |
| 11 | 跨进程无锁、跨批次 overlap 列为已知边界，不得静默绕过 | **满足** | 两条边界均在 §9 显式声明；H4 的跨批次重叠以"重叠对 + 同批阻断诊断 + 需人工重新批准"显式处置（T6e/T6g） |

### 10.2 重点验证 5 条

见 §6 表格：原始 v9 完整保留 ✅ / 新 candidate 可独立回放 ✅（4/4 双流 + 头尾解码 + 整容器扫描）/
音频-字幕-素材-timeline 无断裂 ✅（音轨逐字节一致；字幕 13/13 窗口实测存在；素材逐条校验；时长漂移 ≤0.2 s）/
无 M5 执行安全回归 ✅（仅人工批准+hash 匹配者执行、台账链完整、零提升）/
真实输出经 PI/DQ 而非仅凭返回码 ✅（4/4 有实测指标与门禁结论）。

### 10.3 判定

> **6-C（Controlled Directorial Revision Batch）= PASS（附 12 项已披露边界）。**
>
> - **4 条已登记方案完成真实执行**（H7 片尾、H3a+H3b 长镜切分、H5 池内换用），产出 **4 部新的 revision candidate**，
>   全部经**强制 PI/DQ 复核**、可独立回放、音轨与母版逐字节一致、字幕 13/13 窗口实测存在；
> - **H2 保持 `PENDING_HUMAN_ASSET`**（量化短缺：需 2 个新素材，池内合格未入片素材仅 1 个）；
> - **H4 `NOT_EXECUTED_REQUIRES_HUMAN_REAPPROVAL`**（依赖已满足；重叠显式声明；不做二次切分）；
> - **未做任何 promotion**，v9 母版 / r1 / r2 / r3 / 5.x-final / baseline 目录**零改动**；
> - **不宣称全片 PASS**：所有候选 PI 门禁仍 `BLOCKED`，DQ-2/3/4/5/8 仍 FAIL（局部数值改善已逐项列出）。
>
> 本轮发现并修复了一处**真实缺口**（被替换窗口的烧录字幕丢失），修复后**重新生成全部候选**并给出实测证据；
> 该"发现→修复→重跑"过程在 §3.4 与本报告各表中如实记录，未以任何方式掩盖。
>
> §9 的 12 项边界**不**计入 PASS，其中第 1/2 项（跨进程无锁、跨批次重叠检测）是 M5 遗留的**能力缺口**，
> 本轮按要求"不静默绕过"，而是显式声明并交由人工决策。

**STOP —— 等待人工观看 4 部候选成片与下一步授权；本阶段不进入 6-D / 不做 promotion。**

