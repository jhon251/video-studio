# Stage 33 — STAGE 22.2: Production Fix Candidate Review

> **性质**:工程变更候选评审(基于 Stage 22 + 22.1 全部诊断)。零生产修改、零冻结修改、零渲染、零 baseline 改动。
> 机器可读:`output/stage22_visual_quality/stage22_2_fix_review.json`
> 依据:`STAGE33_STAGE22_..._DIAGNOSTIC.md` · `STAGE33_STAGE22_1_QUERY_COMPLETENESS_REVALIDATION.md` 及其 JSON/原始数据。

---

## R1 — Query 完整执行修复

**判定:SAFE WITH GUARDRAIL(推荐为下一个进入生产的变更,待显式授权)**

- **证据**:32/101 拍真实截断(重放实证,B 型);完整性 51.8%→100% 后池 +42%;**BrainGate 实锤**(S16-B01 被跳过的 `brain implant` query 下有 USABLE/HIGH 0.85 的真实临床试验影像,生产选了实验鼠);S19-B01 相关性升级;跳过 query 含异族候选(haptic glove/GPU/VR play space)——修复同时缓解族级单调。
- **生产安全**:修改对象是 `output/prod01/retrieval_run.py`——Run 01 的 harness,**非冻结模块**;冻结 Stage 12 的 tier 升级语义(pool_precision/two_pass_material)不受影响。
- **最小变更:3 行**——① 循环扩为 `t1[:2]+t2[:1]+t3[:1]`;② 删除 `>=4 break`;③ 每query结果数日志(1 行)。**不改**:下载 cap(top-4/拍)、dedupe、CV2、指派。
- **ranking/scoring 影响**:零——只扩大候选供给,冻结 CV2 以相同方式判定更大的池。
- **成本/延迟**:搜索调用 156→301(+93% API GET,约 +1–2s/拍);**下载与 CV2 调用不变**(cap 不动)。
- **池爆炸风险**:低(池是元数据,下载有 cap,dedupe 不变)。
- **回归测试**:T1 完整性=100%;T2 S16-B01 池含 BrainGate 级候选;T3 每拍池 ≥ BEFORE;T4 无重复下载。
- **回滚**:单文件恢复即可;retrieval_index 逐拍可重建。

## R2 — Entity Query

**判定:RESEARCH ONLY(条件 tier 候选,需 EXP-22.2)**

- **有收益域**:机构公开影像(NASA/universities/DOE——ISS HoloLens 0.95)、公开临床设备(DBS 0.95/EEG 头带 0.9/neurofeedback 患者 0.9)、博物馆档案。
- **无收益/风险域**:专有消费产品(Neuralink → 牙科诊所**语义误命中**);抽象概念;intent 锁定拍(S27-B01)。
- **误命中机制**:品牌词法匹配(implant↔dental)+ CV2 relevance=HIGH 仍可能错实体类——需要实体白名单 + 主张类型校验,不是加 query 字符串就够。
- **条件 tier 设计**:触发 = narration 点名具体机构/产品/试验 且 intent-type=evidence;域 = public_research / public_clinical / archive;位置 = t1 与 t2 之间的升级层,只升级不替代。

## R3 — Intent 类型规范

**判定:RESEARCH FIRST(EXP-22.1)——最高杠杆,实验先行**

8/12 C/D 拍完整执行仍 generic → intent 层是主导路径。最小实验(12 拍 × 2 变体,诊断检索 + 冻结 CV2,~50 搜索 + ~40 CV2 调用):

| 类型 | CURRENT intent(Run 01 实况) | EVIDENCE-ORIENTED 变体 |
|---|---|---|
| 什么时候实现 | 时钟特写 → "clock closeup" | 三尺度 timeline 图表 或 Honest Neutral;测试 `technology roadmap diagram` |
| 五层技术 | 神经实验室/VR review | 分层证据拍(L1 真 VR 照、L4 真 EEG 实验室)或阶梯图;测试 `VR headset vs EEG cap` 配对 |
| 推测而非预测 | 化学白板 | 元陈述 → Honest Neutral 或"研究者+路线图"实照;测试 `research roadmap neuroscience` |
| 技术瓶颈 | 神经元显微 | **微电极阵列特写**(瓶颈本体硬件);测试 `microelectrode array closeup` |
| 抽象概念(看见≠进入) | 头显+空房 | 双真照分屏(戴/摘)或 Honest Neutral;测试 `removing VR headset` |
| 读 vs 写 | fMRI/神经纤维 | READ=BrainGate 电极阵(已证可得)、WRITE=DBS 植入设备(entity 实验已证 0.95);两个 query 均测 |

**成功标准**:≥4/6 类型出现 ≥1 个非 stock、与主张映射的 USABLE/HIGH 候选;cliché 型被选 ≤1 次。

## Visualization(分类,不实现)

| 类 | 拍 | 数 |
|---|---|---|
| **A 真需要图表** | S27-B01(三尺度时间线)、S20-B01/B02(带宽对数图)、S02-B03+S33B-B01/02/03(五层阶梯)、S18-B02/B03+S18B-B02(读vs写) | 8 |
| **B 真实证据足够** | S28-B02(微电极阵列特写)、S26-B01(真 VR+AI 照) | 2 |
| **C 两者均可** | S19-B01(假体图解 vs 真实试验照)、S04-B02(MR 透视照 vs 示意) | 2 |
| **D 仅装饰** | 无——**时钟本身就是"装饰即失败"的反例** | 0 |

结论:图表是 class A(约 8 拍)的**定向能力**,非通用 pipeline 步骤;对 B/C 类强行加图表反而劣化。

## Recurring Anchor:HOLD(排 EXP-22.4)

有价值但必须先有族级多样性预算(EXP-22.3),否则退化为 EXP-21.2b 的疲劳模式。

## 最终矩阵

| Candidate | Evidence | Production Safety | Recommendation |
|---|---|---|---|
| R1 Query completeness | BrainGate 实锤 + 池 +42% | **SAFE WITH GUARDRAIL**(3 行,非冻结件) | ✅ **可直接进入下一阶段**(首个生产修复,带回归测试) |
| R2 Entity Query | 域依赖(4/4/2) | 研究期;有误命中风险 | 🔬 先实验(EXP-22.2,条件 tier) |
| R3 Intent normalization | RC1 主导(8/12 完整执行仍 generic) | 分类学未验证前不安全 | 🔬 先实验(EXP-22.1,杠杆最高) |
| Visualization | 8 个 A 类拍、0 图表 | 需新能力 | 🔬 先实验(EXP-22.5,A 类 only) |
| Recurring Anchor | 合理但有疲劳风险 | 依赖族级预算 | ⏸ HOLD(EXP-22.3 之后) |

**执行顺序建议**:R1(最小生产修复)→ EXP-22.1(intent 诊断)→ EXP-22.2(entity tier)→ EXP-22.3(族级预算)→ EXP-22.5(可视化)→ EXP-22.4(anchor)。

**必须继续保持的冻结边界**:14 冻结模块+指纹 · Gate/V1/CV2 rubric 与权重 · correspondence 定义与 60% 标准 · Production Entry/Final Gate · render_163 active baseline 与 render_162 历史 · Stage 18–21 关闭线 · Honest Neutral 语义(永不计入 correspondence)。

---

```
STAGE 22.2 = REVIEW COMPLETE · STOP
R1 = SAFE WITH GUARDRAIL(3 行修复,推荐进入) · R2 = RESEARCH ONLY · R3 = EXPERIMENT FIRST ·
Visualization 定向能力(A 类 8 拍) · Anchor HOLD · 冻结边界清单重申 · 未实施任何生产变更
STOP——等待授权
```
