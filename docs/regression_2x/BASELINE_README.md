# 2.x 基线说明（进入 3.x 的起点）

> 本文件是 2.x 基线的**唯一入口说明**。基线以 ZIP + SHA256 + 逐文件 manifest 固化（本仓库**无 Git**）。
> 配套：`REGRESSION_REPORT.md`（验收报告）、`inputs.md` / `prompts.json`（三组选材）、`logs/`（全部日志）、`outputs/`（三组成片）。

## 1. 基线身份

| 基线 | 语义 | ZIP | 文件数 | 源码字节 | manifest |
|---|---|---|---|---|---|
| `2.x-final-baseline` | **2.x 验收时点**（含 V2.0.3 配音修复，**不含** 3.x-Preflight 改动） | `baseline/2.x-final-baseline.zip`<br>sha256 `24dd412529207afa7df9c0b755b5bf7e1816a299268d551f9ae491ab95b3241e` | 691 | 9,057,176 | `baseline/baseline_manifest_2.x-final-baseline.json` |
| `2.x-preflight-baseline` | 3.x 开发的起点（含 3.x-Preflight 全部基础设施修复） | `baseline/2.x-preflight-baseline.zip`<br>sha256 `02a99f6980e8a9de279989f73d1cc77af6790bfdcf80ec353a527c5a6b8f275e` | 322 | 6,997,506 | `baseline/baseline_manifest_2.x-preflight-baseline.json` |
| `3.x-phase1-baseline` | 3.x Phase 1 完成态（真实 LLM 内容保真 + 本地素材最小装配） | `baseline/3.x-phase1-baseline.zip`<br>sha256 `fc583a76a8bfafb13ec918a77bc924e369a6a3167600e2065fd1eac2e3d741ed` | 323 | 7,024,272 | `baseline/baseline_manifest_3.x-phase1-baseline.json` |
| `3.x-phase1.1-baseline` | 3.x Phase 1.1 完成态（费用对账通道修复 + 15 处 subprocess 编码收口 + 2 个新测试） | `baseline/3.x-phase1.1-baseline.zip`<br>sha256 `028202759de6181a52967004207ffa6646dd184d0ea6b901f22951d137e0fb7b` | 325 | 7,046,909 | `baseline/baseline_manifest_3.x-phase1.1-baseline.json` |
| `3.x-phase2-baseline` | 3.x Phase 2-A/2-B 完成态：镜头级素材装配 + 素材时间轴 + 装配单测 | `baseline/3.x-phase2-baseline.zip`<br>sha256 `798911e79934ef1836b285f72baf47aecb4337838cf8536250d0b663703a8caf` | 326 | 7,073,866 | `baseline/baseline_manifest_3.x-phase2-baseline.json` |
| `3.x-phase2b1-baseline` | 3.x Phase 2-B.1 完成态：旁白完整性 + 分段状态/复用/重试 + 渲染时长契约 | `baseline/3.x-phase2b1-baseline.zip`<br>sha256 `574a161bd8ba10206a925169a29d085dad115f6ee25bf8c36cc627e73c326baa` | 328 | 7,125,103 | `baseline/baseline_manifest_3.x-phase2b1-baseline.json` |
| `3.x-phase2c-baseline` | 3.x Phase 2-C 完成态：素材不足降级分类学 + 逐镜头完整可追溯 + 成片抽帧核验 | `baseline/3.x-phase2c-baseline.zip`<br>sha256 `21b685f65db87bf1de4265090d3589dce87cf7747b8a26b272ef93f7bd7bde77` | 330 | 7,181,305 | `baseline/baseline_manifest_3.x-phase2c-baseline.json` |
| `3.x-phase2d-baseline` | 3.x Phase 2-D 完成态：外部素材 Provider 边界层（抽象/标准化/下载校验/许可证/安全资源）+ local_ingest 兼容实现 | `baseline/3.x-phase2d-baseline.zip`<br>sha256 `27b28f7df4f18749af550477886a5eedd1698e5cb40e6acbd36051043dca2b02` | 332 | 7,253,154 | `baseline/baseline_manifest_3.x-phase2d-baseline.json` |
| `3.x-phase2e-baseline` | 3.x Phase 2-E 完成态：接入唯一真实 Provider（Wikimedia Commons）+ 真实网络验证 + 截断/限流/鉴权等 6 项真实缺陷修复 | `baseline/3.x-phase2e-baseline.zip`<br>sha256 `2a2b9ac855ef143a8d423f5ec203ebd764b91069ce916b03932b913073bf7fb5` | 333 | 7,283,985 | `baseline/baseline_manifest_3.x-phase2e-baseline.json` |
| `4.x-phase4ab-baseline` | 4.x 第一阶段（4-A+4-B）完成态：只读质量/成本指标 `run.py metrics` + 离线三态语义核验 `run.py semantic-check`（`MATCH`/`MISMATCH`/`UNKNOWN`，类别式规则、**无数值阈值**）；3-A 真值表 TP=2/FP=0/FN=0；36/36 套件 rc=0 | `baseline/4.x-phase4ab-baseline.zip`<br>sha256 `3a7eb41a04d9043bbdb68bc4a7ad817874df152353e16d53d214415ecc90191f` | 345 | 7,490,170 | `baseline/baseline_manifest_4.x-phase4ab-baseline.json` |
| `4.x-phase4c-baseline` | **4.x Phase 4-C 完成态**：人审候选替换闭环（只读复核队列 `run.py review` + 人工选定记录 `run.py select-candidate` 写**既有** `decisions`/`changelog`；渲染侧只读消费并 **fail-closed**）；真实替换 2 次（S04/S06）经 `redo` 产出 render v4（v1–v3 append-only 保留）；回归 **37/37 套件 rc=0**、批次 22/24（2 项网络 `PENDING（环境）`） | `baseline/4.x-phase4c-baseline.zip`<br>sha256 `08018d4e81d8c3df0a85953158bda1d86c02494237413f4b91b2b6d56f09171d` | 348 | 7,538,751 | `baseline/baseline_manifest_4.x-phase4c-baseline.json` |
| `5.x-phase5e-baseline` | **5.x Phase 5-E 多模态证据质量校准与可解释性完成态（前一基准）**：新增**只读评估层** `core/mm_quality.py`（冻结真值集加载/结构校验/**覆盖度**/指纹钉定、用例评估、**边界距离**、**证据分级**（MODEL_EVIDENCE/RULE_INFERENCE/ENGINEERING_THRESHOLD/UNKNOWN）、**四段式可解释链**、指标聚合、**层间冲突检测**、**阈值敏感性披露**、5-F 建议清单）、`ops/mm_quality.py`（只读编排）、只读子命令 `run.py mm-quality`、**冻结真值集** `tests/fixtures/mm_truth_set_v1.json`（14 例，sha256 `7eb952f2797e180c…`，覆盖 S04/S05/S06 + MATCH/MISMATCH/UNCERTAIN + 视角差异 + 时序切换 + 三类 fail-closed）、`tests/mm_quality_test.py`（**34/34**）；校准结果：**14/14 用例满足真值集（0 违例/0 UNRESOLVED/0 冲突）**、**三层 MATCH 精确率 = 1.0（零误报）**、5-A/5-D 的 UNKNOWN 只出现在"内容正确但证据弱"的 T06/T08 且**阈值扰动下稳健**、**放宽 margin −0.01 即把 T05→MATCH（明确不采纳）**；**未改任何阈值/判定逻辑**，4-B/5-A/5-D 模块与词表 sha256 与 5-D 基线一致、重跑结果与冻结证据一致（原结果未被覆盖）；回归：套件 **45/45 rc=0**、批次 **24/24**、3-A **16/16**、5-C 只读脚本全 rc=0、5-D 53/53、5-E 34/34（冻结证据 drift 0）；5-F 仅提 6 条建议（R1–R6，均未实施） | `baseline/5.x-phase5e-baseline.zip`<br>sha256 `3934369a7f62e14ca93a08b58c24b898345e5f03ee0fe2d46a875fef5f4f2b57` | 374 | 8,140,706 | `baseline/baseline_manifest_5.x-phase5e-baseline.json` |
| `5.x-phase5f-baseline` | **5.x Phase 5-F 多模态最终判定 Judge 完成态（当前基准）**：新增**只读裁决内核** `core/mm_judge.py`（J0–J6 显式规则 + **5 级证据优先级**（4-B 文本/5-A 单帧/5-D 多帧+时序）+ **不选边冲突处理（→UNKNOWN）** + **10 个理由码** + 最终 DoD 生成 + 职责边界声明；**无任何阈值参数**）、`ops/mm_judge.py`（只读编排）、只读子命令 `run.py mm-judge`、**Judge 真值覆盖层** `tests/fixtures/mm_judge_truth_v1.json`（sha256 `a6332858a94d4a7f…`，引用 5-E 冻结真值集 `7eb952f2797e180c…` **未改它**）、`tests/mm_judge_test.py`（**43/43**）；`run.py mm-judge` 在冻结 14 例上 **14/14 满足 Judge 真值（0 违例/0 未解决）**、最终 **MATCH=4 / MISMATCH=3 / UNKNOWN=6（UNKNOWN ≥ 下限 5，合法保留；未为提升通过率放宽任何条件）**、**DoD 12/12 PASS**；#43–#48 逐项处置（#45/#46/#48 解决，#43/#44/#47 保留）、R1–R6 判定完成（R3/R4/R6 进最终产品，R1/R2 未来研究，R5 产品决策）；回归：**电池 25/25 rc=0、套件 46/46 rc=0（含 subprocess_encoding_test 6/6）**、冻结日志恢复 True/DRIFT 0。注意：最终 MATCH 需全层一致 → MATCH 数低于 5-A 单独判定（#50，BY DESIGN）；Judge 未接入生产判定链（#49，默认关闭只读）。 **基线冻结于代理环境验证窗口**（wikimedia 直连 TLS 超时期间经 HTTP 代理完成电池；探测记录 `logs/ss3_proxy_probe.json`） | `baseline/5.x-phase5f-baseline.zip`<br>sha256 `e4dd33ad427020250ae83fc3e53cabca6baf27fd1d5606e375264ca37c39dc4d` | 378 | 8,213,757 | `baseline/baseline_manifest_5.x-phase5f-baseline.json` |
| `5.x-post-final-maintenance-baseline` | **5.x 收尾后维护（5-K，2026-09-21）完成态（当前基准，⚠ 回归未全绿见下）**：形式采纳 post-final 的 2 处既有改动并**修正其缺陷** —— ① 静态图输入 `-loop 1 -framerate 1 -t ceil(d)+2` + 每段 `trim=duration=d,setpts=PTS-STARTPTS`（原 `-t d` 形态每镜静默短 ~1 s，实测 d=2/20/73.4 → 1.000/19.000/72.000 vs 冻结形态 1.967/19.967/73.367；修正后与冻结形态**逐例 Δ=0.000**）；② `tools/ffmpeg_tool.py` `raw`/`render` 超时 1800→7200 s（`probe/concat/ffprobe` 未动）；③ 默认配置 = 当前官方模型（M/F `deepseek-flash`、R `deepseek-v4-pro`；router 不再回退历史别名并登记 `LEGACY_MODEL_IDS`）；④ 新增 `tests/maintenance_fixes_test.py` **28/28**（含"视频输入路径不受影响"反证与 Judge/真值集/阈值/评估器/人工决策链**逐字节守卫**）；⑤ CHANGELOG 补 5-H/5-I/5-J/5.x Final/5-K 并修复倒序；⑥ `.bak` 杂物隔离留痕；⑦ 审计发现只登记（KNOWN_ISSUES #52–#64）；**禁改项实测未改**：Judge/truth set/threshold/multimodal evaluator/human decision chain 与 `5.x-final-baseline` **逐字节一致**，`5.x-final-baseline.zip` 哈希不变。⚠ **回归状态（明示未全绿）**：针对性 28/28 ✅；批次 24 项 **21 符合预期 / 3 红**（`metrics_readonly` 钉定过期、`run_ingest_test`=#62、`phase2e_real_provider`=`PROVIDER_TIMEOUT` 环境）；套件 **47 个 → 44 rc=0 / 3 红**（`cost_accounting_test`/`pipeline_mock` 均 `KeyError: 'mock'`、`metrics_test` 17/18）；`e2e_mechanical` rc=0 但结果 MAXROUNDS/BLOCKED（#63）；红项根因 = item ③ 配置副作用或环境网络，**与代码改动无关**；明细 `baseline_status_5.x-post-final-maintenance-baseline.json` 与 `PHASE5K_REPORT.md` | `baseline/5.x-post-final-maintenance-baseline.zip`<br>sha256 `b24023647f263f3f300f6de8af23b4ae532f4d4d769e7a117b68046f6eb48c14` | 385 | 8,346,816 | `baseline/baseline_manifest_5.x-post-final-maintenance-baseline.json` |
| `5.x-post-final-maintenance-baseline-r2` | **5.x 收尾后维护第二版（5-L，2026-09-21）完成态（当前基准，✅ 全绿）**：修 5-K 已确认失败项 —— ① **生产默认仍为真实 DeepSeek**（`config/config.json` 无 `llm.mock`）；② 新增**独立离线 mock 配置** `config/config.mock.json`（= 生产配置逐字副本 + 仅追加 `llm.mock`，来源与不变式写在文件 `_offline` 块），`run_ingest_test` / `run_all_tests`（机械 E2E）/ `cost_accounting_test` / `pipeline_mock` **显式**指定，mock **不是**生产默认（新增 `tests/offline_mock_test.py` **23/23** 守卫）；③ M5d 由过期的 `3.x-final-baseline` **改钉当前有效基线**（测试契约更新，断言强度不变），4-A 证据脚本同步改钉；1 处公开的测试契约更新（"mock 运行费用为 0"→"按价目表如实计价"）；④ `p_96efdc03e1aa` 以 5-K 修正参数**重渲染**（render v8）：**视频轨 1511.0 s → 1531.96 s**（时间轴 1532.0 s），−16.1 LUFS / TP −2.5 dBFS，旧 v7 成片 sha 未变，topic/script/claims/人工决策全未变。**回归（电池 25 步全 rc=0）**：批次 **24/24**、套件 **48/48**、E2E **3/3 SETTLED**、`run_ingest_test` **PASS**、`phase2e_real_provider` **13/13**、针对性 **28/28 + 23/23**、冻结证据日志恢复 **drift 0**；旧 `5.x-final-baseline` sha256 未变。详见 `PHASE5L_REPORT.md`（含 r2 一次性重冻说明：先冻结 `eea8d411…`，补 CHANGELOG 5-L 条目后重冻为 `2adc09c4…`） | `baseline/5.x-post-final-maintenance-baseline-r2.zip`<br>sha256 `2adc09c4092352f3c13af7b000db04b11e5ae34c96eb8389549ad7e3bcfb64e7` | 387 | 8,369,624 | `baseline/baseline_manifest_5.x-post-final-maintenance-baseline-r2.json` |
| `5.x-post-final-maintenance-baseline-r3` | **5.x 收尾后维护第三版（5-M 成片字幕化，2026-09-23 冻结）（当前基准，✅ 全绿）**：把成片"**画面内整段文案**"改为"**底部逐条字幕**" —— ① 新增 `src/video_studio/core/captions.py`（纯函数单一事实源：切句 → 按停顿细分 ≤36 字 → 按视觉宽度折 ≤2 行、优先标点断行、行首不放标点 → 单条显示 = 字数/5.0 clamp **[1,8] s** 并在镜头窗口内均匀铺开 → `to_srt`（每条单行，可文本检索）+ `to_ass`（PlayRes=分辨率、**底部居中 Alignment=2**、Outline=3、字号=高度×4.2%、MarginV=高度×5%））；② `agents/subtitle/agent.py` 改用之产出 cue 化 SRT（21 段 → **216 条 cue**）；③ `agents/editing/agent.py` 删除"每段一条 drawtext（自适应字号/硬折行/**画面正中**/整段 enable）"，改为**一次 libass `ass=filename='…':fontsdir='C\:/Windows/Fonts'`**（滤镜位置不变：concat 后、fade 前；时长契约/音频母带链/素材装配/HITL 均未动）。**验证**：`tests/captions_test.py`（新）**21/21**；视觉探针（真实素材+真实脚本+同款滤镜）单行/两行字幕底部居中无溢出；真实成片 render **v9 `t_d0a54bdf1810`**：容器 1532.0 s / **视频轨 1531.96 s** / 38,300 帧 / **−16.1 LUFS、TP −2.5 dBFS**，topic/script/claims/人工决策**未变**，v1–v8 保留；字幕覆盖率 **64.5%**、最大静默 4.6 s。**回归（电池 25 步全 rc=0，4,397 s）**：批次 **24/24**（含 `phase2e_real_provider` 13/13）、套件 **49/49 rc=0**、E2E **3/3 SETTLED**、`run_ingest_test` PASS、冻结证据日志 **drift 0**、代码/测试指纹电池前后一致（`c495dd64913c…`）；旧 `5.x-final-baseline` sha256 未变。详见 `PHASE5M_REPORT.md`（含两处**如实披露**并已修正的自身缺陷：ASS 命名依赖 `task["task_id"]`、`strip_v2_test` 烧录源 glob 过期；另有 OPEN 登记 #65 旁白/时间轴不匹配 570.3 s） | `baseline/5.x-post-final-maintenance-baseline-r3.zip`<br>sha256 `e02cdaa7309dfbd7d5244a90661d65d40eeaf648f97c5f783f5656a4b10f9a16` | 389 | 8,399,512 | `baseline/baseline_manifest_5.x-post-final-maintenance-baseline-r3.json` |
| `5.x-final-baseline` | **5.x Final 收口与冻结（2026-09-19）**：5-A～5-J 全部 PASS/CLOSED，`5.x FINAL = COMPLETE / FROZEN`；`verify_baseline.py` → **MATCH（missing 0 / drifted 0）**；相对 `5.x-phase5g-baseline` delta = 修改 2（`cli.py`、`ops/report.py`）/ 新增 2（`ops/mm_review_confirm.py`、`ops/test_review_confirm.py`）/ 删除 0；评估子系统（`mm_judge`/`mm_quality`/`multimodal`/`mm_temporal`/词表）**零改动**；人工决策记录 19 条 append-only JSONL；母片 Run01–04 哈希不变。（本行由 5-K 按 `PHASE5_FINAL_CLOSEOUT.md` 事实补记 —— 5.x Final 自身未在本表登记，见 KNOWN_ISSUES #61 ⑨） | `baseline/5.x-final-baseline.zip`<br>sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e` | 384 | 8,314,155 | `baseline/baseline_manifest_5.x-final-baseline.json` |
| `5.x-phase5g-baseline` | **5.x Phase 5-G 多模态真值集 v2 完成态**：真值集扩充为 **32 例 / 3 项目**（多镜头 12 / 纯色 fail-closed 6 / 域边界；运动素材 0 = LIMITATION 如实记录），`core/mm_quality.py` 仅加 v2 校验分支（**评分/判定/阈值零改动**），v1 14 例零回归，p_ab2b 2 处实例粒度层-人分歧如实入档；电池 25/25 rc=0、套件 46/46 rc=0。（本行由 5-K 按 5-G 阶段报告与 `baseline/baseline_manifest_5.x-phase5g-baseline.json` 补记 —— 5-G 自身未在本表登记，见 KNOWN_ISSUES #61 ⑨） | `baseline/5.x-phase5g-baseline.zip`<br>sha256 `355b2a053adeecb6…`（full：见 `baseline/baseline_manifest_5.x-phase5g-baseline.json` 的 `zip_sha256`） | 382 | 8,295,672 | `baseline/baseline_manifest_5.x-phase5g-baseline.json` |
| `5.x-phase5d-baseline` | **5.x Phase 5-D 多帧/时序多模态证据增强完成态**：新增**只读平行证据层** `core/mm_temporal.py`（每镜头 **7 帧**加密采样 + 帧间视觉一致性 + 逐帧域投票 + 边际分布 → **T0–T7 规则** + MATCH/MISMATCH/UNKNOWN + 置信度）、`ops/mm_temporal.py`（只读编排 + 5-A 引用副本）、只读子命令 `run.py mm-temporal`、`tests/mm_temporal_test.py`（**53/53**）；`core/mm_worker_clip.py` **加法式**新增 `return_embeddings`（默认 false → 5-A 输出逐字节不变）；**默认关闭**、fail-closed 齐备；真实结果：v6 计数 `MATCH=4 / MISMATCH=0 / UNKNOWN=2`（与 5-A 同向），冻结 4-B 真值产物上 S04/S06 `MISMATCH`（方向与 4-B 一致）；**解释 5-C 的 S06 退化**：v5(front) `MATCH/HIGH`（中位边际 0.0745）vs v6(side) `UNKNOWN/MEDIUM`（0.0061），两版**逐帧投票均 1.0、无 split** ⇒ 非采样噪声、而是视角导致的稳定域区分度不足；**不改 4-B/5-A 结果**、DB 零写、项目 78 文件未变；回归：套件 **44/44 rc=0**、批次 **24/24**、3-A **16/16**、5-C 只读脚本全 rc=0（冻结证据 drift 0） | `baseline/5.x-phase5d-baseline.zip`<br>sha256 `cab3324bad69bb56252cce7344372dff5fa90e6d980c030843e072019e2d73d8` | 370 | 8,042,659 | `baseline/baseline_manifest_5.x-phase5d-baseline.json` |
| `5.x-phase5c-baseline` | **5.x Phase 5-C 人工候选替换生效 + 全链复验完成态**：人工（`human:project-owner`）明确选定 5-B 排序第一候选后，走**既有 4-C 闭环**（`select-candidate` → `decisions`+`changelog` → 人工 `redo`：S06 `front`→`side`，decision `d_5ffb9971d5a3` / changelog `#902`）产出 **v6 `t_6d692b93e342`**（v1–v5 全部保留）；替换后复验：h264+aac / 104.0 s、**独立 ebur128 −16.1 LUFS / TP −2.7 dBTP**、**6/6 抽帧 corr_ok**（S06 像素级证实为 side 素材 0.354 > front 0.215）、4-B `MATCH=6`、attribution 1:1（6/6）、许可门禁 6/6、**库级 append-only：删除 0 / 改写 0**、**仅 S06 变化**、fail-closed N1–N5 全 PASS 且零写入；**如实登记退化**：S06 的 5-A 由 `MATCH` → `UNKNOWN/MM_AMBIGUOUS`（v6 计数 MATCH 5→4 / UNKNOWN 1→2，**无 MISMATCH**，未调阈值未改逻辑）；唯一代码改动 = `tests/multimodal_test.py` F2 过期校准（首轮 42/43 → 修正后 43/43，失败证据留档）；回归：3-A 16/16、3-B ×2 rc=0、4-A…4-G/5-A/5-B 证据脚本 rc=0、套件 **43/43 rc=0**、批次 23/24（唯一非预期项 = 网络 `PENDING（环境）`） | `baseline/5.x-phase5c-baseline.zip`<br>sha256 `227c3a2d2be5675a69a3a0bf321d9575eea64a0138d0e2d0930e47f9e0268525` | 367 | 7,955,906 | `baseline/baseline_manifest_5.x-phase5c-baseline.json` |
| `5.x-phase5b-baseline` | **5.x Phase 5-B 多模态候选生成完成态**：基于 5-A 三态判定 + 视觉证据，为 **MISMATCH/低置信**镜头**只生成候选**（候选含 asset/来源/许可证/**CLIP 视觉相似度**/旁白关联/风险与限制）；**不自动选材·替换·redo**，不写库不写产物（`select_candidate_called=0`、`redo_triggered=0`），生产变更仍只走 4-C 人工闭环；真实 S04/S06 → `CANDIDATES_READY`（0.2886/0.2817/0.2788，均 `FREE_ATTRIBUTION`）且**包含 4-C 历史人工选定素材**；三路径齐备（合格候选 / 空池 `MMC_NO_CANDIDATES` / 许可不合格 `MMC_NO_LICENSED_CANDIDATE`）+ fail-closed；4-B/5-A 证据原样保留；套件 **43/43 rc=0**、批次 24/24 rc=0 | `baseline/5.x-phase5b-baseline.zip`<br>sha256 `dee0e33cad31418bb04fd76ae9d6d62d394cdd1741e22b8ba7ef31e9a39ab67e` | 367 | 7,946,132 | `baseline/baseline_manifest_5.x-phase5b-baseline.json` |
| `5.x-phase5a-baseline` | **5.x Phase 5-A 多模态语义验证器完成态**：真实视觉模型 **CLIP ViT-B/32**（本地权重、离线 CPU、确定性）对「旁白期望域 ↔ 实际画面」做**只读**三态验证（MATCH/MISMATCH/UNKNOWN + 相似度证据 + 置信度 + 模型/版本/输入指纹）；**默认关闭**，仅由只读命令 `run.py multimodal-check` 触发；**4-B 结果原样保留**（新增证据层，不覆盖不删除）；fail-closed（模型/环境/解析/超时 → UNKNOWN，禁止伪造）；真值回归在冻结产物 `a_2ed5f41d6b58` 上 S04/S06 双 MISMATCH 与 4-B **6/6 一致**；套件 **42/42 rc=0**、批次 24/24 rc=0 | `baseline/5.x-phase5a-baseline.zip`<br>sha256 `1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac` | 364 | 7,888,961 | `baseline/baseline_manifest_5.x-phase5a-baseline.json` |
| `4.x-final-baseline` | **4.x 最终收口基线**：4-A～4-G 全部授权项经 DoD 矩阵逐项审计并绑定可复算证据；全量回归 41/41 套件 + 批次 24/24；冻结底座（配置/DB schema/许可门禁/旁白/4-B 词表/配音链）**逐字节未改**；LRA 语义经审计判定为 `loudnorm` **目标参数**（非硬门槛，实测闸门对 LRA=99/0.5 结论不变）；4-G 建议全部只读未执行；网络 PENDING 记录未被改写。**相对上一基线仅 `CHANGELOG.md`/`STATUS.md` 两处文档变更（代码 0 修改/0 新增/0 删除）** | `baseline/4.x-final-baseline.zip`<br>sha256 `5992da33fa4cb7ed0ec3767b3137d299def623ca2a645bed18a8cbc50bb9f2c0` | 360 | 7,824,335 | `baseline/baseline_manifest_4.x-final-baseline.json` |
| `4.x-phase4g-baseline` | **4.x Phase 4-G 只读节奏分析与人工建议完成态（当前基准）**：`run.py rhythm <pid> [--json]`（只读，不经过 `build_engine()`）——10 条规则（镜头过短/过长、旁白段落过短/过长、切换落在旁白句中、旁白超时轴被裁、切换密度高/低、静态画面持续、BGM duck 碎片化）+ 6 类 UNKNOWN（**无法判断时不给建议**）；每条建议带 scene_id/当前时长/规则/证据/动作/风险/置信度且 `status=SUGGESTION、applied=false、executed=false`；**不改**时间轴·时长·旁白·素材·BGM、不自动 redo、不绕过 HITL、不写库/不写产物；真实项目只读实测 11 建议/0 UNKNOWN；套件 **41/41 rc=0**、批次 24/24 rc=0 | `baseline/4.x-phase4g-baseline.zip`<br>sha256 `1daf93a1a3971ae5b0c22b57b1fe81a23a878d763c543ea801aabd02adf013c3` | 360 | 7,819,574 | `baseline/baseline_manifest_4.x-phase4g-baseline.json` |
| `4.x-phase4f-baseline` | **4.x Phase 4-F 可选 BGM + 旁白 ducking 完成态**：BGM 为**默认关闭**的可选扩展（缺省不新增任何输入/滤镜，既有输出行为不变）；来源/sha256/许可/**attribution** 全量校验，失败一律 fail-closed（`[BGM_REJECTED] <code>`，不静默降级）；确定性 ducking 规则（旁白期间 -26 dB / 之外 -20 dB / 250 ms 线性过渡、提前 ramp、重叠合并、`amix normalize=0`）；实测 duck 深度 **6.0 dB**、旁白电平与单独旁白一致、成片 **-15.9 LUFS / TP -8.0 dBTP**；套件 **40/40 rc=0**、批次 24/24 rc=0 | `baseline/4.x-phase4f-baseline.zip`<br>sha256 `214374a1d14a6daf2729c7a8df63056bb8562dcaa4fa5e27e4e5d7cd59f45a23` | 357 | 7,759,635 | `baseline/baseline_manifest_4.x-phase4f-baseline.json` |
| `4.x-phase4e-baseline` | **4.x Phase 4-E 检索质量量化完成态**：固定测试集 A/B 基准（23 语料 / 21 查询 / 六组）+ 多语言检索词典（12 概念对齐 4-B 的 12 域）+ 指标 TP/FP/UNKNOWN/FN 可复算；A=v1 冻结 → B=v2 改进：TP 19→43、FP 39→18、域命中 0.6875→**1.0**、top1 0.5625→**1.0**、空结果正确 0.6667→**1.0**；中文组域命中 0.40→**1.00**、真实网络中文查询 0→8 候选；**改进默认关闭**、未绕过许可/校验/4-B；套件 **39/39 rc=0**、批次 24/24 rc=0 | `baseline/4.x-phase4e-baseline.zip`<br>sha256 `275f9a1aa5f4f2f493df10dabcbfd544438146d40679ff47951433d90eb0f55b` | 355 | 7,684,598 | `baseline/baseline_manifest_4.x-phase4e-baseline.json` |
| `4.x-phase4d-baseline` | **4.x Phase 4-D 供给韧性底座完成态**：失败分类表（32 码 → TRANSIENT/PERMANENT/POLICY/LICENSE）+ 有界确定性重试计划（429 `Retry-After` 上限内采纳）+ 搜索层**元数据**缓存（默认关闭、命中后仍重新下载校验）+ 可控降级阶梯（五档 + 三条不变量）；八条路径全部 fail-closed、失败不污染既有产物/台账/版本链；**未接第二 Provider、未改数据库结构、默认配置逐字节未变**；套件 **38/38 rc=0**、批次 24/24 rc=0 | `baseline/4.x-phase4d-baseline.zip`<br>sha256 `f2c783d493a9cb9fe0e2b1601e22a9eaa117d07a2ef885103e0fd2b2d0a51641` | 351 | 7,622,277 | `baseline/baseline_manifest_4.x-phase4d-baseline.json` |
| `4.x-phase4c-fix-baseline` | **4.x Phase 4-C 收尾修复完成态**：S05 复用连带 `MISMATCH` 经 `review` → 人工 `select-candidate` → `redo` 产出 render **v5**（v1–v4 append-only 保留）后**消除**；语义 `MATCH=6/MISMATCH=0/UNKNOWN=0`、成片 104.000s / 响度 **-16.1 LUFS、TP -2.7 dBTP** / 抽帧 6/6；**相对上一基线代码 0 修改/0 新增/0 删除**（仅 `CHANGELOG.md`、`STATUS.md` 两处文档登记）；37/37 套件 rc=0 | `baseline/4.x-phase4c-fix-baseline.zip`<br>sha256 `3b0e998e1c2e0de180b711b71242423ead90ecfca3f5e73e1bfe18078b6ad96e` | 348 | 7,543,538 | `baseline/baseline_manifest_4.x-phase4c-fix-baseline.json` |
| `3.x-final-baseline` | 3.x Final 收口：只读 `run.py report` + 成本边界三口径分离 + 运行手册 + 已知问题台账；回归 34/34 套件、批次 21/21 非预期 = 0 | `baseline/3.x-final-baseline.zip`<br>sha256 `b82ba77ea85cfd22ad7206b95f2a86b927b585254d375d941a3ee1a1dcc4646f` | 340 | 7,422,723 | `baseline/baseline_manifest_3.x-final-baseline.json` |
| `3.x-phase3b-baseline` | 3.x Phase 3-B 完成态：音频响度契约统一（-16 LUFS ±1 LU / TP ≤ -1.5 dBTP）；正式链与 `stage32b` 共用 `core/audio.py` 母带链；成片真实 `ebur128` 实测并 fail-closed | `baseline/3.x-phase3b-baseline.zip`<br>sha256 `ca00c1ec353c1742354b5afee208d374f89912f62df0630062c6f61a92ffb23e` | 337 | 7,384,398 | `baseline/baseline_manifest_3.x-phase3b-baseline.json` |
| `3.x-phase3a-baseline` | 3.x Phase 3-A 完成态：署名/许可台账（`attribution`+credits）与 4 条自动断言 + 许可机械分类/门禁（外部素材范围）+ 查询阶梯（分簇检索）+ 真实链路端到端 **16/16 PASS**（真实下载 11,543,130 字节） | `baseline/3.x-phase3a-baseline.zip`<br>sha256 `296dd44b31020e718ab239d521630b2dcf13b2ca41a7c16cf3961673a8e4e74e` | 335 | 7,333,842 | `baseline/baseline_manifest_3.x-phase3a-baseline.json` |
| `3.x-phase3a-wip` | ⚠ **历史中间态**（2026-09-13 收工断点，**非验收基线**）：当时 Wikimedia 被网络链路阻断、真实下载尚未跑通，按纪律记 PENDING 并冻结为 `-wip`；次日网络恢复后在最终代码上冻结了正式基线 | `baseline/3.x-phase3a-wip.zip`<br>sha256 `ae377d45223ad0374e317f96bd92ce9f2a4c56a805f4ebd37c19b04f4dcf2920` | 335 | 7,326,138 | `baseline/baseline_manifest_3.x-phase3a-wip.json` |

> ⚠ **关于 r1 的回归状态（事实口径补记，未改写历史）**：`5.x-post-final-maintenance-baseline`（r1）冻结时其
> 首轮全量回归为 **FAILED（未全绿）**：批次 21/24、单元套件 44/47、`e2e_mechanical` 结果为 MAXROUNDS/MAXROUNDS/BLOCKED；
> 根因 = 采纳的真实默认配置移除了内联 `llm.mock`（离线用例失去 mock：`KeyError: 'mock'`、真实模型触发冻结 claim 闸门
> fail-closed、离线 E2E 转真实 API），另有 1 项环境网络（Wikimedia TLS）。该 r1 状态文件已标注 `NOT_ALL_GREEN`。
> **上列 5-K 首轮数字保持原样**；红项在 5-L 中逐项修正（见 r2 行与 `PHASE5L_REPORT.md`）。
> 注：上表 r1 行内文字**未改写**（保持冻结当时的口径），后续事实仅以本注补记。

- ZIP 内容：`2.x-final-baseline` = `src/ config/ tests/ scripts/ docs/` + `run.py pyproject.toml README.md CHANGELOG.md STATUS.md`；
  `2.x-preflight-baseline` 起（含 phase1/1.1/2）= 同上但**排除 `docs/`**（避免"文档里写自身 zip 哈希"的循环，只固化代码/配置/测试/脚本 + 根文件）。
- 两者均排除 `output/ projects/ models/ .venv_tts/ bin/*.exe __pycache__`（整树 17.97 GB，源码仅 ~9.5 MB）。
- manifest 的每个文件 sha256 均由**ZIP 内部字节**重算（`rebuild_manifests.py`），与 zip 一一对应，不存在"清单与包不一致"的可能。
- 关键指纹：`config/config.json b264644539b2adbb…`、`voice/agent.py 216eb5f69192261d…`、
  `tools/tts_tool.py b671b339634b9778…`、`run.py dd5aa9af6e6ceb0c…`、`pyproject.toml edf0cdb1cc2659e3…`；
  Preflight 版 `tools/ffmpeg_tool.py 1f2aa35873a6e060…`、`agents/retrieval/agent.py 1ab0e144d74b573c…`（冻结版对应 `b7c0e508c0611fd1…`）。
  Phase 2 新增/变更：`agents/editing/agent.py 8872979cbe95828c…`、`agents/retrieval/agent.py e882391fc826995c…`、
  `tests/scene_assembly_test.py 1d97374d4b10032d…`（`core/engine.py` 在 2-A/B 未改动）。
  Phase 2-B.1 新增/变更：`core/narration.py 579fd024f7a790eb…`（新）、`agents/voice/agent.py 9f102d2b78b8ba91…`、
  `agents/editing/agent.py 7940b9df089c868b…`、`tools/ffmpeg_tool.py 7b62ab0f628da874…`、
  `tests/narration_contract_test.py a169a5f081fde543…`（新）、`agents/retrieval/agent.py` 未变、`config/config.json` 未变
  （`b264644539b2adbb…`，即**未改 mock 配置**）。
  Phase 2-C 新增/变更：`core/materials.py e1358fa8573168de…`（新）、`agents/editing/agent.py 7940b9df089c868b…`、
  `agents/voice/agent.py 9f102d2b78b8ba91…`（产物遍历改最新优先）、`agents/qa/agent.py`（同上）、
  `tests/material_taxonomy_test.py 751fb59ff88b13f3…`（新）、`config/config.json` 仍未改。
  Phase 2-D 新增/变更：`tools/material_provider.py 78c753f9ec32bb53…`（新）、
  `agents/retrieval/agent.py d63302b00a2c7a6d…`、`agents/editing/agent.py 5486c7ca98d191ec…`、
  `core/materials.py 52fd30073ee1f38f…`、`tests/material_provider_test.py 634bc913b055eba9…`（新）；
  `config/config.json` 仍未改（`b264644539b2adbb…`，即**未接入任何真实外部服务**）。
  Phase 2-E 新增/变更：`tools/provider_wikimedia.py 9fd07544d57dc8bb…`（新，唯一真实 Provider）、
  `tools/material_provider.py a52705cc41677cf2…`（容器完整性/错误码透传/节流与 429 退避/文件名黑名单）、
  `agents/retrieval/agent.py 32de908c26a8ab90…`、`agents/editing/agent.py 3d01bb3e9be2afe9…`、
  `core/materials.py e3ff61e1c42089d2…`、`tests/material_provider_test.py 45733c183701fbe4…`；
  **`config/config.json` 仍未改**（默认 `provider=none`）。
  Phase 3-A 新增/变更（基线 `3.x-phase3a-baseline`）：`core/materials.py 253b628c2d0b1348…`
  （许可分类/门禁/适用范围单一事实源）、`tools/material_provider.py 2607f35049716528…`、
  `tools/provider_wikimedia.py f5ee1f6a4183ae45…`（查询阶梯 `shape_queries()`：按拉丁词簇分簇检索 +
  `search()` 逐条尝试/提前停止 + `query_shaping.attempts[]` 留痕）、
  `agents/editing/agent.py 40d2d27728e3358f…`（attribution/credits 交付物 + 台账断言）、
  `tests/attribution_compliance_test.py 5dc20f8937768749…`（新，24/24）、
  `config/config.real.provider.json e74b8da5fbf55fa3…`（新：真实 provider 配置，供真实链路使用）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`，默认 `provider=none`）；
  `agents/retrieval/agent.py`、`agents/voice/agent.py`、`core/engine.py`、`tools/ffmpeg_tool.py` 在 3-A **未改动**。
  基线校验：`verify_baseline.py 3.x-phase3a-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移）。
  收工中间态 `3.x-phase3a-wip`（`provider_wikimedia.py ea37d524de39e195…`，只有"按语料取词"、
  未含分簇检索）保留作历史追溯，**不作为基准**。
  Phase 3-B 新增/变更（基线 `3.x-phase3b-baseline`）：`core/audio.py`（**新**：响度契约单一事实源 =
  母带链构造 + 真实 `ebur128` 测量 + 判定 + 成片级 fail-closed 强制）、
  `agents/editing/agent.py aeaf7c2c9f0e2851…`（母带链接入全部脚本渲染分支 + `aresample` 复原采样率 +
  `render_output.audio_loudness` 证据 + 不达标阻断）、`agents/audio/agent.py`（方案目标值改由契约生成）、
  `stage32b/vo.py`、`stage32b/render.py`、`stage32b/qc.py`（复用同一母带链；qc 由 ±2 LU 收紧为统一 ±1 LU）、
  `tools/ffmpeg_tool.py 9313f3b46af526f9…`（probe 新增 `sample_rate/channels`）、
  `tests/audio_loudness_test.py`（**新**，32/32）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`）；
  `core/materials.py`、`tools/material_provider.py`、`tools/provider_wikimedia.py`、`agents/retrieval/agent.py`、
  `agents/voice/agent.py`、`core/engine.py` 在 3-B **未改动**。
  基线校验：`verify_baseline.py 3.x-phase3b-baseline` → **MATCH**（0 缺失、0 漂移）。
  Phase 3-C 新增/变更（基线 `3.x-final-baseline`）：`ops/report.py` + `ops/__init__.py`（**新**：只读报告数据层）、
  `cli.py`（新增 `report` 子命令 + `stdout/stderr` 固定 UTF-8 的 `_force_utf8_io()`）、
  `tests/report_command_test.py`（**新**，18/18：五场景 + 只读性）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`）；
  `core/materials.py`、`tools/*`、`agents/*`、`core/engine.py` 在 3-C **未改动**（只新增只读查询路径）。
  基线校验：`verify_baseline.py 3.x-final-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移**）。
  最终 snapshot：`snapshots/3.x-final-20260915.{zip,db,json}`（DB sha256 `61e05c01ea5bd412…`）。
  运维文档（在 `docs/`，不入包）：`RUNBOOK.md`、`COST_BOUNDARY.md`、`KNOWN_ISSUES.md`、
  `regression_2x/PHASE3C_REPORT.md`、`regression_2x/PHASE3C_CHECKPOINT.md`。
  Phase 4-A/4-B 新增/变更（基线 `4.x-phase4ab-baseline`，4.x 第一阶段）：
  `core/semantics.py`（**新**：离线三态语义验证器，类别式规则、无数值阈值）、
  `core/lexicons/semantics_v1.json`（**新**：语义知识库 v1 = 12 域 + 12 同形词条，带版本与 sha256）、
  `ops/metrics.py`（**新**：只读质量/成本指标，输出确定性）、
  `cli.py`（**唯一被修改文件**：接线 `metrics` / `semantic-check` 两个只读子命令，仍不经过 `build_engine()`）、
  `tests/semantic_check_test.py`（**新**，28/28）、`tests/metrics_test.py`（**新**，18/18）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`，已与基线 manifest 逐字节核对）；
  `core/materials.py`、`core/audio.py`、`tools/*`、`agents/*`、`core/engine.py`、`ops/report.py` 在 4-A/4-B **未改动**。
  基线校验：`verify_baseline.py 4.x-phase4ab-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-phase4ab-20260915.{zip,db,json}`（DB sha256 `93b758ee837bf529…`）。
  **回归注记**：36/36 套件 rc=0；批次 21/23 —— 2 项**真实网络**用例（`phase2e_failure_paths` 26/29、
  `phase2e_real_provider`）因 Wikimedia **TLS 握手超时**（链路阻断，一小时前同一脚本 29/29 与 13/13）
  记 **PENDING（环境）**，未改写为 PASS（详见 `PHASE4A_4B_REPORT.md` §6.1）。
  Phase 4-C 新增/变更（基线 `4.x-phase4c-baseline`）：`core/selection_review.py`（**新**：人工选定校验 + 只读读取，
  复用既有许可门禁）、`ops/selection_review.py`（**新**：`review_queue` 只读队列 + `record_selection` 先校验后写既有
  `decisions`/`changelog`）、`tests/human_selection_test.py`（**新**，18/18）；
  修改 `agents/editing/agent.py`（渲染侧只读消费人工选定 + fail-closed）、`cli.py`（`review`/`select-candidate`）、
  `ops/metrics.py`（仅新增只读参数 `artifact_id`）、`tests/metrics_test.py`、`tests/semantic_check_test.py`；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`）。基线校验：`verify_baseline.py 4.x-phase4c-baseline` → **MATCH**；
  阶段 snapshot：`snapshots/4.x-phase4c-20260916.{zip,db,json}`（DB sha256 `8a05cd7aa83d73e2…`）。
  **4-C 收尾修复（基线 `4.x-phase4c-fix-baseline`，2026-09-16）**：S05 的复用连带 `MISMATCH` 经
  `run.py review` → 人工 `select-candidate`（`asset_f3cf2b80432d`）→ `record_selection`（`decisions d_a683da3c5d3b` +
  `changelog #820`）→ `run.py redo`（render **v5 `t_b8f866ddc062`**，v1–v4 append-only 保留）后**消除**；
  **代码 0 修改 / 0 新增 / 0 删除**（仅 `CHANGELOG.md`、`STATUS.md` 两处文档登记，`baseline_delta.py` 实测）；
  语义 `MATCH=6/MISMATCH=0/UNKNOWN=0`、attribution ⟷ 时间轴 1:1、成片 104.000s / **-16.1 LUFS，TP -2.7 dBTP** /
  抽帧 6/6（S05 0.355）、3-A 16/16、3-B 32/32 + 12/12、37/37 套件 rc=0；
  基线校验：`verify_baseline.py 4.x-phase4c-fix-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-phase4c-fix-20260916.{zip,db,json}`。收尾报告：`PHASE4C_FIX_REPORT.md`。
  Phase 4-D 供给韧性底座新增/变更（基线 `4.x-phase4d-baseline`，**最小增量**）：
  `core/supply.py`（**新**：失败分类表 32 码 → TRANSIENT/PERMANENT/POLICY/LICENSE/UNKNOWN + 有界确定性重试计划
  + 搜索层元数据缓存 `SupplyCache` + 可控降级阶梯 `degradation_plan`）、
  `tools/supply.py`（**新**：`ResilientSupply` façade，`verified_only()` 是唯一入池出口；缓存恢复的候选一律重置为未验证）、
  `tests/supply_resilience_test.py`（**新**，55/55）；
  修改 `tools/material_provider.py`（`TransportError.retry_after_s` + 429 `Retry-After`（上限 30s）+ 下载重试统一走
  `core.supply.retry_decision`；新增 3 个**加法**策略键 `supply_cache=False` / `supply_cache_ttl_s=900` / `retry_after_max_s=30`）、
  `agents/retrieval/agent.py`（外层 façade + 检索产物加法字段 `supply` / `supply_report`）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…` 与基线 manifest 一致）、**无数据库表/列变更**、
  **未接第二 Provider**；八条路径 fail-closed、失败不污染既有产物/台账/版本链（`logs/phase4d_*.json`）。
  基线校验：`verify_baseline.py 4.x-phase4d-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-phase4d-20260916.{zip,db,json}`。报告：`PHASE4D_REPORT.md`。
  Phase 4-E 检索质量新增/变更（基线 `4.x-phase4e-baseline`，**只量化不改选材**）：
  `core/retrieval_quality.py`（**新**：分词 v2 / 词边界匹配 / 概念扩展打分 `score_v2` / zh→en 扩展 `expand_query_latin` /
  指标 `evaluate`·`ab_compare` / 配置 `retrieval_settings` 缺省 v1）、
  `core/lexicons/retrieval_synonyms_v1.json`（**新**：12 概念对齐 4-B 的 12 域 + 歧义形式登记）、
  `tests/retrieval_bench_v1.json`（**新，入基线**：固定测试集 23 语料 / 21 查询 / k=5）、
  `tests/retrieval_quality_test.py`（**新**，35/35）；
  修改 `agents/retrieval/agent.py`（opt-in 接线 + `retrieval_config` 加法留痕；**缺省 v1/不扩展 = 既有行为**）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`）、**无数据库表/列变更**、4-B 词表与真值钉定未动、4-D 行为未动；
  A/B 结果见 `PHASE4E_REPORT.md` §3 与 `logs/phase4e_ab_results.json`；真实网络中文查询探针 `logs/phase4e_network_probe.json`（仅记录）。
  基线校验：`verify_baseline.py 4.x-phase4e-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-phase4e-20260916.{zip,db,json}`。
  Phase 4-F 可选 BGM + ducking 新增/变更（基线 `4.x-phase4f-baseline`，**BGM 默认关闭**）：
  `core/bgm.py`（**新**：`bgm_settings` 缺省关闭；`verify_bgm` 全量校验含**许可门禁与 attribution 必填**；
  `narration_intervals`/`duck_amount_at`/`gain_db_at`/`gain_curve`/`volume_expression` 确定性 ducking 规则；
  `mix_filters` 混音片段与证据）、`tests/bgm_ducking_test.py`（**新**，48/48）；
  修改 `agents/editing/agent.py`（BGM 闸门 + 预混 + BGM 路径两遍母带 + `bgm`/`audio_config` 证据 + credits BGM 段，
  **关闭时不新增任何输入/滤镜**）、`core/audio.py`（**纯加法**：`measure_loudnorm_input`/`normalize_two_pass`，
  既有链与 QC 未改）；**`config/config.json` 仍未改**（`b264644539b2adbb…`）、**无数据库表/列变更**。
  基线校验：`verify_baseline.py 4.x-phase4f-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-phase4f-20260916.{zip,db,json}`。报告：`PHASE4F_REPORT.md`。
  Phase 4-G 只读节奏分析新增（基线 `4.x-phase4g-baseline`，**只读、不写任何生产数据**）：
  `core/rhythm.py`（**新**：`rhythm-advisor-v1`，10 条规则 + 6 类 UNKNOWN，纯函数、仅标准库）、
  `ops/rhythm.py`（**新**：`mode=ro` 只读读取既有 `render_output`/`voice_output` + 输入指纹）、
  `tests/rhythm_advisor_test.py`（**新**，34/34）；修改 `cli.py`（新增只读子命令 `rhythm`，不经过 `build_engine()`）；
  **`config/config.json` 仍未改**（`b264644539b2adbb…`）、**无数据库表/列变更**、未触碰任何生产 agent；
  证据：`logs/phase4g_rhythm_evidence.json`（场景矩阵 + 真实项目只读报告 + 只读/确定性证明）。
  基线校验：`verify_baseline.py 4.x-phase4g-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-phase4g-20260916.{zip,db,json}`。报告：`PHASE4G_REPORT.md`。
  4.x Final Consolidation / Audit（基线 `4.x-final-baseline`，**无产品代码变更**）：
  对照 4.x 总 DoD 逐项审计 4-A～4-G（8 张子表，逐项绑定证据）；全量回归 41/41 套件 + 批次 24/24；
  **冻结底座逐字节审计**（对比 4.x 起点 `4.x-phase4ab-baseline`）：`config/config.json`、`db/schema.py`、
  `core/materials.py`、`core/narration.py`、`core/semantics.py` + `semantics_v1.json`、`agents/voice/agent.py`
  **逐字节未改**；其余改动文件均为加法/默认关闭且**无函数被删除**；
  **LRA 语义判定**：`TARGET_LRA=11` 是 `loudnorm` 目标参数 + 复现参考值，**不是硬门槛**
  （闸门 `check_contract()` 只判 I 与 TP；实测把 LRA 设为 99/0.5，结论不变）；实测 4-C v5 成片 LRA **2.0 LU**、
  4-F 含 BGM 预混 **18.30 LU** → 交付成片 **13.8 LU**；**未改音频链、未改契约常量**；
  4-G 建议全部只读未执行；网络 PENDING 记录未被改写。**verdict = PASS WITH FOLLOW-UP**
  （3 项 follow-up 见 `PHASE4X_FINAL_AUDIT.md` §0）。审计证据：`logs/phase4x_audit.json`（`phase4x_audit.py`）。
  基线校验：`verify_baseline.py 4.x-final-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/4.x-final-20260916.{zip,db,json}`。报告：`PHASE4X_FINAL_AUDIT.md`。
  5.x Phase 5-A 多模态语义验证新增（基线 `5.x-phase5a-baseline`，**默认关闭 + 只读**）：
  `core/multimodal.py`（**新**：`mm_settings` 缺省关闭；期望域推导 4-B 主 / 4-E 回退 + **词边界**命中；
  `frame_plan`；`verdict_for_scene` 三态规则；`run_worker` fail-closed 码表；`validate` 报告与指纹）、
  `core/mm_worker_clip.py`（**新**：真实 CLIP worker，本地权重 `models/clip/…/clip-vit-base-patch32`、
  offline CPU 单线程）、`ops/multimodal.py`（**新**：只读编排，`mode=ro` 读库 + 临时目录抽帧）、
  `tests/multimodal_test.py`（**新**，34/34）；修改 `cli.py`（新增只读子命令 `multimodal-check`，
  不经过 `build_engine()`）；**`config/config.json` 仍未改**、**无数据库表/列变更**、
  **4-B 词表与真值钉定未改**（新增证据层，`overwrites_4b_results=false`）。
  真值回归：冻结产物 `a_2ed5f41d6b58` 上 S04/S06 双 MISMATCH，与 4-B **6/6 判定方向一致**。
  证据：`logs/phase5a_multimodal_evidence.json`（模型指纹 `a63082132ba4f97a…`、逐帧/产物 sha256、只读与确定性证明）。
  基线校验：`verify_baseline.py 5.x-phase5a-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/5.x-phase5a-20260916.{zip,db,json}`。报告：`PHASE5A_REPORT.md`。
  5.x Phase 5-B 多模态候选生成新增（基线 `5.x-phase5b-baseline`，**只生成候选**）：
  `core/mm_candidates.py`（**新**：候选池归一 / `asset_id` / 许可判类与门禁 / **CLIP 视觉证据** /
  资格判定与排除原因码 / 报告）、`ops/mm_candidates.py`（**新**：只读编排 + 人工确认命令**文本**）、
  `tests/mm_candidates_test.py`（**新**，29/29）；修改 `cli.py`（新增只读子命令 `mm-review`，不经过 `build_engine()`）；
  **`config/config.json` 仍未改**、**无数据库表/列变更**、**4-B 词表与 5-A 验证器未改**、**未新增任何写入口**
  （生产变更仍只走 4-C `select-candidate` + 人工 `redo`；实测 `select_candidate_called=0`、`redo_triggered=0`）。
  证据：`logs/phase5b_candidates_evidence.json`（真实 S04/S06 候选 + 三路径 + 4-C 交叉核对 + 只读/确定性）。
  基线校验：`verify_baseline.py 5.x-phase5b-baseline` → **MATCH**（0 缺失、0 漂移）；
  阶段 snapshot：`snapshots/5.x-phase5b-20260916.{zip,db,json}`。报告：`PHASE5B_REPORT.md`。
  5.x Phase 5-C 人工候选替换生效 + 全链复验（基线 `5.x-phase5c-baseline`，**运维/闭环阶段**）：
  **`src/` 零改动**；唯一代码改动是 `tests/multimodal_test.py` F2 的**过期校准**（写死"5 个成片" → 成片字典逐字节未变
  **且** 成片条数 == DB 成功渲染版本数；首轮 42/43 的失败证据留档于 `logs/phase5c_rerun/PRESERVED_*`，登记 `KNOWN_ISSUES.md` #37）；
  替换由**人工**经 4-C 既有闭环完成（`select-candidate` → decision `d_5ffb9971d5a3` + changelog `#902` → 人工 `redo` → v6）；
  **未新增任何写入口、未改任何阈值/契约/词表**；`config/config.json`、DB schema 均未改。
  证据：`logs/phase5c_*.json`（前后对比 / 成片核验 / append-only（库级）/ fail-closed / 回归汇总）、
  `logs/phase5c_rerun/**`（全量回归输出，冻结日志已原样恢复 drift 0）、
  证据归档 `snapshots/phase5c-tests-archive-20260916.zip`（sha256 `1135ad4b898c1703…`）。
  基线校验：`verify_baseline.py 5.x-phase5c-baseline` → **MATCH**（0 缺失、0 漂移）；
  相对 5-B 的 delta：**修改 3（CHANGELOG.md / STATUS.md / tests/multimodal_test.py）/ 新增 0 / 删除 0**；
  阶段 snapshot：`snapshots/5.x-phase5c-20260916.{zip,db,json}`。报告：`PHASE5C_REPORT.md`、断点卡 `PHASE5C_CHECKPOINT.md`。
  5.x Phase 5-D 多帧/时序多模态证据增强（基线 `5.x-phase5d-baseline`，**只读平行证据层**）：
  `core/mm_temporal.py`（**新**：7 帧采样 / 时序一致性 / 逐帧投票 / 边际分布 / **T0–T7 规则** / 三态 + 置信度）、
  `ops/mm_temporal.py`（**新**：只读编排 + 5-A 引用副本）、`tests/mm_temporal_test.py`（**新**，53/53）；
  修改 `cli.py`（新增只读子命令 `mm-temporal`）、`core/mm_worker_clip.py`（**加法式** `return_embeddings`，
  默认 false → 5-A 输出逐字节不变，已由 H4/H5/I1 断言）；
  **`config/config.json` 仍未改**、**无数据库表/列变更**、**4-B 词表与 5-A 判定模块未改**、
  **未新增任何写入口**（不换材/不选材/不 redo/不改时间轴；实测 DB 字节与五张表行数未变、项目 78 文件未变）。
  证据：`logs/phase5d_evidence.json`（ALL_GREEN=true：真实运行/视角解释/阈值敏感性/受控夹具/fail-closed/只读证明）。
  基线校验：`verify_baseline.py 5.x-phase5d-baseline` → **MATCH**（0 缺失、0 漂移）；
  相对 5-C 的 delta：**修改 4（CHANGELOG.md / STATUS.md / cli.py / mm_worker_clip.py）/ 新增 3 / 删除 0**；
  阶段 snapshot：`snapshots/5.x-phase5d-20260917.{zip,db,json}`。报告：`PHASE5D_REPORT.md`。
  5.x Phase 5-E 多模态证据质量校准与可解释性（基线 `5.x-phase5e-baseline`，**只读评估层**）：
  `core/mm_quality.py`（**新**：冻结真值集校验/覆盖度/指纹钉定 + 用例评估 + 边界距离 + 证据分级 +
  可解释链 + 指标 + 层间冲突 + 敏感性披露 + 5-F 建议）、`ops/mm_quality.py`（**新**：只读编排）、
  `tests/fixtures/mm_truth_set_v1.json`（**新，冻结真值集 14 例**）、`tests/mm_quality_test.py`（**新**，34/34）；
  修改 `cli.py`（新增只读子命令 `mm-quality`）。
  **`config/config.json` 仍未改**、**无数据库表/列变更**、**4-B 词表/5-A 阈值/5-D 规则一字未改**
  （模块与词表 sha256 与 5-D 基线一致；重跑结果与 5-C/5-D 冻结证据一致）、**未新增任何写入口**、
  **未自动换材/选材/redo、未改时间轴**；实测 DB 字节与五张表行数未变、项目 78 文件未变。
  证据：`logs/phase5e_quality.json`（校准 14/14）、`logs/phase5e_evidence.json`（**ALL_GREEN=true**）。
  基线校验：`verify_baseline.py 5.x-phase5e-baseline` → **MATCH**（0 缺失、0 漂移）；
  相对 5-D 的 delta：**修改 3（CHANGELOG.md / STATUS.md / cli.py）/ 新增 4 / 删除 0**；
  阶段 snapshot：`snapshots/5.x-phase5e-20260917.{zip,db,json}`。报告：`PHASE5E_REPORT.md`。

## 2. 三组选材端到端结果

命令：`python docs/regression_2x/run_all_tests.py [--fresh]`

| 组 | 选材（UTF-8 逐字入库） | 2.x 验收时点 | Preflight 后（全新项目） |
|---|---|---|---|
| A | 做一期介绍黑洞的短视频。 | `p_a96a7b8bcb79` 26/26 SETTLED ✅ | `p_a5414a3b32a8` 26/26 SETTLED ✅ |
| B | 做一期介绍脑机接口发展现状的视频，要求区分真实技术、实验阶段和未来推测。 | `p_11d338f7dc9f` 26/26 ✅ | `p_be9640ccbafd` 26/26 ✅ |
| C | 制作一条60秒科技科普视频，面向普通观众，节奏适中，包含开头钩子、分镜、旁白、字幕和结尾总结。 | `p_1b49b0c2b0b7` 26/26 ✅ | `p_97edad86cda3` 26/26 ✅ |

成片真实性（每组均核验）：h264 1280×720（126 帧 / 4.200s）+ aac 24 kHz 单声道（4.226s），2 条流，
`ffmpeg -f null` 解码 rc=0，抽帧可见烧录字幕，音轨峰值 -3.94 dB / RMS -19.98 dBFS。
**三组成片字节相同**（sha256 `46ac0c5792836df0dd2a0130e31547a4…`）——Mock 模式的必然结果。

本地 ingest 回归：`python docs/regression_2x/run_ingest_test.py`
→ `asset_index.material_mode=local_ingest`(2 文件) → `retrieval` 候选 2（`query_source=dependency_artifacts`）
→ **`render.visual_source=material_timeline` / `material_assembly=SUCCEEDED` / `scenes=1`（mock 脚本仅 1 段）**
→ 成片 2 条流（h264 1280×720 + aac 24 kHz）→ **免费抽帧核验**：t=2.1s 画面与分配素材相关 **0.747**（argmax 命中）。

## 2b. 3.x Phase 2-A/2-B 真实素材装配结果（2026-09-13）

命令：`python docs/regression_2x/phase2_accept.py`（真实 LLM；`--resume/--redo/--verify` 续跑/重做/仅复核）

| 项 | 结果 |
|---|---|
| 项目 | `p_ab2b352e06b8`，选材"做一期介绍 VR 与脑机接口设备长什么样的短视频。"，真实花费 **$0.107305**（19 次调用） |
| 检索 | `material_mode=local_ingest`，3 个候选全部命中（分 25 / 22 / 14，带 `matched_tokens`） |
| 时间轴 | 12 镜头、12/12 有素材、**3 个不同素材**、`material_assembly=SUCCEEDED`、`visual_source=material_timeline` |
| 成片 | `t_dc426762251a_draft.mp4` 14,825,389 bytes / **238.500s** / h264 1920×1080 30fps **7155 帧** / aac 24 kHz 单声道；ffmpeg 解码 **rc=0** |
| 在屏证据 | 8 个已渲染镜头**全部** argmax 命中各自素材（corr 0.672–0.744）；**不同素材**镜头对最大相关 **0.099** |
| 回归 | 28/28 套件 rc=0；3 组机械 E2E SETTLED 出片；真实小测 $0.002558；ingest 链路含抽帧 PASS；ffprobe 真实性 PASS |
| PENDING | 成片 238.5s < 时间轴 438s → S09–S12 未渲染（旁白音轨仅 7/12 段，`-shortest` 截短；**素材装配侧无缺陷**） |

详见 `docs/regression_2x/PHASE2_REPORT.md`；原始证据 `logs/phase2_accept.json`、`logs/phase2_evidence.md`、
`logs/phase2_voice_stage_attempts.md`、`logs/phase2_video_probe_first_render.txt`。

## 2c. 3.x Phase 2-B.1 结果（2026-09-13）：旁白完整性与渲染时长契约

命令：`python docs/regression_2x/phase2b1_fault_inject.py run <pid> [--inject N] [--cycles K]`（受控故障注入）
+ `python tests/narration_contract_test.py`（40 项确定性单测）+ `python docs/regression_2x/phase2_accept.py --verify <pid>`

| 项 | 结果 |
|---|---|
| 受控注入（第 4 段永久网络失败） | cycle1 `real=11 injected=3` → cycle2/3 `real=11`（**成功段 0 次重复生成**）→ `voice BLOCKED`，`[NARRATION_INCOMPLETE]`，`confidence=0.0`，`narration.mp3` 未被覆盖 |
| render 阻断 | `render BLOCKED`（`render 前闸门` 文案），**未产生新成片**；依赖层面不足以防住（render 直接依赖只有 editing_plan+audio_mix）→ 闸门必需 |
| 清除注入后 | `voice 12/12 COMPLETE`，仅补 seg04（该轮 real TTS 调用 **1** 次），11 段 REUSED |
| 时长容差 | `narration.mp3` **439.056s** vs 时间轴 **438.0s** = **0.24%**（容差 10%） |
| 全 timeline 成片 | `t_dba5c8008b82_draft.mp4` 25,033,388 bytes / **438.000s** / 2 流 / 解码 rc=0；`video_duration_ok=true` |
| 抽帧 | **S01–S12 全部命中各自素材**（corr 0.670–0.745），未渲染镜头 **0** 个 |
| 回归 | 29/29 套件；3 机械 E2E 全 SETTLED（17.000s）；真实小测 $0.002967、**MockLLM=0**；ingest PASS |

详见 `docs/regression_2x/PHASE2B1_REPORT.md`；原始证据 `logs/phase2_accept.json`（verdict PASS）、
`logs/phase2_evidence.md` §4b、`logs/phase2b1_fault_inject.log`。

## 2d. 3.x Phase 2-C 结果（2026-09-13）：素材不足降级分类学 + 完整可追溯

命令：`python docs/regression_2x/phase2c_fault_matrix.py`（4 个真实故障项目）+
`python docs/regression_2x/phase2c_trace.py`（逐镜头追溯核对）+ `python tests/material_taxonomy_test.py`（40 项）

| 用例 | render | 关键证据 |
|---|---|---|
| A_normal `p_4aa4468e3f97` | SUCCEEDED | S01 `LOCAL_INGEST`（命中 6）**抽帧命中**；S02 `NO_CANDIDATE`→占位（`selected_asset=null`）**占位被抽帧证实不是素材**；成片 10.0s / decode rc=0 |
| B_no_candidate `p_5bac5e31b984` | **BLOCKED** | 全镜头 `NO_CANDIDATE` → `ASSEMBLY_BLOCKED` → **无成片**；`[ASSET_INSUFFICIENT]` |
| C_low_match `p_4a41155020ff` | SUCCEEDED | `LOW_MATCH`（分数 1 < 阈值 3）→ `THEME_FALLBACK` + `needs_hitl=true`；**降级素材在屏且标注为降级** |
| D_unusable `p_240b84a2edef` | **BLOCKED** | `ASSET_UNUSABLE`（`ASSET_DECODE_FAILED`）；**损坏文件从未进入 ffmpeg**；无成片 |
| 真实 12 镜头项目 | SUCCEEDED | 成片 25,033,388 bytes / **438.000s** / 2 流 / rc=0；**12/12 抽帧命中**（0.670–0.745）；分配与 2-B.1 逐一致 |
| 追溯核对 | — | **38/38 通过**（每镜头完整决策记录 / 占位不伪造 / `appears_in_film` 与证据一致） |

详见 `docs/regression_2x/PHASE2C_REPORT.md`、`PHASE2C_FAULT_REPORT.md`；原始证据
`logs/phase2c_fault_matrix.{log,json}`、`logs/phase2c_traceability.{md,json}`。

## 2e. 3.x Phase 2-D 结果（2026-09-13）：外部素材 Provider 边界层

命令：`python tests/material_provider_test.py`（46 项）+
`python docs/regression_2x/phase2d_provider_e2e.py`（端到端 12 项）+
`python docs/regression_2x/phase2d_boundary_matrix.py`（10 类故障，40 项断言）

| 项 | 结果 |
|---|---|
| local_ingest 兼容实现 | 就地校验（不下载不复制），打分与旧链路一致（16 vs 16） |
| Provider 契约 | 标准化字段完整；`provider/source_id/source_url/license/sha256/bytes` 全可追溯 |
| 10 类故障 | **40/40**：明确错误码、不落盘、不当命中；9 类无成片且 render BLOCKED；许可证类降级到 local_ingest 并出片 + HITL |
| 端到端上屏 | **12/12**：外部素材（`local_catalog / ext-ccby-001 / CC BY 4.0`）进 timeline 且**抽帧证实上屏**（t=2.0s，corr 0.696）；许可证未明候选被拒 → 占位 + HITL + `license_pending` |
| 安全资源 | 危险文件名/可执行扩展名拒绝、magic bytes 类型判定、大小上限流式中断、索引先查后下（传输层 0 次调用）、缓存上限拒绝而非静默淘汰、并发上限、不执行下载内容 |
| 未接入真实服务 | `config/config.json` 未改（`b264644539b2adbb…`），默认 `provider=none` |

详见 `docs/regression_2x/PHASE2D_REPORT.md`、`PHASE2D_FAULT_REPORT.md`；原始证据
`logs/phase2d_provider_e2e.json`、`logs/phase2d_boundary_matrix.json`。

## 2f. 3.x Phase 2-E 结果（2026-09-13）：唯一真实 Provider（Wikimedia Commons）

命令：`python docs/regression_2x/phase2e_real_provider.py`（真实网络 13 项）+
`python docs/regression_2x/phase2e_failure_paths.py`（失败路径 29 项）+ `python tests/material_provider_test.py`（46 项）

| 项 | 结果 |
|---|---|
| 选型与可达性 | Commons **200 / 3.7s / 3882 hits**（免费、无 key、无付费额度）；Openverse 超时（`logs/provider_reachability.txt`） |
| 真实搜索/标准化 | 8 条真实候选，`provider/source_id/source_url/license/attribution` 齐全；许可证类别机械分类 |
| 真实下载/缓存 | 3,636,037 字节（另一轮 21,772 字节且 `rate_limited=21` 后退避重试成功）；内容寻址缓存落盘 |
| **真实上屏证据** | 成片 10.000s / 2 流 / decode rc=0；抽帧 **corr 0.486 / 0.996**，`appears_in_film=true` |
| 失败路径 8 类 | **29/29**：未配置 key / **真实 401** / 429 / **真实搜索超时** / 下载超时 / 截断 / 许可证缺失（+RESTRICTED）/ 策略上限 → 全部 BLOCKED 且无成片 |
| 本轮修的 6 个真实缺陷 | 截断骗过全部检查（→`ASSET_TRUNCATED`）/ 错误码塌缩 / 中文查询未编码 / 文件名白名单过严 / 下载腿缺节流（429 退避）/ 抽帧判据过严（margin 0.15） |
| 未接真实服务时的行为 | 默认 `provider=none` **未改**；未配置/失败时产物含具体错误码，无可用素材 → BLOCKED（不静默成功） |

详见 `docs/regression_2x/PHASE2E_REPORT.md`、`PHASE2E_FAULT_REPORT.md`；原始证据
`logs/phase2e_real_provider.json`、`logs/phase2e_failure_paths.json`、`logs/auth_probe.txt`、
`logs/query_shaping_probe.txt`；中间态归档 `snapshots/3.x-phase2e-wip-20260913.*`。

## 3. 全部测试命令

```powershell
cd C:\mp4agent\video-studio
python scripts/check_binaries.py <某个.mp4>            # 二进制真实性 + 真实探测
python tests/smoke_mock.py                             # 12 项
python tests/pipeline_mock.py                          # 12 项（真实 ffmpeg 成片）
python tests/scene_assembly_test.py                    # 15 项（Phase 2：3 镜头→3 素材装配，免费确定性）
python tests/narration_contract_test.py                # 40 项（Phase 2-B.1：分段状态/复用/重试/闸门/时长契约，免费）
python tests/material_taxonomy_test.py                 # 40 项（Phase 2-C：六类降级诊断/策略/禁止静默降级/阻断，免费）
python tests/material_provider_test.py                 # 46 项（Phase 2-D：Provider 契约 + 10 类故障 + 安全资源，免费）
python docs/regression_2x/run_all_suites.py            # 31 个套件
python docs/regression_2x/run_all_tests.py --fresh     # 三组选材 E2E 出片
python docs/regression_2x/run_ingest_test.py           # 本地 ingest 全链 + 抽帧核验
python docs/regression_2x/real_small_test.py           # 真实 LLM 小测（消耗少量额度；打印 MockLLM 调用数）
python docs/regression_2x/phase2_accept.py             # 真实素材装配验收（消耗额度；--verify 仅复核）
python docs/regression_2x/phase2b1_fault_inject.py     # 受控 TTS 故障注入（status/segments/redo/run --inject/render-args）
python docs/regression_2x/phase2c_fault_matrix.py      # Phase 2-C 素材不足 4 类真实构造
python docs/regression_2x/phase2c_trace.py             # Phase 2-C 逐镜头可追溯核对报告
python docs/regression_2x/phase2d_provider_e2e.py      # Phase 2-D 外部素材端到端（进 timeline + 抽帧上屏）
python docs/regression_2x/phase2d_boundary_matrix.py   # Phase 2-D 10 类外部素材故障矩阵
python docs/regression_2x/phase2e_real_provider.py     # Phase 2-E 真实 Provider 全链路（真实网络，无 key）
python docs/regression_2x/phase2e_failure_paths.py     # Phase 2-E 失败路径（真实/受控 8 类，含 --only 6,8）
python docs/regression_2x/probe_providers.py           # provider 可达性探测（选型用）
python docs/regression_2x/checkpoint_check.py          # 断点自检（stuck 任务 + 语法）
python docs/regression_2x/phase2_evidence.py <ID>      # 证据汇总（任务/成本/素材/音轨/契约/成片/时间轴）
python docs/regression_2x/verify_baseline.py <tag>     # 基线零漂移校验
python docs/regression_2x/rebuild_manifests.py         # 从 zip 重算基线清单（校验用）
```

最近一次结果（`3.x-phase2e-baseline`）：**31/31 套件 rc=0**（含 `material_provider_test` 46/46、
`material_taxonomy_test` 40/40、`narration_contract_test` 40/40）；三组 E2E 全 SETTLED 且出片
（各 17.000s、24000Hz 真实旁白）；ingest PASS；真实小测 PASS（**MockLLM=0**）；真实素材装配 PASS
（438.0s、**S01–S12 全在屏**）；Phase 2-C 故障矩阵 A/C 出片、B/D **BLOCKED 且无成片**、追溯 **38/38**；
Phase 2-D 边界矩阵 **40/40**、端到端 **12/12**；**Phase 2-E 真实 Provider 链路 13/13**（真实搜索/下载、
抽帧 corr 0.486/0.996 证明真实远端素材上屏）、**失败路径 29/29**（含真实 401/429/超时）；二进制检查 PASS；
基线零漂移 **MATCH**。

## 4. 2.x 已知问题（问题清单）

| # | 级别 | 问题 | 状态 |
|---|---|---|---|
| ① | ~~P1~~ | `bin/ffprobe.exe` 曾是 `ffmpeg.exe` 副本（同 SHA256）→ 探测返回"无流"等误导结果 | ✅ **已修**（3.x-Preflight：替换真 ffprobe + 工具层 `FFPROBE_INVALID` fail-closed + `scripts/check_binaries.py`） |
| ② | ~~P1~~ | **Mock 模式内容与选材无关**（不同选材产出字节相同成片） | ✅ **真实链路已验证**（3.x Phase 1：三组真实 LLM 内容各不相同）；Mock 模式本身仍与选材无关（设计如此） |
| ③ | ~~P1~~ | **素材不上屏**：渲染恒为纯色底 + 烧录字幕 | ✅ **已修**（3.x Phase 2-A/2-B：按素材时间轴逐镜头装配；8/8 在屏抽帧命中，不同素材镜头最大相关 0.099） |
| ④ | ~~P2~~ | retrieval 无 query 且读不到 asset_index（`asset_audit` 是兄弟节点）→ ingest 素材永远 0 候选 | ✅ **已修**（query 回退依赖产物 + 项目内"文件最多"索引优先） |
| ⑤ | P2 | **无音乐/BGM 能力**：仅 `audio_plan` 文本（-14 LUFS + BGM 闪避），无 BGM 素材/生成 | **PENDING**（能力缺口，非回归；本轮明确未授权） |
| ⑥ | ~~P2~~ | README 缺 Claim 审核步骤（claim gate 会阻塞 15 类生产任务） | ✅ **已修**（README 补全 0–9 步流程与素材三态） |
| ⑦ | ~~P2~~ | **成片长度由旁白音轨决定**（`-t {total} -shortest`）：`voice` 段不完整时成片被截短，素材时间轴后段镜头不上屏 | ✅ **已修**（Phase 2-B.1：移除 `-shortest` 改 `apad` + `-t timeline`；产出后校验 `\|成片-时间轴\| ≤ 1.0s`；实测成片 438.0s、S01–S12 全在屏，未渲染镜头 0 个） |
| ⑧ | ~~P2~~ | **`VoiceAgent` 失败开放**：TTS 段失败只记 `errors`，任务仍 SUCCEEDED、`confidence=1.0` | ✅ **已修**（Phase 2-B.1：全段齐备才 SUCCEEDED；不完整写 INCOMPLETE 证据后抛错 → FAILED/BLOCKED；逐段 `status/attempts/errors[code]`） |
| ⑪ | ~~P3~~ | `voice` TTS 成功率不稳定（1/12、9/12、7/12；`speech.platform.bing.com` 间歇性连不上） | ✅ **已缓解**（Phase 2-B.1：错误分类 `TTS_NETWORK` 可重试 + 退避重试 3 次 + **成功段复用**（`segments_manifest.json`）→ 复跑只补失败段；实测注入场景复跑 real TTS 调用仅 1 次即达 12/12） |
| ⑫ | P2（新） | **网络依赖显式化**：TTS 不可达时 `voice` 现在会判失败并阻塞管线（这是**要求的行为**，不再是静默降级） | **已记录**：机械 E2E 因此依赖 TTS 可达；若遇断网会如实 BLOCKED，不会伪造旁白 |
| ⑨ | P3 | mock 脚本 `duration_s=15` 与台词长度不匹配（成片按时间轴 17s，旁白实际约 4s → 尾部静音） | PENDING（仅 mock 数据；契约行为正确：旁白短则静音补齐、视频不缩短） |
| ⑩ | P3 | ffprobe 为 2022 full build，与 `ffmpeg 7.1` 版本不同代（功能可用，只用于探测） | 记录在案；如需同版本可后补（本次网络下载被阻断） |
| ⑬ | P3（新） | `LOW_MATCH` 的相似度是**词法**判定（CJK 二元组/单字/拉丁词），会出现"字面无关但语义相关"的素材被判低匹配 | 已如实记录为降级（`THEME_FALLBACK` + `needs_hitl=true`），**不伪装成命中**；语义级镜头↔旁白对齐属后续阶段（本阶段明确不做） |
| ⑭ | P3（新） | 素材可用性判定含**尺寸下限**（默认 320×180）；低于此的自有素材会被判 `ASSET_TOO_SMALL` 并降级 | 策略可配（`editing.min_asset_width/height`）；判定与原因码全部落盘，不静默丢弃 |
| ⑮ | ~~P2~~ | **外部 provider 未接真实服务** | ✅ **已接入唯一真实 Provider**（Phase 2-E：Wikimedia Commons，免费无 key）；默认 `config.json` 仍为 `provider=none`，启用方式见 README |
| ⑯ | P3 | 许可证判定是**机械规则**（空/unknown/unchecked → 拒收 + HITL；`fair use` 等 → `RESTRICTED` 拒收），不做语义判定 | 明确不做"自动许可证判定"（越界）；真实素材需人工确认许可证后再入库 |
| ⑰ | P3（新） | Wikimedia 媒体主机（`upload.wikimedia.org`）会对短时多次下载返回 **429**；搜索 API 不受影响 | 已内置节流（`min_interval_s`）与 429 专用退避/重试预算（`rate_limit_backoff_s` / `rate_limit_retries`），限流次数计入 `stats.rate_limited`；驱动对资产层用例具备"抖动识别 + 重跑" |
| ⑱ | P3（新） | 中文查询对 Commons 命中率低（实测 0 命中），完整旁白拼接查询也会 0 命中 | 已实现**机械查询整形**（去重取前 N 词）；如需中文语料库需另选 Provider（**未授权**，本阶段只接一个） |

**未伪造项**：provider=`none` 时 `image`/`video` 工具直接 `NEEDS_CONFIG` 报错、`search` 降级 OfflineProvider，
均不产生候选；检索为空时产物明确写"未做任何伪造"；镜头关键词交集为空时该镜头记
`fallback_state=SOLID_COLOR_CARD` + `selected_asset=None`，**不拿别的素材顶替**。

## 5. 边界申明（不得混淆）

- **工程闭环 PASS**：`输入选材 → 规划 → 分镜/素材需求 → 执行 → 真实可解码 MP4`，三组各自 26/26 任务、文件可解码。
- **内容保真**：Mock 下文案与选材无关；**真实 LLM 链路已验证内容各不相同**（3.x Phase 1，三组逐环节主题词命中）。
- **真实素材已上屏**（③ 已修，Phase 2-A/2-B）：有抽帧证据（8/8 命中、跨素材相关 0.099）；**且**（Phase 2-B.1 后）
  成片时长 = 素材时间轴时长（438.0s），S01–S12 全部实际出现在成片 → 不再有"素材装配成功但后段没上屏"的情形。
- **旁白要么完整、要么失败**（⑦⑧ 已修）：`voice` 不完整即 FAILED/BLOCKED；`render` 在调用 ffmpeg 前阻断 +
  产出后校验时长；旁白短则静音补齐（不缩短视频），超容差则阻断。网络不可达时管线会如实阻塞，**不会伪造旁白**。
- **BGM PENDING**（⑤）：没有音乐生成/混入能力。
- 禁止放宽：Claim 闸门、HITL 闸门、append-only 产物、exec 隔离、断点恢复（`recover`/`redo`）——以上均为回归门槛。

## 6. 进入 3.x 的安全边界

1. 以**当前基准** `3.x-phase2e-baseline.zip`（sha256 `2a2b9ac855ef143a8d423f5ec203ebd764b91069ce916b03932b913073bf7fb5`，
   零漂移：`python docs/regression_2x/verify_baseline.py 3.x-phase2e-baseline` → **MATCH**）为回归基准；
   历史基准 `3.x-phase2d-baseline.zip` / `3.x-phase2c-baseline.zip` / `3.x-phase2b1-baseline.zip` /
   `3.x-phase2-baseline.zip` / `2.x-preflight-baseline.zip` 保留可查；**不得修改**任何已冻结 ZIP 的内容。
2. 每次合并前必跑 §3 全部命令（套件 + 三组 E2E + ingest + 二进制检查；真实链路按授权另跑）。
3. 不得移除/放宽 §5 末行列出的五道机制；不得改既有 task/artifact/事件契约（26 类产物类型、事件类型、闸门顺序）。
4. DB 迁移须保持历史行可读与 `changelog` 审计链（照 V2.0.2 `migrate()` 做法）。
5. 3.x 新能力以**新增** Agent/模块为主；BGM、**第二个 Provider / 多 Provider 竞价**、自动许可证判定、
   语义级对齐、成本对账、Git tag 的转正需**单独授权**。

## 7. Git 状态

- 仓库**无 `.git`**（`STATUS.md:5` 记载"无 Git 仓库（按用户指示不引入版本控制）"）。
- `git tag 2.x-final-baseline` → **BLOCKED（待用户裁定）**；等价物为 `baseline/` 下的 ZIP + 各自 manifest。
- 若日后 `git init`：需 `.gitignore` 排除 `output/ projects/ models/ .venv_tts/ bin/*.exe __pycache__`（占全树 17.97 GB 中的绝大部分）。
