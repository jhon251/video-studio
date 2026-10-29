# 4.x Phase 4-C 收尾修复报告：S05 复用连带 MISMATCH（2026-09-16）

**授权范围**：只做一次 4-C 收尾修复——用**人审候选替换闭环**消除 S05 的 `MISMATCH`，并重跑指定的全部核验；
同时产出新基线 ZIP + manifest + SHA256。**未进入 4-D/4-E/4-F**，**未接第二 Provider/BGM/UI**，
**未做自动语义改选材**，**未改数据库结构**，**未改任何冻结契约/判定逻辑/阈值**，**未改两项网络用例的 PENDING 状态**。

先决校验：修复前先复验上一冻结基线 `4.x-phase4c-baseline.zip`
sha256 `08018d4e81d8c3df0a85953158bda1d86c02494237413f4b91b2b6d56f09171d`（与报告一致）。

本报告按授权要求给出 **7 项**。

---

## 1. 修复方式：`review` → 人工选定 → `select-candidate` → `redo` → changelog/审批 → append-only/version+1

| 步骤 | 命令/动作 | 证据 |
|---|---|---|
| ① 只读复核队列 | `python run.py review p_f4b466a4a024` | 仅读 `decisions`/`changelog`/素材台账；**待办 0 / 必须 BLOCKED 0**（修复后复核视图） |
| ② 人工选定（**由人决定，非自动**） | `python run.py select-candidate p_f4b466a4a024 --scene S05 --asset asset_f3cf2b80432d --by human:project-owner --reason "4-C 收尾修复：S05 讲佩戴/眼镜语境，应使用 VR 头显素材；选侧面产品图（复用计数最少），替代无关鲨鱼照片"` | 先校验后写：`HUMAN_SELECTION_*` 校验通过（在池内、可用、许可清晰） |
| ③ 决定落库（**只写既有表**） | `decisions` `d_a683da3c5d3b`（`node=selection_override`、`state=approved`、`made_by=human:project-owner`）+ `changelog` `#820`（`human_confirmed=1`） | `logs/phase4c_human_decision_evidence.json`；任务/产物/事件表**未新增行** |
| ④ 重渲染 | `python run.py redo t_1dbf3c1bc6f7` → `t_b8f866ddc062`（**version=5**）→ `run.py run <pid>` 执行至 `SUCCEEDED` | v1–v4 任务与产物**全部保留、未被改写**（append-only + version+1） |
| ⑤ 审批闸门 | 渲染侧只消费 `state=approved` 的 `selection_override` | 时间轴新增 `selection_source="human_review"` + `human_selection{decision_id,decided_by,reason,decided_at}` |

**修复语义**：S05 由"被释放的鲨鱼照 `asset_28160d959ed5`（复用策略 `prefer_unused` 连带选中）"改为
人工选定的 `asset_f3cf2b80432d`（`Meta Quest 3 side View.jpg`）。
**未自动处理任何一步**：候选由人挑、理由由人给、替换由 `redo` 显式触发。

## 2. 语义三态核验（4-B，对**新成片**）：`MATCH=6 / MISMATCH=0 / UNKNOWN=0`

| 镜头 | 判定 | 命中规则 | 素材 |
|---|---|---|---|
| S01 | MATCH | `R4_DOMAIN_SUPPORT` | Visitor using a Meta Quest 3 VR headset … |
| S02 | MATCH | `R4_DOMAIN_SUPPORT` | Meta Quest 3 front View.jpg |
| S03 | MATCH | `R4_DOMAIN_SUPPORT` | Meta Quest 3 side View.jpg |
| S04 | MATCH | `R4_DOMAIN_SUPPORT` | Visitor using a Meta Quest 3 VR headset …（人工） |
| **S05** | **MATCH** | `R4_DOMAIN_SUPPORT` | **Meta Quest 3 side View.jpg（本次人工修复）** |
| S06 | MATCH | `R4_DOMAIN_SUPPORT` | Meta Quest 3 front View.jpg（人工） |

- 证据：`logs/phase4c_semantic_after.json`、`logs/phase4c_evidence_summary.txt` §6。
- **S05 的 `MISMATCH` 已消除**（上一轮如实登记的转移问题闭环）；4-B 的真值表**仍钉在 3-A 冻结产物
  `a_2ed5f41d6b58`**（`TRUTH_ARTIFACT`），**未**为新成片改真值——否则就是"改真值凑绿"。

**未产生新的连带问题（复用检查）**：与上一版成片 `a_d6411bfe1e32` 相比**仅 S05 变化**
（`asset_28160d959ed5` → `asset_f3cf2b80432d`）；鲨鱼素材 `asset_28160d959ed5` 已**释放且未被任何镜头接管**；
三个 VR 素材复用计数**均衡为各 2 镜**：`asset_4f49f4c7edd0`=[S01,S04]、`asset_edece2b357f1`=[S02,S06]、
`asset_f3cf2b80432d`=[S03,S05]。证据：`logs/phase4c_reuse_check.json`。

## 3. attribution ⟷ 新时间轴 1:1（6/6）PASS

台账 `a_e369526c2f47`（随 v5 生成）⟷ `material_timeline`：**台账 6 条 / 有素材镜头 6 个**，逐条
`scene_id` + `asset_id` + `sha256` 全部一致；`restricted_or_unknown_in_film=[]`；
credits 文件 `output/credits_t_b8f866ddc062.txt`。证据：`logs/phase4c_replacement_relations.json`、
`logs/phase4c_evidence_summary.txt` §4。

## 4. 成品实测：ffprobe / 响度 / 逐镜头抽帧

| 项 | 实测 | 判定 |
|---|---|---|
| 成片 | `projects/p_f4b466a4a024/output/t_b8f866ddc062_draft.mp4` | — |
| ffprobe | `video/h264` 1920×1080 + `audio/aac` 24000 Hz 单声道；`format.duration=104.000000s` | PASS |
| 时长契约 | `timeline_authoritative`：timeline 104.0s == video 104.0s（Δ=0.0s）；旁白 112.728s 超长 8.728s（8.39% < 10% 容差，按契约裁剪，`audio_trimmed_to_timeline=true`） | PASS |
| **响度（3-B 契约 -16±1 LUFS / TP ≤ -1.5 dBTP）** | **I=-16.1 LUFS，TP=-2.7 dBTP，Δ=-0.1 LU**（`ok=true`，`ffmpeg ebur128=peak=true`） | **PASS** |
| **逐镜头抽帧核验** | `frame_pearson_48x48`，**检查 6 镜 / 失败 0 镜**：S01 0.459、S02 0.921、S03 0.348、S04 0.472、**S05 0.355**、S06 0.919（阈值 0.30） | **6/6 PASS** |
| 指标汇总（4-A 只读） | 上屏 `verified_true=6 / false=0 / rate=1.0`，`corr_min=0.348`、`corr_mean=0.579`；语义 6/0/0；响度 ok | PASS |

证据：`logs/phase4c_new_film_evidence.json`（原始 ffprobe/响度/抽帧 JSON）。

## 5. 3-A 关键断言与 3-B 回归

| 项 | 命令 | 结果 |
|---|---|---|
| **3-A 真实链路（离线复核）** | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS**（含 `attribution` 条目 6 == 有素材镜头 6、时长/响度契约、抽帧相关度；S05 0.355 ≥ 0.30） |
| **3-B 响度契约套件** | `tests/audio_loudness_test.py` | **32/32**（含 D7 阻断原因、D8 故障项目不交付合规成片） |
| **3-B 失败路径** | `phase3b_failure_paths.py` | **12/12** |

**3-A 关键断言未退化**：16 项全部仍 PASS；被替换的三个镜头抽帧相关度
S04 0.736(鲨鱼照)→**0.472**、S05 0.732→**0.355**、S06 0.732→**0.919**，均 ≥ 阈值 0.30。

## 6. `provider=none` 回归 + 4-A/4-B/4-C 套件与全量套件

| 项 | 结果 |
|---|---|
| **`provider=none` 回归** | `config/config.json` sha256 `b264644539b2adbb…` 与冻结基线 manifest **一致**（本次未改默认配置）；默认配置项目仍 `mode=none`、外部请求/下载 = 0 且照常出片（`tests/metrics_test.py` M5 组、`logs/phase4ab_provider_none.txt`） |
| 4-A 指标 | `tests/metrics_test.py` **18/18**（确定性两次逐字节一致、只读、`provider=none` 证据） |
| 4-B 验证器 | `tests/semantic_check_test.py` **29/29**（真值钉在冻结产物 + C0 载体断言、离线、只读） |
| 4-C 机制 | `tests/human_selection_test.py` **18/18**（H1 无决策不变、H2 覆盖生效、H3 池外 BLOCKED、H4 不可用、H5 空池、H6 只写两表、H7 投影键、H8 台账 1:1） |
| **全量套件** | `run_all_suites.py` → **37 total / 37 rc=0 / FAILED: []**（在**已冻结的最终代码树**上重跑） |
| 回归批次 | `phase3a_regression_batch.py` 24 项中 **22 项 rc=0**；`phase3a_classify_batch.py` 非预期 2 项 = **真实网络**用例 |
| **网络（环境，状态未改）** | `phase2e_failure_paths.py` / `phase2e_real_provider.py` → **`PENDING（环境）`**（Wikimedia TLS 握手超时 / `PROVIDER_TIMEOUT`）；**期望值未修改、状态未改写** |

## 7. 新基线 ZIP + manifest + SHA256（零漂移 MATCH）

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4c-fix-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4c-fix-baseline.zip`（5,891,489 字节） |
| **zip sha256** | **`3b0e998e1c2e0de180b711b71242423ead90ecfca3f5e73e1bfe18078b6ad96e`** |
| 文件数 / 源码字节 | **348 文件 / 7,543,538 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/`**，与 4-C 基线同口径） |
| manifest | `docs/regression_2x/baseline/baseline_manifest_4.x-phase4c-fix-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4c-fix-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移**） |
| 断点快照（非基线，仅归档） | `snapshots/4.x-phase4c-fix-20260916.{zip,db,json}`（zip sha256 与基线 zip 相同 `3b0e998e…d96e`；DB sha256 `45717d780cbaed9f…`，12,255,232 字节） |
| 上一冻结基线（未动） | `4.x-phase4c-baseline.zip` sha256 `08018d4e…171d`；`4.x-phase4ab-baseline.zip` sha256 `3a7eb41a…191f` |

**本次修复相对 `4.x-phase4c-baseline` 的差异（`baseline_delta.py` 实测）**：**代码 修改 0 / 新增 0 / 删除 0**；
文件级差异仅**文档登记**两处（`CHANGELOG.md`、`STATUS.md`，记录本次收尾修复）。
→ 该 0 代码增量直接证明：S05 的修复**没有**靠改代码/改阈值/改判定逻辑完成，而是走**既有**的人工替换闭环。

**未做（STOP 点）**：未进入 4-D/4-E/4-F；未接第二 Provider；未做 BGM/UI/节奏自动改时长/Git tag；
未做自动语义改选材或自动生成替换候选；未改数据库结构；未改任何冻结契约、4-A/4-B 判定逻辑与阈值；
未修改两项网络用例的 `PENDING（环境）` 状态与期望值。
