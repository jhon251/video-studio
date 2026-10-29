# 6-A / M1 实施报告：Production Integrity + Directorial Quality **只读度量层**

- 日期: 2026-09-23
- 授权范围（本轮）：**只实施 M1**（只读 metrics/report）；**未进入 M2 硬门接线**
- 严格遵守：① 未修改 5.x Final / r1 / r2 / r3 **基线**；② 未修改渲染行为 / apad 契约 / 素材选择 / 剪辑 / TTS / 字幕生成逻辑；
  ③ 未自动修复 / 未换素材 / 未剪辑 / 未重渲染；④ 只新增只读 metrics/report 能力；
  ⑤ 未修改 5.x 评估模块、Judge、truth set、threshold（`core/mm_*.py`、`core/multimodal.py`、词表、`mm_*truth*` 一律未动）
- 机器可读产物：
  - `docs/regression_2x/logs/phase6a_integrity_v9.json`（`schema=production-integrity-v1`）
  - `docs/regression_2x/logs/phase6a_direction_v9.json`（`schema=directorial-quality-v1`）

---

## 1. 修改文件（新增/改动清单）

**新增（只读度量层）**
| 文件 | 说明 |
|---|---|
| `src/video_studio/core/integrity.py` | PI-1…PI-6 纯函数度量 + `summarize()`（四态口径，`UNKNOWN≠PASS`） |
| `src/video_studio/core/direction.py` | DQ-1…DQ-7 纯函数度量 + `measure_freeze()`（只读 freezedetect）+ 四态语义规则 |
| `src/video_studio/ops/integrity.py` | `build_integrity_report()`（DB `mode=ro`+`query_only`，只读编排）+ 文本/JSON 输出 |
| `src/video_studio/ops/direction.py` | `build_direction_report()` + 证据加载（复用既有只读 4-B/5-A/5-D/Judge 报告） |
| `tests/integrity_test.py` | M1 自身回归（**28/28**） |
| `tests/direction_test.py` | M1 自身回归（**25/25**） |
| `tests/fixtures/production_integrity_truth_v1.json` | 真值集（19 例：v9 真实样本 + 合成故障夹具口径） |
| `tests/fixtures/build_integrity_fixtures.py` | 合成夹具构建器（离线 ffmpeg，只写临时目录） |
| `docs/regression_2x/phase6a_battery.py` | 6-A 电池（步骤表 AST 取自 5-F 电池；6-A 专用备份/留档路径） |
| `docs/regression_2x/phase6a_audit.py` / `phase6a_extra.py` | 6-A 只读审计脚本（上一轮交付） |

**改动（严格追加，不改既有行为）**
| 文件 | 改动 | 影响面 |
|---|---|---|
| `src/video_studio/cli.py` | 新增两个**只读**子命令 `run.py integrity` / `run.py direction`，并加入既有只读白名单（**不经过 `build_engine()`**） | 仅新增分支；既有命令与渲染路径零改动（见 §6 回归） |

> **未改动**：`agents/**`（含 editing/voice/subtitle）、`core/narration.py`、`core/captions.py`、`core/audio.py`、
> `core/materials.py`、`core/mm_*.py`、`core/multimodal.py`、`ops/report.py`、`ops/metrics.py`、`config/*.json`、任何 baseline/快照。

---

## 2. PI-1 … PI-6 实际输出（v9 真实样本）

命令：`run.py integrity p_96efdc03e1aa --film-task t_d0a54bdf1810`
（成片 `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`；`read_only=true, enforced=false`）

| 指标 | 状态 | 实测输出 |
|---|---|---|
| **PI-1** narration 实际覆盖率 | **FAIL** | narration **961.656 s** / timeline **1532.0 s** → coverage **0.6277**、shortfall **570.344 s**（阈 0.90） |
| **PI-2** 双侧 duration mismatch | **FAIL** | shortfall **570.344 s**（>30 s 且 37.2% > 10%）；`excess=0.0`、`within_tolerance=false`；既有 excess 规则保留 |
| **PI-3** 成片 silence 区间/占比/最长 | **FAIL** | 静音块 **1**：**961.144 → 1532.013 s**、最长 **570.869 s**、占比 **0.3726**、尾部静音 **570.869 s**（阈 8 s / 10% / 5 s） |
| **PI-4** AV 轨道 duration/连续性 | **PASS** | 视频 **1531.96 s** / 音频 **1532.0 s** / 容器 1532.0 s / **38,300 帧** @25 fps；轨差 0.04 s、帧数一致 |
| **PI-5** subtitle coverage/orphan | **FAIL** | **216** cue、显示 987.6 s（占时间轴 0.6446）；**orphan 73 条（0.338）**，首条 **967.4 s**（阈 0.02） |
| **PI-6** narration↔timeline 边界漂移 | **FAIL** | 21 段：最大绝对漂移 **552.16 s**（3 位小数原始值）/**552.2 s**（1 位小数表）、末段漂移 **−568.344 s**（阈 5 s） |
| **汇总** | **FAIL** | FAIL=5 / PASS=1 / UNKNOWN=0 / NOT_ASSESSABLE=0 |

## 3. DQ-1 … DQ-7 实际输出（v9 真实样本）

命令：`run.py direction p_96efdc03e1aa --film-task t_d0a54bdf1810 --evidence docs/regression_2x/logs/audit_p96efdc_mm.json`
（`read_only=true, enforced=false`；freezedetect 实测已启用）

| 指标 | 状态 | 实测输出 |
|---|---|---|
| **DQ-1** Hook visual relevance | **UNKNOWN** | hook=S01：既有各层均为 `UNKNOWN`（4b/5a/5d/judge）→ **UNKNOWN（不得视为 PASS）**；语义项独立标注 |
| **DQ-2** 素材复用/重复 | **FAIL** | 21 镜 **4 唯一素材**（阈 ≥6）；最大素材占比 **0.3329**（510/1532 s） |
| **DQ-3** 静态保持时长 | **FAIL** | 平均 **72.952 s**、最长 **95.0 s**、**21/21 镜 > 25 s**（阈 0.20）；freezedetect 实测冻结块 **389**、最长 **10.8 s** |
| **DQ-4** 视觉密度 | **FAIL** | **0.822 镜变/分钟**（阈 ≥2.0）、唯一素材 0.157/分钟、冻结块 15.2/分钟 |
| **DQ-5** 高潮视觉覆盖 | **FAIL**（结构项）／语义 **FAIL** | 核心论点镜 **20/21**（非核心 = S16），核心内素材 **4**（阈 ≥6）→ 结构 FAIL；语义：核心镜头存在 **MISMATCH** → 语义 FAIL（必须暴露） |
| **DQ-6** 片尾完整性 | **FAIL**（结构项）／语义 **UNKNOWN** | 末 2 镜 **outro 关键词 0**；尾部静音 570.869 s（>5 s）→ 结构 FAIL；语义无充分证据 → UNKNOWN |
| **DQ-7** 总评 | **FAIL** | FAIL=5 / UNKNOWN=1 / PASS=0；语义项单列（DQ-1/5/6），`unknown_is_not_pass=true` |

**语义纪律（本轮硬性要求）**：`MATCH / MISMATCH / UNKNOWN / NOT_ASSESSABLE` 四态显式区分；
无证据 → `NOT_ASSESSABLE`；证据不足 → `UNKNOWN`；**UNKNOWN 与 NOT_ASSESSABLE 在汇总中均不计入 PASS**（有单测覆盖 D1a–D1d、D5a–D5c、D6a/6b、D7）。

## 4. v9 是否被正确识别 —— **是（逐项对齐 6-A 审计与人工结论）**

| 人工/审计事实 | M1 实测 | 是否识别 |
|---|---|---|
| narration **961.656 s** | PI-1/PI-2 输入与输出均为 961.656 s | ✅ |
| timeline **1532.0 s** | PI-1/PI-2 输入与输出均为 1532.0 s | ✅ |
| 静音 **961.14 → 1532.01 s** | PI-3：**961.144 → 1532.013 s**（570.869 s、37.26%） | ✅ |
| **73 条** subtitle orphan | PI-5：**orphan_cues = 73**（首条 967.4 s、占比 0.338） | ✅ |
| 素材重复 / 静态保持 | DQ-2 4 素材、DQ-3 21/21 镜 >25 s、DQ-4 0.822/分钟 | ✅ |
| Hook 无相关性证据 | DQ-1 **UNKNOWN**（不是 PASS） | ✅ |
| 无高潮 / 缺片尾 | DQ-5 结构 FAIL + 语义 FAIL；DQ-6 结构 FAIL（outro 0 + 尾部静音 570.9 s） | ✅ |
| 工程门禁结论 | M1 **不改** 5-M PASS 与 r3 冻结状态（只读层） | ✅ |

## 5. 真值集与测试结果

- 真值集：`tests/fixtures/production_integrity_truth_v1.json`（`schema=production-integrity-truth-v1`，**19 例**）：
  ① `V9-REAL` 真实失败样本（含 961.656/1532.0、静音块、216 cue/73 orphan、逐镜时长与素材、每素材秒数、非核心镜 S16）；
  ② 合成故障口径：T02 短音频、T03 长音频、T04/T05 静音（内部/尾部）、T06/T07 字幕（对齐/orphan）、T08 轨道错位、
  T09 素材重复、T10 静态保持、T11 高密度、T12/T13 片尾（缺/有）、T14 高潮无多样性、T15 段漂移、T16 缺音频；
  ③ 语义三态：T17 UNKNOWN、T18 MISMATCH、T19 无证据 NOT_ASSESSABLE。
- **M1 自身测试（全部通过，可重复运行）**
  - `tests/integrity_test.py` → **28/28**（含 I3e **v9 真实成片**静音、I4c v9 轨道、I5d **v9 真实字幕 73 orphan**、
    I8a/I8b **只读证明**（项目目录零新增、DB sha256 不变）、I9 CLI 结构）
  - `tests/direction_test.py` → **25/25**（含 D3c freezedetect 只读实测、D4c/D5d/D6c v9 真值、D8a 只读证明、D8b/D8c CLI）
- 合成夹具全部离线生成（ffmpeg，写临时目录），**不落项目目录、不写 DB**。

## 6. 回归结果（现有回归）—— 实测

| 范围 | 结果 |
|---|---|
| 全量单元套件（step 25 `unit_suites` 复跑，含 M1 新增两套件） | **51 个 → 51 rc=0**（`integrity_test` **28/28**、`direction_test` **25/25**、`maintenance_fixes_test` **28/28**） |
| 全量批次（24 项） | **22 项符合预期 / 2 项非预期**（**均为环境网络**，见下） |
| 全量电池（25 步，步骤表 AST 取自 5-F 电池） | **24/25 步 rc=0**（唯一红步 = `3a_regression_batch`，其红因即上述 2 项环境项）；总耗时 **4,451 s**；冻结证据日志恢复 **True**（164 改写回拷 / 2 新增 / 0 删除） |
| 关键项抽查 | `metrics_readonly` **18/18**、`run_ingest_test` **PASS**、`e2e_mechanical` **3/3 SETTLED**、`phase2e_real_provider` **13/13**、`real_small_test` **PASS**、`suite_all` rc=0 |
| 未触碰项 | 24 个守卫文件（`core/mm_*.py`、`core/multimodal.py`、`core/semantics.py`、`core/selection_review.py`、`core/audio.py`、`core/materials.py`、`core/narration.py`、`core/captions.py`、`agents/{editing,voice,subtitle}`、`tests/fixtures/mm_*truth*`、`tests/mm_*_test.py`）**与 r3 逐字节一致**（`logs/phase6a_guard_check.json`） |

**2 项环境红项（非代码回归，逐条给证据）**

| 项 | 现象 | 判定 |
|---|---|---|
| `cost_boundary`（`phase3c_cost_boundary.py`） | 在 `balance_cny()`（line 44/139）处 `urllib.error.URLError: [WinError 10061] 目标计算机积极拒绝` → DeepSeek 余额端点不可达；本会话环境**未配置** `HTTP(S)_PROXY`（仅 `npm_config_noproxy`） | **环境（出网路径）**；同一项在 5-M 电池（09-23）为 PASS |
| `phase2e_failure_paths` | **23/29**：6 项真实 provider 故障注入（401 / 下载超时 / 损坏下载 / 许可缺失 / 超大素材）**全部塌缩为 `PROVIDER_DOWNLOAD_FAILED`** → 说明**下载路径本身不可达**，脚本未到达被注入的故障语义 | **环境（Wikimedia 下载路径不可达）**；同一项在 5-M 电池（09-23）为 **29/29**；历史上即登记为"需要真实搜索，不可达时失败（环境，非代码）" |

> 结论：**M1 未引入任何代码/测试回归**（51/51 套件 rc=0；2 项红项为出网环境，且均给出与 09-23 成功轮的对照）。

## 7. baseline / 指纹变化（如实报告）

| 项 | 结果 |
|---|---|
| r3 基线**工件** | `5.x-post-final-maintenance-baseline-r3.zip` **未被改写**（sha 与 manifest 一致、389 条目不变；`logs/phase6a_guard_check.json`） |
| 旧 `5.x-final-baseline` | sha256 **仍为 `be1717b9…`**（未触碰） |
| 工作树相对 r3 的漂移 | **2 个已有文件**：`src/video_studio/cli.py`（新增两个只读子命令）、`tests/maintenance_fixes_test.py`（M8d 守卫**测试契约更新**，见 §9）；**新增 8 个文件**（M1 模块/测试/真值集/夹具） |
| 代码/测试指纹（`src/ config/ tests/ scripts` + 根文件，共 **395** 文件） | r3 冻结时 `c495dd64913c…` → 现在 `da1be48c58bc7c…`；差异 = 上表 10 个文件（2 改 + 8 新增），**无其它任何文件被改动** |
| 成片/产物 | v9 成片 sha256 未变（**未重渲染**）；项目目录/DB 在 M1 运行后 sha256 不变（单测 I8b / D8a 断言） |

> 说明：M1 只新增只读能力，但新增 CLI 子命令必须改 `cli.py`、修守卫口径必须改 `maintenance_fixes_test.py`（二者均在 r3 manifest 内）→
> 工作树出现 **2 处预期漂移**；按纪律**不重冻、不覆盖任何历史基线**，新检查点留待后续授权阶段。

## 8. 边界确认（本轮"不做"清单）

- ❌ 未接线（不阻断、不 BLOCKED、不改任务状态）：PI/DQ 全部指标 `enforced=false`，只报告；
- ❌ 未改渲染/音频链/时间轴/素材/字幕生成；未重渲染任何成片；
- ❌ 未自动修复任何 6-A 发现（#65/#67/#68/#69/#70 仍为登记项）；
- ❌ 未修改 `5.x-final-baseline` / r1 / r2 / r3 基线工件；未新增基线 tag。
## 9. 过程如实披露（本轮）

1. **电池两次运行**：首轮 2026-09-23 22:29 启动，在**第 2 步（批次）执行期间被外部杀死**（Windows Job runner 退出；未生成 summary，电池自带的"另存 + 回拷"收尾未执行）。
   已按纪律处置：`phase6a_preserve_and_restore.py` **补做收尾**（101 个被改写日志回拷、83 个本轮产物留档 `logs/phase6a_rerun/`、复核 **drift 0 / missing 0**）；
   随后给电池加**逐步落盘**（`phase6a_regression_progress.json`，防再次被杀丢失中间结论），并于 09-24 18:55 **完整重跑**得 §6 结果（首轮中间产物保留在留档目录，未改写、未删除）。
2. **M8d 守卫契约更新（本轮唯一改动既有测试）**：5-K 的 `M8d` 原断言"`ops/` 下不得出现任何新文件"，而 6-A/M1 经授权新增两个**只读度量**模块
   （`ops/integrity.py`、`ops/direction.py`）→ 该轮批次内套件首跑 `maintenance_fixes_test` 27/28（唯一红 = M8d）。
   已做**测试契约更新**：改为"**显式白名单**内的只读 metrics/report 模块可新增，白名单外任何新增 ops/ 模块一律 FAIL"，
   并对白名单模块施加 **AST 级只读静态检查**（禁止 `write_artifact`/`attach_artifact`/`build_engine`/`commit`/`create_task`/`run_cycle` 等调用与 SQL 写语句）
   + **只读连接标记**（同时出现 `mode=ro` 与 `query_only`）。**强度不降**：白名单外新增仍 FAIL；更新后该套件 **28/28**，电池 step 25 复跑 **51/51**。
3. **未做**：未接线（PI/DQ 全部 `enforced=false`）、未改渲染/音频链/apad/素材/剪辑/TTS/字幕生成、未重渲染、未自动修复 #65/#67/#68/#69/#70。

