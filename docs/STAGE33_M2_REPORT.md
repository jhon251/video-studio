# Stage 3.3 P1-M2 报告（stage33 核心模块 + Coral Visual Plan 冻结）

> 状态：M2 完成，**STOP 等待人工裁决**。未进入 M3（legacy 回归）、未渲染、未碰 SEALED 资产。

## 1. 交付物与冻结信息

| 项 | 值 |
|---|---|
| visual_plan.json | `output/stage33/coral/visual_plan.json`（**25 beats / 20 镜**） |
| **plan_sha（冻结）** | `b122f0bda2cac4dd695cb18f88b2beea3cef33a02effa7c7cde8c51890f8e4fd` |
| input_fingerprint | `f56ea720b79776aa`（narration+shotlist+package+alignment+契约常量） |
| Validator Gate | **PASS_WITH_REPAIRS**（修复 33，**junk 0**，junk 率 0.0%） |
| director_mode | LLM（Qwen2.5-3B Q4）；按镜回退仅 3 个无素材镜（S01/S10/S16），**17/20 镜 LLM 导演** |
| LLM 原始输出 | `output/stage33/coral/llm_raw/*.json`（60 份，全部 SHA 记录于 plan 报告） |

新增/修改文件：`src/video_studio/stage33/`（9 模块）、`scripts/run_stage33.py`、3 个脚本式测试（全绿）、`docs/STAGE33_P1_PREFLIGHT.md`、本报告。**3.2b/3.1.4/2.x/冻结稿零修改**（终检：stage32b `__init__.py` 仍 SEALED；coral mp4 SHA 仍 3C629B62…）。

## 2. Coral Plan 全指标（用户验收清单逐项）

| 指标 | 值 | 对照 |
|---|---|---|
| beat 总数 | **25**（20 镜） | 1.25 beats/镜 |
| SAFE_VIDEO | **2**（M-S06-323、M-S20-1034——包内真实视频候选，LLM 自主选中） | 3.2b: 0 |
| SAFE_IMAGE | 8 | 3.2b: 11（整镜） |
| SAFE_COMPOSITE | 0 | — |
| DATA_GRAPHIC | 1 | 3.2b: 0 |
| SELF_CREATED_GRAPHIC | 11 | 3.2b: 0 |
| TEXT_CARD | 3 | 3.2b: **9（45%）** |
| **文字卡比例** | **12.0%** | 上限 30% ✓；连续最大 2 ✓ |
| motion 类型 | 4（PUSH_IN 10 / HOLD 10 / PAN_V 3 / PULL_OUT 2） | 下限 4 ✓ |
| transition | 全 HARD_CUT | P1 口径 ✓ |
| composition | 5 种（FULL_BLEED 13 / CENTER_CROP 6 / UPPER_TITLE 3 / THIRDS 2 / SPLIT_H 1） | ≥2 ✓ |
| semantic_role | 10 种（DATA 10 / SUBJECT 3 / EMOTIONAL 2 / CONTEXT 2 / BACKGROUND 2…） | 多样性 ✓ |
| 叙事弧 | HOOK(S01) → DEVELOPMENT(S02–S19) → **ESCALATION(S16,S17) → CONCLUSION(S20)**；**climax_beat=B022（S18「十年的选择」）** | escalation/climax/release ✓ |
| motif/callback | **M-OPENING-CLOSING：B001（开场「褪色的城市」）→ B025（结尾「等待降温」）**，构图+风格主色回收 | 具体回收位置 ✓ |
| 逐 beat 理由字段 | 25/25 全部非空（what_to_show/why_this_expression/motion_reason/relation/fallback_reason/decision_chain） | ✓ |
| Truth | 图形数字全部逐字来自口播原文（TRUTH 违规 0）；beat 文本 25/25 逐字覆盖冻结稿 | ✓ |
| Rights | 白名单外素材引用 0；UNKNOWN/UNSAFE/sem<50 进入 LLM 上下文 0（sanitizer 断言） | ✓ |

## 3. 导演决策抽样（真实 plan 内容）

- **S06「海水温度只要升高一两度，珊瑚就会开始发烧。」→ SAFE_VIDEO（M-S06-323 温度变化视频）+ HOLD_MICRO**，理由："展示海水温度变化对珊瑚的影响，通过冷色调的深青背景，突出珊瑚在高温下的脆弱"；
- **S09「海龟从白化的珊瑚旁游过…」→ SAFE_IMAGE + EMOTIONAL + SLOW_PUSH_IN**，理由："通过视觉细节的放大…营造出宁静而悲凉的氛围"；
- **S18（climax）「珊瑚礁的生死，取决于…」→ SELF_CREATED_GRAPHIC + HOLD_MICRO**，理由："保持画面稳定，聚焦关键信息，传达重要性"；
- **S20 结尾拆 2 beats**，末 beat SLOW_PULL_OUT 收束（Validator 收束归一）；
- 无素材镜（S01/S10/S16）走规则回退，`why_this_expression` 明确标注"规则回退：…"——诚实留痕。

## 4. Validator 修复明细（33 项，全部 routine，junk 0）

`SEMANTIC.DIRECTION_CONSIST ×1、SEMANTIC.MOTIF_VAGUE ×1、SAFETY.VIDEO_NO_SOURCE ×10、SAFETY.MATERIAL_AUTO_ASSIGN ×12、BUDGET.MOTION_RUN ×1、BUDGET.RHYTHM ×1、BUDGET.OPENING ×1、SEMANTIC.MOTIF_FALLBACK ×1` 等。
含义：LLM 常选 SAFE_VIDEO 但多数镜无视频候选 → 确定性自动降级/指定图片候选（保留表达意图）；方向/母题/节奏按契约归一。**junk（LLM 输出垃圾）= 0**。

## 5. 性能实测（M2 全记录）

| 指标 | 实测 |
|---|---|
| 完整 Coral plan 生成时间 | **6.1 分钟**（arc 30.6s + 20 镜 15–31s/镜 + 少量重试） |
| prompt / completion tokens | 37,178 / 5,284（首轮） |
| tokens/s | ≈12–16（本次长输出均值低于 M1 冒烟的 17，属正常波动） |
| **峰值 RAM** | **5,507 MB**（ctx 16384 + 生成中，2s 采样） |
| 首 token | 每镜 ~0.2–0.5s（prompt 缓存热） |

## 6. M2 已知问题（如实报告，不擅自修复，供下一步裁决）

1. **arc phases 质量**：LLM 原样输出 6 个单镜 HOOK 段（S01–S06 各一段），规则补全后才具备 HOOK→DEVELOPMENT→ESCALATION→CONCLUSION 结构——arc 的 LLM 输出质量是本轮最弱项；
2. **NUM_RE 单字误判**：`NUM_RE` 把"一/二"等单字当数字（S01「一座…」被误标 DATA → 该 beat 落了 DATA_GRAPHIC）——需修数字词表（≥2 字或带单位才算数字），属 M3 修复项；
3. **motion 分布不均**：HOLD_MICRO+PUSH_IN 占 20/25（下限 4 达标但重心集中）——P2 节奏/转场层将自然丰富；
4. **理由文案**：个别 beat 的 what_to_show 混入相邻镜内容（S20 提到 S19 的"海边小孩"），且中英混写——Validator 按设计不判理由文案真伪（创意域，人工抽查项）；
5. **SAFE_COMPOSITE 0**：P1 的 COMPOSITE 档未被 LLM 选用（图形叠加执行侧在 M4 才落地）——非错误，P1 档位保留。

## 7. 停止线

- **不进入 M3**（legacy 字节级回归）；**不渲染**；不 SEAL；不修改任何冻结物。
- 待人工裁决：① 本 plan 的导演决策质量是否达标（重点看 §3 抽样 + visual_plan.json）；② 是否授权 M3（legacy 回归）→ M4（执行渲染）；③ §6 修复项是否并入后续轮次。
- 判读入口：`output/stage33/coral/plan_report.md`、`visual_plan.json`、`validator_log.json`。
