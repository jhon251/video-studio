# RUN 02 PREFLIGHT — 检查清单与状态

> **性质**:Preflight 与实验配置冻结。零生产渲染、零冻结/baseline 修改。
> 机器可读:`output/prod02/run02_preflight.json` · claims:`run02_critical_claim_review.json` · manifests:`run02_control_manifest.json` / `run02_treatment_manifest.json` · 子实验:`visualization_subexperiment.json`

## P-1 题材决策 — **CONFIRMED**

同 SAO narration 作为 Control/Treatment 配对样本:同 narration / 同音轨 / 同 beat 边界 / paired evaluation(101 拍)。不重生成 narration。

## P-2 CRITICAL Claim 人工确认 — **CONFIRMED / CLOSED(2026-09-06 正式归档)**

- 全片 atomic claim 分解:**101 拍 / 113 条主张**;AI 提议重要性 CRITICAL 76 / IMPORTANT 34 / SECONDARY 3;
- **人工编辑裁决(76/76 CRITICAL 全部处理)**:确认 CRITICAL **65** · 降级 IMPORTANT **10**(S02-B01/S10-B01/S12-B01/S17-B01/S19-B01/S24-B02/S24-B03/S25-B02/S29-B01/S30-B03,理由逐条留档)· 1 条 AI-CRITICAL 未被人工输入覆盖(S25B-B02#C1"算力开销天文数字")→ **按规则保留 UNKNOWN**,不自动归类;
- id/文本差异 1 处已按文本唯一匹配处置并留档:降级 #10 输入 id S30-B02#C1,实际匹配 S30-B03#C1;
- **最终重要性分布:CRITICAL 65 / IMPORTANT 44 / SECONDARY 3 / UNKNOWN 1**(合计 113);
- **正式收口归档**:claims 层已密封(seal sha256 前 16 位见 preflight JSON);10 条降级记录、S30-B02→S30-B03 文本唯一匹配说明、S25B-B02 UNKNOWN 人工未覆盖说明全部归档于 `run02_critical_claim_review.json` meta.p2_closure;
- **自此冻结**:narration / claim_text / claim_type / beat_id / claim_id / AI_proposed_importance 不再修改(密封 sha256 为证)。

## P-3 Visualization Mockup 子实验 — **AUTHORIZED / REGISTERED**

- 范围:仅 22.5 A 类(structural/quantitative/comparison/non-photographic),规划 8 拍(三尺度 timeline、约束网、带宽对数图、五层阶梯 ×2、读vs写、两半边);
- 对照:同拍 retrieval 最优照片候选;独立评分(claim coverage / info-gain),不与检索改良混算;失败 → HONEST_NEUTRAL;
- 无 rubric 调整、无自动 evidence bonus;标记 **EXPERIMENT_ONLY**。

## P-4 Production 启动硬门槛

| 门槛 | 状态 |
|---|---|
| Integrity:14/14 冻结指纹 · baseline render_163(`7e148585564716cd`)· Run 01 母片(`ff119fcd1c559b52`)· Gate/CV2/Assignment hash 不变 | **PASS** |
| Experiment isolation:双臂 manifest 可复现 · 同 narration/音轨/边界 · 唯一变量 = routing · per-claim EQS 不参与自动决策 | **PASS** |
| Safety:B2=0 · Tempi=REJECTED · pseudo=0 · generic-as-evidence=0 · false claim=0 · LOW 自动采纳=0(禁用词表已注册,生产期强制) | **PASS(预注册)** |
| Evaluation 预注册阈值复核:coverage ≥0.42 · A 级 ≥35% · C+D ≤6% · ADR ≤0.25 · correspondence ≥85% · 六项 safety 全 0 | **PASS(仍有效)** |
| 成本 sanity:盲评 ~990 calls < 预估×1.5 | **PASS** |

**停止条件(生产期强制)**:任一 safety 违例 · 成本 > 预估×1.5 · isolation 破坏 · 冻结指纹改变 · 配对无法严格成立 → 即停。

## 成本 / 运行时 / 回滚

- 预估:搜索 340–380 · 下载/CV2 430–470 · 盲评 ~990 vision(评价侧)· 墙钟 **5–6h** · 较 Run 01 +15–25% 调用;
- 回滚:删除 `output/prod02/` 即完全回滚(baseline/冻结件全程零触碰)。

## 最终状态

## 状态总览

| 项 | 状态 |
|---|---|
| P-1 题材(同 narration 配对) | **PASS / CONFIRMED** |
| P-2 CRITICAL 确认 | **PASS / CLOSED**(归档完成) |
| P-3 可视化子实验 | **PASS / REGISTERED / EXPERIMENT ONLY** |
| P-4 生产硬门槛 | **PASS** |
| Production Start | **PENDING AUTHORIZATION** |

```
RUN 02 PREFLIGHT = READY
唯一待授权:Production Start
STOP——等待授权;不自行开始 Run 02
```
