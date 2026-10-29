# 5.x Phase 5-E 报告：多模态证据质量校准与可解释性增强（只读评估层）

> **授权（逐字遵守）**：只做 5-E，**完成后 STOP，不进入 5-F/Final**。目标：在**不改变自动选材与既有判定逻辑**
> 的前提下，评估 5-A/5-D 多模态证据的**可靠性、边界与可解释性**。
> ① 冻结小型真值集（≥覆盖 S04/S05/S06、MATCH/MISMATCH/UNKNOWN、视角差异、时序切换）；
> ② 5-A 单帧 / 5-D 多帧 / 4-B 文本证据**并列**输出、不覆盖原结果；③ 分析 margin/top-k/投票/一致性/视角/阈值敏感性，
> **禁止为提高通过率调阈值**；④ 明确区分**模型证据 / 规则推断 / 工程阈值 / UNKNOWN**；
> ⑤ 不自动换材/选材/redo、不改时间轴、不写生产 DB；⑥ 真值缺失/模型不可用/证据冲突/样本不足必须 fail-closed；
> ⑦ 评估是否需要 5-F，**只提建议不实施**；⑧ 全量回归 3-A～5-D，网络 PENDING 保持原状；
> ⑨ 输出报告、真值集/校准证据、已知限制、evidence.json、新 baseline + manifest + SHA256；⑩ STOP。
>
> **授权基线**：`5.x-phase5d-baseline.zip` sha256
> `cab3324bad69bb56252cce7344372dff5fa90e6d980c030843e072019e2d73d8`（**与授权书逐字节一致**、
> ZIP 自洽、`verify_baseline` → **MATCH**）。
>
> **判定：PASS**（含 §9 如实登记的限制 #43–#48；未改任何阈值/判定逻辑，未伪造任何 PASS）

---

## 1. 冻结小型真值集（授权第 1 条）

`tests/fixtures/mm_truth_set_v1.json`（**冻结**，14 例）：

| 用例 | 素材 | 内容标签 | 覆盖 |
|---|---|---|---|
| T01 S04 真值产物 | `a_2ed5f41d6b58` | MISMATCH | S04 / MISMATCH / 规则推断 |
| T02 S06 真值产物 | `a_2ed5f41d6b58` | MISMATCH | S06 / MISMATCH |
| T03 S01 v6 清晰匹配 | `a_fa4716cffb26` | MATCH | S01 / 边界远 |
| T04 S02 v6 清晰匹配 | `a_fa4716cffb26` | MATCH | S02 / 边界远 |
| T05 S04 v6 人工修复后 | `a_fa4716cffb26` | MATCH | S04 / 边界近 |
| T06 S05 v6 边界 | `a_fa4716cffb26` | MATCH | S05 / 边界近 / UNKNOWN-by-design |
| T07 S06 front（v5） | `a_e369526c2f47` | MATCH | S06 / **视角 front** |
| T08 S06 side（v6） | `a_fa4716cffb26` | MATCH | S06 / **视角 side** / UNKNOWN-by-design |
| T09 视角成对（front vs side） | 两版 v5/v6 | MATCH | **视角差异**（要求 margin 降、两版均非 MISMATCH） |
| T10 镜头内切图夹具 | 受控生成 | MISMATCH | **时序切换**（要求 `UNKNOWN/MMT_TEMPORAL_SPLIT`） |
| T11 静态对照夹具 | 受控生成 | UNCERTAIN | **时序对照**（只要求不误报切换） |
| T12 期望域缺失探针 | v6 S01 + 无义旁白 | UNCERTAIN | fail-closed（`*_UNKNOWN_DOMAIN`） |
| T13 模型不可用探针 | 缺失模型目录 | UNCERTAIN | fail-closed（`*_MODEL_MISSING`） |
| T14 帧数不足探针 | v6 S06 + 2 帧 | UNCERTAIN | fail-closed（`MMT_INSUFFICIENT_FRAMES`） |

**每个用例包含**：`content_label`（人工/历史结论 —— 来自 4-B 真值钉定、4-C/5-C 人工决定记录，**不是模型输出**）
+ `content_label_provenance`（出处，缺则真值集非法）+ `expect.{allow, must_not, require_code_any,
require_not_code_any, require_stability}` + `covers`（覆盖度标签）。

**指纹钉定**：定稿 sha256 **`7eb952f2797e180cf85bd84236414caf878cb617c0bc885031ef423fef1dca9e`**，
写在 `core/mm_quality.py::TRUTH_SET_PIN`，由 `tests/mm_quality_test.py` A6 与 `logs/phase5e_evidence.json`
**双向核对**（改了真值集不更新指纹 → 立即失败）。
**开发期修正留痕**：首次校准运行暴露三处夹具缺陷（T11 过度约束语义、T12 旁白含词表命中词、T13 fault 名与实现不一致），
修正后重新定稿（初稿 `1a138555…` → 定稿 `7eb952f2…`），两版哈希均记入 `truth_set_history`；**定稿后未再修改**（#48）。

---

## 2. 三层并列评估（授权第 2 条：不覆盖原结果）

`run.py mm-quality p_f4b466a4a024` 对每个用例**同时**给出 4-B / 5-A / 5-D 的 verdict+code 与依据；
5-A/5-D 的报告与日志、4-B 的判定**均未被本层改写**（§7 证明）。

| 用例 | 内容标签 | 4-B | 5-A（3 帧） | 5-D（7 帧 + 时序） |
|---|---|---|---|---|
| T01 S04 真值 | MISMATCH | MISMATCH | MISMATCH | MISMATCH |
| T02 S06 真值 | MISMATCH | MISMATCH | MISMATCH | MISMATCH |
| T03 S01 v6 | MATCH | MATCH | MATCH | MATCH |
| T04 S02 v6 | MATCH | MATCH | MATCH | MATCH |
| T05 S04 v6 | MATCH | MATCH | MATCH | MATCH |
| T06 S05 v6 | MATCH | MATCH | **UNKNOWN**（`MM_AMBIGUOUS`） | **UNKNOWN**（`MMT_AMBIGUOUS`） |
| T07 S06 front（v5） | MATCH | MATCH | MATCH | MATCH |
| T08 S06 side（v6） | MATCH | MATCH | **UNKNOWN**（`MM_AMBIGUOUS`） | **UNKNOWN**（`MMT_AMBIGUOUS`） |
| T09 视角成对 | MATCH | — | — | 成对检查：margin(v5) > margin(v6) ✔、两版投票一致 ✔ |
| T10 切图夹具 | MISMATCH | — | — | **UNKNOWN**（`MMT_TEMPORAL_SPLIT`）✔ 要求 |
| T11 静态对照 | UNCERTAIN | — | — | MISMATCH（**不作语义断言**；稳定性 `STABLE` ✔） |
| T12 域缺失 | UNCERTAIN | — | UNKNOWN（`MM_UNKNOWN_DOMAIN`） | UNKNOWN（`MMT_UNKNOWN_DOMAIN`） |
| T13 模型不可用 | UNCERTAIN | — | UNKNOWN（`MM_MODEL_MISSING`） | UNKNOWN（`MM_MODEL_MISSING`） |
| T14 帧数不足 | UNCERTAIN | — | — | UNKNOWN（`MMT_INSUFFICIENT_FRAMES`） |

**结果：14/14 用例满足真值集要求（0 违例 / 0 UNRESOLVED / 0 层间冲突）。**

---

## 3. 可靠性指标（授权第 3 条前半：margin / top-k / 投票 / 一致性）

| 层 | 用例数 | 违例 | UNKNOWN | MATCH | MISMATCH | **MATCH 精确率** | MISMATCH 召回 | MATCH 召回 |
|---|---|---|---|---|---|---|---|---|
| 4-B（文本规则） | 8 | 0 | 0 | 6 | 2 | **1.0** | 1.0 | 1.0 |
| 5-A（3 帧） | 10 | 0 | 4 | 4 | 2 | **1.0** | 1.0 | 0.667 |
| 5-D（7 帧+时序） | 13 | 0 | 6 | 4 | 3 | **1.0** | 0.667 | 0.667 |

- **零误报**：三层都没有把内容为 MISMATCH 的用例判成 MATCH（`false_match_on_mismatch_cases = []`）；
- **5-A/5-D 的 UNKNOWN 只落在"内容为 MATCH 但证据弱"的 T06/T08**（保守，不是误判）；
- **5-D 的 MISMATCH 召回 0.667 不是漏判**：唯一"非 MISMATCH"的内容-MISMATCH 用例是 **T10（切图夹具）**，
  而该用例**要求**的输出正是 `UNKNOWN/MMT_TEMPORAL_SPLIT`（时序不稳定 → fail-closed 优先于语义判定）；
  这正是"规则优先级"与"召回"两个口径必须分开看的原因（**本报告以"用例是否满足真值集要求"为准**）。

**边界距离（离翻转还差多少）**：

| 用例 | 判定 | `sim − min_sim` | `\|边际\| − margin` | `投票 − 下限` | `一致性 − 下限` | 期望域 top-1? |
|---|---|---|---|---|---|---|
| T03 S01 | MATCH | +0.090 | **+0.040** | +0.40 | +0.250 | ✔ |
| T04 S02 | MATCH | +0.078 | **+0.070** | +0.40 | +0.250 | ✔ |
| T05 S04 | MATCH | +0.062 | **+0.008**（贴边） | +0.40 | +0.250 | ✔ |
| T07 S06 front | MATCH | +0.078 | **+0.055** | +0.40 | +0.225 | ✔ |
| T06 S05 | UNKNOWN | +0.036 | **−0.0029**（贴边） | +0.40 | +0.250 | ✔ |
| T08 S06 side | UNKNOWN | +0.025 | **−0.0139** | +0.40 | +0.219 | ✔ |
| T01 S04 真值 | MISMATCH | −0.015 | +0.038 | — | +0.250 | ✘（top-1=`wildlife`） |
| T02 S06 真值 | MISMATCH | +0.004 | +0.018 | — | +0.206 | ✘（top-1=`wildlife`） |

**top-k 分析**：全部**内容-MATCH** 用例（T03–T08）的期望域**都是 top-1**；而内容-MISMATCH 用例
（T01/T02 鲨鱼照）的 top-1 是 `wildlife`、期望域不在 top-1。**top-1 一致性与内容标签在本真值集上 100% 吻合**，
但样本小、且与 margin 规则高度相关 —— 因此**只作为解释性指标**（§8 R6），**未据此改任何规则**。

**投票与一致性**：本项目成片为静态素材，7 帧的 `vote_expected` 在全部用例上都是 **1.0**（逐帧 argmax 一致），
相邻帧余弦 `mean ≥ 0.969`、`min ≥ 0.814` → 全部 `STABLE`；因此**投票/一致性在本项目上不是判别瓶颈**，
真正的瓶颈是**域区分度（margin）**（与 5-D 报告 §5 一致）。

---

## 4. 阈值敏感性（授权第 3 条后半：**只披露，不调参**）

矩阵：`margin ∈ {−0.01, 0, +0.01, +0.02, +0.04}`、`min_stability_cos ∈ {−0.05, 0, +0.05}`
（**正数=更严、负数=更松**；5-E **不采纳**任何改动）。

| 用例 | 层 | 基线 | 翻转（阈值 → 结果） |
|---|---|---|---|
| T06 S05 | 5-A / 5-D | UNKNOWN | **margin −0.01 → MATCH**（放宽即"变好"→ 这正是不能靠调阈值的证据） |
| T05 S04 | 5-A / 5-D | MATCH | margin +0.01 / +0.02 / +0.04 → UNKNOWN |
| T02 S06 真值 | 5-A / 5-D | MISMATCH | margin +0.02 / +0.04 → UNKNOWN |
| T01 S04 真值 | 5-A / 5-D | MISMATCH | margin +0.04 → UNKNOWN |
| T03 S01 | 5-A / 5-D | MATCH | margin +0.04 → UNKNOWN |
| **T04 / T07 / T08 / T10 / T11 / T12 / T14** | — | — | **任何扰动都不翻转** |

- `min_stability_cos ±0.05` **对全部用例无影响**（所有镜头的一致性都远离该下限，最少高出 0.16）；
- **S06(side) 的 UNKNOWN 在任何扰动下都不翻转** → 该结论稳健（与 5-D §5 一致）；
- **收紧**只会把 MATCH/MISMATCH 变成 UNKNOWN（信息更少）；**放宽**会把 UNKNOWN 变成 MATCH（更激进）；
  两者都**未被采纳**。完整逐条记录见 `logs/phase5e_quality.json` → `sensitivity.rows`。

---

## 5. 证据分级与可解释性（授权第 4 条）

**四类证据显式区分**（`evidence_classes`，每条指标都带等级）：

| 等级 | 含义 | 字段数 | 例 |
|---|---|---|---|
| `MODEL_EVIDENCE` | 模型直接产出的数值 | 16 | 逐帧/聚合相似度、`argmax`、`top_k`、相邻帧余弦、投票占比 |
| `RULE_INFERENCE` | 规则推断出的结论 | 8 | `verdict`、`rule_id`、`reason`、`confidence`、`median_margin` |
| `ENGINEERING_THRESHOLD` | 人工设定的工程阈值 | 8 | `min_sim`、`margin`、`min_vote_frac`、`min_stability_cos`、`split_cos`、`frames_per_scene` |
| `UNKNOWN` | 无法判定/未登记（不猜） | 2 | `unresolved`、`unavailable` |

**每个用例都输出四段式可解释链**，例如 T08（S06 side）：

```
[MODEL_EVIDENCE]        帧数=7 期望相似度(中位/最小)=0.22486/0.224823 投票=1.0
                        一致性(mean/min)=0.96892/0.813934 top-k=[xr_device, vehicle, art_culture]
[ENGINEERING_THRESHOLD] min_sim=0.2 margin=0.02 min_vote_frac=0.6 min_stability_cos=0.75 split_cos=0.5
[RULE_INFERENCE]        输出 verdict=UNKNOWN code=MMT_AMBIGUOUS → 依据「边际中位数 0.0061 < 0.02」
[RULE_INFERENCE]        与真值集期望一致（该用例要求 UNKNOWN：内容正确但证据不足）
```

**UNKNOWN 的两种语义被显式区分**（本阶段新增口径，见 §8 R4）：
① **"稳定地判不出来"**（投票一致、无 split、仅边际不足 → `confidence=MEDIUM`，T06/T08）；
② **"环境/输入导致无法判定"**（模型不可用、帧数不足、期望域缺失 → `confidence=LOW`，T12/T13/T14）。

---

## 6. fail-closed（授权第 6 条）

| 触发 | 期望 | 实测 |
|---|---|---|
| 真值集缺失 / 非法 JSON | `MMQ_TRUTH_MISSING` / `MMQ_TRUTH_INVALID` | ✔（测试 A7/A8） |
| 覆盖度不足（删掉 S05 覆盖） | `MMQ_INSUFFICIENT_COVERAGE` | ✔（测试 A3） |
| 真值集被改动而指纹未更新 | 指纹核对失败 → 校准中止 | ✔（测试 A6 双向钉定） |
| 期望域推不出（旁白无词表命中） | `MM_UNKNOWN_DOMAIN` / `MMT_UNKNOWN_DOMAIN` | ✔（T12） |
| 模型不可用 | `MM_MODEL_MISSING`，**不得**出现 MATCH/MISMATCH | ✔（T13） |
| 帧数 < `min_frames` | `MMT_INSUFFICIENT_FRAMES` | ✔（T14） |
| 层执行异常 | 该层记 `layer_error` → 用例 `UNRESOLVED`（**不算通过**） | ✔（测试 B2） |
| 层间冲突（同例 MATCH 与 MISMATCH 并存） | `MMQ_EVIDENCE_CONFLICT` 显式记录 | ✔（测试 C2；本轮真实校准 0 冲突） |

**本轮真实校准**：`unresolved_cases=[]`、`violation_cases=[]`、`conflicts=[]`、`all_cases_resolved=true`。

---

## 7. 只读与"不覆盖"证明（授权第 5 条）

| 断言 | 结果 |
|---|---|
| DB 字节 + 五张表行数（tasks/artifacts/events/decisions/changelog）在全部运行后未变 | **未变** |
| 项目生产文件（78 个，含 6 个成片）逐字节未变、未新增生产产物 | **未变** |
| 静态扫描：校准层无写库/写产物/触发 redo/改阈值的调用形态 | **通过** |
| 4-B 模块与词表、5-A 模块、5-D 模块 sha256 与 **5-D 基线**一致 | **全部一致** |
| 校准读到的 5-A/5-D 判决与 5-C/5-D 阶段的**冻结证据**逐镜头一致（原结果未被覆盖） | **一致** |
| 报告 `policy` 显式声明 `writes_to_db=false`、`changes_thresholds=false`、`overwrites_4b/5a/5d_results=false`、`auto_select/auto_replace/auto_redo=false` | **声明并在测试中断言** |

---

## 8. 是否需要 5-F（授权第 7 条：**只提建议，不实施**）

| 编号 | 建议 | 为什么 | 成本 | 风险 | 本阶段是否实施 |
|---|---|---|---|---|---|
| **R1** | 字幕区域掩码后再算帧间一致性 | 整帧嵌入受烧录字幕影响（#38） | 中 | 改动 5-D 指标 → 需 v2 定义 + 全量回归 | **否** |
| **R2** | 候选的"成片抽帧口径"预测量 | 5-B 资产级打分 vs 5-A/5-D 成片级判定口径不一致（#33） | 中 | 属新证据，**不得**直接用于自动选材 | **否** |
| **R3** | 扩充真值集（多镜头/运动素材/更多项目） | 当前 14 例全部静态素材（#42/#43），不可外推 | 高 | 低（纯评估） | **否** |
| **R4** | 报告层强制区分 UNKNOWN 的两种语义 | "稳定不确定" 易被误读为"模型坏了"（§5） | 低 | 低（仅文案/字段） | **否** |
| **R5** | S06 是否换回 front（或换其它素材） | 5-C 后 S06 的 5-A/5-D 均为 UNKNOWN（稳定歧义） | 低 | 中：改变交付画面，**必须**人工决定 | **否** |
| **R6** | 把 **top-1 域一致性**作为**解释性指标**纳入报告 | 本真值集上 top-1 与内容标签 100% 吻合（§3） | 低 | **不得**作为判定规则（样本小、与 margin 相关） | **否** |

**结论**：5-F **不是**"让 S06 变 MATCH"的补丁；若要做，优先 **R4（低成本、纯解释）** 与 **R3（提高评估可信度）**；
**R1/R2** 触及 5-D/5-B 内部指标，属新能力，必须单独授权并重跑全部真值集与回归。

---

## 9. 已知限制（与 `KNOWN_ISSUES.md` #43–#48 对应）

| 编号 | 内容 |
|---|---|
| **#43** | 真值集小（14 例）且全部来自**同一静态素材项目**；`UNCERTAIN` 仅 4 例 → 结论**不可外推**。 |
| **#44** | "MATCH 精确率 = 1.0"是**在这 14 例上**的结论；UNKNOWN 计为保守而非误报 → 不等于通用精确率。 |
| **#45** | 5-A/5-D 对"内容正确但域区分度不足"的镜头会给 UNKNOWN（T06/T08），降低可判定覆盖率；修它只能换素材或改规则。 |
| **#46** | 敏感性显示 `margin` **放宽 −0.01 即把 T06 变 MATCH**、收紧 +0.02/+0.04 会把 4 个用例变 UNKNOWN；**本阶段不采纳任何改动**。 |
| **#47** | top-1 一致性只是**解释性指标**（本集 100% 吻合但样本小），**未**作为规则依据。 |
| **#48** | 真值集开发期修正三处夹具缺陷并**重新定稿**（初稿/定稿哈希均留痕），定稿后未再修改。 |

---

## 10. 全量回归（3-A～5-D）

见 §12（结果表）。

---

## 11. 交付物清单

| 交付物 | 路径 |
|---|---|
| 冻结真值集 | `tests/fixtures/mm_truth_set_v1.json`（sha256 `7eb952f2797e180c…`） |
| 校准内核 / 只读编排 / CLI | `src/video_studio/core/mm_quality.py`、`src/video_studio/ops/mm_quality.py`、`run.py mm-quality` |
| 单元测试 | `tests/mm_quality_test.py`（**34/34**） |
| 校准证据 | `docs/regression_2x/logs/phase5e_quality.json`（14 用例/指标/冲突/敏感性/可解释链） |
| 证据汇编 | `docs/regression_2x/logs/phase5e_evidence.json`（**ALL_GREEN**） |
| 回归编排与输出 | `docs/regression_2x/phase5e_regression.py`、`logs/phase5e_rerun/**` |
| 报告 / 断点卡 | `docs/regression_2x/PHASE5E_REPORT.md`、`PHASE5E_CHECKPOINT.md` |
| 基线 + manifest + SHA256 | 见 §13 |
| 测试与证据归档 | `snapshots/phase5e-tests-archive-20260917.zip`（203 文件；sha256 `11cea927bfdc0d418fd70c894f09390a87d27b74398993dc708155d8bb8e6087`；ZIP 哈希==manifest、条目逐一校验 0 处不符） |
---

## 12. 回归结果（3-A～5-D）

编排：`docs/regression_2x/phase5e_regression.py`（跑前把 `logs/` 冻结集备份到 `logs_5d_frozen/`，跑完**原样恢复**；
本轮输出另存 `logs/phase5e_rerun/`）。汇总 `logs/phase5e_regression_summary.json`：
`all_rc_zero_raw=true`、`frozen_logs_restored=true`（冻结 **496** 文件 → 改变 159 / 新增 1 / 删除 0 → 全部恢复，**drift 0**）。

| # | 步骤 | 结果 | 用时 |
|---|---|---|---|
| 1 | 3-A 真实链路复验 | **PASS 16/16** | 8.0 s |
| 2 | 3-A 回归批次（24 项，含真实网络项） | **24/24 as_expected（非预期 0）** | 1938.7 s |
| 3–4 | 3-B 契约审计 / 失败路径 | rc=0 / rc=0 | 7.6 / 17.0 s |
| 5–10 | 4-A+4-B / 4-C / 4-D / 4-E / 4-F / 4-G 证据 | 全部 rc=0 | 合计 ≈35 s |
| 11 | 4.x 收口审计（含网络 PENDING 诚实性） | rc=0 | 2.1 s |
| 12–13 | 5-A 多模态证据 / 5-B 候选证据 | rc=0 / rc=0 | 48.7 / 54.0 s |
| 14–18 | **5-C 只读脚本**（append-only / 库级 append-only / 成片核验 / fail-closed / 断点检查） | 全部 rc=0（append-only、db append-only、fail-closed 均 **ALL PASS**） | 合计 ≈12 s |
| 19 | **5-D 测试 + 冻结检查** | **53/53** 、drift 0 | 115.0 / 0.3 s |
| 20 | **5-E 单元测试** | **34/34** | 378.3 s |
| 21 | **5-E 校准（CLI 实跑）** | rc=0（14/14 OK，0 违例/0 冲突） | 190.5 s |
| 22 | 全部 `tests/*.py` 套件 | **45/45 rc=0（FAILED: []）** | 817.1 s |

**网络 PENDING**：本轮真实网络项通过（批次 24/24），历史 `PENDING（环境）` 记录**未被改写**。
**回归后的收尾改动（如实披露）**：回归电池跑完后，仅为把 §8 的建议 **R6（top-1 一致性作为解释性指标）**
写入 `core/mm_quality.py::recommendations()`（**纯静态建议清单，不触及任何判定逻辑/阈值**）；
随后**重跑** `tests/mm_quality_test.py`（**34/34**）与 5-E 校准 CLI（14/14 OK、0 违例）以确认行为不变，
并据此冻结基线。除此之外，回归后未改动任何被电池覆盖的代码。

---

## 13. 基线

- 授权基线：`5.x-phase5d-baseline.zip`，sha256
  `cab3324bad69bb56252cce7344372dff5fa90e6d980c030843e072019e2d73d8`（**与授权书一致**、ZIP 自洽）。
- **本阶段基线（当前基准）**：

| 项 | 值 |
|---|---|
| 基线 | `baseline/5.x-phase5e-baseline.zip` |
| **SHA256** | **`3934369a7f62e14ca93a08b58c24b898345e5f03ee0fe2d46a875fef5f4f2b57`** |
| manifest | `baseline/baseline_manifest_5.x-phase5e-baseline.json`（由 ZIP 内条目字节重建） |
| 文件数 / 源码字节 / ZIP 字节 | **374 / 8,140,706 / 6,095,381** |
| 复验 | `verify_baseline.py 5.x-phase5e-baseline` → **VERDICT: MATCH**（0 缺失、0 漂移） |
| 相对 5-D 的 delta | **修改 3 / 新增 4 / 删除 0** —— 修改：`CHANGELOG.md`、`STATUS.md`、`src/video_studio/cli.py`；新增：`src/video_studio/core/mm_quality.py`、`src/video_studio/ops/mm_quality.py`、`tests/fixtures/mm_truth_set_v1.json`、`tests/mm_quality_test.py` |
| 断点快照 | `snapshots/5.x-phase5e-20260917.zip`（同哈希）+ `.db`（sha256 `dcae4810967ee567b4c25081cfda51f8c6bb2bae7224e8d01523a2648b81f455`，20,340,736 B）+ `.json` |
| 证据汇编 | `logs/phase5e_evidence.json`（**ALL_GREEN=true**） |
| 测试与证据归档 | `snapshots/phase5e-tests-archive-20260917.zip`（sha256 见其同名 manifest） |

**冻结真值集已随基线固化**：`tests/fixtures/mm_truth_set_v1.json`（sha256 `7eb952f2797e180c…`）在基线 ZIP 内，
与代码内 `TRUTH_SET_PIN` 双向钉定一致。

---

## 14. 结论

**PASS**：5-E 在**不改动任何判定逻辑与阈值**的前提下完成了多模态证据的质量校准与可解释性增强 ——
建立了**冻结的 14 例真值集**（含出处与允许/禁止输出），三层证据**并列**评估且原结果未被覆盖；
**三层 MATCH 精确率均为 1.0（零误报）**，5-A/5-D 的 UNKNOWN **只**出现在"内容正确但证据不足"的用例上且
在阈值扰动下**稳健**；`margin` 的**放宽**会把 UNKNOWN 变 MATCH（明确不作为改进手段）；
每条结论都能追溯到**模型数值 → 工程阈值 → 规则推断 → UNKNOWN**四类证据中的哪一类；
fail-closed 覆盖真值/覆盖度/模型/帧数/冲突/未解决六类情形；全量回归 3-A～5-D 通过（网络 PENDING 原状）；
5-F 仅提出 6 条建议（R1–R6），**均未实施**。

**STOP（等待人工授权；不进入 5-F/Final）**
