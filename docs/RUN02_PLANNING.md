# RUN 02 PLANNING — Claim-centered Evidence Routing 受控再生产

> **性质**:PLANNING / RESEARCH / PREFLIGHT ONLY。零生产渲染、零冻结修改、零 baseline 改动。
> 机器可读:`output/prod02/run02_plan.json` · `run02_baseline_metrics.json` · `run02_experiment_matrix.json` · `run02_cost_estimate.json`
> 继承结论全部引自工件:Stage 18 链 · 22.1–22.3 R1 · 22.4 NOT_SUPPORTED · 22.5 SUPPORTED · 22.6 PARTIAL · 22.7/22.8 SUPPORTED · 22.9–22.10 SUPPORTED · 22.11 PARTIAL(κ 0.809,盲 ADR 0.375)· 22.12 BLOCKED。

---

## 1. 核心假设(唯一实验变量)

> 在下游(Gate/V1/CV2/Assignment)**完全冻结**的前提下,仅将计划层从"intent wording → query"替换为 **Claim-centered Evidence Routing**(narration → atomic claims → evidence type → evidence core → evidence-specific query),即可显著降低 generic/mismatch、提高 claim coverage 与真实证据密度,且不牺牲 correspondence 与诚实性。

**对照** = Run 01(同 narration、同 claims、同 TTS;已有母片/池/判定/盲测基线)。**处理** = Run 02(唯一变量 = 计划层路由;含 22.5 可视化路由的受控子实验)。**同 narration 再生产** = 最干净的逐拍配对设计(n=101);新题材泛化留 Phase-2 另行授权。

## 2. P1 — Run 01 可量化基线(全部来自工件,非主观分)

| 指标 | Run 01 值 | 来源 |
|---|---|---|
| 五级分级(A/B/C/D) | 23 / 66 / 8 / 4 | Stage 22 分析师分级(rubric 可一致应用:22.11 κ 0.809) |
| Generic(C+D)拍占比 | **11.9%** | 同上 |
| A 强证据占比 | 22.8% | 同上 |
| **Claim coverage(盲共识均值)** | **0.269** | 22.11 盲测 38 拍子集(κ 0.809)——**与冻结 correspondence 98.02% 的巨大裂缝即本立项依据** |
| Correspondence(冻结定义) | 99/101 = 98.02%(≥60% ✓) | 不变,不重解释 |
| Fallback | 2 拍 / 8.28s(角标已渲染,QA 证非缺陷) | R01-1 |
| 族集中度 | top1 34.7% / top3 ~73% | Run 01 族普查 |
| Reuse | unique 99 · multi_use 2 · adjacent 0 | 冻结审计 |
| 可视化使用 | **0**(22.5 确认 ≥10 拍有机会) | 缺口 |
| 字幕存在性 | 4 处 2–3s 句间停顿(QA 判非缺陷) | presence_scan |
| A/V delta | 0.2s | stage162 同款管线 |
| 外部审片分 | 5/10 · VEQ 3.5/10 等 | **OBSERVED_BY_REVIEWER,外部基线,非真值** |

## 3. P2 — 唯一实验变量与模块矩阵

**EXPERIMENT(仅 4 项)**:① claims 分解(AI 提议 + 用户 preflight 确认 CRITICAL);② intent typing + evidence-type 路由;③ evidence-specific query 生成;④ V1 类拍可视化 mockup(受控子实验,独立评价,失败回 HN)。
**SHADOW(不决策)**:per-claim EQS 向量(22.9/22.10 口径)· entity-class 标注。
**UNCHANGED**:检索 harness(R1 版)· Gate · V1 · CV2 · Assignment 政策(不含族预算,22.6)· 字幕/动作/构图 · correspondence 定义 · TTS 音轨(复用)· render 管线。
完整 18 行矩阵:`run02_experiment_matrix.json`。

## 4. P3 — Evidence Type 路由表(进入/禁止/回退)

| 类型 | 进入 | 禁止 | 回退 |
|---|---|---|---|
| REAL_WORLD_EVIDENCE | 真实人/设备/实验/事件/场所且有公开影像 | 专有内部影像无公开素材时充数 | HN |
| LITERAL | 可直摄对象/动作 | 不可摄抽象机制 | HN |
| DOCUMENT_ARCHIVE | 真实档案影像 | 现代复制品冒充 | HN |
| DATA_QUANTITATIVE | 权威公开数据图 | 无溯源数字图/装饰图表 | VIZ(受控)或 HN |
| VISUALIZATION | 22.5 A 类(结构/数量/时间/比较且不可摄影) | B 类(有真实证据)/D 类(装饰) | HN |
| METAPHORICAL | 修辞有公认视觉映射 | 强行配图 | HN |
| HONEST_NEUTRAL | 以上全不满足或池内无不劣于现任的候选 | **永不计入 correspondence** | — |

**全局禁止**:为对应率把任意图解释成 evidence;ABSTRACT_CG 在 evidence 意图下豁免(22.7 实证);B2/S20–22 抽象段与 Tempi/灾难素材(两项 REJECTED 继续生效)。

## 5. P4 — Visualization 规则

真实证据 > 可视化 > HN。仅 22.5 **A 类**生成(全片约 8 拍);B 类必须真实证据;C 类证据优先;D 类禁止。生成 mockup 为受控子实验(独立评价,失败回 HN);能力未独立验证前不得称为生产功能。

## 6. P5 — 指标

- **Primary**:claim coverage 盲共识均值 ≥ **0.42**(Run01 0.269 + 0.15)· A 强证据 ≥ **35%** · Generic(C+D)≤ **6%** · scalar 隐藏关键缺口 ADR ≤ **0.25**(Run01 0.524)
- **Secondary**:info-gain/E4 不降 · 非 atmosphere 功能 ≥ 75% · max same-family run ≤ 5 · multi_use ≤ 2 · adjacent = 0
- **Safety**:honesty 违例 0 · pseudo 0 · B2/Tempi 0 · LOW 自动采纳 0 · correspondence ≥ **85%(冻结定义,不重解释)** · HN 不计入

## 7. 实验设计

- 配对逐拍(n=101)+ 盲评子集 ≥40 候选(系统 1/3 步长 + 全 CASE_A 拍);
- 盲评 = 3 盲态 LLM 实例(22.11 验证 κ 0.809),**双臂同评**(A/B 候选对同一 claim 集,arm-blind);终审 = 人工 QA(你);
- 回归控制:10 个 routing 不变 NC 拍,池必须与 Run 01 一致(R1 语义回归);B2/Tempi 物料计数 = 0;
- 成功 = primary 4 项全达 + safety 全 0;部分 = primary 2–3 项且 safety 全 0;失败 = 任一 safety 违例 / correspondence < 0.85 / generic 恶化;
- 停止条件:safety 违例即停;池深不足(≥20 拍无合格异族候选)即停报告;人工 QA FAIL 且需触碰冻结件即停。

## 8. 成本(Run 01 实测为基)

| 项 | Run 01 实测 | Run 02 估 |
|---|---|---|
| 搜索 query | 301 | 340–380(R1 完整执行 + 细分) |
| 下载 / CV2 | 429 / 429 | 430–470 / 430–470 |
| TTS | 101 | **0(复用音轨)** |
| 新增 | — | claims 分解 ~101 文本调用 · VIZ mockup 5–8 张(本地)· 双臂盲评 ~990 vision(评价侧) |
| 墙钟 | 4–5 h | **5–6 h**(+15–25% 调用量) |

预算纪律:超预估 50% 即停扩张报告(继承 22.x 惯例)。

## 9. Rollback

Run 02 全部产物隔离于 `output/prod02/`;baseline/冻结件零触碰;回滚 = 删除 prod02 目录。

## 10. Preflight 条件(进入 Run 02 生产前)

- **P-1** 题材决策:默认**同 narration 再生产**(最干净对照);换新题材需知晓混杂代价;
- **P-2** 你在 preflight 确认 claims 分解与 **CRITICAL 标签**(22.12 规则:AI 提议、人类确认);
- **P-3** 授权可视化 mockup 子实验(受控、独立评价);
- **P-4** 授权启动 Run 02 生产。

## 11. 冻结边界

14 冻结模块 · Gate/V1/CV2 · correspondence · render_163 baseline · Run 01 结案封存 · Stage 18–21 CLOSED · per-claim EQS shadow only · Critical 由人类确认。

---

```
RUN 02 PLANNING = READY
核心假设 · Control=Run 01 · Treatment=Claim-centered Routing(唯一变量) · Frozen Boundary ·
Primary/Secondary/Safety 指标 · 配对 n=101 + 盲评 ≥40 · 成本 +15-25% · Rollback = 删 prod02 ·
Preflight P-1..P-4 待确认
STOP——不开始 Run 02 Production,等待授权
```
