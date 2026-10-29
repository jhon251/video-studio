# 5.x Phase 5-F 报告：多模态证据 Judge 收敛与最终边界验证（只读裁决层）

> **授权（逐字遵守）**：只做 5-F，**完成后 STOP，不进入 5.x Final**。目标：确定 4-B/5-A/5-D 多模态证据
> 在最终系统中的**职责边界**，**不追求提高 MATCH 率**。
> ① 在冻结 14 例真值集上建立最终 Judge/证据融合规则；② 4-B/5-A/5-D 保持**独立原始证据**、不覆盖；
> ③ 明确 MATCH/MISMATCH/UNKNOWN 的**最终决策条件、证据优先级、冲突处理**；④ **UNKNOWN 必须是合法最终结果**，
> 禁止通过调阈值减少 UNKNOWN；⑤ 不自动换材/选材/redo、不改时间轴、不写生产 DB；
> ⑥ 对 #43–#48 **逐项**判断（保留/解决/转入最终已知问题），不为 Final 强行解决；
> ⑦ 明确 R1–R6 哪些进最终产品、哪些仅作未来研究项；⑧ 全量回归 3-A～5-E，网络 PENDING 原状；
> ⑨ 输出最终多模态 DoD、报告、evidence.json、已知问题、新 baseline + manifest + SHA256；⑩ STOP。
>
> **授权基线**：`5.x-phase5e-baseline.zip` sha256
> `3934369a7f62e14ca93a08b58c24b898345e5f03ee0fe2d46a875fef5f4f2b57`（**与授权书逐字节一致**、
> ZIP 自洽、`verify_baseline` → **MATCH**）。
>
> **判定：PASS**（含 §8 登记的限制 #43–#50；未改任何判定逻辑与阈值，未伪造任何 PASS）

---

## 1. 最终 Judge / 证据融合规则（授权第 1、3 条）

**输入**：三层**独立**原始证据（不加工、不覆盖）
`4-B`（`verdict/rule`）、`5-A`（`verdict/code` + 相似度/边际/top-k）、`5-D`（`verdict/code/rule_id/confidence` + 逐帧证据）。

**输出**：最终 `MATCH/MISMATCH/UNKNOWN` + **理由码** + **命中规则** + **证据优先级位次** + 人读理由。

| 规则 | 条件（**先命中先返回**） | 最终结果 | 理由码 |
|---|---|---|---|
| **J0** | 所有层不可用（模型/解释器缺失、无帧、无证据） | `UNKNOWN` | `JUDGE_MODEL_UNAVAILABLE` / `JUDGE_NO_EVIDENCE` |
| **J1** | 5-D 报**结构性** UNKNOWN（`MMT_TEMPORAL_SPLIT` / `MMT_INSUFFICIENT_FRAMES` / `MMT_LOW_CONSISTENCY`） | `UNKNOWN` | `JUDGE_STRUCTURAL_UNKNOWN`（附 `propagated_code`） |
| **J2** | 同时存在 `MATCH` 与 `MISMATCH`（层间冲突） | `UNKNOWN` | `JUDGE_EVIDENCE_CONFLICT`（记录 `conflict`） |
| **J3** | 存在 `MISMATCH` 且无 `MATCH` | `MISMATCH` | `JUDGE_MISMATCH_FLAGGED`（记录 `flagged_by`） |
| **J4** | 全部可用层一致 `MATCH`（可用层 ≥ 2） | `MATCH` | `JUDGE_UNANIMOUS_MATCH` |
| **J5** | 仅 1 层可用且其判 `MATCH` | `UNKNOWN` | `JUDGE_INSUFFICIENT_LAYERS` |
| **J6** | 其余（全 UNKNOWN / 部分 UNKNOWN / 期望域缺失） | `UNKNOWN` | `JUDGE_ALL_UNKNOWN` / `JUDGE_PARTIAL_UNKNOWN` / `JUDGE_UNKNOWN_DOMAIN` |

**证据优先级（决策顺序，非"权威排序"）**：

| 位次 | 证据类别 | 规则 | 为什么 |
|---|---|---|---|
| 1 | **结构性证据**（5-D 时序/样本：镜头内切换、帧数不足、一致性不足） | J1 | 画面在时间轴上不是稳定状态时，任何语义判定都失去前提；**不可被 MATCH 覆盖** |
| 2 | **冲突**（任意两层对立） | J2 | 层间矛盾 = 证据不足以收敛 → 不选边、显式记录、交人工 |
| 3 | **错配**（任一层 MISMATCH） | J3 | 漏掉内容错配是**高代价错误**；flagging 是安全动作（人工会复核） |
| 4 | **一致 MATCH**（全层一致） | J4 | MATCH 是**断言**：必须所有可用证据层都不反对 |
| 5 | **无法收敛**（其余） | J0/J5/J6 | **UNKNOWN 是合法最终结果**：交人工或补证据，**禁止**靠调阈值消除 |

**冲突处理**：**不选边**。冲突时最终结果一律 `UNKNOWN` + `JUDGE_EVIDENCE_CONFLICT`，并在报告里记录
`{层: verdict}`（例如 `{4b: MATCH, 5d: MISMATCH}`）供人工判断——**不**用"多数票"或"高优先级层"强行裁决。

**UNKNOWN 的合法性（授权第 4 条）**：本层**没有任何阈值参数**（源码级证明：`mm_judge.py` 不含
`min_sim/min_vote_frac/min_stability_cos/split_cos/frames_per_scene/min_frames` 等 token），
因此**不存在"调阈值减少 UNKNOWN"的代码路径**；DoD **D7** 进一步要求「最终 UNKNOWN 数 ≥ 覆盖层下限」。

---

## 2. 在冻结真值集上的收敛结果（授权第 1、2 条）

`run.py mm-judge p_f4b466a4a024`（三层证据由 5-E 的**只读**校准流程取得；也可 `--from-calibration` 复用）。

| 用例 | 内容标签 | 4-B | 5-A | 5-D | **最终** | 规则 | 理由码 |
|---|---|---|---|---|---|---|---|
| T01 S04 真值 | MISMATCH | MISMATCH | MISMATCH | MISMATCH | **MISMATCH** | J3 | `JUDGE_MISMATCH_FLAGGED` |
| T02 S06 真值 | MISMATCH | MISMATCH | MISMATCH | MISMATCH | **MISMATCH** | J3 | `JUDGE_MISMATCH_FLAGGED` |
| T03 S01 v6 | MATCH | MATCH | MATCH | MATCH | **MATCH** | J4 | `JUDGE_UNANIMOUS_MATCH` |
| T04 S02 v6 | MATCH | MATCH | MATCH | MATCH | **MATCH** | J4 | `JUDGE_UNANIMOUS_MATCH` |
| T05 S04 v6 | MATCH | MATCH | MATCH | MATCH | **MATCH** | J4 | `JUDGE_UNANIMOUS_MATCH` |
| T06 S05 v6 | MATCH | MATCH | UNKNOWN | UNKNOWN | **UNKNOWN** | J6 | `JUDGE_PARTIAL_UNKNOWN` |
| T07 S06 front(v5) | MATCH | MATCH | MATCH | MATCH | **MATCH** | J4 | `JUDGE_UNANIMOUS_MATCH` |
| T08 S06 side(v6) | MATCH | MATCH | UNKNOWN | UNKNOWN | **UNKNOWN** | J6 | `JUDGE_PARTIAL_UNKNOWN` |
| T09 视角成对 | MATCH | — | — | — | （不产生三态） | — | 成对检查：`5d_margin_front_gt_side` ✔、`both_vote_unanimous` ✔ |
| T10 切图夹具 | MISMATCH | — | — | UNKNOWN(`MMT_TEMPORAL_SPLIT`) | **UNKNOWN** | J1 | `JUDGE_STRUCTURAL_UNKNOWN` |
| T11 静态对照 | UNCERTAIN | — | — | MISMATCH | **MISMATCH** | J3 | `JUDGE_MISMATCH_FLAGGED`（覆盖层只要求"不得 MATCH"） |
| T12 域缺失 | UNCERTAIN | — | UNKNOWN | UNKNOWN | **UNKNOWN** | J6 | `JUDGE_UNKNOWN_DOMAIN` |
| T13 模型不可用 | UNCERTAIN | — | UNKNOWN | UNKNOWN | **UNKNOWN** | J0 | `JUDGE_ALL_UNKNOWN`（层码 `MM_MODEL_MISSING`） |
| T14 帧数不足 | UNCERTAIN | — | — | UNKNOWN(`MMT_INSUFFICIENT_FRAMES`) | **UNKNOWN** | J1 | `JUDGE_STRUCTURAL_UNKNOWN` |

**结果：14/14 用例满足 Judge 真值（0 违例 / 0 未解决）；最终三态 `MATCH=4 / MISMATCH=3 / UNKNOWN=6`。**

**UNKNOWN 数（6）≥ 覆盖层下限（5）** → UNKNOWN 被**保留**为合法最终结果（授权第 4 条）：
T06/T08（内容正确但像素证据不足）、T10/T14（结构性：镜头内切换/帧数不足）、T12（期望域缺失）、T13（模型不可用）。
**MATCH 没有因为"想提高通过率"而被放宽**：S05/S06(side) 由 5-A 的 MATCH/UNKNOWN 收敛为 **最终 UNKNOWN**。

---

## 3. 三层职责边界（授权第 2、3 条）

| 组件 | 角色 | 看画面 | 负责 | **不**负责 |
|---|---|---|---|---|
| **4-B** 文本语义 | 文本语义权威（类别式规则，**无阈值**；真值钉定 `a_2ed5f41d6b58`） | ❌ | 文本↔素材语义一致性、真值回归、Judge 的文本侧票 | 画面内容判断；镜头内时序问题 |
| **5-A** 单帧多模态 | 像素语义第一层（CLIP 3 帧） | ✅ | 画面域 ↔ 旁白期望域一致性；与 5-D 交叉验证 | 镜头内时序/切换检测（样本少）；**单独断言 MATCH** |
| **5-D** 多帧/时序 | 像素语义 + 时序结构（CLIP 7 帧 + 帧间一致性 + 逐帧投票） | ✅ | 多帧一致性；**结构性 UNKNOWN 的唯一来源**；逐帧证据与边际分布 | **单独断言 MATCH**；自动换材/选材 |
| **5-F Judge** | 三层融合与**最终判定**（只读、零动作） | 读 5-A/5-D | 最终三态 + 理由码（J0–J6）+ 优先级 + 冲突处理 + DoD 核对 | 自动换材/选材/redo/改时间轴；写库/写产物；**调阈值** |

**独立性与不覆盖（机器可验证）**：`core/multimodal.py`、`core/mm_temporal.py`、`core/semantics.py`、
`core/lexicons/semantics_v1.json` 与冻结真值集在 5-F 结束后 sha256 与 **5-E 基线完全一致**；
重跑三层得到的判定与 5-C/5-D/5-E 冻结证据**逐镜头一致**（见 §5）。

---

## 4. 最终 DoD（授权第 9 条）

完整文档：`docs/regression_2x/PHASE5F_MULTIMODAL_DOD.md`。12 条**可度量**条款（布尔 + 证据指针），
本阶段报告 `dod_all_pass = true`：

| # | 条款 | 现状 |
|---|---|---|
| D1 | 三层证据独立且可单独复算 | ✅ |
| D2 | 三层默认关闭/只读，不写生产状态 | ✅ |
| D3 | 三层原始结果**不被覆盖**（模块/词表/真值集 sha256 与基线一致；重跑与冻结证据一致） | ✅ |
| D4 | 真值集 + Judge 覆盖层冻结、指纹双向钉定、覆盖度 fail-closed | ✅ |
| D5 | Judge 规则 J0–J6 显式 + 5 级优先级 + 冲突处理 | ✅ |
| D6 | 冻结 14 例上**逐例**满足 Judge 真值（0 违例 / 0 未解决） | ✅ |
| D7 | **UNKNOWN 合法**：最终 UNKNOWN ≥ 下限且无阈值调参路径 | ✅ |
| D8 | fail-closed 齐备（模型/解释器/帧/期望域/冲突/真值/覆盖度） | ✅ |
| D9 | 全量回归 3-A～5-E 通过且冻结证据零漂移 | ✅ |
| D10 | 已知限制逐项处置（#43–#48 + 新增 #49/#50） | ✅ |
| D11 | 不自动动作（只输出判定与理由） | ✅ |
| D12 | 交付物齐备（报告 + DoD + evidence.json + 已知问题 + baseline + SHA256） | ✅ |

---

## 5. 只读与"不覆盖"证明（授权第 2、5 条）

| 断言 | 结果 |
|---|---|
| DB 字节 + 五张表行数（tasks/artifacts/events/decisions/changelog）在 5-F 全部运行后未变 | **未变** |
| 项目生产文件（78 个，含 6 个成片）逐字节未变、未新增生产产物 | **未变** |
| 静态扫描：Judge 与三层均无写库/写产物/触发 redo/改时间轴的调用形态 | **通过** |
| Judge 源码**不含任何阈值参数**（不存在"调阈值减少 UNKNOWN"的路径） | **通过**（测试 G4） |
| 4-B/5-A/5-D 判定模块、词表、冻结真值集 sha256 与 **5-E 基线一致** | **全部一致**（测试 G5） |
| 现场重跑三层（live）与复用 5-E 冻结校准（`--from-calibration`）的最终判定**逐例一致** | **一致**（测试 D4） |
| 报告 `policy` 显式声明零动作 + 不调阈值 + 不覆盖 4-B/5-A/5-D 结果 | **声明并在测试中断言** |

---

## 6. #43–#48 逐项处置（授权第 6 条）

| 编号 | 内容 | **处置** | 理由 |
|---|---|---|---|
| **#43** | 真值集小且同质（14 例、单一静态素材项目） | **保留**（转入最终已知问题） | 现有素材范围内无法扩大；扩充需新素材与人工标注工时（R3，建议作为 Final 后第一优先项） |
| **#44** | "MATCH 精确率 = 1.0" 仅在该 14 例口径内成立 | **保留**（口径已限定） | 指标口径已写明；Judge 进一步降低 MATCH 宣称强度（全层一致），不会放大该结论 |
| **#45** | 5-A/5-D 对"内容正确但区分度不足"给 UNKNOWN | **解决**（口径固化） | 5-F 把它**提升为最终判据**（J6）：部分层 UNKNOWN → 最终 UNKNOWN。不再是"层的保守"，而是系统最终语义 |
| **#46** | 阈值敏感性（放宽 margin 会把 UNKNOWN 变 MATCH） | **解决**（禁止路径写死） | Judge 层**无阈值参数**，`thresholds_touched=false`；DoD D7 要求 UNKNOWN ≥ 下限，调阈值会直接破坏真值集 |
| **#47** | top-1 一致性只作解释性指标 | **保留**（未来研究项 R6） | 样本不足以支撑规则化；5-F 未将其纳入 Judge |
| **#48** | 5-E 真值集开发期修正三处夹具缺陷并重新定稿 | **解决**（留痕 + 双指纹钉定） | 初稿/定稿哈希均在 evidence 中留档；本阶段再次核验指纹一致 |

**新增登记**：**#49** Judge 是评估/裁决层、**未接入生产判定链**（默认关闭）→ `BY DESIGN`；
**#50** 最终 MATCH 需**全层一致**，因此 MATCH 数**低于** 5-A 单独判定（本项目 S05/S06 由 MATCH/UNKNOWN 收敛为 UNKNOWN）
→ `BY DESIGN`（授权明确：**不追求提高 MATCH 率**）。

---

## 7. R1–R6 处置（授权第 7 条，**均未在 5-F 实施**）

| 编号 | 建议 | **处置** | 理由 |
|---|---|---|---|
| **R1** | 字幕区域掩码后再算帧间一致性 | **未来研究项** | 触及 5-D 内部指标定义 → 需新授权 + v2 指标 + 全量回归 |
| **R2** | 候选的"成片抽帧口径"预测量 | **未来研究项** | 属新证据能力（5-B 侧），必须保持"只作证据、不驱动自动选材" |
| **R3** | 扩充真值集（多镜头/运动素材/更多项目） | **值得进入最终产品** | 纯评估、零行为风险；直接决定 #43/#44 的可信度边界（建议 Final 后第一优先项） |
| **R4** | 报告层区分 UNKNOWN 两种语义 | **值得进入最终产品** | 5-F 已在**理由码层**实现等价物（`J1/J0` = 结构性/环境；`J6` = 稳定不确定），生产报告沿用即可 |
| **R5** | S06 是否换回 front | **产品决策（非技术项）** | Judge 保持 UNKNOWN；若要 MATCH，必须走 4-C 人工决定 + redo + 复验（禁止自动换材） |
| **R6** | top-1 一致性作为解释性指标 | **值得进入最终产品（仅展示）** | 零判定风险；须标注"非判据、样本小"（#47） |

---

## 8. 已知限制（最终登记）

| 编号 | 内容 | 状态 |
|---|---|---|
| #43 / #44 | 真值集小且同质；精确率口径限于 14 例 | `LIMITATION`（转入最终已知问题） |
| #45 / #46 | 保守 UNKNOWN 已固化为最终判据；阈值改动路径被写死禁止 | `RESOLVED (5-F)` |
| #47 | top-1 一致性仅解释性（R6 仅展示） | `LIMITATION` |
| #48 | 真值集开发期修正已留痕并双指纹钉定 | `RESOLVED (5-F)` |
| **#49** | Judge 未接入生产判定链（默认关闭、只读裁决） | `BY DESIGN`（新增） |
| **#50** | 最终 MATCH 需全层一致 → MATCH 数低于 5-A 单独判定 | `BY DESIGN`（新增，不追求 MATCH 率） |

---

## 9. 交付物清单

| 交付物 | 路径 |
|---|---|
| 最终 Judge 内核 / 只读编排 / CLI | `src/video_studio/core/mm_judge.py`、`src/video_studio/ops/mm_judge.py`、`run.py mm-judge` |
| Judge 真值覆盖层（冻结） | `tests/fixtures/mm_judge_truth_v1.json`（sha256 `a6332858a94d4a7f…`） |
| 冻结真值集（5-E 继承） | `tests/fixtures/mm_truth_set_v1.json`（sha256 `7eb952f2797e180c…`） |
| 单元测试 | `tests/mm_judge_test.py`（**43/43**） |
| Judge 证据 | `docs/regression_2x/logs/phase5f_judge.json` |
| 证据汇编 | `docs/regression_2x/logs/phase5f_evidence.json`（**ALL_GREEN**） |
| 最终多模态 DoD | `docs/regression_2x/PHASE5F_MULTIMODAL_DOD.md` |
| 回归编排与输出 | `docs/regression_2x/phase5f_regression.py`、`logs/phase5f_rerun/**` |
| 基线 + manifest + SHA256 | 见 §11 |
| 测试与证据归档 | `snapshots/phase5f-tests-archive-20260917.zip`（sha256 见其 manifest） |

---

## 10. 回归结果（3-A～5-E）

**最终轮（2026-09-18，独占代理环境，GBK 口径）：25/25 步 rc=0，套件 46/46 rc=0，冻结日志恢复 = True，DRIFT 0。**

| 阶段 | rc | 备注 |
|---|---|---|
| 3a_real_chain | 0 | VERDICT PASS（16/16：A1–A6/B1–B3/C1–C3/D1–D4） |
| 3a_regression_batch | 0 | 24/24 子项（含 phase2e_failure_paths **29/29**、phase2e_real_provider 13/13、suite_all FAILED:[]） |
| 3b_audit / 3b_failure_paths | 0 | 只读审计通过 |
| 4ab/4c/4d/4e/4f/4g_evidence、4x_audit | 0 | 证据与审计全过（两次 API 运行逐字节一致 = True） |
| 5a/5b/5c_*（append_only/db/verify_film/failclosed/checkpoint） | 0 | db_writes=0、production_writes=0 |
| 5d_mm_temporal_test / 5d_frozen_check | 0 | 121.9s；收尾恢复 True |
| 5e_mm_quality_test / 5e_calibration | 0 | 390.2s / 189.0s |
| 5f_mm_judge_test / 5f_judge | 0 | 194.1s / 0.2s；DoD 12/12（dod_all_pass=true） |
| unit_suites | 0 | **46/46**（含 subprocess_encoding_test 6/6） |

过程记录（如实，详见 `PHASE5F_CONTINUE_20260918.md`）：5-F 电池共执行 4 轮——utf-8 轮 25/25 但编码套件 2 项 GBK 前置断言环境失败；GBK#1/#2 受 24/25 网络红项与调度并发影响；**最终轮在代理环境独占运行达 25/25**。旧 24/25 网络失败轮与本会话调度失误已在续作档完整留痕，未删除未伪装。

---

## 11. 基线

- 授权基线：`5.x-phase5e-baseline.zip`，sha256
  `3934369a7f62e14ca93a08b58c24b898345e5f03ee0fe2d46a875fef5f4f2b57`（**与授权书一致**、ZIP 自洽）。
- 本阶段基线：`5.x-phase5f-baseline.zip`
  sha256 `e4dd33ad427020250ae83fc3e53cabca6baf27fd1d5606e375264ca37c39dc4d`
  （378 文件 / 8,213,757 B 源 / 6,121,278 B zip）；`verify_baseline.py` → **MATCH**（missing 0 / drift 0）。
- 相对 5-E delta：**修改 3 / 新增 4 / 删除 0**（CHANGELOG.md、STATUS.md、src/video_studio/cli.py 修改；
  新增 core/mm_judge.py、ops/mm_judge.py、tests/fixtures/mm_judge_truth_v1.json、tests/mm_judge_test.py）——与授权预期一致。
- manifest：`baseline/baseline_manifest_5.x-phase5f-baseline.json`；快照：`snapshots/5.x-phase5f-20260917`。

---

## 12. 结论

**PASS**：5-F 在**不改动任何判定逻辑与阈值**的前提下，为多模态子系统确定了**最终职责边界**与**证据融合规则** ——
4-B（文本，不看画面）/ 5-A（单帧像素）/ 5-D（多帧 + 时序结构）三层**独立并存、互不覆盖**，
Judge 以 **J0–J6 显式规则 + 5 级证据优先级 + 不选边的冲突处理**给出最终三态；
在**冻结 14 例真值集**上**逐例满足** Judge 真值（0 违例 / 0 未解决），
最终 `MATCH=4 / MISMATCH=3 / **UNKNOWN=6**`，**UNKNOWN 被保留为合法最终结果**（≥ 覆盖层下限 5），
**MATCH 未因追求通过率而放宽**（需全层一致）；#43–#48 逐项处置完成（2 解决 / 3 保留 / 1 留痕解决），
R1–R6 给出进最终产品（R3/R4/R6）、未来研究项（R1/R2）与产品决策（R5）的明确判定；
全量回归 3-A～5-E 通过、冻结证据零漂移；最终 DoD 12/12 PASS。

**STOP（等待人工授权；不进入 5.x Final）**
