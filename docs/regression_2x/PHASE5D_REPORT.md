# 5.x Phase 5-D 报告：多帧/时序多模态证据增强（只读平行证据层）

> **授权（逐字遵守）**：只做 5-D，**完成后 STOP，不进入 5-E/Final**。目标：解决 5-A **单帧 CLIP** 导致的
> `MATCH/UNKNOWN` 不稳定。① 多帧采样验证同一 scene 的视觉语义一致性；② 输出每帧证据、聚合规则、
> 最终 MATCH/MISMATCH/UNKNOWN、confidence；③ 保留 4-B 文本语义作为独立证据，不覆盖/改写；
> ④ 不自动换材/选材/redo、不改时间轴；⑤ 默认关闭，模型/素材/证据异常必须 fail-closed → UNKNOWN；
> ⑥ 不修改 5-A 原始结果，只新增 parallel evidence；⑦ 至少覆盖 S04/S05/S06 并解释 5-C 后 S06 的
> MATCH→UNKNOWN 是否因时序/视角差异得到更可靠判断；⑧ 验证 DB 零写/仅允许测试夹具写入，项目生产数据
> 不得被污染；⑨ 全量回归 3-A～5-C，网络 PENDING 保持原状；⑩ 输出测试报告、已知限制、证据汇编、
> 新 baseline + SHA256。
>
> **授权基线**：`5.x-phase5c-baseline.zip`，sha256
> `227c3a2d2be5675a69a3a0bf321d9575eea64a0138d0e2d0930e47f9e0268525`（**已复验与授权书逐字节一致**，
> `verify_baseline.py` → `VERDICT: MATCH`；见 `logs/phase5d_evidence.json` → `baseline`）。
>
> **判定：PASS**（含 §11 如实登记的限制；未放宽任何冻结规则，未伪造任何 PASS）

---

## 1. 目标与设计

**问题（5-A 的实际表现）**：5-A 每个镜头只抽 **3 帧**（窗口 25%/50%/75%）并按**帧平均**得到域分数，
单帧噪声/视角差异会直接改变判定。5-C 的实测就是例子：S06 换成侧面产品图后，5-A 由 `MATCH`
（Δ=0.0742）变为 `UNKNOWN / MM_AMBIGUOUS`（Δ=0.0061）。**单看 3 帧，无法回答"这是采样噪声还是稳定结论"。**

**5-D 的做法**：同一镜头抽 **7 帧**（窗口 12.5%…87.5%，与 5-A 同一个 `frame_plan` 函数），并计算两类互补证据：

| 类别 | 指标 | 回答的问题 |
|---|---|---|
| **时序一致性** | 相邻帧 CLIP 视觉嵌入余弦（mean/min）、两两散布 | 这个镜头在时间轴上是不是**同一个视觉状态**？（镜头内是否切图/换视角） |
| **语义一致性** | 逐帧 argmax 域**投票占比**、逐帧 argmax 域集合 | 逐帧的语义结论是否一致？ |
| **信号强度** | 期望域相似度的 中位数/最小值/均值、与最强其它域的**边际**中位数/最小值 | 信号本身够不够（而不是抖动） |

**规则表（显式、可复算；先命中先返回）**：

| 规则 ID | 条件 | 输出 |
|---|---|---|
| `T0_FAIL_CLOSED` | 模型/解释器不可用、无帧、帧数 < `min_frames`、期望域推不出 | `UNKNOWN` + 明确错误码（置信 LOW） |
| `T1_TEMPORAL_SPLIT` | 最小相邻余弦 < `split_cos`（0.50） | `UNKNOWN / MMT_TEMPORAL_SPLIT`（LOW） |
| `T2_LOW_CONSISTENCY` | 平均相邻余弦 < `min_stability_cos`（0.75） | `UNKNOWN / MMT_LOW_CONSISTENCY`（LOW） |
| `T3_CONSISTENT_MATCH` | 期望域投票 ≥ `min_vote_frac`(0.60) 且 期望相似度中位数 ≥ `min_sim`(0.20) 且 边际中位数 ≥ `margin`(0.02) | `MATCH` |
| `T4_CONSISTENT_MISMATCH` | 同一其它域投票 ≥ `min_vote_frac` 且 其相似度 ≥ `min_sim` 且 −边际中位数 ≥ `margin` | `MISMATCH` |
| `T5_INCONSISTENT` | 无任何域达到 `min_vote_frac`（逐帧结论互相矛盾） | `UNKNOWN / MMT_INCONSISTENT`（LOW） |
| `T6_LOW_SIGNAL` | 期望相似度中位数 < `min_sim` | `UNKNOWN / MMT_LOW_SIGNAL` |
| `T7_AMBIGUOUS` | 其余（边际不足） | `UNKNOWN / MMT_AMBIGUOUS` |

**置信度语义（明确写死，避免误读）**：
· `MATCH/MISMATCH`：`HIGH` = 一致性 ≥ `high_stability_cos`(0.90) **且** |边际中位数| ≥ 2×`margin`；否则 `MEDIUM`；
· `UNKNOWN`：`MEDIUM` = **"稳定地判不出来"**（一致性 ≥ 0.90 且未发生 split）；`LOW` = split/低一致性/前置失败。
即：**UNKNOWN 的置信度描述的是"这个 UNKNOWN 有多可靠"，不是"画面与旁白的匹配程度"。**

**与 4-B / 5-A 的关系**：三层**并列**，互不覆盖。
4-B（类别式文本语义）与 5-A（3 帧 CLIP）的判定原样保留；5-D 只在报告里放 5-A 的**引用副本**
（`five_a_reference`，由既有只读命令对同一产物重跑得到），便于逐镜头对照。

---

## 2. 实现清单

| 文件 | 类型 | 说明 |
|---|---|---|
| `src/video_studio/core/mm_temporal.py` | **新增** | 设置/纯函数指标/一致性分类/规则判定（T0–T7）/worker 调用/报告组装 |
| `src/video_studio/ops/mm_temporal.py` | **新增** | 只读编排：`mode=ro` 读库 → 加密抽帧 → CLIP → 报告 + 5-A 引用副本 |
| `src/video_studio/core/mm_worker_clip.py` | **加法式修改** | 新增 `return_embeddings`（**默认 false**）；为 true 时额外返回 512 维逐图嵌入 |
| `src/video_studio/cli.py` | **加法式修改** | 新增只读子命令 `mm-temporal`（加入既有只读命令白名单，**不经过** `build_engine()`） |
| `tests/mm_temporal_test.py` | **新增** | **53/53**（A–I 九组，见 §9） |
| `docs/regression_2x/phase5d_evidence.py` | 新增（docs 不入基线） | 证据汇编（含阈值敏感性、受控夹具、只读证明） |
| `docs/regression_2x/phase5d_regression.py` | 新增（docs 不入基线） | 3-A～5-C 全量回归编排（冻结证据日志保护） |

**默认关闭**：`tools.multimodal_temporal` 在 `config/config.json` 中**不存在** → `mmt_settings({})["enabled"] is False`
（`_source="default(disabled)"`），管线任何环节都不会调用本层；只能由人工执行 `run.py mm-temporal`。
**不改 5-A 模块**：`core/multimodal.py` 的 sha256 与 5-C 基线一致（§7）。

---

## 3. 逐帧证据与聚合规则（真实数值示例）

以 v6 成片 S06（92–104 s）为例（完整数据见 `logs/phase5d_mmt_v6.json`）：

| 帧 | 时间 | 期望域相似度 | 边际 | argmax 域 |
|---|---|---|---|---|
| S06#0 | 93.5 s | 见报告 `frames[]` | … | `xr_device` |
| S06#1 | 95.0 s | 同上 | … | `xr_device` |
| … | … | | | |
| S06#6 | 102.5 s | | | `xr_device` |

聚合（报告 `aggregate` 字段）：期望相似度中位数 **0.22486**、最小 **0.22482**、边际中位数 **0.006122**、
投票占比 **1.0**（7/7 帧 argmax 均为 `xr_device`）；时序（`stability`）：相邻余弦 mean **0.96892**、
min **0.813934**、类别 **STABLE**、`split=false`、散布 0.004。

报告字段（每个镜头都会给出）：`frames[]`（逐帧 id/time_s/sha256/期望相似度/argmax/边际/top-3）、
`aggregate{}`（上述聚合）、`stability{}`（一致性/类别/split/散布/相邻余弦序列）、
`rule_id`、`confidence`、`reason`（人读依据）、`expected_domain(+来源)`、`narration_sha256`、
`five_a_verdict/code/expected_sim/delta/frames`（引用副本）。

---

## 4. 真实结果（三个版本对照）

`run.py mm-temporal p_f4b466a4a024 [--artifact …]`（真实 CLIP，本地权重
`a63082132ba4f97a…`，CPU 单线程；每镜头 7 帧）：

| 镜头 | v6（当前，side） | v5（替换前，front） | 冻结 4-B 真值产物（鲨鱼照） |
|---|---|---|---|
| S01 | MATCH `T3` HIGH（0.2901 / Δ0.0605） | MATCH `T3` HIGH | MATCH `T3` |
| S02 | MATCH `T3` HIGH（0.2778 / Δ0.0897） | MATCH `T3` HIGH | MATCH `T3` |
| S03 | MATCH `T3` MEDIUM（0.2404 / Δ0.0350） | MATCH `T3` MEDIUM | MATCH `T3` |
| S04 | MATCH `T3` MEDIUM（0.2621 / Δ0.0281） | MATCH `T3` MEDIUM | **MISMATCH `T4`（wildlife 最像）** |
| S05 | UNKNOWN `T7` MEDIUM（0.2362 / Δ0.0171） | UNKNOWN `T7` MEDIUM | MATCH `T3` |
| **S06** | **UNKNOWN `T7` MEDIUM（0.2249 / Δ0.0061）** | **MATCH `T3` HIGH（Δ0.0745）** | **MISMATCH `T4`（wildlife 最像）** |
| 计数 | MATCH 4 / MISMATCH 0 / UNKNOWN 2 | MATCH 5 / MISMATCH 0 / UNKNOWN 1 | MATCH 4 / **MISMATCH 2** / UNKNOWN 0 |
| 5-A 同产物计数 | MATCH 4 / MISMATCH 0 / UNKNOWN 2 | MATCH 5 / MISMATCH 0 / UNKNOWN 1 | MATCH 4 / MISMATCH 2 / UNKNOWN 0 |

- **与 5-A 完全同向**（三个版本计数一致）：说明多帧/时序证据**没有**推翻 5-A，也没有引入新的判定分歧；
- **与 4-B 真值方向一致**：冻结产物上 S04/S06 判 `MISMATCH`（最像域 `wildlife`），与 4-B 的
  `R3_DOMAIN_DISJOINT` / `R2_SENSE_CONFLICT` 方向一致（本层同样**不覆盖** 4-B 的结论）；
- 本项目成片均为**静态素材**，6 个镜头全部 `STABLE`（min 相邻余弦 S06 0.814，其余 ≥0.9977）。

---

## 5. S04 / S05 / S06 专项：5-C 的 S06 `MATCH→UNKNOWN` 究竟是什么

| 指标 | v5（front 视角） | v6（side 视角） | 结论 |
|---|---|---|---|
| 5-D 判定 | `MATCH` / `T3_CONSISTENT_MATCH` / **HIGH** | `UNKNOWN` / `T7_AMBIGUOUS` / MEDIUM | 与 5-A 同向（MATCH→UNKNOWN） |
| 5-A 判定（引用） | MATCH | UNKNOWN / `MM_AMBIGUOUS` | 一致 |
| 期望相似度中位数 | 0.2777 | 0.2249 | 下降 0.053 |
| **边际中位数** | **0.0745** | **0.0061** | **跌破 0.02 阈值** |
| 逐帧 argmax 投票 | **1.00**（7/7 = `xr_device`） | **1.00**（7/7 = `xr_device`） | **帧间无分歧** |
| 帧间一致性 mean/min | 0.975 / 0.853 | 0.969 / **0.814** | 均 `STABLE`、**无 split** |
| 最强其它域 | computing_device 等 | `vehicle`（0.2188） | 侧视图与 vehicle 域接近 |

**结论（回答授权第 7 条）**：
1. **不是时序/视角抖动造成的单帧噪声**：v6 的 S06 在 **7 帧上逐帧 argmax 全部是期望域**（投票 1.0）、
   **帧间一致性 0.969**、`split=false`；若是采样噪声，应出现投票分散（`T5`）或一致性下降（`T2`/`T1`）。
2. **是"该视角下 CLIP 域区分度本身不足"**：换成侧面产品图后，`xr_device` 与 `vehicle` 的中位边际从
   0.0745 掉到 **0.0061**，稳定地低于 0.02 阈值。时序层因此把 5-A 的 `UNKNOWN` 从"3 帧下的不确定"
   升级为**"7 帧一致的稳定不确定"**（`confidence=MEDIUM`）。
3. **时序证据不能把它改判为 MATCH**：要变 MATCH 只能①调阈值或②换素材；两者本阶段**都没做**（#39）。
   **因此 5-C 的 S06 退化被确认为"真实的内容/视角效应"，而非采样偶然 —— 这是比单帧更可靠的判断。**
4. **S04 / S05 不受影响**：S04 在三个版本上都是 `T3 MATCH`（真值产物上因素材是鲨鱼照而 `T4 MISMATCH`，
   与 4-B 一致）；S05 在 v5/v6 上都是 `T7 UNKNOWN`（边际 0.0171，稳定歧义，MEDIUM），与 5-A 一致。

---

## 6. fail-closed（含真实模型的受控时序切换夹具）

| 场景 | 期望 | 实测 |
|---|---|---|
| 模型目录不存在（临时配置指向不存在的 `models/__no_such_clip__`） | 逐镜头 `UNKNOWN` + `MM_MODEL_MISSING`，**无** MATCH/MISMATCH | 6/6 `UNKNOWN`、`scene codes={MM_MODEL_MISSING}`、`any_match_or_mismatch=false` |
| 无帧 | 报告级 `MMT_NO_FRAMES` + 逐镜头 `T0` | 通过（`counts.UNKNOWN=1`） |
| worker 结果非法 JSON | `MM_PARSE_FAILED`（不抛异常） | 通过 |
| worker 未产出结果 | `MM_WORKER_FAILED` | 通过 |
| 帧数 < `min_frames`(3) | `MMT_INSUFFICIENT_FRAMES` | 通过 |
| 期望域推不出（词表未命中） | `MMT_UNKNOWN_DOMAIN` | 通过 |
| **受控夹具：镜头内切图**（两张视觉差异明显的图各 3 s 拼成 6 s 成片，真实 CLIP） | `UNKNOWN / MMT_TEMPORAL_SPLIT`（`T1`） | 相邻余弦 min **0.452 < 0.50** → `SPLIT` → `MMT_TEMPORAL_SPLIT` ✔ |
| 受控夹具：静态对照（同一张图 6 s） | 不触发 `T1` | 一致性 min **0.99999** → `STABLE` ✔ |

---

## 7. 只读与"不覆盖"证明（授权第 4/6/8 条）

| 断言 | 结果 |
|---|---|
| 真实 DB 字节与五张表行数（`tasks/artifacts/events/decisions/changelog`）在 5-D 全部运行后未变 | **未变**（`logs/phase5d_evidence.json` → `readonly_and_preservation`） |
| 项目生产文件（78 个，含 6 个成片）逐字节未变、未新增生产产物 | **未变**（逐文件 sha256 比对） |
| 静态扫描：`core/mm_temporal.py` + `ops/mm_temporal.py` 无任何写库/写产物/触发 redo 的调用形态 | **通过** |
| `core/multimodal.py`（5-A 判定逻辑）sha256 与 5-C 基线 manifest **一致** | **一致**（未被本阶段改动） |
| 对同一产物重跑既有 `multimodal-check`，判定/相似度与 5-C 冻结证据**一致** | **一致**（5-A 结果未被覆盖） |
| 报告 `policy` 显式声明 `overwrites_4b_results=false`、`overwrites_5a_results=false`、`auto_select/auto_replace/auto_redo/changes_timeline=false`、`writes_to_db=false` | **声明并在测试中断言** |
| 测试夹具只写临时目录/伪造 root；**不触碰项目 DB 与项目目录** | **通过**（测试前后 DB 哈希一致） |
| 回归电池会创建自己的夹具项目（既有惯例） | 如实记录：`projects/tasks/...` 行数增加，**项目生产数据未变** |

---

## 8. 阈值敏感性（如实披露）

对 `margin` ±0.005/±0.01、一致性阈值（`min_stability_cos`/`split_cos`）±0.05/±0.10 做扰动复算
（用报告中的逐帧/聚合证据，**不重跑模型**），逐镜头列出判定是否翻转：见
`logs/phase5d_evidence.json` → `threshold_sensitivity`。**任何在扰动下翻转的镜头都在报告里列出**，
不做隐藏；本项目的静态镜头（S01–S05）在一致性阈值 ±0.10 内结论不变。

---

## 9. 单元测试（53/53）

| 组 | 内容 | 数量 |
|---|---|---|
| A | 默认关闭 / 配置非法值回退（不放松）/ 提示词与 5-A 一致 / 规则表齐备 | 4 |
| B | 时序指标纯函数（投票、相邻余弦、散布、中位数/最小值、单帧、期望域缺失、逐域均值、一致性分类边界） | 8 |
| C | 规则 T0–T7（MATCH+置信度分级、MISMATCH、歧义、split、低一致性、低信号、帧数不足、期望域缺失、模型不可用透传） | 11 |
| D | fail-closed（模型/解释器缺失、无帧、报告级无帧、非法 JSON、无结果、无标签） | 7 |
| E | 真实模型回归（冻结真值产物方向一致、v6 计数同向、全部 STABLE、逐帧证据完整、规则/置信度齐备） | 6 |
| F | **S06 视角解释**（v5 MATCH/HIGH vs v6 UNKNOWN/MEDIUM、投票均 1.0、差异在边际、S06 一致性显著更低） | 4 |
| G | **真实模型受控时序切换夹具**（切图 → `T1`；静态对照不触发；512 维嵌入确实参与时序） | 3 |
| H | 只读与不覆盖（DB/文件未变、静态无写、5-A 模块哈希、5-A 输出未覆盖、policy 声明） | 6 |
| I | 确定性（两次运行逐字节、纯函数一致、帧计划固定、人读标注只读） | 4 |

命令：`python tests/mm_temporal_test.py` → **53/53 通过**。

---

## 10. 全量回归（3-A～5-C）

编排脚本：`docs/regression_2x/phase5d_regression.py`（与 5-C 同机制：跑前把 `logs/` 冻结集备份到
`logs_5c_frozen/`，跑完**原样恢复**并逐文件校验；本轮输出另存 `logs/phase5d_rerun/`）。
汇总：`logs/phase5d_regression_summary.json`（`frozen_logs_restored=true`，`all_rc_zero_raw=true`）。

| # | 步骤 | 结果 | 用时 | 证据 |
|---|---|---|---|---|
| 1 | 3-A 真实链路复验 | **PASS 16/16** | 8.1 s | `phase5d_rerun/3a_real_chain.log` |
| 2 | 3-A 回归批次（24 项，含 3 项依赖真实网络） | **24/24 as_expected（非预期 0）** —— 本轮网络可用，`phase2e_real_provider` 13/13 | 1375.9 s | `phase5d_rerun/phase3a_regression_batch.json` |
| 3 | 3-B 契约审计 | rc=0 | 8.7 s | `phase5d_rerun/3b_audit.log` |
| 4 | 3-B 失败路径 | rc=0 | 17.9 s | `phase5d_rerun/3b_failure_paths.log` |
| 5 | 4-A+4-B 证据 | rc=0 | 18.1 s | `phase5d_rerun/4ab_evidence.log` |
| 6 | 4-C 证据 | rc=0 | 1.5 s | `phase5d_rerun/4c_evidence.log` |
| 7 | 4-D 证据 | rc=0 | 1.1 s | `phase5d_rerun/4d_evidence.log` |
| 8 | 4-E A/B 基准 | rc=0 | 0.1 s | `phase5d_rerun/4e_ab_benchmark.log` |
| 9 | 4-F BGM/ducking | rc=0 | 12.4 s | `phase5d_rerun/4f_evidence.log` |
| 10 | 4-G 节奏建议 | rc=0 | 0.4 s | `phase5d_rerun/4g_evidence.log` |
| 11 | 4.x 收口审计 | rc=0 | 2.0 s | `phase5d_rerun/4x_audit.log` |
| 12 | 5-A 多模态证据 | rc=0（真值回归 + 只读 + fail-closed 复核） | 47.8 s | `phase5d_rerun/5a_evidence.log` |
| 13 | 5-B 候选证据 | rc=0（三路径 + 4-C 交叉核对 + 只读/确定性） | 52.8 s | `phase5d_rerun/5b_evidence.log` |
| 14 | **5-C append-only / attribution / 许可门禁** | rc=0，**ALL PASS** | 0.1 s | `phase5d_rerun/5c_append_only.log` |
| 15 | **5-C 库级 append-only（对冻结 DB 快照）** | rc=0，**ALL PASS**（删除 0 / 改写 0） | 1.2 s | `phase5d_rerun/5c_db_append_only.log` |
| 16 | **5-C 成片核验**（v6 成片） | rc=0（104.0 s / −16.1 LUFS / TP −2.7 dBTP / 6/6 corr_ok） | 4.1 s | `phase5d_rerun/5c_verify_film.log` |
| 17 | **5-C fail-closed 负向验证** | rc=0，**ALL PASS**（零写入） | 5.8 s | `phase5d_rerun/5c_failclosed.log` |
| 18 | **5-C 断点状态检查** | rc=0（版本链 v1–v6、v6 成片在位） | 0.3 s | `phase5d_rerun/5c_checkpoint_check.log` |
| 19 | **5-D 单元套件** | **53/53** | 103.4 s | `phase5d_rerun/5d_mm_temporal_test.log` |
| 20 | 全部 `tests/*.py` 套件 | **44/44 rc=0（FAILED: []）** | 407.5 s | `phase5d_rerun/unit_suites.log`、`suites_summary.json` |

**冻结证据保护**：回归前冻结集 **488 个文件**（含 5-A/5-B/5-C 全部证据），运行中被改写 157 个、新增 1 个、
删除 0 个；跑完**全部原样恢复**，`phase5d_frozen_check.py` 复核 → **DRIFT 0 / MISSING 0**。
**网络 PENDING**：本轮真实网络项通过（批次 24/24），但历史 `PENDING（环境）` 记录**未被改写**（4.x 收口审计
的"PENDING 诚实性"检查仍通过）。

---

## 11. 已知限制（与 `KNOWN_ISSUES.md` 编号对应）

| 编号 | 内容 |
|---|---|
| **#38** | 帧间一致性用**整帧** CLIP 嵌入：烧录字幕会贡献帧间差异（S06 side 视角实测 min 0.814，其它镜头 ≥0.9977）→ `min_stability_cos`/`split_cos` 为工程默认；未做字幕区域掩码。 |
| **#39** | 时序层**不改变** 5-A 的结论方向：S06 仍 UNKNOWN（升级为"稳定地不确定"，MEDIUM）；**不会**把 UNKNOWN 变 MATCH。 |
| **#40** | 阈值为工程默认、可配置且非法值回退；敏感性已披露（§8）。 |
| **#41** | 逐帧嵌入（512 维）使报告体积线性增长（42 帧 ≈150 KB）；`frames_per_scene` 无上限保护；超时 900 s 只是等待预算。 |
| **#42** | `T1`/`T2` 分支在本项目成片上**不出现**（全部静态素材）；由真实模型受控夹具与合成证据单测覆盖，**不可外推**到多镜头/运动素材。 |

---

## 12. 基线

- 上一基线（授权依据）：`5.x-phase5c-baseline.zip`，sha256
  `227c3a2d2be5675a69a3a0bf321d9575eea64a0138d0e2d0930e47f9e0268525`
  （**与授权书逐字节一致**、ZIP 自洽：哈希==manifest、manifest==ZIP 条目）。
- **本阶段基线（当前基准）**：

| 项 | 值 |
|---|---|
| 基线 | `baseline/5.x-phase5d-baseline.zip` |
| **SHA256** | **`cab3324bad69bb56252cce7344372dff5fa90e6d980c030843e072019e2d73d8`** |
| manifest | `baseline/baseline_manifest_5.x-phase5d-baseline.json`（由 ZIP 内条目字节重建） |
| 文件数 / 源码字节 / ZIP 字节 | **370 / 8,042,659 / 6,063,180** |
| 复验 | `verify_baseline.py 5.x-phase5d-baseline` → **VERDICT: MATCH**（0 缺失、0 漂移） |
| 相对 5-C 的 delta | **修改 4 / 新增 3 / 删除 0** —— 修改：`CHANGELOG.md`、`STATUS.md`、`src/video_studio/cli.py`、`src/video_studio/core/mm_worker_clip.py`；新增：`src/video_studio/core/mm_temporal.py`、`src/video_studio/ops/mm_temporal.py`、`tests/mm_temporal_test.py` |
| 断点快照 | `snapshots/5.x-phase5d-20260917.zip`（同哈希）+ `.db`（sha256 `2c6ad9561b138823f44068016877b9ee924d7d9a19c6180d930cdc1f698371d5`，19,562,496 B）+ `.json` |
| 证据归档 | `snapshots/phase5d-tests-archive-20260917.zip`（194 文件；sha256 `711b95e6f460be760dabb6b4884504a45854f6c634be6f0bff2651e431b8da80`；ZIP 哈希==manifest、条目逐一哈希校验 0 处不符） |

**口径**：与历史一致，基线 `--no-docs` 收录（`src/config/tests/scripts` + `run.py/pyproject.toml/README.md/
CHANGELOG.md/STATUS.md`）；`docs/` 下的报告/证据脚本/日志以 SHA256 钉定在
`logs/phase5d_evidence.json`、`phase5d_regression_summary.json` 与归档 manifest 中。

---

## 13. 结论

**PASS**：5-D 以**只读平行证据层**的方式解决了"单帧 CLIP 导致 MATCH/UNKNOWN 不稳定"的问题 ——
加密到 **7 帧/镜头**并给出**帧间时序一致性 + 逐帧投票 + 边际分布**，用 **T0–T7** 显式规则输出三态与置信度；
真实项目上三层（4-B / 5-A / 5-D）结论**同向且互不覆盖**，冻结真值产物上 S04/S06 与 4-B 方向一致；
**S06 的 5-C 退化被证明是"视角导致域区分度下降"的稳定效应**，不是采样噪声（逐帧投票 1.0、无 split）；
默认关闭、fail-closed 齐备、DB 零写、5-A/4-B 结果未被覆盖；全量回归 3-A～5-C 通过
（单元套件 **44/44**、批次 **24/24**、3-A **16/16**、5-C 只读脚本全 rc=0，冻结证据 drift 0）。

**待人工决策（下一阶段才可动）**：是否按 #38 做"字幕区域掩码后再算一致性"；是否放宽 `margin`（**不建议**：
敏感性分析显示 `margin` −0.01 会把 S05 这类边际镜头翻成 MATCH，属放宽规则）；是否给 S06 换回 `front`
或换其它素材（需新的 5-B 报告 + 新的人工决定 + redo）。

**STOP（等待人工授权；不进入 5-E/Final）**
