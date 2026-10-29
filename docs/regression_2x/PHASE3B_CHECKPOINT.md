# 3.x Phase 3-B 完成与交接点（2026-09-15）

> **状态：Phase 3-B 已完成，判定 PASS，基线 `3.x-phase3b-baseline` 已冻结并零漂移校验。**
> 本文件是**阶段收尾与下一阶段（3-C）的交接点**：结论看 `PHASE3B_REPORT.md`，进度看 `STATUS.md`。
> **未进入 3-C**（按授权 STOP）。

---

## 1. 一句话结论

音频响度契约已**在正式生产链真实落地**（不是改方案文本）：契约 **-16 LUFS（±1 LU）/ 真峰 ≤ -1.5 dBTP**，
单一事实源 `core/audio.py`；正式 Agent 链与 `stage32b` 路径**共用同一条母带链**；渲染后用真实
`ffmpeg ebur128=peak=true` **实测成片**，证据写入 `render_output.audio_loudness`，**不达标即 fail-closed**。

## 2. 关键实测（全部真实音频 / 真实渲染）

| 对象 | 处理前 | 处理后 | 证据 |
|---|---|---|---|
| 正式链 3-A 真实项目成片（104.0s，真实 TTS + 真实 Wikimedia 素材） | **-19.7 LUFS** | **-16.1 LUFS / TP -2.7 dBTP（Δ -0.1 LU，corrections=0）** | `logs/phase3b_real_evidence.txt` |
| 正式链 2-E 项目成片 | -22.0 LUFS | （历史产物，未重跑；被本阶段的 6 号缺陷误改后已还原为 -22.0） | `logs/phase3b_audit.json` |
| `stage32b` 交付成片 | **-17.7 LUFS** | **-16.8 LUFS / TP -1.9 dBTP**（QC Gate PASS） | `logs/phase3b_audit.json` |
| 机械 E2E A/B 组成片（plan 模式 + 真实 TTS） | — | **-16.1 LUFS / TP -2.9 dBTP** | `logs/phase3b_audit.json` |
| 真实音频片段（原样 / -20dB / +20dB） | -19.6 / -39.6 / +0.4 LUFS 级 | **-16.2 / -16.2 / -16.1 LUFS** | `tests/audio_loudness_test.py` B 组 |

## 3. 实现位置（改哪里了）

| 文件 | 作用 |
|---|---|
| `src/video_studio/core/audio.py`（新） | 契约常量、母带链构造（`loudnorm`→`alimiter`，支持 `aresample` 复原采样率与 `post_gain_db`）、真实测量（`ebur128=peak=true`）、判定（测不到即不通过）、配置读取、成片级 fail-closed 强制 |
| `src/video_studio/agents/editing/agent.py` | 所有脚本渲染分支套母带链；渲染后实测成片 → 不达标 `TASK_BLOCKED` + `LoudnessContractError`；`render_output.audio_loudness` 证据块 |
| `src/video_studio/agents/audio/agent.py` | `audio_plan` 目标值改由契约生成；如实标注"母带链在渲染阶段真实执行"与"BGM 未实现" |
| `src/video_studio/stage32b/{vo,render,qc}.py` | 复用同一母带链；render 做同样实测；qc 响度断言由 ±2 LU 收紧为**统一 ±1 LU** |
| `src/video_studio/tools/ffmpeg_tool.py` | probe 新增 `sample_rate/channels`（纯新增字段）——`loudnorm` 输出 192 kHz，必须复原采样率 |
| `tests/audio_loudness_test.py`（新） | 契约/实测/强制/故障注入，**32/32** |
| `docs/regression_2x/phase3b_failure_paths.py`（新） | 真实渲染失败路径，**12/12** |
| `docs/regression_2x/phase3b_audit.py`（新） | 两条路径的实测审计（可随时复跑） |

## 4. fail-closed 语义（下一阶段不要放松）

- 偏差 **≤3 LU** → 允许 1–2 次**只重编音频**（`-c:v copy`，不改采样率/时长）的收尾校正，逐次写入 `passes[]`；
- 偏差 **>3 LU** → **拒绝静默校正、直接 BLOCKED**（说明母带链没生效，静默"修好"会掩盖故障）；
- **测不到**（无音轨/无 ffmpeg）→ 不合格；
- 不达标时**不写 `render_output`**（不产出"成功但不达标"的成片）；
- `apply_mastering=false` 只跳过处理、**不放松 QC**（因此会让渲染 fail-closed——故障注入用，不可用于交付）。

## 5. 回归（最终代码，网络可用）

- **33/33 套件 rc=0**（新增 `audio_loudness_test` 32/32）；
- 回归批次 **19/19 项 rc=0，非预期结果 = 0**（`logs/phase3a_regression_batch_classified.json`）；
- 3-A 真实链路复核 **16/16 PASS**（重渲染后抽帧相关系数逐条不变）；
- 2-C 追溯 38/38、2-C 故障矩阵 A/C 出片 B/D BLOCKED、2-D 边界 40/40、2-D provider 12/12、
  2-E 真实链路 13/13、2-E 失败路径 29/29、ingest PASS（0.747）、E2E A/B/C SETTLED、
  2-A/B 验收 PASS、真实小测 PASS（MockLLM=0）、二进制真实性 PASS。

## 6. 阶段基线（零漂移已校验）

| 项 | 值 |
|---|---|
| 标签 | `3.x-phase3b-baseline` |
| ZIP | `docs/regression_2x/baseline/3.x-phase3b-baseline.zip`（5,831,698 字节） |
| zip sha256 | `ca00c1ec353c1742354b5afee208d374f89912f62df0630062c6f61a92ffb23e` |
| 文件数 / 源码字节 | **337 文件 / 7,384,398 字节**（代码/配置/测试/脚本 + 根文件，排除 `docs/`） |
| manifest | `baseline_manifest_3.x-phase3b-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 校验 | `verify_baseline.py 3.x-phase3b-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移**） |
| 断点归档 | `snapshots/3.x-phase3b-final-20260915.{zip,db,json}`（DB sha256 `9446f07211d73c6b…`，9,261,056 B） |

关键指纹（相对 3-A 基线）：`core/audio.py`（**新**）、`agents/editing/agent.py aeaf7c2c9f0e2851…`、
`tools/ffmpeg_tool.py 9313f3b46af526f9…`、`tests/audio_loudness_test.py`（**新**）、
`stage32b/{vo,render,qc}.py`（改用共享契约）；
**未改动**：`config/config.json b264644539b2adbb…`（仍 `provider=none`）、`core/materials.py 253b628c2d0b1348…`、
`tools/material_provider.py 2607f35049716528…`、`tools/provider_wikimedia.py f5ee1f6a4183ae45…`、
`agents/retrieval/agent.py 32de908c26a8ab90…`、`agents/voice/agent.py 9f102d2b78b8ba91…`、`core/engine.py becfdd8e56dd0e8b…`。

## 7. 未解决项 / 已知限制（下一阶段不要误读）

1. **2-E 历史成片的音轨字节不可完全复原**：本阶段测试首版曾就地校正它（-22.0 → -16.0 LUFS），
   已改为"只操作副本"，并用 `phase3b_restore_2e_film.py` 把**集成响度**还原为 -22.0 LUFS；
   真峰由原 -13.0 变为 -3.5 dBTP（AAC 有损重编所致），原始实测值保留在 `logs/phase3b_audit.json`。
2. **stage32b 保留其历史 +0.4 dB 限幅补偿** → 成片落在 -16.8 LUFS（契约内，非恰好 -16）；
   若要精确 -16 需去掉该补偿（会影响其既有验收口径，本阶段不做）。
3. **`phase3b_failure_paths` 用例 2 使用了一个"不可能达到"的真峰契约（-40 dBTP）** 来验证 TP 分支的
   fail-closed；这是**合成契约**，不是产品建议值（默认仍是 -1.5 dBTP）。
4. 契约可通过 `tools.ffmpeg.loudness.*` 覆盖，**默认即授权值、默认不放松**。

## 8. 下一阶段（3-C）入口与边界

- 入口：`PHASE3B_REPORT.md`（结论）→ `STATUS.md`（进度）→ 本文件（交接）。
- 3-C 若按既定计划进行（只读 `run.py report` / 成本与配额分离 / ①–⑱ 问题分诊 / 最终基线），
  可直接复用：`logs/phase3a_regression_batch_classified.json`（回归口径）、
  `phase3b_audit.py`（响度实测）、`PHASE3A_REPORT.md` §9 与 `PHASE3B_REPORT.md` §8 的问题清单。
- **未授权事项**：BGM、第二 Provider、语义级自动改选材、UI、`run.py report`、成本对账、Git tag、
  大规模重构、默认 `provider=none`、Claim/HITL/append-only/恢复/任务与产物/event 契约——**一律不要顺手做**。
