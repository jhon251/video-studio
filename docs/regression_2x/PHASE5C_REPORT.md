# 5.x Phase 5-C 报告：人工选定候选 → redo 生效 → 全链复验（真实多模态候选替换）

> **授权范围（逐字遵守）**：只做 5-C，**禁止进入 5-D**；① 由**人工明确选择** 5-B 候选（禁止自动选材）；
> ② **复用 4-C 既有** `select-candidate → decision → changelog → redo/version+1` 闭环，**不新增写入口**；
> ③ 用**真实 S04 或 S06** 完成至少一次多模态候选替换；④ 替换后重新验证 4-B、5-A、3-A、3-B、attribution、
> license gate、版本链；⑤ 证明旧版本仍保留、append-only、人工 decision/changelog 可追溯；⑥ 替换失败/许可证失败/
> 候选失效/模型不可用**必须 fail-closed**，禁止自动回退到其它素材；⑦ 必须证明**未修改未授权镜头**；
> ⑧ 全量回归 3-A～5-B；⑨ 输出替换前后证据、人工 decision、redo/version chain、语义结果、渲染/响度/抽帧结果、
> 新 baseline 与 SHA256；⑩ 完成后 **STOP**。
>
> **判定：PASS（含 1 项如实登记的退化观察，见 §11/§12 — 未放宽任何规则、未伪造任何 PASS）**

- 项目：`p_f4b466a4a024`（`test_phase3a_real_chain`）
- 本阶段**未改动任何产品代码/契约/阈值**（改动仅限 `docs/regression_2x/` 下的只读证据脚本与日志）
- 证据目录：`docs/regression_2x/logs/phase5c_*.json`、`docs/regression_2x/logs/phase5c_rerun/`

---

## 1. 人工决定（唯一写入口，复用 4-C）

| 项 | 值 |
|---|---|
| 命令 | `python run.py select-candidate p_f4b466a4a024 --scene S06 --asset asset_f3cf2b80432d --by human:project-owner --reason "…"` |
| 决定者 | `human:project-owner`（人工自填标识，无登录/签名 — 见 #20） |
| decision | `d_5ffb9971d5a3`（`node=selection_override`、`state=approved`） |
| changelog | **#902**（`target_type=selection_override`、`target_id=S06:asset_f3cf2b80432d`、`human_confirmed=1`） |
| 镜头 | **S06**（收尾边界镜头；旁白为"最后交代边界：Cardboard 没用…"） |
| 替换 | `asset_edece2b357f1`（`Meta Quest 3 front View.jpg`）→ **`asset_f3cf2b80432d`**（`Meta Quest 3 side View.jpg`） |
| 理由（原文） | "5-C 人工确认：S06 为收尾边界镜头（中性产品交代）。5-B 候选中 Meta Quest 3 side View.jpg 的域视觉相似度最高（CLIP 0.2886 > 当前 front 0.2777），许可 FREE_ATTRIBUTION、来源可溯；该镜头旁白不涉及佩戴动作细节，侧面产品图语义适配。接受复用（S03/S05 已用）并知悉需重跑渲染与全部核验。" |

**"人工明确选择"的证据**：`--by`/`--reason` 均为必填，缺一即拒绝（§7 N2/N3）；素材必须在该镜头的**已验证候选池**内（§7 N1）；
5-B 报告与 5-C 全流程**零自动写入**（`select_candidate_called=0`、`redo_triggered=0`、`db_writes=0`，见 §7 N4）。

**为什么改 S06 而不改 S04**：S04（52–77s）旁白讲"佩戴/重量/起雾"等**佩戴动作**，现有 `Visitor using a Meta Quest 3…`
（真人佩戴照，抽帧 corr 0.472、5-A `xr_device` 0.2627）语义更贴合；S06 为中性产品交代，侧面产品图适配且是 5-B 排序第一。

---

## 2. 替换前后证据（同一项目、逐项可复算）

| 项 | 替换前（v5） | 替换后（v6） |
|---|---|---|
| render 任务 | `t_b8f866ddc062` | **`t_6d692b93e342`** |
| render_output 产物 | `a_e369526c2f47` | **`a_fa4716cffb26`** |
| 产物文件 sha256 | `a68b73789073939318130a1daf6c9d5526f7fd6731109402d6d9730c570ab531` | `6958ed3d8742938e2a1560b67cfe474bf3dcdfbc075f2ae0b51f85685140a15e` |
| 产物记录哈希（LF 归一化口径 `sha256[:16]`）/ 字节 | `1188fedae92204e5` / 103,731 | `bd82d94eecc9943d` / 104,478 |
| 成片 | `t_b8f866ddc062_draft.mp4`（5,999,206 B） | `t_6d692b93e342_draft.mp4`（**6,027,761 B**） |
| 成片 sha256 | `8f6749adf92930aac3fd0f22bb60bb9a8efa346b3c380d9d680bc97df94493b4` | **`1c5759229cab328e985c10f1efd480e4ddc0d0409640c655092f14bfcfd1beef`** |
| attribution 产物 | `a_7e538cdbc013` | `a_47e0498f66c2` |
| 时长 | 104.0 s | 104.0 s |
| 响度（渲染记录） | ok=true / −16.1 LUFS / TP −2.7 dBTP | ok=true / −16.1 LUFS / TP −2.7 dBTP |
| 时间轴（主题材） | S01 Visitor / S02 front / S03 side / S04 Visitor / S05 side / S06 **front** | S01 Visitor / S02 front / S03 side / S04 Visitor / S05 side / S06 **side** |

证据：`logs/phase5c_before.json`（替换前快照）、`logs/phase5c_after.json`、`logs/phase5c_compare.json`（逐项对比）。

**S06 画面像素级证据**（`logs/phase5c_film_verify.json`；v6 成片 98.0s 抽帧 ↔ 素材 48×48 灰度 Pearson）：

| 素材 | 相关系数 |
|---|---|
| `asset_f3cf2b80432d`（side，替换后） | **0.354118**（argmax） |
| `asset_edece2b357f1`（front，替换前） | 0.214879 |
| `asset_4f49f4c7edd0`（Visitor） | −0.065783 |

→ 替换**确实进入了交付画面**（不是只改了元数据）；人工目视复核同样确认 v5/S06 为正面产品图、v6/S06 为侧面（头带）产品图。

---

## 3. redo / 版本链（append-only，version+1）

```
v1 t_ec83e67de429 SUCCEEDED
v2 t_539c107ab85e SUCCEEDED
v3 t_b7a62ec8e29a SUCCEEDED
v4 t_1dbf3c1bc6f7 SUCCEEDED
v5 t_b8f866ddc062 SUCCEEDED   ← 替换前当前版本（仍保留）
v6 t_6d692b93e342 SUCCEEDED   ← 本次 redo（人工执行 python run.py redo t_b8f866ddc062）
```

- 旧版本**全部保留**：v1–v5 的 `render_output` 产物文件哈希、成片文件哈希、成片文件本体**逐项未变**（`phase5c_append_only.json` B 段全 True）；
  5 个旧成片文件仍全部在 `projects/p_f4b466a4a024/output/`。
- **库级 append-only 证明**（`logs/phase5c_db_append_only.json`，与 5-B 冻结的替换前 DB 快照
  `docs/regression_2x/snapshots/5.x-phase5b-20260916.db`（sha256 `9b6321d25ce6ec2a…`）逐表逐行逐列对比）：

| 表 | 替换前行数 | 当前行数 | 删除 | 改写 | 新增 |
|---|---|---|---|---|---|
| projects | 1160 | 1160 | 0 | 0 | 0 |
| tasks | 7228 | 7229 | 0 | **0**（见下） | 1（`t_6d692b93e342`） |
| artifacts | 6269 | 6271 | 0 | 0 | 2（`a_47e0498f66c2`,`a_fa4716cffb26`） |
| decisions | 1455 | 1456 | 0 | 0 | 1（`d_5ffb9971d5a3`） |
| changelog | 901 | 902 | 0 | 0 | 1（`#902`） |
| events | 51655 | 51669 | 0 | 0 | 14（事件流） |

- **唯一的就地改写**是 `redo` 的设计语义：6 个下游任务的 `dependencies` 由 v5 渲染任务**重指**到 v6 渲染任务
  （`thumbnail`/`qa`/`compliance`/`critic_final`/`platform`/`analytics`，且**只改了这一列**、状态/版本未变、全部属于本项目）。
  脚本以**白名单精确断言**（行集合、列集合、新旧取值三条件）而非"忽略差异"，其余任何行改写都会判 FAIL。
  **无任何 decision/changelog/artifact/event/project 行被改写或删除。**

---

## 4. 未授权镜头未被改动（逐镜头证明）

| 镜头 | 窗口 | 替换前素材 | 替换后素材 | 变化 |
|---|---|---|---|---|
| S01 | 0–12 s | `asset_4f49f4c7edd0`（automatic） | 同 | 无 |
| S02 | 12–32 s | `asset_edece2b357f1`（automatic） | 同 | 无 |
| S03 | 32–52 s | `asset_f3cf2b80432d`（automatic） | 同 | 无 |
| S04 | 52–77 s | `asset_4f49f4c7edd0`（human_review） | 同 | 无 |
| S05 | 77–92 s | `asset_f3cf2b80432d`（human_review） | 同 | 无 |
| **S06** | 92–104 s | `asset_edece2b357f1`（human_review） | **`asset_f3cf2b80432d`**（human_review） | **仅此一处** |

- 6 个镜头的**时间窗、时长、旁白、章节**完全一致；`video_duration_s` 104.0 s 未变；
- 断言：`changed_scenes == ["S06"]` 且 `window_same` 对所有镜头为真（`phase5c_append_only.json` C 段 ok=true）。

---

## 5. 语义结果（4-B / 5-A / 5-B 三层，替换后重跑）

**4-B 离线类别式语义核验（对 v6 成片）**：`MATCH=6 / MISMATCH=0 / UNKNOWN=0`（词表指纹 `083e8d55c9899706…` 未变）
→ `logs/phase5c_semantic_after.json`。**4-B 判定逻辑、词表与真值钉定（`a_2ed5f41d6b58`）均未改动。**

**5-A 真实 CLIP 多模态核验（逐镜头 3 帧 25/50/75%，`--artifact` 钉定到对应版本）**：

| 镜头 | 替换前（v5 `a_e369526c2f47`） | 替换后（v6 `a_fa4716cffb26`） |
|---|---|---|
| S01 | MATCH（exp 0.2897 / Δ0.0597） | MATCH（Δ≥0.02） |
| S02 | MATCH（0.2775 / Δ0.0893） | MATCH |
| S03 | MATCH（0.2409 / Δ0.0355） | MATCH |
| S04 | MATCH（0.2627 / Δ0.0292） | MATCH |
| S05 | UNKNOWN `MM_AMBIGUOUS`（0.2369 / Δ0.0175） | UNKNOWN `MM_AMBIGUOUS` |
| **S06** | **MATCH（0.2777 / Δ0.0742）** | **UNKNOWN `MM_AMBIGUOUS`（0.2248 / Δ0.0061）** |
| 合计 | MATCH=5 / MISMATCH=0 / UNKNOWN=1 | **MATCH=4 / MISMATCH=0 / UNKNOWN=2** |

→ `logs/phase5c_mm_before_v5.json`、`logs/phase5c_mm_after.json`。
**这是本阶段唯一的退化项，如实登记（§11 #32）；未放宽 `min_sim=0.20`/`margin=0.02` 阈值、未改判定逻辑、未伪造 MATCH。**
两次运行都没有产生 `MISMATCH`（画面错配未被引入；替换后 S06 的画面确为 XR 设备侧面产品图，只是 CLIP 域判别边际不足）。

**5-B 候选生成（对 v6 成片，只读）**：`S05`、`S06` 均 `CANDIDATES_READY`（各 2 条：`front` 0.2817、`Visitor`，
均 `FREE_ATTRIBUTION`；当前 side 因 `CURRENT_ASSET` 被排除）→ `logs/phase5c_mmb_after.json`；
`meta.readonly=true`、`db_writes=0`、`production_writes=0`、`select_candidate_called=0`、`redo_triggered=0`。
**即：5-B 只是把"下一步可选什么"摆出来，未做任何自动替换。**

---

## 6. 渲染 / 响度 / 抽帧（替换后 v6 成片）

| 项 | 结果 |
|---|---|
| 容器/编码 | `mov,mp4,m4a,3gp,3g2,mj2`；视频 **h264 High 1920×1080 yuvj420p 30 fps（3114 帧）**；音频 **aac LC 24 kHz 单声道（2439 帧）** |
| 时长 | 容器 104.000 s == 产物 `video_duration_s` 104.0 s（误差 <0.5 s；时间轴权威） |
| 独立响度复测（`ffmpeg ebur128=peak=true`，非读取渲染记录） | **I = −16.1 LUFS**（契约 −16 ±1 LU）、**TP = −2.7 dBTP**（≤ −1.5）→ 契约成立 |
| 渲染记录响度 | ok=true、−16.1 LUFS、TP −2.7 dBTP、Δ=−0.1 LU、corrections=0、母带链 `loudnorm=I=-16:TP=-1.5:LRA=11,alimiter,aresample=24000` |
| 逐镜头抽帧反查（48×48 灰度 Pearson，`min_corr=0.30`、`argmax_margin=0.15`） | S01 0.459 / S02 0.921 / S03 0.348 / S04 0.472 / S05 0.355 / **S06 0.354**，**6/6 corr_ok，argmax 全部命中该镜头所选素材** |
| 渲染自检 `material_verification` | `frame_pearson_48x48`，检查 6 镜、失败 **0** 镜 |
| 可解码性 | ffprobe 2 流 + ffmpeg 解码 rc=0（3-A D1/A6） |

证据：`logs/phase5c_film_verify.json`。

---

## 7. fail-closed 负向验证（`logs/phase5c_failclosed.json`，全部 PASS）

| 用例 | 触发 | 期望 | 实测 |
|---|---|---|---|
| N1 | 选定素材**不在候选池**（`asset_deadbeef0000`） | 拒绝 + **零写入** | rc=3，`HUMAN_SELECTION_NOT_IN_POOL`；DB 哈希与时间轴**未变** |
| N2 | **无人工归属**（`--by` 为空） | 拒绝 + 零写入 | rc=3，`HUMAN_SELECTION_NO_REVIEWER` |
| N3 | **无理由**（`--reason` 为空） | 拒绝 + 零写入 | rc=3，`HUMAN_SELECTION_NO_REASON` |
| N4 | **视觉模型不可用**（`--config` 指向模型目录不存在的临时配置） | 5-B 必须 `UNKNOWN:MMC_MM_UNAVAILABLE`，**不自动回退**到别的判据、零候选 | 报告级 `UNKNOWN/MMC_MM_UNAVAILABLE`，6 镜全部同码，**候选 0 条**，`db_writes=0`、`production_writes=0`、`select_candidate_called=0`、`redo_triggered=0` |
| N5 | 同上，5-A 路径 | 必须 `UNKNOWN:MM_MODEL_MISSING`，不产出 MATCH/MISMATCH | `MATCH=0 / MISMATCH=0 / UNKNOWN=6`，`applied=false` |

- 5 个用例的前后 **DB sha256 完全一致**（`ade7058863885db2…`）、时间轴完全一致 → **零写入**成立；
- 许可不合格（`HUMAN_SELECTION_LICENSE_BLOCKED`）在本项目**无法用真实素材触发**（4 个可用素材全部 `FREE_ATTRIBUTION`，
  另 6 个已被 `ASSET_OVERSIZE`/`PROVIDER_RATE_LIMITED` 拒于池外）→ 该分支由既有 `tests/human_selection_test.py`
  的夹具用例覆盖（真实代码路径），并在 5-B 侧以 `LICENSE_NOT_CLEAR` 排除码机械生效；**本报告不声称在真实素材上跑过该分支**。

---

## 8. attribution 与许可门禁（替换后）

- **attribution ↔ 时间轴 1:1**：台账 `a_47e0498f66c2` 6 条 ↔ 有素材镜头 6 个，`scene_id` 顺序一致，
  每条 `selected_asset.sha256` 与磁盘文件 sha256 **逐一相符**，`appears_in_film=true`、`film_evidence.match=true`
  （corr 0.459/0.921/0.348/0.472/0.355/**0.354**）。
- **S06 台账**：`provider=wikimedia_commons`、`source_id=139518403`、`license=CC BY-SA 4.0`、
  `license_class=FREE_ATTRIBUTION`、`attribution=Roy.wonder.cohen`、`usage_restrictions=CC BY-SA 4.0`。
- **许可门禁复核**（用真实函数 `core.materials.license_gate_applies` / `license_block_reason` 对产物里的完整
  `selected_asset` 投影逐镜头重算）：6/6 `gate_applies=true`、`gate_block_reason=None`、`license_class` ∈ {PUBLIC_DOMAIN,
  FREE_ATTRIBUTION}、`license_cleared=true`；`licence_blocked_candidates=[]`。
- **credits 文本随片落盘**：`output/credits_t_6d692b93e342.txt`（6 条，含 provider/source_id/license/attribution）。
- **3-A B1/B2/B3**：成片内无 RESTRICTED/UNKNOWN 素材；被拒候选带明确错误码且未入片。

证据：`logs/phase5c_append_only.json`（D/E 段）、`logs/phase5c_rerun/3a_real_chain.log`。

---

## 9. 未改动清单（冻结项）

- 产品代码：**零改动**（`src/` 无任何变更；5-B 基线后仅新增 `docs/regression_2x/phase5c_*.py` 只读证据脚本）；
- 契约/阈值：响度契约、素材验证（48×48 Pearson/0.30/0.15）、4-B 类别式规则与词表（sha 前缀 `083e8d55c9899706`）、
  5-A 阈值（0.20/0.02）、5-B 阈值（0.22/3/许可必清）、许可门禁、HITL、append-only/version+1 —— **全部未改**；
- `config/config.json`、DB schema：未改；`models/`（CLIP 权重）仅以 sha256 钉定引用，未改；
- 未接第二个 Provider、未做 BGM/UI/自动发布、未进入 5-D；
- 5-A/5-B 的冻结报告与日志：**本阶段回归运行后已原样恢复**（`logs_5b_frozen/` 备份 + 逐文件哈希校验，
  `phase5c_regression_summary.json` → `frozen_logs_restored=true`），新结果另存 `logs/phase5c_rerun/`。

---

## 10. 全量回归（3-A～5-B，2026-09-16 收工前完成）

编排脚本：`docs/regression_2x/phase5c_regression.py`（**运行前后保护冻结证据**：先把 `logs/` 全量备份到
`logs_5b_frozen/`，跑完把被改动的既有日志**原样恢复**并逐文件校验；本轮结果另存 `logs/phase5c_rerun/`）。
汇总：`logs/phase5c_regression_summary.json`（`frozen_logs_restored=true`）。

| 步骤 | 结果 | 用时 | 证据 |
|---|---|---|---|
| 3-A 真实链路复验 | **PASS 16/16**（`FAIL=0 PENDING=0`） | 8.4 s | `phase5c_rerun/3a_real_chain.log`、`3a_real_chain.json` |
| 3-A 回归批次（24 项） | **23/24 as_expected**（唯一非预期项 = 依赖真实网络的 `phase2e_real_provider`：Wikimedia TLS 握手超时 → `PROVIDER_TIMEOUT`；与冻结的 `PENDING（环境）` 一致，**未改写状态**） | 1356 s | `phase5c_rerun/phase3a_regression_batch.json/.log` |
| 3-B 契约审计 | rc=0 | 6.5 s | `phase5c_rerun/3b_audit.log`、`3b_audit.json` |
| 3-B 失败路径 | rc=0 | 14.7 s | `phase5c_rerun/3b_failure_paths.log`、`3b_failure_paths.json` |
| 4-A+4-B 证据 | rc=0（含 `provider=none` 与语料库 A/B 指标） | 12.6 s | `phase5c_rerun/4ab_evidence.log` |
| 4-C 证据（对 v6 重算） | rc=0（attribution 1:1 = PASS；4-B 对 v6 `MATCH=6`；复用连带检查：与上一版仅 S06 不同） | 1.2 s | `phase5c_rerun/4c_evidence.log` |
| 4-D 证据 | rc=0（超时降级 / 不污染既有项目 / 阶梯与默认配置） | 1.0 s | `phase5c_rerun/4d_evidence.log` |
| 4-E A/B 基准 | rc=0（歧义查询全记 UNKNOWN、不假匹配） | 0.1 s | `phase5c_rerun/4e_ab_benchmark.log` |
| 4-F BGM/ducking | rc=0（−15.9 LUFS / TP −8.0 dBTP；静音与受限许可两条 fail-closed 成立） | 10.6 s | `phase5c_rerun/4f_evidence.log` |
| 4-G 节奏建议 | rc=0（建议 11 条全部 `applied=false`；只读、两次运行一致） | 0.3 s | `phase5c_rerun/4g_evidence.log` |
| 4.x 收口审计 | rc=0（4-G 只读复核 + 网络 PENDING 诚实性核对：基线内 PENDING 行仍保留） | 1.6 s | `phase5c_rerun/4x_audit.log`、`4x_audit.json` |
| 5-A 多模态证据 | rc=0（冻结产物真值回归 + 当前成片 + fail-closed 复核） | 39.1 s | `phase5c_rerun/5a_evidence.log` |
| 5-B 候选证据 | rc=0（三条路径 + 只读/确定性 + 4-C 历史决定交叉核对） | 42.1 s | `phase5c_rerun/5b_evidence.log` |
| 单元套件（全部 `tests/*.py`） | **43/43 rc=0（FAILED: []）** | 312.7 s | `phase5c_rerun/unit_suites.log`、`suites_summary.json` |

**首轮 42/43 的成因与处置（如实记录）**：首轮 `multimodal_test` 33/34 失败于 F2 —— 断言里写死了「5 个成片」，
而 5-C 授权替换使项目变为 **6 个成片**（`{'files': 78, 'films': 6}`）。该断言属**过期校准**（只读规则本身未被违反：
同一断言的"项目文件逐字节未变"部分通过）。已改为**更强**的结构断言（成片字典逐字节未变 **且** 成片条数 == DB 中
成功渲染版本数），**未放宽任何规则、未改任何产品逻辑与阈值**；首轮失败证据原样留档
（`phase5c_rerun/PRESERVED_suite_multimodal_test_failed_20260916.log`、`PRESERVED_suites_summary_42of43.json`），
登记为 `KNOWN_ISSUES.md` **#37**。修正后复跑即为上表的 **43/43**。

**回归后的库级 append-only 复验**（`logs/phase5c_db_append_only.json`，`ALL_PASS=true`）：与 5-B 冻结 DB 快照相比
**删除 0 / 改写 0**（tasks 仍仅那 6 条白名单依赖重指）；新增行全部来自回归电池自建的夹具项目
（projects +71、tasks +332、artifacts +299、decisions +33、changelog +13、events +2312），
且 5-C 应有的新行（`t_6d692b93e342`、`a_47e0498f66c2`、`a_fa4716cffb26`、`d_5ffb9971d5a3`、changelog `#902`）
**确实存在**。

---

## 11. 如实登记的退化与观察

| 项 | 内容 |
|---|---|
| **观察 1（退化）** | S06 的 5-A 判定由 **MATCH（Δ=0.0742）退化为 UNKNOWN/`MM_AMBIGUOUS`（Δ=0.0061 < 0.02）**：替换后画面是 XR 设备**侧面/头带**特写，CLIP 12 域打分中 `xr_device 0.2248` 与 `vehicle 0.2188` 仅差 0.006。**未引入 MISMATCH**，4-B 仍 `MATCH=6`；副作用是 v6 成片在 5-A 上比 v5 少一个 MATCH。如实登记为 #32，**不通过调阈值消除**。 |
| **观察 2（方法学）** | 5-B 候选排序使用**素材原图**的 CLIP 相似度（side 0.2886 > front 0.2817），而 5-A 判定使用**成片抽帧**（画面已按 16:9 裁切/叠字幕）。两者在本例中**方向不一致**：资产级更高的候选在成片级反而更低。登记为 #33，建议后续在候选证据里补"成片抽帧口径"的预测量（属新能力，需新授权）。 |
| **观察 3（复用连带）** | 替换后 `side` 被 S03/S05/S06 **三个镜头**使用（`front` 仅 S02），画面多样性下降；5-B 已把"已被其它镜头占用"作为风险列出，人工在 reason 中明示"接受复用"。登记为 #34。 |
| **未变项** | S05 的 5-A 边际（Δ≈0.0175）在替换前后一致，仍为 UNKNOWN → 与 5-B 报告一致（#24 既有登记）。 |

---

## 12. 与 4-C 闭环的一致性

- 复用既有三件套（`select-candidate` 写 `decisions`+`changelog` → 人工 `redo` 建 version+1 → `run` 执行）；
- 渲染侧读"最新一条已批准的人工选定"，校验其来自候选池、可用、许可已清，写入 `selection_source="human_review"`
  与 `human_selection{decision_id,decided_by,reason,decided_at}`（v6 时间轴 S06 中可见 `d_5ffb9971d5a3`）；
- 5-C 与 4-C 的历史 decision（S04 `d_a74b1d9f5ab6`/#798、S06 `d_9a7600dfeebf`/#799、S05 `d_a683da3c5d3b`/#820）
  全部保留且未被改写 —— 同镜头多条决定时渲染取最新一条（S06 的 #902 覆盖 #799 的**生效指针**，历史行仍在）。

---

## 13. 基线

- 上一基线：`baseline/5.x-phase5b-baseline.zip`，sha256 `dee0e33cad31418bb04fd76ae9d6d62d394cdd1741e22b8ba7ef31e9a39ab67e`
  （367 文件 / 7,946,132 B；本轮复验 **zip 哈希==manifest、manifest==zip 条目** → 冻结 ZIP 自洽未变）。
- 本阶段基线（**当前基准**）：

| 项 | 值 |
|---|---|
| 基线 | `baseline/5.x-phase5c-baseline.zip` |
| **SHA256** | **`227c3a2d2be5675a69a3a0bf321d9575eea64a0138d0e2d0930e47f9e0268525`** |
| manifest | `baseline/baseline_manifest_5.x-phase5c-baseline.json`（由 ZIP 内条目字节重建，权威口径） |
| 文件数 / 源码字节 / ZIP 字节 | **367 / 7,955,906 / 6,035,577** |
| 复验 | `verify_baseline.py 5.x-phase5c-baseline` → **VERDICT: MATCH**（zip 哈希相符、清单==条目、missing 0、drift 0） |
| 相对 5-B 的 delta | **修改 3 / 新增 0 / 删除 0** —— `CHANGELOG.md`、`STATUS.md`（5-C 章节）、`tests/multimodal_test.py`（F2 校准，登记 #37） |
| 断点归档 | `snapshots/5.x-phase5c-20260916.zip`（同哈希）+ `.db`（sha256 `a46ec08c644bc295c4818e0c59736ceb8a206d897a766fb13e345a9c6585a9af`，18,800,640 B）+ `.json` |
| 证据归档 | `snapshots/phase5c-tests-archive-20260916.zip`（sha256 `1135ad4b898c17033c339bd4ba52afa074e86f72dcbcc13bd780fc3bd2f5fc4d`，200 文件） |

**口径说明**：基线按历史惯例 `--no-docs` 收录（`src/config/tests/scripts` + `run.py/pyproject.toml/README.md/
CHANGELOG.md/STATUS.md`），故 `docs/` 下的 5-C 报告/断点卡/证据脚本与 `logs/` 证据**不在 ZIP 内**（与 3.x/4.x/5-A/5-B 一致）；
它们以 SHA256 钉定在本报告与 `logs/phase5c_evidence.json`、`snapshots/phase5c-tests-archive-20260916.manifest.json` 中。

---

## 14. 结论

**PASS（含 §11 如实登记的退化观察）**：在**人工明确选定** 5-B 排序第一的候选后，走完 4-C 既有闭环并重新渲染，
版本链 v1→v6 完整保留，**仅 S06** 的素材指针改变，旧版本与全部历史决定逐字节未变（库级比对：删除 0 / 改写 0），
attribution/许可门禁/响度/抽帧/时长契约全部通过，fail-closed 五例全部成立且零写入；
3-A **16/16**、3-B 两脚本 rc=0、4-A…4-G/5-A/5-B 证据脚本 rc=0、单元套件 **43/43**、批次 23/24（唯一非预期项为
网络 PENDING 环境项）；基线 `5.x-phase5c-baseline` 复验 **MATCH**，相对 5-B delta = 修改 3 / 新增 0 / 删除 0。
**未放宽任何规则、未新增任何写入口、未改写任何 PENDING/BLOCKED 状态、未进入 5-D。**

**待人工决策（下一阶段才可动）**：是否按 #33 增加"成片抽帧口径"的候选预测量；是否把 S06 换回 `front` 或其它素材
（需新的 5-B 报告 + 新的人工决定）；LRA 是否升级为硬门槛（#15）。

**STOP（等待人工授权再进入 5-D）**
