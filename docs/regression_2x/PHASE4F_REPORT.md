# 4.x Phase 4-F 报告：可选 BGM + 旁白 ducking（2026-09-16）

**授权**：进入 4-F；以 `4.x-phase4e-baseline.zip` 为基线；不使用 Git；保持 3.x 音频链、3-B 响度契约、
旁白完整性、时间轴权威时长、4-A～4-E 逻辑不变；**BGM 必须是 Optional Extension、默认关闭**；
必须有明确的音乐来源/许可状态/attribution；未验证许可、来源不明或校验失败的 BGM 必须拒绝；
旁白必须优先于 BGM；ducking 必须确定性、可复算、可测试；最终母带仍满足 `-16 LUFS ±1` / `TP ≤ -1.5 dBTP` / LRA 契约；
BGM 关闭时既有输出保持原行为；不做节奏自动改时长/自动语义改选材/第二 Provider/UI/自动发布/5.x；
不改数据库结构；**不把 BGM 失败静默降级为未声明的音频输出**。完成后 STOP，不进入 4-G。

**前置校验（基线）**：`docs/regression_2x/baseline/4.x-phase4e-baseline.zip`
sha256 `275f9a1aa5f4f2f493df10dabcbfd544438146d40679ff47951433d90eb0f55b`（实测一致，5,942,274 字节）。

**结论：PASS**（10 条路径全部覆盖；BGM 关闭行为不变；开启时契约达标；失败一律 fail-closed 且不污染台账）。

---

## 1. 变更文件与影响面

| # | 文件 | 类型 | 影响面 |
|---|---|---|---|
| 1 | `src/video_studio/core/bgm.py` | **新增** | BGM 配置（默认关闭）/ 全量校验（来源·sha256·音频流·解码·时长·响度·静音·异常·**许可**·**attribution**）/ ducking 规则（时间段·增益曲线·ffmpeg 表达式）/ 混音片段构造 |
| 2 | `tests/bgm_ducking_test.py` | **新增** | 4-F 单测 **48/48**（A–G 七组，覆盖 10 条路径） |
| 3 | `docs/regression_2x/phase4f_evidence.py` | **新增**（docs，不入基线） | 证据收集（校验矩阵 / ducking 实测 / 成片证据 / fail-closed） |
| 4 | `src/video_studio/agents/editing/agent.py` | 修改（**加法 + 默认关闭**） | 渲染侧：BGM 校验闸门 → 预混（旁白 + 带包络的 BGM）→ BGM 路径专用两遍母带 → 交给**原有**分支；产物新增 `bgm` / `attribution.audio_config`；credits 增加 BGM 段（仅开启时） |
| 5 | `src/video_studio/core/audio.py` | 修改（**纯加法**） | 新增 `measure_loudnorm_input()` 与 `normalize_two_pass()`（仅 BGM 路径调用）；既有 `measure_loudness` / `check_contract` / `mastering_chain` / `enforce_loudness_on_film` **一字未改** |
| — | `CHANGELOG.md` / `STATUS.md` | 修改（文档登记） | 版本条目与断点状态 |

**未改动**：`config/config.json`（sha256 `b264644539b2adbb…` 不变）、`db/schema.py`（**无表/列变更**）、
`core/materials.py`（许可门禁）、`core/semantics.py`（4-B）、`core/supply.py`/`tools/supply.py`（4-D）、
`core/retrieval_quality.py`（4-E）、`core/narration.py`（旁白完整性/时长契约）、3-B 既有母带链与 QC。

## 2. BGM 开关与默认行为证据

| 项 | 实测 |
|---|---|
| 默认 | `tools.bgm` 缺省 → `enabled=False`（`_source=default(disabled)`）；`bed_db=-20`、`duck_db=-26`、`ramp_ms=250` |
| 关闭时渲染 | 渲染 SUCCEEDED，`render_output.bgm.applied=False`、无 `premix`/`master` 字段；**不新增任何 ffmpeg 输入/滤镜**（A4 断言：关闭走原分支，`narration_audio_render = narration_audio`） |
| 关闭时 credits | `attribution.bgm = null`，`credits_text` **不含** BGM 段（G5 断言） |
| 参数越界 | `duck_db > bed_db` → 收敛为 `bed_db` 并记录说明（**不放松"旁白优先"**）；非法 `ramp_ms` → 回退默认（A3） |
| 既有链路 | `core/audio.py` 既有函数未改（A5 断言 `bgm`/BGM 字样不出现在其改动范围）；3-B 套件 **32/32** 通过 |

## 3. ducking 规则、参数与波形/响度证据

**规则（确定性、可复算）**：
1. **旁白时间段**由 voice 产物的**逐段真实时长**顺序累加得到（`narration_intervals`），与旁白音轨拼接顺序一致；不猜、不取整。
2. 旁白期间 BGM 增益 = `duck_db`（默认 **-26 dB**），旁白之外 = `bed_db`（默认 **-20 dB**）；
   边界各做 `ramp_ms`（默认 **250 ms**）**线性**过渡；**旁白开始前提前 ramp**（`[a-r, a]`）进入 duck，
   保证"旁白不被 BGM 盖住"。
3. 相邻/重叠时间段**合并**（`max` 包络）→ 句子中间不会抬起。
4. 混音用 `amix=inputs=2:duration=first:normalize=0`（**不做等权归一**，旁白电平不被改变）。
5. 全部由纯函数产出：`gain_db_at()` / `volume_expression()`；同一 (时间段, 参数) 必然给出同一增益曲线与同一 ffmpeg 表达式（B2/B3/B3b/B5 断言；表达式字符串即证据）。

**实测（`phase4f_evidence.py`，真实 ffmpeg 测量）**：

| 观测点 | 实测 | 规则 |
|---|---|---|
| 旁白期间 BGM 窗口均值 | **-57.1 dB** | duck 档 |
| 旁白之外 BGM 窗口均值 | **-51.1 dB** | bed 档 |
| **duck 深度** | **6.0 dB** | `duck_db - bed_db = -6 dB` ✓ |
| 片尾（旁白结束之后） | **-51.1 dB** | 已恢复到 bed 档 ✓ |
| 混音中旁白窗口电平 vs 旁白单独电平 | **-33.1 dB vs -33.1 dB（差 0.0 dB）** | 旁白优先、未被 BGM 抬高 ✓ |
| 增益曲线采样 | t=0…2.75s 均为 -26.0 dB（旁白区间内）；旁白结束后回到 -20.0 dB | 与表达式一致 ✓ |

## 4. BGM 来源、sha256、许可与 attribution

| 项 | 本阶段证据（测试用自生成音；真实音乐文件走**同一条**校验链） |
|---|---|
| 来源 | `provider=local_bgm`、`source_id=test_tone_v1`（本地自备）；**无 provider 且无 source_id → `BGM_SOURCE_UNKNOWN` 拒绝** |
| sha256 | 校验块记录实测 sha256；如配置里给了期望值则**必须一致**，否则 `BGM_HASH_MISMATCH` |
| 许可 | 经 `core.materials.classify_license` 机械判类：`CC BY-SA 4.0` → `FREE_ATTRIBUTION`（放行）；`fair use` → `RESTRICTED` → **拒绝**；`unknown`/缺失 → **拒绝** |
| attribution | **必填**；缺失 → `BGM_ATTRIBUTION_MISSING` 拒绝。合规时写入 `render_output.bgm.verify.attribution` 与 credits |
| 其它拒绝码 | `BGM_NOT_CONFIGURED`、`BGM_FILE_MISSING`、`BGM_EMPTY_FILE`、`BGM_NOT_AUDIO`、`BGM_DECODE_FAILED`、`BGM_TOO_SHORT`、`BGM_LOUDNESS_NOT_MEASURED`、`BGM_SILENT`、`BGM_ABNORMAL_LOUDNESS`、`BGM_LICENSE_*`、`BGM_PARAM_INVALID`、`BGM_MIX_FAILED` |

**说明（如实登记）**：本阶段**没有下载任何真实音乐作品**（未接第二 Provider、未授权音乐来源），
测试与证据使用**自生成音频**作为 BGM 夹具并**明确标注**为测试用途；许可/来源/attribution 的**校验链**是真的、
对真实音乐文件同样生效（同一 `verify_bgm` 入口）。

## 5. 十条路径覆盖（授权要求 1–10）

| # | 路径 | 实测结果 | 证据 |
|---|---|---|---|
| 1 | BGM 关闭 | 渲染 SUCCEEDED；`bgm.applied=False`；无 BGM 输入/滤镜；credits 无 BGM 段 | D1/D2/G5 |
| 2 | BGM 开启且许可合规 | 渲染 SUCCEEDED；`applied=True`；契约达标（**-15.9 LUFS / TP -8.0 dBTP**） | D3/D4/D5/D6 |
| 3 | BGM 缺失（enabled 但无 source / 文件不存在） | `BGM_NOT_CONFIGURED` / `BGM_FILE_MISSING` → 拒绝（校验层）+ 渲染 fail-closed | C2/C3 |
| 4 | BGM 下载/校验失败 | 非音频/损坏 → `BGM_NOT_AUDIO`/`BGM_DECODE_FAILED`；sha256 不符 → `BGM_HASH_MISMATCH`；空文件 → `BGM_EMPTY_FILE` | C4/C5 |
| 5 | BGM 许可不明或受限 | `unknown` → `BGM_LICENSE_UNCLEAR`；`fair use` → `BGM_LICENSE_RESTRICTED`；缺 attribution → `BGM_ATTRIBUTION_MISSING`；**引擎级**受限许可渲染 → `BLOCKED` 且无成片 | C10/C11/D11 |
| 6 | 旁白与 BGM 重叠时 ducking | 实测 duck 深度 **6.0 dB**（旁白期间 -57.1 dB vs 之外 -51.1 dB）；旁白窗口电平与旁白单独一致（差 0.0 dB） | E1/E2 |
| 7 | 旁白结束后的 BGM 恢复 | 片尾窗口 **-51.1 dB** = bed 档（差 0.0 dB）；恢复段由 `ramp_ms` 线性过渡 | E4/B3 |
| 8 | BGM 过长 / 过短 / 静音 / 异常响度 | 过长 → `atrim` 到片长（`trimmed_to_film=True`，D3）；过短 → 补静音（`padded_after_bgm_end=True`，D8）；静音 → `BGM_SILENT` 拒绝（C6/D9）；异常响度 → `BGM_ABNORMAL_LOUDNESS` 拒绝（C7） | D3/D8/C6/C7/D9 |
| 9 | 渲染失败与 fail-closed | 静音 BGM 与受限许可：渲染 **BLOCKED**、无成片、无 `render_output`、error 带 `[BGM_REJECTED] <code>`；`decisions`/`changelog` 零新增 | D9/D10/D11 |
| 10 | attribution / credits 与最终音频配置一致 | 开启时 credits 含 BGM 段（来源/许可/归属/sha256/ducking）、`attribution.bgm` 齐全、`license_classes_used` 计入 BGM 类别、`audio_config.bgm_applied=True`；关闭时全部为 null/无该段 | G1–G5 |

## 6. 契约与成品证据（ffprobe / 旁白完整性 / 响度）

| 项 | 实测（BGM 开启的成片） |
|---|---|
| 成片 | `t_*_draft.mp4`（引擎级用例，14.000s 时间轴） |
| ffprobe | `video/h264` + `audio/aac` 24000 Hz 单声道，`format.duration = 14.000000` |
| 时间轴权威时长 | `video_duration_ok=True`（timeline 14.0s == video 14.0s） |
| 旁白完整性 | `narration_state=COMPLETE`；渲染前闸门未改（**旁白优先于 BGM 体现在流程顺序**：先判旁白完整性，再处理 BGM） |
| **最终响度** | **ok=True，I = -15.9 LUFS**（目标 -16 ±1）、**TP = -8.0 dBTP**（≤ -1.5） |
| LRA | 契约值 `target_lra=11`（与 3-B 相同，未改）。**收口审计更正（2026-09-16）**：`target_lra=11` 是 `loudnorm` 的目标参数 + 复现参考值，**不是硬门槛**（闸门只判 I 与 TP）；且 `measure_loudness()` 只解析 I/TP，**LRA 并不记录在 `audio_loudness` 证据里**（初版表述不准确，已更正）。实测：预混输入 **18.30 LU** → 两遍母带后与交付成片均 **13.8 LU**（见 `PHASE4X_FINAL_AUDIT.md` §4） |
| 母带方法（BGM 路径） | **两遍线性 loudnorm**（同一契约常量 `-16 / -1.5 / 11`）+ `alimiter` + `aresample`；成片仍由**既有** `enforce_loudness_on_film` 实测把关（未改） |

**为什么 BGM 路径用两遍线性 loudnorm（如实说明工程原因）**：含 BGM 的混音动态更大（实测 LRA≈18 LU），
**单遍动态** loudnorm 会系统性低于目标（该混音实测 **-19.5 LUFS**，偏差 3.5 LU > 既有 3 LU 收尾校正上限
→ 按契约 fail-closed）。两遍法第一遍测量、第二遍 `linear=true` 精确应用（`target_offset=3.53` 被正确采纳），
实测落到 **-15.9 LUFS**。BGM 关闭时**不使用**该函数，既有单遍链与全部行为不变。

## 7. 回归

| 项 | 结果 |
|---|---|
| 套件 | `run_all_suites.py` → **40 total / 40 rc=0 / FAILED: []**（39 + 新增 `bgm_ducking_test` **48/48**） |
| 3-B 响度契约 / 失败路径 | **32/32** / **12/12** |
| 3-A 真实链路（离线复核） | 见 §10 补记（`phase3a_real_chain --resume p_f4b466a4a024`） |
| 4-A / 4-B / 4-C / 4-D / 4-E | 见 §10 补记 |
| 回归批次 | 见 §10 补记 |

## 8. `provider=none` 与网络 PENDING

- `config/config.json` sha256 `b264644539b2adbbf0f6897b5a118b2a` 与 4-E 基线 manifest **一致**；
  `tools.bgm` 缺省不存在 → BGM 关闭；`provider=none` 行为、4-D 缓存/重试、4-E 检索开关默认值均**未变**。
- 两项 Wikimedia 真实网络用例（`phase2e_failure_paths` / `phase2e_real_provider`）**状态与期望值未改写**，
  仍记 `PENDING（环境）`；本轮实测通过**仅作记录**。4-F 全部断言**离线**（自生成音频 + 本地目录 provider）。

## 9. 新 baseline（ZIP + manifest + SHA256）

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4f-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4f-baseline.zip`（5,966,731 字节） |
| zip sha256 | `214374a1d14a6daf2729c7a8df63056bb8562dcaa4fa5e27e4e5d7cd59f45a23` |
| 零漂移校验 | `verify_baseline.py 4.x-phase4f-baseline` → **MATCH** |
| 断点快照 | `snapshots/4.x-phase4f-20260916.{zip,db,json}` |
| 相对上一基线 | **代码 修改 2 / 新增 2 / 删除 0**（+ `CHANGELOG.md`、`STATUS.md` 文档登记） |

## 10. 回归补记（4-A…4-E、3-A/3-B、批次）

| 项 | 命令 | 结果 |
|---|---|---|
| **3-A 真实链路（离线复核）** | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS / FAIL 0 / PENDING 0**（真实 LLM + 真实 Provider 11,543,130 字节 + TTS 6/6 + 时长 104.0s + 抽帧 S01 0.459 / S02 0.921 / S03 0.348 / S04 0.472 / S05 0.355 / S06 0.919） |
| 4-A 指标 | `tests/metrics_test.py` | **18/18** |
| 4-B 验证器 | `tests/semantic_check_test.py` | **29/29**（真值仍钉 `a_2ed5f41d6b58`，**未改**） |
| 4-C 机制 / 现状 | `tests/human_selection_test.py` / `phase4c_evidence.py` | **18/18** / 版本链 v1–**v5 `t_b8f866ddc062`**、语义 `MATCH=6/MISMATCH=0/UNKNOWN=0`、鲨鱼素材仍释放未用 |
| 4-D 供给韧性 | `tests/supply_resilience_test.py` / `phase4d_evidence.py` | **55/55** / 八条路径 **fail-closed 8/8**、不污染检查全真 |
| 4-E 检索质量 | `tests/retrieval_quality_test.py` / `phase4e_ab_benchmark.py` | **35/35** / 改进幅度 B-A：TP **+24**、FP **−21**、域命中 **+0.3125**、top1 **+0.4375**（与 4-E 冻结值一致） |
| 3-B 响度 / 失败路径 | `tests/audio_loudness_test.py` / `phase3b_failure_paths.py` | **32/32** / **12/12** |
| 套件总量 | `run_all_suites.py` | **40 total / 40 rc=0 / FAILED: []** |
| 回归批次 | `phase3a_regression_batch.py` | **24 项全部 rc=0，非预期结果 = 0**（2 项真实网络用例本轮实测通过，**状态仍记 `PENDING（环境）`，未改写**） |

## 11. 冻结结果

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4f-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4f-baseline.zip`（5,966,731 字节） |
| **zip sha256** | **`214374a1d14a6daf2729c7a8df63056bb8562dcaa4fa5e27e4e5d7cd59f45a23`** |
| 文件数 / 源码字节 | **357 文件 / 7,759,635 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/`**） |
| manifest | `baseline/baseline_manifest_4.x-phase4f-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4f-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移） |
| 断点快照 | `snapshots/4.x-phase4f-20260916.{zip,db,json}`（DB sha256 `5bda3091f06eef59…`，15,069,184 字节） |
| 上一冻结基线（未动） | `4.x-phase4e-baseline.zip` sha256 `275f9a1a…f55b` |
| 相对上一基线（`baseline_delta.py` 实测） | **代码 修改 2 / 新增 2 / 删除 0**：改 `agents/editing/agent.py`、`core/audio.py`；增 `core/bgm.py`、`tests/bgm_ducking_test.py`；另有 `CHANGELOG.md`、`STATUS.md` 两处文档登记。`config/config.json` 与 DB schema **未变** |

## 12. 未做与已知限制（如实登记）

1. **未接入真实音乐来源**（无第二 Provider、未下载音乐作品）：BGM 夹具为自生成音频；校验链对真实文件同样生效。
2. **未做 loop 拼接**：BGM 短于片长时**补静音**（不循环、不改变节奏），并在证据里标记 `padded_after_bgm_end`。
3. **ducking 基于旁白时间段（非信号侧链）**：规则显式、可复算、可测试；不做内容自适应压缩。
4. **BGM 路径使用两遍线性 loudnorm**（原因见 §6）；BGM 关闭时链路不变。
5. **不做音乐推荐/风格匹配/情绪判断**；不自动挑选 BGM（只能由配置显式指定）。
6. 3.x/4-C/4-D/4-E 的既有限制**不变**（`KNOWN_ISSUES.md`、各阶段报告 §限制）。

**停止点**：按授权**完成 4-F 即 STOP**，不进入 4-G。
