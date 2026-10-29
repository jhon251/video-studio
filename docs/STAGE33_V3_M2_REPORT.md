# Stage 3.3 V3-M2 报告（Coral V3 Visual Statement Plan 生成 + G1–G4）

> 状态：plan 已冻结，G1–G4 全 PASS，**STOP 等待 V3-M3 授权**。未渲染、未覆盖 P1、3.2b/3.1.4/2.x 零改动。

## 1. 冻结信息

| 项 | 值 |
|---|---|
| visual_plan.json | `output/stage33/coral/v3/visual_plan.json`（**35 beats / 20 镜**） |
| **plan_sha** | `d60e60f796eb00070329e9da178228e6b83001ead28426c43dd23fd7b9e7c245` |
| input_fingerprint | `35ad4b267fca03a8` |
| director_mode | LLM（**15/20 镜 LLM 决策**；按镜回退 5：S03/S07/S10/S12/S19） |
| LLM 原始输出 | `output/stage33/coral/v3/llm_raw/*.json`（SHA 全记录于 plan_report） |
| 生成耗时 | **47 分钟**（statement 输出 2400 tokens/镜 + 5 镜重试） |

## 2. G1–G4 逐项结果

| Gate | 结果 | 数据 |
|---|---|---|
| G1 Statement 结构 | **PASS**（PASS_WITH_REPAIRS） | 修复 13：`attention_target 非原文子串 ×12`（LLM 常选概念词，如"珊瑚白化"而非原文词，已确定性修复为原文数字/关键词）+ `director_note 超 80 字 ×1`；junk=0、rejects=0 |
| G2 反模板 | **PASS** | 模板名违规 **0**；模板式句式 **0**；全文复制 **0**；幻觉计划（抠像/生成式等）**0** |
| G3 Safety/Truth/Rights | **PASS**（有 1 处新发现，见 §4） | junk=0；evidence_material 全部白名单一致；数字⊆原文（graphic 层） |
| G4 Executor 可表达性 | **PASS** | 无幻觉计划；19 处运动意图不可行 → **HOLD 留痕**（"平移速度不足 1px/帧 → HOLD（静止优先）"等，全部诚实记录在 spec.motion_note） |

## 3. Director 转型证据（抽样，真实字段）

| beat | 镜 | 注意力设计（真实输出） |
|---|---|---|
| B010 | S06 | target=`一两度`（原文子串）；三层=海洋背景/珊瑚礁/温度变化曲线；stages=揭示+几何遮罩；graphic=`一两度`；rel=contrast"视觉焦点的递进"——**"让观众先看数字、再看它带来的影响"的完整命题** |
| B014 | S08 | target=`百分之一`；三层=海底背景/十米珊瑚礁/海洋生物；motion=none"静止即完整表达"；graphic=`百分之一`——注意力命题成立 |
| B030 | S18（climax） | target=`珊瑚礁的生死`；foreground=数字"十年"；rel=contrast——但 path 文案与 target 不一致（见 §4） |
| B034 | S20 | target=`会呼吸的城市`；三层含"呼吸的比喻"——但 path 为模板占位符（见 §4） |
| B017 | S10（回退） | 规则命题：焦点"绑在"、诚实标注"无素材诚实降级" |

**结论（回答本阶段核心问题）**：Director **已开始**从"选模板"转向"设计观众如何看懂这句话"——B010/B014 是真正的注意力命题（目标词、路径、分层职责、时序、关系解释俱全），全计划 0 模板名；但转型不完整（§4 三处漂移）。相比 P1 的"DATA_GRAPHIC+PUSH_IN"，抽象层确已提高一层；相比"成熟导演"，仍有明显差距。

## 4. 如实上报的问题（不自行修复，待裁决）

1. **【G3 校验缺口·本轮发现】B010 的 visual_evidence 文本含自造数字 `0.457 ±0.068°C`**（口播原文只有"一两度"）。现有 S3 只校验 graphic 层数字⊆原文，未校验 statement 文本字段中的数字——**建议 M3 前补上"全部 statement 文本字段数字 ⊆ 口播原文"校验并重新生成 plan**（本轮计划已冻结，该违规字段已留档供复查）；
2. **B034（S20）attention_path = "第一眼看X→第二眼理解Y"**——LLM 把 schema 提示的占位符原样输出（模板化残留），且 layers 中英混写（"城市 silhouett"）；
3. **B030（climax）path 与 target 不一致**（target 是"珊瑚礁的生死"，path 却说"第一眼看数字"）；
4. **1 处 motion intent/necessity 矛盾**（B034：intent=attention_shift 但 necessity 写"静止即完整表达"）；
5. **19/35 beats 运动意图 → HOLD 降级**：LLM 大量要求 attention_shift，但 1px/帧 门槛下平移不可行——v3 成片将**大量静止 + 锚点词淡入**。这是"静止优先"设计与实现门槛的共同结果，可能仍是"静态卡流"观感——由 V3-M3 成片人工裁决；
6. **release_beats 为空**：LLM 的 arc 未给出 release_shots（pacing 说明只提到 climax 对比）。

## 5. 停止线

- **不进入 V3-M3（execute）**；不渲染；不 SEAL；不动任何冻结物；
- 待裁决：① 本 plan 是否接受；② §4-1 的 G3 校验缺口：先补校验+重跑 plan，还是先 execute 出片再一并评估；③ 授权 V3-M3 执行渲染。
- **STOP。**
