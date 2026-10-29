# 4.x Phase 4-A + 4-B 报告：只读质量指标 + 离线三态语义核验

- 日期：2026-09-15
- 授权范围（逐字）：**"现在只授权 4-A + 4-B 第一阶段实现"**（只允许新增只读 metrics / 离线只读三态语义验证器 /
  测试与证据与必要文档；不得接第二 Provider、不得改默认配置与冻结契约、不得自动改选材或改成片、
  不得改数据库结构、不得做 BGM/UI/节奏自动改时长/Git tag；完成后立即 STOP，不进入 4-C 及以后）
- 阶段判定：**PASS**

---

## 0. 实现前检查（先核对再动手）

| 检查项 | 结果 |
|---|---|
| 冻结基线核对 | `python docs/regression_2x/verify_baseline.py 3.x-final-baseline` → zip 哈希与 manifest 一致、清单==ZIP 条目；`3.x-final-baseline.zip` sha256 = `b82ba77ea85cfd22ad7206b95f2a86b927b585254d375d941a3ee1a1dcc4646f`（与记录一致） |
| 是否使用 Git | **未使用**（仓库无 `.git`，已实测 `Test-Path .git` = False） |
| 是否需要改数据库结构 | **不需要**：4-A/4-B 全部从既有表与产物 JSON 只读取数（`mode=ro`），判定结果只在内存与证据文件 |
| 是否需要改冻结契约 | **不需要**：不触碰 Claim/HITL、append-only、redo、时间轴权威时长、旁白完整性、响度契约、素材验证、许可台账；未新增 artifact/event 类型 |
| 离线语义手段可用性 | CLIP ViT-B/32 权重**存在于本机**（`models/clip/.../pytorch_model.bin` 605 MB），但仅在 `.venv_tts`（torch+transformers），系统 Python **无 torch**；且 CLIP 文本编码器**仅英文**，无法直接读中文旁白 |
| 方法选择（据实） | 3-A 误选的真实机制是**字面/词义**问题而非图像内容问题（见 §3.4 根因），故采用**离线、可解释、可复算的词典+语境**判定（类别式规则、无数值阈值），**未引入 torch/CLIP 依赖**，**未调用 LLM** |
| 结论 | **不阻塞**，按最小方案实现 |

## 1. 实现变更清单

相对冻结基线 `3.x-final-baseline` 的**全部**变更（`logs/phase4ab_change_list.json`）：

| 类型 | 文件 | 说明 |
|---|---|---|
| MODIFIED | `src/video_studio/cli.py` | 新增 `metrics` / `semantic-check` 两个子命令；两者与 `report` 一样**不经过 `build_engine()`**（无建库/建目录/派发任务等副作用） |
| ADDED | `src/video_studio/ops/metrics.py` | 4-A 只读指标（项目模式 + 全库模式）+ 4-B 的项目级装配 `semantic_report()` |
| ADDED | `src/video_studio/core/semantics.py` | 4-B 验证器核心：词典加载、域投票、同形词义解析、桥分类、三态判定（纯函数） |
| ADDED | `src/video_studio/core/lexicons/semantics_v1.json` | 语义知识库 v1（域关键词 + 同形词义标记；带版本与 sha256） |
| ADDED | `tests/metrics_test.py` | 4-A 测试 **18/18** |
| ADDED | `tests/semantic_check_test.py` | 4-B 测试 **28/28** |

**未改动**：数据库结构与任何表/列；`config/config.json`（sha256 与基线 manifest 一致，见 §4）；
`core/materials.py`、`tools/*`、`agents/*`、`core/engine.py`、`core/audio.py`、`ops/report.py`；
冻结契约（Claim/HITL、append-only、redo、时间轴权威时长、旁白完整性、响度契约、素材验证、许可台账）。
**未接入第二 Provider、未做 BGM/UI/节奏、未建 Git tag。**

## 2. 命令、返回码与测试结果

| 命令 | 返回码 | 关键结果 | 产物 |
|---|---|---|---|
| `python run.py metrics p_f4b466a4a024 --json` | **0** | 质量/契约/素材/成本/语义/人工六类齐全 | `logs/phase4ab_metrics_project_{a,b}.json` |
| `python run.py metrics --all --json` | **0** | 全库汇总（197 项目 / 294 镜头） | `logs/phase4ab_metrics_corpus_{a,b}.json` |
| `python run.py semantic-check p_f4b466a4a024 --json` | **0** | `MATCH=4 MISMATCH=2 UNKNOWN=0` | `logs/phase4ab_semantic_truth.json` |
| `python run.py metrics p_不存在` | **2** | `项目不存在: ...`（明确信息、不崩溃） | — |
| `python tests/metrics_test.py` | **0** | **18/18 PASS** | `logs/phase3a_metrics_readonly.log` |
| `python tests/semantic_check_test.py` | **0** | **28/28 PASS** | `logs/phase3a_semantic_check.log` |
| `python docs/regression_2x/phase4ab_evidence.py` | **0** | 一次性采集全部证据 | `logs/phase4ab_evidence_summary.txt` |
| `python docs/regression_2x/run_all_suites.py` | 见 §6 | 全部套件 rc=0 | `logs/suites_summary.json` |
| `python docs/regression_2x/phase3a_regression_batch.py` + `phase3a_classify_batch.py` | 见 §6 | 批次 + 非预期判读 | `logs/phase3a_regression_batch_classified.json` |

测试覆盖的关键断言（节选）：

- **确定性**：项目模式与全库模式**两次运行 JSON 逐字节一致**（`M2` / `M3`）；
- **离线**：把 `socket.socket` 换成禁止连接的实现后，语义核验仍能完成（`D2`）——**不访问网络**；
- **只读**：运行前后 DB `sha256`/大小/行数不变、只读连接写操作被 SQLite 拒绝、连续运行无新增任务/事件（`D3`/`D4`/`M4`）；
- **不猜测**：覆盖不足 → `UNKNOWN` 且**不得**当作 `MATCH`（`B4`）；无素材/空输入 → `UNKNOWN`（`B5`/`B6`）；
- **可解释**：每条判定都带规则 ID、理由、命中关键词、共享词分类（词级桥 vs 字面碎片）（`C5`/`C7`）；
- **口径分离**：成本标"估算（非账单）"、外部素材标"非计费"且给用量（`M1c`/`M1d`）。

## 3. 真值表、混淆计数与阈值来源

### 3.1 3-A 真值表（授权指定验收）

| 镜头 | 旁白主题（摘） | 选中素材 | 判定 | 命中规则 |
|---|---|---|---|---|
| S01 | VR 头显长什么样、Quest 3/PSVR2/PICO 4 外观 | `Visitor using a Meta Quest 3 VR headset…` | **MATCH** | `R4_DOMAIN_SUPPORT` |
| S02 | 一体机：Quest 3 / PICO 4 官方图 | `Meta Quest 3 front View.jpg` | **MATCH** | `R4_DOMAIN_SUPPORT` |
| S03 | 主机 VR/PC VR：PSVR2、Valve Index 头带与 IPD | `Meta Quest 3 side View.jpg` | **MATCH** | `R4_DOMAIN_SUPPORT` |
| **S04** | 佩戴动作：头带/面罩/IPD | `Tiburón azul (Prionace glauca), canal Fayal-**Pico**, islas Azores…`（鲨鱼） | **MISMATCH** | **`R3_DOMAIN_DISJOINT`** |
| S05 | 戴眼镜路径：Apple Vision Pro 光学插片 | `Visitor using a Meta Quest 3 VR headset…` | **MATCH** | `R4_DOMAIN_SUPPORT` |
| **S06** | 边界交代：Cardboard、第三方眼镜资料 | `Tiburón azul … canal Fayal-**Pico** …`（鲨鱼） | **MISMATCH** | **`R2_SENSE_CONFLICT`** |

### 3.2 混淆计数

| 指标 | 值 |
|---|---|
| TP（S04/S06 正确标 MISMATCH） | **2 / 2** |
| FN（应为 MISMATCH 却未标） | **0** |
| FP（S01/S02/S03/S05 被误报） | **0** |
| TN（S01/S02/S03/S05 未误报） | **4 / 4** |
| UNKNOWN（无法判断） | **0**（本样本六镜均有判定） |

> **样本量诚实声明**：真值样本 **n=6**（其中正例 2、反例 4），这是**冒烟级验收**，**不是准确率估计**。
> 独立样本（非 3-A 项目）描述性结果：`p_a2fe33da8739` → MATCH 2 / MISMATCH 0 / UNKNOWN 0；
> `p_ab2b352e06b8` → MATCH 11 / MISMATCH 0 / UNKNOWN 1（未用于调参）。

### 3.3 阈值来源：**本判定没有数值阈值**

判定为**类别式规则**（先命中先返回，规则 ID 写入证据）：

| 规则 | 条件 | 结论 |
|---|---|---|
| `R0_NO_ASSET` | 镜头无选中素材（占位/纯色底） | `UNKNOWN` |
| `R1_MISSING_INPUT` | 旁白文本或素材名为空 | `UNKNOWN` |
| `R2_SENSE_CONFLICT` | 共享**同形词**在两侧被解析为**不同词义**（凭知识库 sense markers） | `MISMATCH` |
| `R3_DOMAIN_DISJOINT` | 两侧都识别出语义域、两域集合**不相交**、且**没有词级（≥3 字符整词）桥** | `MISMATCH` |
| `R4_DOMAIN_SUPPORT` | 两侧语义域**有交集** | `MATCH` |
| `R5_NO_POSITIVE_SUPPORT` | 其余（覆盖不足/无正向支持） | `UNKNOWN` |

- **无可调阈值**：规则里没有相似度阈值、没有概率门限、没有"匹配分"阈值；**因此不存在"下调阈值凑通过"的空间**。
- **知识库来源与版本**：`core/lexicons/semantics_v1.json`（version `semantics-v1`，sha256 `083e8d55c9899706…`）
  由**人工编写**：12 个语义域（zh 子串 / latin 整词） + 12 个同形词条（每词义附语境标记）。
  写作动机**如实说明**：S04/S06 的误选暴露了"字面碎片被当作语义支持"和"品牌词与地名同形"两类问题；
  知识库是**通用**登记（域与同形词表），**不是**针对这 6 个镜头逐例打补丁（例如 `pico` 之外的
  `quest/valve/index/apple/galaxy/surface/pixel/vision/rift/cardboard` 条目在本样本中未被用到）。

### 3.4 根因发现（本次实现的关键事实）

3-A 的 S04/S06 误选**并非**"品牌 PICO 与地名 pico 同形"这么简单：S04 的检索文本**根本不含 `PICO`**，
其 `matched_tokens` 实测为 `["IP","Me","Qu","es","et","st","ta","ue"]`——即匹配器 `kw_tokens` 产生的
**2 字符字面碎片**（`es` 落在 *Azores* 内部、`ta`/`st` 落在其它拉丁词内部）。因此：

- 本验证器把共享词分为**词级桥**（拉丁整词，可作语义支持）与**字面碎片**（噪声，不作支持），
  并把碎片明细写进证据；
- `R3`（域不相交且无词级桥 → MISMATCH）正是为这类"靠碎片桥接"的选材设计的——它命中了 S04；
  而 S06 的检索文本确实含 `PICO 4`，由 `R2`（同形词义冲突）命中。**两条独立规则各抓一个**。

## 4. metrics JSON 与两次输出一致性

| 检查 | 结果 | 证据 |
|---|---|---|
| 项目模式两次运行**逐字节一致** | ✅（`len=2439` 两次相同） | `logs/phase4ab_metrics_project_a.json` / `_b.json` |
| 全库模式两次运行**逐字节一致** | ✅ | `logs/phase4ab_metrics_corpus_a.json` / `_b.json` |
| 输出**无时间戳**、列表排序固定 | ✅（代码层保证：无时间字段、`sorted` 排序） | `ops/metrics.py` |
| 与 `run.py report` 口径一致 | ✅ 成本估算 $0.093796 与下载字节 11,543,130 两处相同 | `tests/metrics_test.py M6` |

全库汇总（只读、描述性，`--all`）：

```json
{"projects": 197, "scenes": 294, "scenes_with_asset": 159, "on_screen_rate": 1.0,
 "match": 113, "mismatch": 13, "unknown": 168, "semantic_mismatch_rate": 0.0442,
 "loudness_ok": 54, "requests": 12, "downloaded_bytes": 76759808}
```

> **口径说明**：`UNKNOWN=168/294`（57%）反映**知识库覆盖有限**（历史项目大量使用中文命名本地素材/纯色底）；
> 13 个被标记 `MISMATCH` 的历史镜头**没有标注**，**只登记为待人工复核**（`logs/phase4ab_semantic_corpus.json`），
> **不声称**它们是已确认错误。`loudness_ok=54` 只统计**有响度证据**的项目（3-B 之前的项目无此字段）。

## 5. `provider=none` 回归证据

| 检查 | 结果 | 证据 |
|---|---|---|
| `config/config.json` 未被修改 | ✅ 现 sha256 `b264644539b2adbb…` == 冻结基线 manifest 中的值 | `logs/phase4ab_provider_none.txt`、`tests/metrics_test.py M5d` |
| 默认配置产出的项目仍走本地/无外部素材路径 | ✅ 样本 `p_611d6a99a4c1`：`mode=none`、`external_requested` 为空、请求/下载字节均为 0 | 同上（`M5b`） |
| 默认路径仍能产出成片 | ✅ 该样本有 `render_output`；套件与批次全绿（§6） | `M5c`、§6 |
| 新命令不改状态 | ✅ `metrics`/`semantic-check` 前后 DB sha256/行数不变、写操作被 SQLite 拒绝 | `tests/metrics_test.py M4`、`tests/semantic_check_test.py D3/D4` |

## 6. 3-A / 3-B 回归结果

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **36 total / 36 rc=0 / FAILED: []**（34 旧 + 新增 `semantic_check_test` **28/28**、`metrics_test` **18/18**） |
| **3-A 真实链路复核（离线）** | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS / 0 FAIL / 0 PENDING** |
| **3-B 响度契约（离线实测当前交付成片）** | `phase3b_audit.py <显式路径>` | 正式链成片 **-16.1 LUFS / TP -2.7 dBTP（Δ -0.1，达标）**；`stage32b` 交付成片 **-16.8 / -1.9（达标）**；E2E A 组成片 **-16.1 / -2.9（达标）** |
| 3-B 契约单测 / 失败路径 | `tests/audio_loudness_test.py` / `phase3b_failure_paths.py` | **32/32** / **12/12** |
| 3-C 只读报告 | `tests/report_command_test.py` | **18/18** |
| 2-C 追溯 / 故障矩阵 | `phase2c_trace.py` / `phase2c_fault_matrix.py` | **38/38** / A/C 出片、B/D **BLOCKED** |
| 2-D 边界 / Provider E2E | `phase2d_boundary_matrix.py` / `phase2d_provider_e2e.py` | **40/40** / **12/12** |
| ingest / E2E / 真实小测 / 二进制 / 2-A·B 验收 / 3-C 成本 | 同批次 | 全部 rc=0（ingest 抽帧 0.747；E2E A/B/C **SETTLED**；`real_small_test` PASS（MockLLM=0）；`check_binaries` PASS；`phase2_accept --verify` PASS（12/12 在屏，1 项 UNKNOWN）；`phase3c_cost_boundary` rc=0） |
| 批次汇总 | `phase3a_regression_batch.py` | **23 项中 21 项 rc=0**；**2 项非零且均为真实网络用例（环境）**，见下 |

### 6.1 两项网络回归：`PENDING（环境）`——不是本阶段代码问题

| 项 | 本次结果 | 失败形态 | 环境证据 | 跨时点对照 |
|---|---|---|---|---|
| `phase2e_failure_paths.py` | rc=1，**26/29**（用例 6/7/8 未达预期） | 三者都停在 **`PROVIDER_TIMEOUT`**（这三例都需先做**真实搜索**） | `logs/phase4ab_net_probe.txt`：`commons/upload.wikimedia.org` **TCP 可连、TLS 握手超时**；`api.deepseek.com` 0.04s、`speech.platform.bing.com` 0.97s **正常** | 约 1 小时前的 3-C 批次中同一脚本 **29/29**（`logs/phase3c_batch_console.txt`） |
| `phase2e_real_provider.py` | rc=1 | `TransportError: [PROVIDER_TIMEOUT]` | 同上 | 3-C 批次中同一脚本 **13/13** |

- **归因**：Wikimedia 域名再次出现**链路级 TLS 阻断**（与 3-A 记录的环境事件同型），与本阶段代码无关——
  §1 的变更清单显示本阶段**未触碰**任何 provider / retrieval / 网络代码；失败发生在传输层握手阶段。
- **纪律**：这两项**如实标记 `PENDING（环境）`，未改写为 PASS，也未修改其期望值**（批次判读里仍是"非预期结果"）。
  网络恢复后重跑即可（`python docs/regression_2x/phase2e_failure_paths.py`、`... phase2e_real_provider.py`）。
- **边界澄清**：本阶段的**范围判定不受影响**（4-A/4-B 的验收全部离线完成且全绿）；但若以"批次必须 100% 全绿"
  作为门槛，则**整体回归应记 `PENDING`**，直到这两项网络用例在可用网络下重跑通过。本报告采用前者并在 §判定中双写。

## 7. 新 baseline、文件数、字节数、SHA256、manifest

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4ab-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4ab-baseline.zip`（5,872,360 字节） |
| zip sha256 | `3a7eb41a04d9043bbdb68bc4a7ad817874df152353e16d53d214415ecc90191f` |
| 文件数 / 源码字节 | **345 文件 / 7,490,170 字节**（`src/ config/ tests/ scripts/` + `run.py pyproject.toml README.md CHANGELOG.md STATUS.md`；**排除 `docs/`**） |
| manifest | `baseline_manifest_4.x-phase4ab-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4ab-baseline` → **MATCH**：zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移** |
| 阶段 snapshot | `snapshots/4.x-phase4ab-20260915.{zip,db,json}`（DB sha256 `93b758ee837bf529…`，10,522,624 B） |
| **冻结基线（上一版）未被动过** | `3.x-final-baseline.zip` sha256 仍为 `b82ba77ea85cfd22ad7206b95f2a86b927b585254d375d941a3ee1a1dcc4646f`，且其 manifest 内部一致（`logs/phase4ab_baseline_check.txt`） |

> **说明**：`verify_baseline.py 3.x-final-baseline` 现在会显示 `drifted vs tree: 1 ['src/video_studio/cli.py']`
> ——这是**预期漂移**（本阶段唯一被修改的文件，用于接线两个只读子命令）；**基线工件本身完好**（zip == manifest）。
> 变更全貌见 §1 与 `logs/phase4ab_change_list.json`。

## 判定

- **4-A + 4-B（本授权范围）：`PASS`** —— 交付物、真值表验收（TP=2/FP=0/FN=0）、确定性、离线、只读、
  `provider=none` 不变、测试与证据齐备；未触碰任何冻结契约与数据库结构。
- **完整回归：`PENDING`（仅因 2 项真实网络用例的环境阻断）** —— 36/36 套件 rc=0、批次 21/23，
  2 项网络项（`phase2e_failure_paths`、`phase2e_real_provider`）在 §6.1 中如实标记 `PENDING（环境）`，
  **未**改写为 PASS，也**未**修改其期望值。
- 一并声明：**3-A 成片质量未因本阶段改善**（S04/S06 错配素材仍在片内；替换属 4-C，未授权）。

## 8. 未完成项与已知问题（如实登记，未解决项不得写成已完成）

1. **只检测不改片**：4-A/4-B **没有**改善 3-A 成片质量——S04/S06 的错配素材**仍在成片内**；
   替换属 **4-C（人审候选替换）**，本次**未授权**。
2. **知识库覆盖有限**：全库 294 镜头中 `UNKNOWN=168`（57%）；历史中文命名素材/纯色底基本无法判定。
3. **13 个历史镜头被标记 `MISMATCH` 但无标注**：仅登记待人工复核，**不得**当作已确认缺陷。
4. **lexicon v1 未收录其它同形词**：例如 `keyboard`（电脑键盘 / 乐器键盘）——实测该类样本会被域交集**误支持为
   `MATCH`**，已用测试 `B9` **固定其观察行为**并在此登记（**未**为了让测试变绿而临时扩表）。
5. **未实现 LLM 语义判定**：授权允许"若必须使用 LLM 需缓存/记账/版本化"，本次选择**离线确定性**方案；
   LLM 判定作为后续可选增强（须缓存 + 记账 + 版本化 + 明确非确定性）。
6. **判定结果不落库**：新增 artifact 类型需先报告并获授权（本次未做），证据以文件形式留在 `logs/`。
7. **真值样本 n=6**：属冒烟级验收，**不构成准确率结论**；须在 4-C/后续阶段扩大标注样本。
8. **3.x 已知问题仍保留**（`docs/KNOWN_ISSUES.md`）：#1 语义误选（本阶段起**可检测**，但**未修复**）、
   #2 2-E 历史成片不可完全复原、#3 `stage32b` +0.4 dB 补偿、#4 中文检索命中率、#5 429 常态、#6 本地素材不做
   许可门禁、#7 响度契约可配置、#8 成本仅估算、#9 失败路径合成契约、#10–#13 等——**状态一律不变**。

## 9. 停止点

按授权：**未**接入第二 Provider、**未**修改默认配置、**未**改数据库结构、**未**自动改选材或生成替换候选、
**未**修改成片、**未**做 BGM/UI/节奏自动改时长/Git tag，**未**改动 Claim/HITL·append-only·redo·
时间轴权威时长·旁白完整性·响度契约·素材验证·许可台账。**已完成即 STOP，不进入 4-C/4-D/4-E/4-F。**
