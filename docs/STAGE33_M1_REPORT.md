# Stage 3.3 P1-M1 报告（模型与工具链准备 · 实测数据）

> 状态：M1 完成，**STOP 等待人工裁决**（是否接受 CPU 实测性能）。未进入 M2，未写任何 stage33 业务模块，未渲染 Coral，未改动 SEALED 资产。

## 1. 环境实测

| 项 | 实测 |
|---|---|
| CPU | AMD Ryzen 7 8745HS（8C/16T，Zen4） |
| RAM | 31.3GB（空闲 19.4GB） |
| 磁盘 | C: 空闲 270.4GB |
| GitHub | **不可达**（API 与下载均超时） |
| hf-mirror | 可达（GGUF 下载 2.5–2.9 MB/s） |
| pypi.org / 清华源 | 可达；llama-cpp-python **无任何 Windows 轮子**（仅 sdist，源码构建失败）→ 弃用 pip 路线 |

## 2. 工具链落地（走通路径：hf-mirror 托管的官方构建）

| 组件 | 路径 | 校验 |
|---|---|---|
| llama.cpp Windows CPU 官方包 | `bin/llamacpp/`（53 文件，zip 16.1MB） | `llama-server.exe` **version 9637 (aedb2a5e9)**，Clang 20.1.8；zip SHA256=f7783c2b… 与 checksums.sha256 一致 ✓ |
| Qwen2.5-3B-Instruct Q4_K_M | `models/llm/qwen2.5-3b-instruct-q4_k_m.gguf`（1.96GB = 2,104,932,768 B） | 下载 11.8 分钟；SHA256=626B4A6678B86442240E33DF819E00132D3BA7DDDFE1CDC4FBB18E0A9615C62D |

## 3. 运行实测（用户要求的全部指标）

| 指标 | 实测 |
|---|---|
| 模型加载时间 | **2.1s**（mmap；`/health`→`{"status":"ok"}`） |
| 空闲常驻内存 | 3316 MB |
| **峰值 RAM（生成中，2s 采样 360 次）** | **3496 MB**（≈3.5GB，符合 3.0–3.5GB 预估） |
| 首 token（冷启动，含 prompt eval） | 10.3s / 8.3s |
| 首 token（热，prompt 缓存） | 0.22–0.25s |
| **tokens/s** | **16.27–18.27**（平均 ≈17） |
| 完整 mini-Plan 生成时间（3 镜 3 beats，810–890 tokens） | **44.7–61.5s** |
| JSON 合法率 | **6/6 = 100%**（4+2 轮） |
| schema 通过率 | **6/6 = 100%**（jsonschema 严格校验） |
| JSON Schema constrained output | ✓ `response_format={"type":"json_schema",...}` 原生生效（b9637） |

**Coral 全片预估**（诚实外推，M2 实测为准）：≈40 beats × ~150 tok + arc/motif ≈ **6.5–7.5k tokens ≈ 6–8 分钟 @17 tok/s**（对比：VO 生成 52 分钟）——**不构成生产瓶颈**。

## 4. Director 创意多样性证据（最小脱敏输入，3 镜）

单次输出实测（强化指令后）：
- **expression**：SAFE_IMAGE → DATA_GRAPHIC → SAFE_IMAGE（随 beat 信息类型变化；数据句正确落到 DATA_GRAPHIC）
- **motion**：PAN_V → SLOW_PUSH_IN → SLOW_PULL_OUT（随语义变化：全景→强调→揭示全貌收束）
- **composition**：FULL_BLEED → UPPER_TITLE（≥2 种）
- **semantic_role**：ESTABLISHING / ACTION / CONTEXT（3 种）
- **narrative_purpose / relation_to_previous / what_to_show / why_this_expression / motion_reason**：全部逐 beat 非空且内容各异 ✓
- transition 全部 HARD_CUT ✓（默认正确；输入无时间/话题变化，无理由用 dissolve）
- 证明：模型能按信息类型/节奏位置给出不同决策，**不是模板选择器**。

## 5. M1 发现（诚实记录，供 M2 schema/Validator 采纳）

mini schema 故意放宽了部分字段，暴露出真实缺口（M2 的正式 schema 与 Validator 将逐条封死）：
1. `beat_types` 被填成字段名列表（应为 INFO/DATA/EMOTION 等枚举）→ M2：enum 收紧；
2. `climax_beat` 填了 shot_id（应为 beat_id）→ M2：Validator 引用存在性校验；
3. `SAFE_IMAGE` 出现 source_material=null 的 beat → M2：**expression↔source_material 一致性硬校验**（该规则已在 v2 设计 §8.2，本次实测证明必要性）；
4. `callback_plan` 内容空泛 → M2：motif 引用必须指向真实 motif registry；
5. `emphasis_target` 偶有缺失 → M2：必填+子串校验。
结论：**LLM 输出创意多样性成立；边界一致性必须且只能由确定性 Validator 保证**——与 v2 架构预期完全一致。

## 6. SEALED 资产保护执行记录

- 写入范围仅：`models/llm/`、`bin/llamacpp/`、`output/stage33/m1_smoke/`、`output/stage32b/_m1_legacy_baseline.json`、`output/stage32b/coral_backup/`（只读复制）；
- **coral 目录零写入**；抽查 final_preview.mp4（3C629B62…）与 voiceover.wav（24A1AC2A…）与 SEAL 固化值一致 ✓；
- 146 文件 baseline SHA 清单已存档（baseline 文件自身 SHA=85745D2D…）；
- 完整备份 `output/stage32b/coral_backup/`（146 文件）就绪（M3 legacy 回归用）。

## 7. M1 验收判定

| 验收标准 | 结果 |
|---|---|
| 模型可运行 | ✓（2.1s 加载，/health ok，llama-server 9637） |
| Constrained JSON 正常 | ✓（json_schema 生效；合法率与 schema 通过率 100%） |
| 实测性能可接受 | ✓ 按数据（17 tok/s；全片计划 ≈6–8 分钟；峰值 3.5GB）——**由人工最终裁定** |
| 无 SEALED 资产改动 | ✓（抽查一致 + 写入范围清单） |

**M1 = PASS（附人工性能裁定）。STOP，等待授权进入 M2（stage33 业务模块与 coral visual_plan 生成）。**
