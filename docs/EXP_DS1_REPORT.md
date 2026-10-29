# EXP-DS1 报告：自动域信号实验（CV2 rubric v2）

- 日期: 2026-09-10 · 性质: 离线实验（零生产代码修改、零渲染、零冻结件触碰）
- 命名空间: `output/audit_20260910_ds1/`

## 1. 已完成的前置与准备

- ✅ Domain Ontology v1（28 域节点 / 11 近域边 / 同义集 / 伞形域废除清单）——`domain_ontology_v1.json`
- ✅ Evidence Core Table v1（101 拍：SELF=8、NO_EXPECTATION=12、DOMAIN_BOUND=89；伞形域零残留，S08-B01/S32-B02/S16-B02 三反例修正全部落表）——`evidence_core_table_v1.json`
- ✅ rubric v2 实验提示词（冻结 rubric v1 + `content_domain / domain_confidence / domain_evidence` 三字段 + 本体词表约束），定义于实验文件 `ds1_signal.py`（冻结模块 vision_controlled.py 零修改）
- ✅ 信号采集脚本（可续跑、增量落盘、402 熔断）

## 2. 执行结果：信号源不可用（fail-closed 按设计触发）

| 信号方案 | 探测结果 |
|---|---|
| S1 CV2 rubric v2（视觉） | HTTP **402 Insufficient Balance**（首候选即熔断，符合脚本设计的账户级熔断） |
| S2 文本 LLM 降级信号 | HTTP **402 Insufficient Balance**（共享账户余额，同样不可用） |
| S3 人工标注 | 即 DC1 已有人工标注——但 DS1 的被测对象恰是"自动信号"，人工标注无法替代被测项 |

**零信号可获得。** 全部六项硬指标（信号-人工一致率、Hydrogen 捕获、三反例、REVIEW 率、fail-closed 场景、零回归中的信号相关项）**无法测量**。

## 3. 指标

| 指标 | 要求 | 实测 |
|---|---|---|
| 信号-人工一致率 ≥85% | 需信号 | **N/A（信号不可得）** |
| Hydrogen Ladder 捕获 1/1 | 需信号 | N/A |
| 三反例走向 | 需信号 | N/A（ECT/本体路径的离线静态推演已在 G10 设计中给出：PASS/PASS/REJECT，但无自动信号实证） |
| REVIEW ≤25% | 需信号 | N/A |
| fail-closed | 触发即正确行为 | **✅ 按设计触发**（402 → 熔断 → 不产生任何伪信号 → 实验停止） |
| 零回归 | 全绿 | ✅ R1–R8 8/8 · 模块单测 12/12 · 编排器 16/16 · 冻结指纹 14/14 · Run01–04 母片哈希全部不变 |

## 4. 失败案例

**唯一失败案例 = 外部资源阻塞**：DeepSeek 账户余额耗尽（HTTP 402），S1/S2 双信号源同时不可用。非代码缺陷、非设计缺陷、非数据缺陷——实验本体（本体 v1/ECT v1/rubric v2/门规则）已就绪并冻结于审计命名空间，额度恢复后重跑 `python ds1_signal.py` 即可续跑（增量设计，已缓存量 0）。

## 5. 成本变化

- 零生产代码修改、零渲染、零冻结件触碰、零 Run01–04 artifact 变更（母片哈希复验不变）
- API 成本：2 次被 402 拒绝的探测调用（0 计费 token）
- 新增产物仅审计命名空间：本体 v1、ECT v1、rubric v2 定义、信号脚本、本报告

## 6. G10 自动信号生产化条件

**不满足。** G10 保持 DESIGN 状态，不得投产。恢复条件（全部为外部/授权项）：
1. DeepSeek 账户充值（恢复 S1/S2 信号源）；
2. 重跑 EXP-DS1（脚本与前置产物已就绪，续跑即可）；
3. 六项硬指标全过后，G10 才可进入生产化（且须同时确认验收口径重定义——域一致 CORRESPONDING ≥60 / HN≈37–39% 的诚实代价，见 G10 设计 §6）。

```
EXP-DS1 = FAIL（信号源不可用：S1/S2 双 402；六项指标无法测量）
G10 = 保持 DESIGN，不得投产
已完成并冻结 = Ontology v1 · ECT v1 · rubric v2 · 信号脚本（续跑就绪）
零回归 = R1-R8 8/8 · 模块 12/12 · 编排器 16/16 · 冻结 14/14 · Run01-04 哈希不变
失败案例 = API 402 Insufficient Balance（外部资源；fail-closed 按设计触发）
成本变化 = 零生产影响；API 2 次拒绝探测（0 计费）
STOP——等待授权（恢复额度后重跑 EXP-DS1）
```

## 附录：续跑记录（同日第二次尝试）

- 按原设计续跑 `ds1_signal.py`（冻结本体 v1 / ECT v1 / rubric v2 未动）：首候选即 HTTP **402 Insufficient Balance**，账户额度仍未恢复 → 按指令 fail-closed 停止，未产生任何信号，未伪造结果。
- 六项指标仍全部 N/A；零回归复验通过（Run01–04 母片与 14/14 冻结指纹不变；signals.json 未创建——零写入）。
- 恢复条件不变：账户充值 → 续跑 `ds1_signal.py`（101 候选，增量）→ 六项硬指标全过 → G10 方可进入生产化。
