# Stage 3.3 P1 Preflight / Implementation Plan Review（Coral Visual Director MVP）

> 状态：**仅计划，不实现**。本文件是 P1 开工前的实现计划与 Gate 验证方案，等待授权后执行。
> 依据：`docs/STAGE33_VISUAL_DIRECTOR_DESIGN.md` v2（已批准）+ 本轮 P1 执行约束（8 条）。
> 关键发现（相对 v2 设计的**更安全修正**）：P1 可以做到 **3.2b 零文件改动**，暂不需要重开协议（详见 §5）。

---

## 1. P1 目标与成功标准（引用用户裁定）

> **成功标准：Coral 成片肉眼明显优于当前 3.2b 成片，而不是仅仅机器 Gate 更复杂。**

P1 只解决 v2 明确的 7 项第一优先级（全部落到机器可查指标）：

| # | 目标 | P1 机器指标（Gate 依据） |
|---|---|---|
| 1 | 消除连续深色纯文字卡 | 文字卡率 ≤30%（beats 口径）；连续 ≤2；卡=排版化模板（非纯深底白字） |
| 2 | 消除裸素材/裸视频播放 | 图片 beat 全部带语义化运动；视频 beat 默认非 SOURCE_NATIVE（`video_raw_count=0`） |
| 3 | 增加视觉层级 | 每 beat 有构图格+安全区；单 beat 元素 ≤3；字幕区永独占 |
| 4 | 图片运动多样化且语义绑定 | 全片 motion 类型 ≥4；每 motion 有 `motion_reason`（语义方向词典） |
| 5 | 按 beat 类型决定表达 | beat_types → 表达档/角色映射（DATA→图形、CAUSE→流程、CONTRAST→对比…） |
| 6 | 视觉服务口播而非"有素材就放" | 每 beat 有 `what_to_show/why_this_expression`（LLM 决策）；无素材 ≠ 自动文字卡 |
| 7 | TEXT_CARD 为最后一级 | 表达阶梯六档 + Validator 强制执行降级顺序 |

---

## 2. P1 文件变更清单（全部为新增；**零 3.2b 修改**）

### 2.1 新增文件（实现）

| 文件 | 职责 |
|---|---|
| `src/video_studio/stage33/__init__.py` | `STAGE33_VERSION="3.3-p1"`、`STAGE33_STATUS="DEV"` |
| `src/video_studio/stage33/schemas.py` | 全部枚举/常量：预算 cap、运动语法参数带、语义方向词典、转场理由表、图形模板表、风格契约默认值 |
| `src/video_studio/stage33/sanitizer.py` | 输入白名单化：只保留 rights∈{SAFE}∪{CONDITIONAL 且 commercial_use} 且 sem≥50 的候选；剥离 URL；稳定排序；产出 LLM context JSON（**不含任何 URL/文件系统引用**） |
| `src/video_studio/stage33/director.py` | LLM Director：llama-server 生命周期管理（subprocess 启停/健康检查）、prompt 构建（角色+约束+语法手册+context）、JSON-schema 约束请求、解析/重试 ≤2、失败→回退标记 |
| `src/video_studio/stage33/planner_fallback.py` | 规则回退规划器（v1 设计的词典+规则，**字节级确定**）；LLM 不可用/两次被拒时启用 |
| `src/video_studio/stage33/expander.py` | 确定性实现展开：Director 决策 → 具体 spec（beat 时间=字符比例、motion 参数、构图矩形、模板变体=seed 哈希、硬切），不做创意判断 |
| `src/video_studio/stage33/validator.py` | Deterministic Validator/Safety Gate：§7 全清单校验 + 字段级修复 + validator_log + budget_report + 修复超 5% → REJECTED |
| `src/video_studio/stage33/plan_builder.py` | visual_plan.json 组装 + input_fingerprint + 幂等跳过 + plan_sha |
| `src/video_studio/stage33/graphics.py` | 3 个 P1 图形模板渲染（PIL 12.3.0，1920×1080 PNG）：NUMBER_EMPHASIS / COMPARISON / TYPO_COMPOSITION + 排版化文字卡渲染 + source_tag 角标；字体=`output/production_002/build_v2/msyh.ttc`；PIL 失败降级 ffmpeg drawbox/drawtext |
| `src/video_studio/stage33/executor.py` | plan 执行：beat 视频片 → 镜 mp4（**时长=legacy adopted_duration，音轨=既有 VO segments，硬切拼接**）→ 产出 3.2b 兼容工件 → import 调用 3.2b `render.build_final`/`qc.run_qc`（不改 3.2b） |
| `src/video_studio/stage33/visual_qc.py` | P1 视觉 QC（§8 清单）+ legacy vs plan 对照报告 + 抽帧图（sheet）生成 |
| `scripts/run_stage33.py` | CLI：`model-setup / plan / execute / visual-qc / p1-gate` |
| `scripts/_fetch_qwen_gguf.py` | hf-mirror 重试下载 Qwen GGUF（沿用 `_fetch_*` 模式） |
| `scripts/_fetch_llamacpp.py` | GitHub releases 拉取 llama.cpp Windows CPU 预编译包（含校验）；失败回退 pip llama-cpp-python（清华源） |

### 2.2 新增文件（测试，脚本式，沿用仓库约定）

| 文件 | 覆盖 |
|---|---|
| `tests/stage33_sanitizer_test.py` | 白名单过滤（UNKNOWN/UNSAFE/sem<50 必滤）、URL 剥离、稳定排序 |
| `tests/stage33_validator_test.py` | 全 Gate 项 + 字段修复 + 修复上限 + REJECTED 语义 + 安全断言 |
| `tests/stage33_expander_test.py` | 时间比例、motion 参数带、语义方向词典、模板变体确定性 |
| `tests/stage33_planner_fallback_test.py` | 两次运行字节级一致（幂等）+ 输出 schema 合规 |
| `tests/stage33_graphics_test.py` | 3 模板渲染非空/尺寸 1920×1080/数字==原文（Truth 校验） |

### 2.3 允许修改的文件（P1 阶段）

**无。**（v2 设计 §23 设想的 3.2b plan-mode 接入，被 §5 的"兼容工件 + import 复用"方案替代，P1 不需要。）

### 2.4 绝对禁止修改（P1 全期）

2.x 全部 / Truth/Evidence / Creator Style v2 / 冻结稿 / 3.1.4 全部 / Material Package / rights gate / threshold / `stage32b/` 全部 8 文件 / `scripts/run_stage32b.py` / `docs/STAGE31_4_SEAL.md`、`docs/STAGE32B_SEAL.md` 及 SEAL 固化的一切产物（coral 3.2b 输出目录、7 个 manifest、SHA 记录）。

---

## 3. 完整数据流（LLM Director → Validator → visual_plan.json → 3.2b 执行）

```text
[输入，全部只读]
 冻结稿 V2_FINAL_SCRIPT_JARVIS.md（CRLF 归一化读取）
 shotlist.json（role/visual_target 仅提示）
 3.1.4 Material Package（shot_mapping/all_shots.json + metadata/materials.json + rights）
 alignment_manifest.json（真值时间轴，从 3.2b coral 读取）
        │
        ▼
(1) sanitizer.py ──→ LLM context（白名单候选 + 稿文 + shotlist 元数据 + 风格契约 + 约束手册）
        │                 无 URL、无网络、无文件系统
        ▼
(2) director.py（本地 Qwen，llama-server + JSON-schema 约束）
    产出【创意核心】：narrative_arc（phases/pacing/climax/whitespace/motifs/callbacks）
    + 逐 beat：beat_types/intensity/emphasis_target/expression/semantic_role/source_material(material_id)
    + what_to_show/why_this_expression/fallback_reason/motion_reason/transition_reason/composition_reason
    （LLM 是"这一段应该被怎么看见"的决策者，不是模板分类器；失败→planner_fallback）
        │
        ▼
(3) expander.py（确定性实现展开：时间/运动参数/构图/模板变体/硬切）── 与 (2) 合并
        ▼
(4) validator.py（唯一大门）── PASS / PASS_WITH_REPAIRS(≤5%) / REJECTED（重生成≤2→回退→仍拒则停用上报）
        ▼
(5) plan_builder.py → output/stage33/coral/visual_plan.json（fingerprint+plan_sha，幂等）
        ▼
(6) executor.py：beat 视频片（素材运动 / 图形模板 / 排版卡）→ 硬切拼镜（时长=VO 真值，音轨=既有
    VO segments 原样挂载）→ output/stage33/coral/{production/shots/,manifests/,subtitles.ass,
    audio/segments/}（3.2b 兼容工件；blocked/shot_assembly manifest 按 beat 聚合重映射，其余
    alignment/vo/subtitle 为冻结副本）
        ▼
(7) import 3.2b render.build_final（concat+字幕钳制+烧录+loudnorm/alimiter，代码零改动）
        → output/stage33/coral/production/final_preview.mp4
        ▼
(8) import 3.2b qc.run_qc/gate_qc（技术 QC 13 项，代码零改动）
        + stage33.visual_qc（P1 视觉 QC + legacy 对照报告 + 抽帧图）
```

时间轴不变量：P1 全片**只有硬切**（转场是 P2），beat 时长之和 == 镜 adopted_duration == legacy 时间轴 → 字幕/音轨/QC 与 legacy 完全同口径，只有画面内容变化。

---

## 4. Qwen2.5-3B-Instruct Q4 本地部署

| 项 | 方案 |
|---|---|
| 模型 | `Qwen/Qwen2.5-3B-Instruct-GGUF` 的 `qwen2.5-3b-instruct-q4_k_m.gguf`（约 2.0GB），经 `HF_ENDPOINT=https://hf-mirror.com` + 重试下载 |
| 模型路径 | `models/llm/qwen2.5-3b-instruct-q4_k_m.gguf`（新增 `models/llm/` 目录） |
| 推理引擎 | llama.cpp 预编译 Windows CPU 包（GitHub releases zip，约 50MB）→ `bin/llamacpp/`（`llama-server.exe`）；备用链：pip `llama-cpp-python`（清华源）→ transformers fp16（最后手段） |
| 服务方式 | `llama-server --model … --port 8081 --ctx-size 4096 --jinja`，本地 HTTP；Python 用 `requests` 调用；**JSON-schema 约束输出**（llama-server 原生支持；不支持则降级 GBNF grammar） |
| CPU 内存预计 | 权重 ~2.0GB + KV(4096) ~0.3GB + 运行缓冲 ~0.7–1.0GB → **峰值约 3.0–3.5GB**（31.3GB 机器安全；与 F5-TTS 不同时运行——P1 不重跑 VO） |
| 吞吐预计 | 3B Q4 于桌面级 CPU ≈ 8–14 tok/s；P1 计划输出目标 ≤2.5k tokens + prompt ~2.5k → **单计划约 5–15 分钟** |
| 模型回退 | Qwen2.5-1.5B-Instruct-GGUF（~1.0GB，约 2× 快）；再回退 `planner_fallback`（无 LLM） |
| 健康检查 | 模型加载成功、`/health` OK、JSON-schema 输出解析 100%（3 镜 smoke）、峰值内存记录 ≤8GB |
| 安全面 | llama-server 只监听 127.0.0.1；director 无任何文件系统/网络/FFmpeg 权限（除 127.0.0.1:8081 HTTP） |

**两级生成架构（保证 LLM 是 Director 且 CPU 可行）**：一次 LLM 调用产出全片**创意决策**（arc/逐 beat 表达与理由/母题/回收），确定性 expander 负责参数实现——LLM 决定"怎么被看见"，规则只做翻译与校验。

---

## 5. 3.2b SEALED 重开协议：P1 结论 = **不重开**（比 v2 设计更安全）

### 5.1 方案变更说明

v2 设计 §23/§24 假设 P1 需给 3.2b 加 plan-mode。Preflight 实读 `assemble.py`/`render.py`/`qc.py` 后确认：`render.build_final()` 与 `qc.run_qc()` **只依赖输出目录内固定布局**（`production/shots/Sxx.mp4`、`manifests/*.json`、`subtitles.ass`）。因此 P1 采用 **"兼容工件 + import 复用"**：新增 stage33.executor 产出同布局工件，然后 import 调用 3.2b 函数（调用≠修改）。**3.2b 全部 8 文件、run_stage32b.py 在 P1 期间零改动。**

### 5.2 legacy 字节级回归（P1 仍必须执行，证明 3.2b 未被影响）

1. **快照**：对 coral 3.2b 输出目录全部文件计算 SHA 并存档（`output/stage32b/coral/_preflight_legacy_baseline.json`，含与 `docs/STAGE32B_SEAL.md` 固化 SHA 的对照）——证明起点==SEAL 状态；
2. **备份**：整目录复制 `output/stage32b/coral_backup/`（秒级恢复能力）；
3. **重跑**：在原始 coral 目录用**既有 VO 段**重跑 legacy 链：`subtitle → blocked → assemble → render → qc`（`--force`；不重跑 VO、不重检索——VO 段与 Material Package 只读复用）；
4. **比对**：逐文件 SHA == 快照（关键项：final_preview.mp4 `3C629B62…`、subtitles.srt `B6D82D4B…`、subtitles.ass `275EFED0…`、voiceover.wav `24A1AC2A…`、7 个 manifest）；
5. **判定**：全部一致 → legacy 路径证明字节级稳定，P1 继续；**任一不一致 → 立即 STOP、从备份恢复、报告（不修复）**。

### 5.3 plan/legacy 隔离

- plan 全部工件只写 `output/stage33/**`；3.2b 目录除第 3 步的"重跑-比对"外不被写入；
- 重跑结果必须与快照一致（确定性流水线的自我证明），因此 legacy 目录在回归后状态==回归前状态。

### 5.4 若 P2 需要转场进入 render 内部

届时才启用 v2 §23 重开协议（新增-only diff + 备份回滚 + 本 §5.2 同款字节级回归）。**P1 不启动。**

---

## 6. 新增 vs 3.2b 接入（回答"哪些是新增、哪些是允许接入"）

- **新增**：`stage33/` 全部模块 + `scripts/run_stage33.py` + 2 个 fetch 脚本 + 5 个测试（§2.1/2.2）；
- **允许的 3.2b 接入**：仅 Python `import video_studio.stage32b.render / .qc` 并调用 `build_final()/run_qc()`（只读调用，不改文件、不改函数、不改状态字段）；`stage32b/__init__.py` 保持 `SEALED`；
- **不允许**：任何 3.2b 文件写操作、任何"顺手修 3.2b 遗留（如 qc.py 旧口径注释）"行为——遗留项只记录不修。

---

## 7. P1 Gate 逐项自动验证（`run_stage33.py p1-gate` 一键执行，任一 FAIL → STOP，只报告）

| Gate | 自动验证内容 | 失败动作 |
|---|---|---|
| G1 Validator | visual_plan.json 通过 validator（PASS 或 PASS_WITH_REPAIRS 且修复 ≤5%）；REJECTED=FAIL | STOP+报告 validator_log |
| G2 安全断言 | ① 所有 source_material ∈ 白名单（rights/threshold）；UNKNOWN/UNSAFE/sem<50 出现次数=0 ② narration_span 逐字匹配冻结稿 ③ GraphicSpec.numbers ⊆ 原文数字集 ④ 章节标题仅原文/通用词 ⑤ LLM 上下文无 URL、director 无网络调用面（代码审查+运行时日志） | STOP+报告违规字段 |
| G3 预算/禁令 | 文字卡率 ≤0.30；连续 ≤2；同模板连续 ≤2/全片 ≤4；抽象 beat 连 3 禁卡；motion 类型 ≥4；同 motion 连续 ≤3；每镜 ≤3 beats；最小 beat 1.2s；p90/p10 ≤3 | STOP+报告 budget_report |
| G4 legacy 字节回归 | §5.2 快照→重跑→逐文件 SHA 比对 | 任一不一致：STOP+备份恢复 |
| G5 确定性 | planner_fallback 跑两次→visual_plan 字节级一致；LLM 计划 schema 合规率 100%（生成方差如实记录报告，不作 FAIL 条件） | 回退路径不一致=FAIL |
| G6 技术 QC | 3.2b `qc.run_qc` 于 `output/stage33/coral`：13 项全 PASS | STOP+报告 |
| G7 渲染 Gate | 3.2b `gate_render` PASS（88–112s/1080p25/48kHz/字幕烧录） | STOP+报告 |
| G8 交付完整 | visual_plan.json（plan_sha）+ 20 镜 plan shots + final_preview.mp4 + 对照报告 + human_review 清单 + 抽帧图齐备 | STOP+缺件清单 |
| G9 模型健康 | llama-server 加载 Q4_K_M、/health、smoke 输出解析 100%、峰值内存 ≤8GB | STOP+日志 |
| GH 人工观看 | **人工观看 Round 1**（对照报告 + 两版抽帧 + 清单）——机器不代判 | 等待人工裁决 |

> G1–G9 全绿 + GH 人工裁决"肉眼明显优于 3.2b"→ P1 达成；任何 FAIL → STOP，只报告，修复需下一步授权。

---

## 8. P1 Visual QC（stage33/visual_qc.py，机器项）

① 文字卡率/连续数 ② 模板重复 ③ motion 类型直方图（≥4）④ video_raw_count（=0）⑤ beat 覆盖（每句 ≥1 beat、理由字段非空率=100%）⑥ 构图格使用 ≥3 种 ⑦ 元素数 ≤3 ⑧ arc 完整性（有开场/收束处理、climax 唯一 HIGH）⑨ motif 引用存在 + callback 顺序合法 ⑩ 字幕区无碰撞（几何检查）。输出 `output/stage33/coral/visual_qc.json` + **legacy vs plan 对照报告**（`comparison_report.md`：文字卡率、运动类型、图形数、裸播数、arc、逐镜表达对照表）+ 两版抽帧 sheet。

---

## 9. 执行顺序（里程碑，每步完成即报告）

| 里程碑 | 内容 | 产出 |
|---|---|---|
| **M1** | 网络可达性检查（hf-mirror/GitHub）→ 下载 Qwen GGUF + llama.cpp（重试 fetcher）→ llama-server 启动/JSON-schema smoke（3 镜）→ 内存/时延记录 | models/llm/ + bin/llamacpp/ + smoke 报告 |
| **M2** | sanitizer/director/expander/validator/plan_builder/planner_fallback + 5 测试 → coral visual_plan.json 生成 → G1/G2/G3/G5 通过（**计划级，先不渲染**） | visual_plan.json + validator_log |
| **M3** | legacy 回归（§5.2）→ G4 | 回归比对报告 |
| **M4** | graphics/executor → plan 渲染 → import 3.2b render+qc → G6/G7/G8/G9 | 新 Coral 成片 + 双 QC 报告 |
| **M5** | visual_qc + 对照报告 + human_review 清单 + 抽帧图 → **人工观看 Round 1** | P1 验收包 |

每个里程碑结束 STOP 报告（真实数据）；任何 Gate FAIL 即 STOP，等待授权。

---

## 10. 依赖与风险检查清单（M1 前置）

| 项 | 状态/预案 |
|---|---|
| PIL 12.3.0 | 已在 `.venv_tts` ✓（图形渲染可行；降级=ffmpeg drawbox/drawtext） |
| requests | 已在 `.venv_tts` ✓（llama-server HTTP 客户端） |
| RAM 31.3GB | ✓（模型峰值 ~3.5GB 安全） |
| hf-mirror 可达性 | M1 首查；不可达 → 换镜像/重试策略，仍不可达则 **STOP 上报**（不用 API 键，不破坏"本地模型"路线） |
| GitHub releases 可达性 | M1 首查；失败 → pip llama-cpp-python（清华源）→ transformers fp16 兜底 |
| llama-server JSON-schema 支持 | smoke 验证；不支持 → GBNF grammar 兜底 |
| 3B 输出质量/速度 | smoke 3 镜评估；质量不可用 → 1.5B → 回退规划器（如实报告，不隐瞒） |
| legacy 重跑中的素材下载 | 优先本地文件（`preview_file` 路径）；确需下载时 URL 内容理论上稳定（Commons 上传不可变），若因网络导致重跑失败 → **STOP**（不伪造回归） |

---

## 11. 明确不做（P1 范围外，防止蔓延）

转场（非硬切）、剩余 7 个图形模板、icon 库、章节标题图形、片头片尾/fade/署名 roll、绿幕、BGM/SFX、调色 LUT、字幕样式升级、MotifRegistry 之外的 P2/P3 项、任何 3.2b/3.1.4/2.x 修改、SEAL、进入 P2。AudioCue 字段在 plan schema 中保留占位（值为 NONE），但 P1 不合成任何音频。

---

## 12. 待授权事项（本轮 STOP 点）

1. 批准本 Preflight（文件清单 / 零改动 3.2b 方案 / 里程碑顺序 / Gate 清单）；
2. 确认 M1 开始执行（含 Qwen GGUF 与 llama.cpp 下载）；
3. 确认 legacy 回归允许在原始 coral 目录"快照→重跑→比对"（含备份恢复条款）；
4. 确认 P1 验收以"G1–G9 全绿 + 人工观看 Round 1 裁决"为准。

**STOP。等待授权后开始 P1 实现（从 M1 起）。**
