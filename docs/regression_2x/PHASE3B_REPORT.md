# 3.x Phase 3-B 报告：音频响度契约统一与落地

- 日期：2026-09-15
- 授权范围（逐字）：**"继续执行 3.x Phase 3-B：音频响度契约统一与落地"**（目标 `-16 LUFS` / `TP ≤ -1.5 dBTP` /
  允许误差 `±1 LU`；不得只改方案文本或测试脚本；不达标 fail-closed；真实音频与真实渲染验证；完成后立即 STOP）
- 阶段判定：**PASS**

---

## 0. 判定摘要（逐项）

| # | 授权要求 | 判定 | 证据 |
|---|---|---|---|
| 1 | 先定位并审计两条渲染路径的音频处理差异 | **PASS** | §1（真实实测：正式链 `apad` 无处理 **-19.7 LUFS**；stage32b -17.7 LUFS 且 QC 口径为 ±2 LU） |
| 2 | 在**正式生产链**落地统一响度处理（真实 ffmpeg `loudnorm` + limiter） | **PASS** | §2：`core/audio.py` 母带链接入 `agents/editing` 全部脚本渲染分支；真实成片 **-16.1 LUFS / TP -2.7 dBTP**（§3） |
| 3 | 增加可复核实测 QC（LUFS / true peak / 目标与误差 / 不达标 fail-closed） | **PASS** | §2.3 + §4：`ebur128=peak=true` 实测，`render_output.audio_loudness` 记录；3 条真实故障注入全部 **BLOCKED** |
| 4 | 为响度契约补充自动断言与失败路径测试 | **PASS** | `tests/audio_loudness_test.py` **32/32**；`phase3b_failure_paths.py` **12/12**（§5） |
| 5 | 使用真实音频 / 真实渲染验证，不得用 mock 数值伪造 | **PASS** | §3/§5：真实 TTS 旁白（24 kHz）+ 真实 ffmpeg 渲染 + 真实引擎两次渲染；所有数值均为 ebur128 实测 |
| 6 | 运行完整回归，3-A/2-C/2-D/2-E 不退化 | **PASS** | §6：**33/33 套件 rc=0**；3-A 真实链路复核仍 **16/16 PASS**（抽帧相关系数逐条不变） |
| 7 | 更新报告 / checkpoint / 测试证据 / baseline，记录 SHA256 并做零漂移校验 | **PASS** | §8：`3.x-phase3b-baseline`，`verify_baseline.py` → **MATCH**（0 缺失 0 漂移） |

## 1. 审计：两条渲染路径的音频处理差异（真实实测）

命令：`python docs/regression_2x/phase3b_audit.py`（记录 `logs/phase3b_audit.json`，全部为 `ebur128` 实测）

| 对象 | 原处理链 | 实测 I | 实测 TP | 相对 -16±1 LU |
|---|---|---|---|---|
| **正式 Agent 链**（3-A 真实项目 104s 成片） | 仅 `-af apad`（**无任何响度处理**） | **-19.7 LUFS** | -3.3 dBTP | **FAIL（Δ -3.7 LU）** |
| 正式 Agent 链（2-E 项目成片） | 仅 `apad` | **-22.0 LUFS** | -13.0 dBTP | **FAIL（Δ -6.0 LU）** |
| **stage32b 交付成片** | `loudnorm=I=-16:TP=-1.5:LRA=11,alimiter,volume=+0.4dB` | **-17.7 LUFS** | -2.2 dBTP | **FAIL（Δ -1.7 LU）** |
| 原始 TTS 旁白 | —（TTS 直出） | -19.6 LUFS | -2.3 dBTP | （输入基准） |

差异定性：
- **目标值**两条路径其实一致（stage32b 写 `-16`；而音频 Agent 的 `audio_plan` 却写 `-14 LUFS` + BGM 闪避，
  与实现和交付物都不符）；
- **实现**上正式链**根本没有落地**（只有 `apad`），stage32b 有链但**单遍 `loudnorm` 落在 -17.7**，
  且它的 QC 断言是 `-18 ≤ I ≤ -14`（**±2 LU 旧口径**），所以"-1.7 LU"从未被发现；
- 两条路径的目标值**没有共享定义**（各写各的字符串），也没有对成片做统一的实测判定。

## 2. 实现（单一切实源 + 正式链接入 + 实测 QC）

### 2.1 `src/video_studio/core/audio.py`（新增，单一事实源）

- 契约常量：`TARGET_LUFS=-16.0`、`MAX_TRUE_PEAK_DBTP=-1.5`、`TOLERANCE_LU=1.0`、`TARGET_LRA=11`；
- 滤镜构造：`loudnorm_filter()`、`limiter_filter()`（`alimiter=limit=0.7079` = -3.01 dBFS）、
  `mastering_chain(post_gain_db=0, sample_rate=None)`；
- **真实测量**：`measure_loudness()`（`ffmpeg -af ebur128=peak=true -f null -`，解析集成响度与真峰）、
  `check_contract()`（测不到即**不通过**）、`verify_file()`（产出可写进产物的证据块，含目标/误差/方法）；
- 配置读取：`contract_from_config()`、`mastering_enabled_from_config()`（默认=授权契约值，**默认不放松**）；
- 成片级强制：`enforce_loudness_on_film()`（**fail-closed 语义**见 §2.4）。

### 2.2 正式生产链（`agents/editing/agent.py`）

- 所有**脚本渲染分支**（多镜头 concat / 单背景图 / 纯色底 + 旁白或占位音）都改为
  `-af "<母带链>[,apad]"`，母带链 = `loudnorm=I=-16:TP=-1.5:LRA=11, alimiter=limit=0.7079:…, aresample=<输入采样率>`；
- 渲染完成后对**成片**实测（§2.3）；`render_output` 新增 `audio_loudness` 证据块
  （`ok / measured_lufs / measured_true_peak_dbtp / delta_lu / contract / method / mastering_applied /
  audio_chain / corrections / passes[]`）；
- **不达标 → `TASK_BLOCKED` + `LoudnessContractError`**，不写 `render_output`（绝不产出"成功但不达标"的成片）。

### 2.3 `agents/audio/agent.py`（方案不再说假话）

`audio_plan` 的目标值改为**从 `core.audio` 契约读取**（-16 LUFS / TP -1.5 / ±1 LU / LRA 11），
并如实标注：母带链在渲染阶段**真实执行**、且"本阶段不做 BGM（`bgm.implemented=false`）"
（原方案宣称的 `-14 LUFS` 与 BGM 闪避此前并不存在）。

### 2.4 fail-closed 语义（关键设计）

`enforce_loudness_on_film(film, max_corrections=2, max_correction_lu=3.0)`：

| 情形 | 行为 |
|---|---|
| 达标 | 通过（`corrections=0`） |
| 偏差 ≤ 3 LU（链已生效的收尾残差） | 允许 1–2 次**只重编音频**的收尾校正（`volume`/`alimiter`；`-c:v copy`，不改采样率/时长），每次尝试写入 `passes[]` |
| **偏差 > 3 LU**（说明母带链没生效） | **拒绝静默校正** → 直接判不合格 → 渲染 BLOCKED（避免"把故障修好"从而掩盖故障） |
| 测不到（无音轨/无 ffmpeg） | 判不合格（绝不当作通过） |

## 3. 真实响度测量证据（真实音频 / 真实渲染，非 mock）

| 对象 | 实测 I | 实测 TP | Δ | 判定 | 证据 |
|---|---|---|---|---|---|
| **3-A 真实项目成片重渲染**（104.0s，真实 TTS + 真实 Wikimedia 素材，render `t_b7a62ec8e29a`） | **-16.1 LUFS** | **-2.7 dBTP** | **-0.1 LU** | **达标**（`corrections=0`） | `logs/phase3b_real_evidence.txt` |
| ↳ 独立复测（不信任自述） | -16.1 LUFS | -2.7 dBTP | -0.1 LU | 达标 | 同上 |
| ↳ 音轨属性 | aac 24000 Hz 单声道（**未被 loudnorm 改成 192 kHz**） | | | | 同上 |
| **stage32b 交付成片重跑**（102.1s） | **-16.8 LUFS** | **-1.9 dBTP** | -0.8 LU | **达标** | `logs/phase3b_audit.json` |
| 正式链渲染命令中的链（auditable） | `loudnorm=I=-16:TP=-1.5:LRA=11,alimiter=limit=0.7079:attack=1:release=10:level=false,aresample=24000` | | | | `render_output.audio_loudness.audio_chain` |
| 真实音频片段 ×3（原样 / -20dB / +20dB，取自真实 TTS 旁白） | -16.2 / -16.2 / -16.1 LUFS | -3.0 / -3.0 / -7.2 dBTP | -0.2 / -0.2 / -0.1 LU | 达标 | `tests/audio_loudness_test.py` B 组 |

> 采样率一栏是**实测踩到的真实缺陷**：`loudnorm` 内部按 192 kHz 处理并输出 192 kHz，
> 不显式 `aresample` 就会把 24 kHz 旁白变成 192 kHz（AAC 再降到 96 kHz）。首版测试即抓到
> （`film sample_rate=96000` vs `narration 24000`），修复后 `D9` 断言通过。

## 4. QC 的落地位置与可复核性

| 环节 | 位置 | 说明 |
|---|---|---|
| 处理 | `agents/editing/agent.py::_narration_args` | 母带链进入真实 ffmpeg 命令（写入 `audio_loudness.audio_chain`） |
| 判定 | `agents/editing/agent.py::render`（时长校验之后、抽帧核验之前） | `enforce_loudness_on_film` 实测成片；不达标 → `TASK_BLOCKED` + 异常 |
| 证据 | `render_output.audio_loudness` | 目标值/实测值/误差/方法/链/校正次数/每次尝试 |
| 旧路径 | `stage32b/render.py` + `stage32b/qc.py` | render 用同一条链（保留 +0.4dB 补偿）并做同样实测；qc 断言从 **±2 LU 收紧为统一 ±1 LU** |
| 只读复核 | `docs/regression_2x/phase3b_real_evidence.py`、`phase3b_audit.py` | 直接读产物 + 独立 `ebur128` 复测 |

## 5. 测试与失败路径（真实渲染，非 mock）

`tests/audio_loudness_test.py` → **32/32 PASS**（命令：`python tests/audio_loudness_test.py`）

| 组 | 内容 | 关键实测 |
|---|---|---|
| A（11 项） | 契约常量/滤镜串/配置默认不放松/判定原语（测不到、超差、真峰超限、达标） | `-16.0/-1.5/1.0`；`LOUDNESS_NOT_MEASURED`/`LOUDNESS_OUT_OF_RANGE`/`TRUE_PEAK_EXCEEDED` |
| B（5 项） | 真实旁白片段（原样/-20dB/+20dB）过母带链 | -16.2/-16.2/-16.1 LUFS，TP ≤ -3.0 dBTP，采样率 24000 保持 |
| C（6 项） | 成片级强制语义 | 大幅偏差（-44.7 LUFS / 28.7 LU）**拒绝静默校正**；小残差（-18.2）收尾校正至 -16.0；无音轨 → 不合格 |
| D（10 项） | **正式引擎渲染入口**（真实 TTS 旁白 + 真实 ffmpeg） | 成片 -16.2 LUFS / TP -3.0 dBTP；`audio_loudness.ok=true`；时长 14.0s（2-B.1 契约不变）；**音轨 24000 Hz 保持**；`apply_mastering=false` → **BLOCKED**（`LOUDNESS_OUT_OF_RANGE：I=-19.7`）且不交付成片 |

`docs/regression_2x/phase3b_failure_paths.py` → **12/12 PASS**（记录 `logs/phase3b_failure_paths.json`）

| # | 用例（真实渲染） | 实测结果 |
|---|---|---|
| 1 | 关掉母带链（`apply_mastering=false`） | 成片实测 -19.7 LUFS → **BLOCKED**，无 `render_output`，错误码 `LOUDNESS_OUT_OF_RANGE` |
| 2 | 契约把真峰要求设为不可能达到（-40 dBTP） | 实测 TP -2.9 dBTP > 上限 → **BLOCKED**（`TRUE_PEAK_EXCEEDED`） |
| 3 | 真实静音旁白（有合法时长） | 实测 I=-70.0 LUFS、真峰缺失 → **BLOCKED**（`LOUDNESS_OUT_OF_RANGE` + `TRUE_PEAK_NOT_MEASURED`） |

每条都断言：任务非 SUCCEEDED、无 `render_output` 交付物、原因指向响度契约、且落盘文件按该用例契约实测确为不合规
（证明不是"合规片被误拦"）。

## 6. 回归（最终代码 + 网络可用）

`docs/regression_2x/phase3a_regression_batch.py` → **19/19 项 rc=0，非预期结果 = 0**
（`logs/phase3a_regression_batch_classified.json`）。

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **33 total / 33 rc=0 / FAILED: []**（新增 `audio_loudness_test` **32/32**） |
| 3-B 契约单测 | `tests/audio_loudness_test.py` | **32/32** |
| 3-B 失败路径 | `phase3b_failure_paths.py` | **12/12** |
| 3-A 合规套件 | `tests/attribution_compliance_test.py` | **24/24**（未退化） |
| 3-A 真实链路复核 | `phase3a_real_chain.py --resume p_f4b466a4a024` | **16/16 PASS**（重渲染后抽帧相关系数逐条不变：0.459/0.921/0.348/0.736/0.471/0.732） |
| 旁白契约（2-B.1） | `tests/narration_contract_test.py` | **40/40**（曾因 `ctx=None` 回归，已修并复测） |
| 素材装配（2-A/B） | `tests/scene_assembly_test.py` | **15/15**（曾因测试替身缺 `engine.config` 回归，已改为代码侧容错并由测试复测） |
| 2-C 追溯 / 故障矩阵 | `phase2c_trace.py` / `phase2c_fault_matrix.py` | **38/38** / A/C 出片、B/D **BLOCKED 且无成片** |
| 2-D 边界 / Provider E2E | `phase2d_boundary_matrix.py` / `phase2d_provider_e2e.py` | **40/40** / **12/12** |
| 2-E 真实链路 / 失败路径 | `phase2e_real_provider.py` / `phase2e_failure_paths.py` | **13/13** / **29/29** |
| 3 机械 E2E | `run_all_tests.py --fresh` | A/B/C **全 SETTLED**（成片 17.000s / 24 kHz；实测 **-16.1 LUFS / TP -2.9 dBTP**） |
| 本地 ingest / 2-A·B 验收 / 二进制 / 真实小测 | 同批次 | `run_ingest_test` PASS（0.747）、`phase2_accept --verify` PASS、`check_binaries` PASS、`real_small_test` PASS（MockLLM=0） |

> **采样率回归风险已被覆盖**：2-B.1 的旁白契约、E2E 的 `24 kHz` 预期、以及本阶段新增的
> `aresample` 断言共同保证"加了 loudnorm 也不会改采样率"。本阶段期间出现过两次**真实回归**
> （`ctx=None` → `narration_contract` 失败；测试替身无 `engine.config` → `scene_assembly` 失败），
> 都已按"改代码而非改测试"的方式修复并复测（见 §7 缺陷 7/8）。

## 7. 本阶段发现并修复的缺陷（8 项，含 2 次真实回归与 1 项取证污染）

| # | 缺陷 | 发现方式 | 处理 |
|---|---|---|---|
| 1 | **正式链根本没有响度处理**（只有 `apad`）：成片 -19.7 / -22.0 LUFS | 审计实测 | 落地统一母带链（§2.2） |
| 2 | **`loudnorm` 输出 192 kHz**：不加 `aresample` 会把 24 kHz 旁白变 192 kHz（AAC 再降 96 kHz） | 新测试 D9 实测 | 探测输入采样率并 `aresample` 复原（并在 `ffmpeg_tool` 探测里补 `sample_rate/channels`） |
| 3 | **stage32b QC 口径过松**（±2 LU）且实际输出 -17.7 LUFS 从未被发现 | 审计实测 | QC 改用统一契约（±1 LU）；render 用同一链并做实测收尾 |
| 4 | **`audio_plan` 与实现不符**（宣称 -14 LUFS + BGM 闪避，实际两条都没有） | 审计 | 方案目标值改由契约生成；注明 BGM 未实现 |
| 5 | **我第一版"自动校正"会掩盖故障**（关掉母带链也能被自动修好） | 故障注入用例 D6 | 改为：偏差 >3 LU **拒绝校正、直接 fail-closed**（§2.4） |
| 6 | **测试首版污染历史证据**：就地校正了 2-E 项目成片（-22.0 → -16.0 LUFS） | 自查（C4 用例） | 测试改为**只操作副本**；用 `phase3b_restore_2e_film.py` 把该成片**集成响度还原为 -22.0 LUFS**（有损重编不可逆，原始 TP -13.0 与还原后 -3.5 的差异已如实记录） |
| 7 | **回归①（真实）**：`_narration_args` 在 `ctx=None` 时探测采样率 → `narration_contract_test` 失败 | 回归批次 `suite_all` | `probe_audio_rate` 对 `ctx=None` 返回 None；调用侧加守卫（**改代码，不改测试**） |
| 8 | **回归②（真实）**：测试替身 `Eng()` 无 `engine.config` → `scene_assembly_test` 失败 | 回归批次 `suite_all` | 代码侧改用 `getattr(engine, "config", None)`（缺配置即用契约默认值），**不修改冻结测试** |

## 8. 未解决项 / 已知限制（如实列出）

1. **2-E 历史成片的音轨字节不可完全复原**（#6）：集成响度已还原到记录的 -22.0 LUFS，但真峰由 -13.0 变为 -3.5 dBTP
   （AAC 有损重编所致）；原始实测值保留在 `logs/phase3b_audit.json`。
2. **stage32b 保留其历史 +0.4 dB 限幅补偿**：因此其成片落在 -16.8 LUFS（契约内，但非恰好 -16）；
   若要精确 -16 需去掉该补偿（会影响其既有验收口径，本阶段不做）。
3. **`apply_mastering=false` 开关存在**：它是故障注入用的合法配置，**不能**用于交付不合规成片——QC 会直接 BLOCKED（用例 1 实测）。
4. **BGM 未实现**（授权边界）：`audio_plan.bgm.implemented=false` 如实标注；混音/闪避不在本阶段。
5. **契约可配置**（`tools.ffmpeg.loudness.*`）：默认即授权契约值，**默认不放松**；变更需显式配置。
6. 未做：第二 Provider、语义级自动改选材、UI、`run.py report`、成本对账、Git tag、大规模重构、
   修改 Claim/HITL/append-only/恢复/任务与产物/event 契约。**未进入 3-C。**

## 9. 复现命令

```bat
:: 1) 审计（真实实测两条路径）
python docs\regression_2x\phase3b_audit.py
:: 2) 契约单测（真实音频/真实渲染；32/32）
python tests\audio_loudness_test.py
:: 3) 失败路径（真实渲染故障注入；12/12）
python docs\regression_2x\phase3b_failure_paths.py
:: 4) 真实成片取证（读产物 + 独立 ebur128 复测）
python docs\regression_2x\phase3b_real_evidence.py p_f4b466a4a024
:: 5) 全量回归批次（含 33 套件）
python docs\regression_2x\phase3a_regression_batch.py
python docs\regression_2x\phase3a_classify_batch.py     :: 期望"非预期结果 = 0"
:: 6) 基线零漂移校验
python docs\regression_2x\verify_baseline.py 3.x-phase3b-baseline
```

## 10. 阶段基线

| 项 | 值 |
|---|---|
| 标签 | `3.x-phase3b-baseline` |
| ZIP | `docs/regression_2x/baseline/3.x-phase3b-baseline.zip`（5,831,698 字节） |
| zip sha256 | `ca00c1ec353c1742354b5afee208d374f89912f62df0630062c6f61a92ffb23e` |
| 文件数 / 源码字节 | **337 文件 / 7,384,398 字节**（代码/配置/测试/脚本 + 根文件，**排除 `docs/`**） |
| manifest | `baseline_manifest_3.x-phase3b-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 校验 | `verify_baseline.py 3.x-phase3b-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移**） |
| 断点归档 | `snapshots/3.x-phase3b-final-20260915.{zip,db,json}`（DB sha256 `9446f07211d73c6b…`，9,261,056 B） |

关键指纹（相对 3-A 基线）：`core/audio.py`（**新**）、`agents/editing/agent.py aeaf7c2c9f0e2851…`、
`tools/ffmpeg_tool.py 9313f3b46af526f9…`、`tests/audio_loudness_test.py`（**新**）、
`stage32b/{vo,render,qc}.py`（改用共享契约）；
**未改动**：`config/config.json b264644539b2adbb…`（仍 `provider=none`）、`core/materials.py 253b628c2d0b1348…`、
`tools/material_provider.py 2607f35049716528…`、`tools/provider_wikimedia.py f5ee1f6a4183ae45…`、
`agents/retrieval/agent.py 32de908c26a8ab90…`、`agents/voice/agent.py 9f102d2b78b8ba91…`、`core/engine.py becfdd8e56dd0e8b…`。

交接点：`docs/regression_2x/PHASE3B_CHECKPOINT.md`。

## 11. 停止点

按授权：**未**做 BGM、**未**接入第二个 Provider、**未**做语义级自动改选材、**未**做 UI/`run.py report`/
成本对账/Git tag、**未**做大规模重构、**未**修改默认 `provider=none`、**未**改动 Claim/HITL、append-only、
断点恢复、任务/产物/event 契约。旁白完整性闸门、时间轴权威时长、素材验证与许可台账均保持不变（33/33 套件回归）。
**在此停止，等待下一步授权（3-C）。**
