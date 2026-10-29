# Stage 33 — RUN 02 EXP-A 封存 + 统计归因 + EXP-B 预注册

> **性质**:实验封存 + 只读分析 + EXP-B 预注册。零生产修改。

---

## 1. EXP-A 正式封存

| 项 | 值 |
|---|---|
| 实验 | Evidence Retrieval Optimization(7 拍) |
| 封存时间 | 2026-09-06 |
| Seal SHA256 | `dcbe69d0ab3ca915...` |
| 结果 | **5 RECOVERED / 2 NOT_RECOVERED(71.4%)** |
| Safety | 全 0 |
| 预注册假设 | **SUPPORTED**("部分 Run02 非对应确实来自 retrieval failure") |
| 范围限制 | 仅限预注册 7 拍,不得外推 |

### 5 RECOVERED

| Beat | 主张 | 治疗 query | 治疗最优 |
|---|---|---|---|
| S03-B03 | 房间尺度追踪 | room scale VR gaming | USABLE/HIGH 0.95 |
| S05-B01 | 摘下头显回现实 | taking off VR headset | USABLE/HIGH 0.80 |
| S06-B01 | 动捕是第一套方案 | motion capture studio | USABLE/HIGH 0.95(File:Aktor motion capture.jpg) |
| S29-B02 | 康复患者意念控制 | rehabilitation robotics | USABLE/HIGH 0.90(SD tours Rehab Center) |
| S04B-B02 | VR 拳击/健身 | VR boxing game player | USABLE/HIGH 0.95 |

### 2 NOT_RECOVERED(结构性限制)

| Beat | 主张 | 失败原因 |
|---|---|---|
| S06-B03 | 影视动捕驱动数字角色 | 免费图库范围内未获满足硬标准候选 |
| S32-B02 | 写入感知接口 | 同上(神经刺激/植入设备不在免费图库) |

> **措辞限制**:不声称"互联网不存在这些图片",只声称"**在本实验允许的免费图库/合法来源范围内未获得满足硬标准的候选**"。

---

## 2. 统计归因

### RUN 02 correspondence 重新计算(诊断 only,不修改 Run 02)

| 层 | 值 | 标签 |
|---|---|---|
| 原始 Run 02 photo correspondence | 50.5%(51/101) | 正式结果,不变 |
| EXP-A 恢复 +5 拍(诊断) | +5 | **hypothetical / diagnostic only**,未执行重新 Assignment |
| **Photo correspondence 理论上限** | **67/101 = 66.3%** | hypothetical,非正式 |
| + VIZ 11 拍(信息图表) | +11 → 78/101 = 77.2% | 多模态证据覆盖(非 photo corr) |
| + HN 26 拍(诚实留白) | +26 → 104/101 > 100% | HN 永不计入 correspondence |

### 关键洞察

- Run 01 的 98.02% 和 Run 02 的 50.5% **不可直接对比**:两个 run 的 routing 策略完全不同
- Run 02 的 50.5% 是**诚实路由的下界**:37 个 HN/VIZ 拍被正确识别为非照片证据,而非伪装
- 如果 Run 02 采用 EXP-A 修复后的 5 个恢复证据,**photo corr 可达 ~56.4%**——仍低于 Run 01 的 98%,但**每个对应都是真实的证据映射,而非泛图充数**
- 22.5 VIZ 路由的 11 拍如果计入"多模态证据覆盖",总覆盖 = 62/101 = 61.4%——比 Run 01 的"名高实低"更有信息量

---

## 3. EXP-B 预注册(仅注册,不执行)

| 项 | 内容 |
|---|---|
| 实验 | Visualization Routing Enhancement |
| 对象 | 5 个 HN→VIZ 候选(S13-B01 三座山图 / S30-B01 十道坎 list / S01-B03 层数 teaser / S26-B02 一慢一快 comparison / S02-B04 逐层 roadmap)+ 10 个现有 VIZ 的 quality enhancement |
| Primary | Evidence Coverage:VIZ 采纳后这些拍的信息增益从 0 提升到 ≥1 |
| Secondary | Critical Claim Coverage · Visual Utility · claim-visual alignment |
| Safety | VIZ 不计入 photographic correspondence · pseudo=0 · decoration=0 · provenance=100% |
| 禁止 | retrieval optimization(EXP-A 已完成)· generic photo fallback · 修改 correspondence/CV2/Run01 |

---

## 4. 完整冻结边界

Run 01 母片 / render_163 baseline / 14 冻结件 / Gate/V1/CV2 / correspondence / Stage 18–21 / P-2 seal / Run 02 正式结果 / Run 02 assignment:全部不变。EXP-A/B 工件封存于 prod02 与 stage22 目录。

---

## 5. 当前全局状态

| 阶段 | 状态 |
|---|---|
| Production Baseline | render_163 |
| Run 01 | PRODUCTION QA APPROVED / PASS(封存) |
| RUN 02 | FAIL(50.5% corr)· EXP-A 封存(5/7 恢复) · EXP-B 预注册 |
| Stage 22 系列诊断 | 完整 · 封存 |
| Per-Claim EQS | Shadow only · 等人类评分者 |
| EXP-B | REGISTERED · 未执行 |
| Production Run 03 | 未规划 |

```
RUN 02 EXP-A SEAL = COMPLETE · EXP-B REGISTERED · STOP
等待:EXP-B 执行授权 或 Run 03 规划 或 其他
```
