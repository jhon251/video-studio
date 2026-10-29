# 审计报告：项目 `p_96efdc03e1aa`（GLM5.3flash 声明的逐条核验）

> **审计性质**：**只读**复核。全部结论来自 DB（`mode=ro`）、项目产物、媒体文件哈希与**独立复测**
> （ffprobe / ebur128 / 逐镜头抽帧相关 / 4-B / 5-A / 5-D / Judge）。
> **判定口径**：`VERIFIED`（有直接证据）/ `PARTIAL`（部分成立或需推断）/ `FAIL`（与实测不符）/ `OPEN`（无法判定，如实留白）。
> 审计脚本：`docs/regression_2x/audit_p96efdc{,_b,_c,_d,_e,_f,_g}.py`；原始输出见 `logs/audit_p96efdc_*.json`。
> **审计未修改任何项目数据**（全部连接 `mode=ro`，仅新增 `docs/regression_2x/logs/` 下的审计日志）。

## 0. 项目事实基线（审计实测）

| 项 | 实测 |
|---|---|
| 项目 | `p_96efdc03e1aa`「如果 AI 证明了人类无法理解的数学，人类数学家还有意义吗？AI」（status=ACTIVE） |
| 规模 | 任务 40 个；产物 43 个；事件 **479**；decision **125**（其中 `selection_override` **21**）；changelog **121**（21 条 selection + 100 条 claim） |
| 任务链 | retrieval v1–v6（7 个任务）+ render v1–v7（7 个任务） |
| 成片 | 7 个 `.mp4`（v1/v2/v4/v6/v7 成功；v3 BLOCKED；v5 PENDING） |
| 最终成片 | `t_898378f6b0f8_draft.mp4`：49,660,354 B，sha256 `3f3f0c010d178e41…`，**1532.0 s**，h264 1920×1080（37,775 帧）+ aac 24 kHz |
| 最终时间轴 | **21/21 镜头**全部有素材、全部 `selection_source="human_review"`，使用 **4 个素材**（每镜头候选池 **7** 个） |
| attribution | `a_5cd116b383a3`：21 条 ↔ 21 镜头 **1:1**，`sha256` 与磁盘 **0 处不符**，`restricted_or_unknown_in_film=[]` |
| 许可 | 外部素材 1 张（`PUBLIC_DOMAIN`/`FREE_ATTRIBUTION` 级清）；本地 ingest 3 张（`UNKNOWN`，按设计不受门禁约束，见 KNOWN_ISSUES #6） |

## 1. GLM 声明的逐条核验

| # | GLM 声明 | 判定 | 证据 / 差异 |
|---|---|---|---|
| 1 | "v5 完整成功：21/21 上屏、帧核验 0 失败、响度 −16.1 LUFS 达标" | **PARTIAL** | 帧核验 21/21、0 失败、−16.1 LUFS 在 **v4/v6/v7** 成立；但 **DB 的 v5 (`t_a881aee95cf3`) 是 `PENDING`**（`ASSET_INSUFFICIENT`：分配素材未出现在其镜头窗口内）。**版本号与 DB 不一致**（其"v5/v6/v7"≈ DB 的 v4/v5/v6/v7 之一），需以 DB 为准 |
| 2 | "自动选材是噪声匹配（棋类照片散布在数学章节）" | **VERIFIED** | 事件 `#101514` 明确记录根因：聚合词簇在 Commons 跨语言伪匹配（`Appel/Haken` → 荷兰语 *haken*＝钩织）；v2/v6 自动时间轴的确用到 `asset_cfae038f6106`（国际象棋奥赛男队）、`asset_bd383463dbb9`（女队）等 |
| 3 | "retrieval v6（纳入本地领域素材）→ 20 个候选（含 3 个领域素材、新下载），mp3/txt 会被后缀过滤" | **VERIFIED** | `t_a32ee7dc5760` / 产物 `a_71f77918bc8a`：`material_mode=mixed`、**候选 20**（wikimedia 5 + 本地 15）；含四色定理图、球堆、邮票；本地候选里确有 `narration.mp3`/`seg_*.mp3`/`narration.txt`（**实际未被选入任何镜头**，与"后缀过滤"一致） |
| 4 | "render v6 在帧核验失败：富化池引入的哈希名图片自动选中后，竖图 cover-crop 导致相关性不足" | **VERIFIED** | DB v5 render `t_a881aee95cf3` = `PENDING` + `[ASSET_INSUFFICIENT] {"reason": "分配素材未出现在其镜头窗口内"}`（正是帧核验失败路径） |
| 5 | "离线测量 6 个干净候选裁剪后相关性：MGB/棋类/邮票 PASS，四色图 0.129、球堆 0.294 FAIL" | **PARTIAL**（当前状态可验，历史数值不可复现） | 现状：四色图/球堆已被裁剪为 **1920×1080（AR 1.778）**，独立复测裁剪后相关 **≈1.0**；原始 0.129/0.294 无法复现（文件已被替换）；逻辑上可复算（竖图 cover-crop 会裁掉大部分内容） |
| 6 | "删除污染候选池的哈希名缓存图（可重新下载，证据已留在检索产物中）" | **PARTIAL** | 删除**有记录**：事件 `#101631 OPERATOR_POOL_CLEANUP`（`removed_cache_files=11`，`human_confirmed`）。**但**：① 历史检索产物 `a_609ea7b3c895`/`a_71f77918bc8a` 中仍有 **13 条**候选指向已不存在的文件 → 这些候选**只剩元数据、字节不可复核**；② `media/external/.index.json` 仍登记这些已删文件（缓存索引陈旧，下次检索可能命中"缓存"却无文件） |
| 7 | "对 2 张问题素材中心裁剪到 16:9（元数据含编辑前后 sha）" | **PARTIAL** | "裁剪 2 张"**VERIFIED**：四色图与球堆的 mtime 同为 `09-21 16:30:50`，均为 1920×1080/AR 1.778。"编辑前后 sha" **不是显式字段**，但**可间接还原**：ingest 索引 `a_5990c53da05a` 记录的是**原始 sha**（四色图 `2d8be8beea9c…`、球堆 `a3eec8aee3a3…`、邮票 `03d1791e0d8b…`），而资产/时间轴/attribution 记录的是**当前 sha**（`30dd89a16713…`/`3f0b94a3f2ac…`/`23e71bc8a864…`） → 需人工比对才能得出"编辑前后" |
| 8 | 渲染 v7 成功、帧核验全过、每镜头 7 候选、四色图/邮票自动命中 S03/S04 | **VERIFIED（候选数）** | v7 时间轴每镜头候选 **7** ✓；v6(=DB v6 `t_1500d9fbac31`) 自动版时间轴先命中领域素材，随后 v7 由人工改写为 4 素材方案；"四色图/邮票命中 S03/S04"在 DB v6 自动版可查见（v7 中 S03=四色图、S04=邮票**同样成立**，但来源是人工决定） |
| 9 | "review: semantics 1 MATCH/20 UNKNOWN" | **FAIL（数值不符）** | 实测 4-B：**MATCH=2 / MISMATCH=0 / UNKNOWN=19**（S02、S03 为 MATCH）。差异原因可能是当时针对的是另一版时间轴 |
| 10 | "执行 21 个人工选材决定（全部记录理由）" | **VERIFIED** | `decisions`：21 条 `selection_override`，`made_by` 全为 `human:operator`，`state=approved`，理由长度 16–49 字；`changelog` 对应 21 条 `human_confirmed=1`；覆盖 **21/21** 镜头 |
| 11 | "最终渲染成功：assembly=SUCCEEDED，21/21 镜头全部由人工选定的 4 张领域素材上屏" | **VERIFIED** | v7 `t_898378f6b0f8`：21/21 `human_review` + `human_selection{decision_id,decided_by,reason}`；使用 4 素材（MGB×5、四色图×6、邮票×3、球堆×7）；attribution 1:1；**独立抽帧复测 21/21 通过**（相关 0.77–1.00，argmax 全部命中） |

## 2. 独立复测（不依赖 GLM 的叙述）

| 项 | 实测 | 结论 |
|---|---|---|
| 容器/流 | `mov,mp4` / h264 1920×1080 37,775 帧 + aac 24 kHz | 正常 |
| 时长契约 | 时间轴 1532.0 s == 成片 1532.0 s，`video_duration_ok=true` | 通过 |
| 独立响度（ffmpeg ebur128） | **I = −16.1 LUFS、TP = −2.5 dBFS** | 与渲染记录**完全一致**，落在契约（−16±1 / ≤−1.5 dBTP）内 |
| 逐镜头抽帧（21 镜，各 1 帧中点，48×48 灰度 Pearson） | **21/21 通过**，`want` 0.7723–1.0，argmax 全部命中该镜头所选素材 | 与渲染自检（`frame_pearson_48x48`、21 检查/0 失败）一致 |
| 4-B 语义 | MATCH 2 / MISMATCH 0 / UNKNOWN 19 | 词表粗糙导致 UNKNOWN 偏多（如实） |
| **逐镜头多模态（本项目现场重跑 4-B/5-A/5-D + Judge J0–J6 融合）** | 4-B：MATCH 2/UNKNOWN 19；5-A：MATCH 1/**MISMATCH 3**/UNKNOWN 17；5-D：MATCH 1/**MISMATCH 2**/UNKNOWN 18；**最终：MATCH 1（S03）/ MISMATCH 2（S05、S11）/ UNKNOWN 18** | 18 个 UNKNOWN 中 **14 个是 `JUDGE_UNKNOWN_DOMAIN`**（旁白推不出期望语义域，即 KNOWN_ISSUES #23/#43 的词典覆盖限制），**不是**素材错误 |
| 2 个 MISMATCH（S05、S11）的性质 | S05 期望域 `geography_nature`、S11 期望域 `computing_device`（由 4-E 检索词典回退推导）；对应素材分别是四色定理图、球堆图 → CLIP 认为更像 `document_text`/`art_culture` | **属"域标签口径"分歧，非"放错图"**：同两镜的抽帧相关为 **0.996 / 0.973**，画面确为人工选定素材。判定为**待人工复核项**（建议按 J3 语义如实标记） |
| S18（第 18 镜） | 5-A 判 MISMATCH，但 5-D 报结构性 UNKNOWN → Judge 取 **`JUDGE_STRUCTURAL_UNKNOWN`**（J1 优先级） | 规则优先级按设计生效（结构性证据 > 语义分歧） |
| 稳定性 | 21 镜帧间一致性 0.906–1.0（S12/S16/S17/S18/S19/S20 因长镜头 + 烧录字幕略低） | 全部 `STABLE`、无 `TEMPORAL_SPLIT` |
| 素材文件 ↔ 时间轴/attribution sha | **0 处不符**、0 缺失 | 台账自洽 |
| 许可门禁 | `restricted_or_unknown_in_film=[]`；外部素材许可已清；本地素材按设计不门禁 | 合规 |

## 3. 审计发现（按严重度）

| 级别 | 发现 | 证据 | 影响 / 建议 |
|---|---|---|---|
| **中** | **被删缓存文件在历史检索产物中留下 13 条悬空引用**（`a_609ea7b3c895`、`a_71f77918bc8a`），字节不可再复核 | 审计 E §13d；事件 `#101631`（`removed_cache_files=11`） | 历史检索证据**部分不可复算**；建议：删除时在事件里写"受影响产物 id + 候选 id"，或把候选元数据快照另存（当前事件只记数量与理由） |
| **中** | **`media/external/.index.json` 陈旧**：仍登记已删的 11 个缓存文件（如 `5e990ebc…jpg`、`6ef2190fef07…jpg`） | 审计 D §13c + `.index.json` 内容 | 下次检索可能"缓存命中但文件不存在"→ 需清索引或让 provider 缓存校验文件存在性 |
| **中** | **ingest 索引（`a_5990c53da05a`）与磁盘 sha 不一致 3 处**（四色图/球堆：已由人工裁剪解释；**邮票 `03d1791e0d8b…` → `23e71bc8a864…` 未被"裁剪 2 张"的声明覆盖**，且 mtime 未变） | 审计 G §24 + mtime 取证 | 邮票的 sha 变化**原因不明**（可能是重新下载/替换）；建议补齐该文件的变更说明，或在流程上禁止绕过 ingest 替换素材 |
| **低** | 素材**原地编辑**（中心裁剪）缺失显式的"编辑前/后 sha + 操作者 + 理由"字段：只能靠 ingest 索引与当前 sha 比对推断 | 同上 | 建议：把素材编辑做成**可审计的一等操作**（记录 original_sha/edited_sha/tool/operator/decision_id），而不是靠旁证 |
| **低** | 事件流里有 3 类"人工修复"动作（`OPERATOR_REWIRE_FIX`、`OPERATOR_SUPERSEDE_DUPLICATE`、`OPERATOR_POOL_CLEANUP`）绕过常规任务链直接改状态 | 审计 C §11（`#101565`/`#101593`/`#101631`） | 均已 `human_confirmed` 且带理由（可追溯），但属**运维旁路**；建议在 RUNBOOK 里固化其使用条件与必填字段 |
| **低** | 渲染 v3 `BLOCKED`（ffmpeg RENDER_FAILED）、v5 `PENDING`（帧核验失败）留在任务链中未显式终结为 FAILED | 审计 A §2/§3 | 不影响交付（v7 成功），但"PENDING 未终结"会让状态统计失真；建议运维明确把废弃分支置为 FAILED/SUPERSEDED |

## 4. 未发现问题的项（正面结论）

- 最终成片**内容与旁白/人工选定一致**：21/21 抽帧独立复测通过、argmax 全对（无错配、无占位图）；
- attribution ↔ 时间轴 **1:1**、sha 全对、许可合规、`restricted_or_unknown_in_film=[]`；
- 人工选定**全部来自该镜头候选池**、许可已清、理由齐备（21/21）；
- 响度契约、时长契约独立复测通过；
- **跨项目完整性**：审计对象 `p_f4b466a4a024`（我方 5-F 工作对象）在 5-E 快照 DB 与当前 DB 之间
  **删除 0 / 改写 0**（tasks/artifacts/decisions/changelog/events）→ 本项目审计与 GLM 的工作**未污染** 5-F 的既有证据链。

## 5. 审计结论

GLM5.3flash 的叙述**主干成立**：噪声匹配的根因、富化候选池、帧核验失败、删缓存、裁剪两张、21 条人工选定、
最终 21/21 人工选定素材上屏 —— **均有 DB/产物/独立复测证据支持**。
但有 **3 处必须记录的偏差**：① 版本号与 DB 不一致（其"v5 成功"对应 DB v4/v6/v7，而 DB v5 实为 PENDING）；
② "semantics 1 MATCH/20 UNKNOWN" 实测为 **2 MATCH/19 UNKNOWN**；③ 素材编辑的"前后 sha"**不是显式元数据**，
只能由 ingest 索引与当前文件比对推断，且**邮票的 sha 变化未被其声明覆盖**（OPEN）。
另有 2 项**中等**完整性发现（悬空候选引用、缓存索引陈旧）建议纳入后续修复。

**独立多模态复核补充**：本项目成片在 4-B/5-A/5-D + Judge 下为
`MATCH 1 / MISMATCH 2 / UNKNOWN 18`，其中 18 个 UNKNOWN 的 14 个源于"旁白推不出期望域"（词典覆盖限制），
2 个 MISMATCH 属"域标签口径分歧"（抽帧相关 0.973–0.996，画面确为人工选定素材）。
**结论**：人工选材在**内容层**（画面是否为目标素材）**全部成立**（21/21 抽帧复测 + corr 0.77–1.0），
自动化多模态层给出的是**语义域对齐**上的保守/分歧结论，与人审结论不矛盾，可作为复核线索。
