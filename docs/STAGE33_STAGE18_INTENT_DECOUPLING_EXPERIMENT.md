# Stage 18:Visual Intent 解耦实验报告(Top-10,测试侧)

> 链路按授权执行:Narration → Narrative Meaning → Visual Evidence Core → Evidence Type → Visual Focus(唯一主体+唯一动作)→ Query → **现有候选池** → 冻结 Gate/V1/CV2 判定。零新检索、零新源、零下载、零冻结模块改动、零质量放宽。解耦 intent 一次性生成后冻结(`intent_sha=b9b3460c3775ed94`,检索/匹配期间未改写)。

## 1. A/B 逐拍结果

| Beat | visual_focus(新) | evidence_type | 旧素材(fit) | 新最佳候选(fit) | GENERIC/MISMATCH(旧) | 判定 |
|---|---|---|---|---|---|---|
| S30-B01 | 工厂中机械臂执行工种,工人在场 | INDUSTRY_SITE | Tesla megacasting(0.50) | **Martin 吉他厂机械臂(0.90 USABLE / HIGH)** | MISMATCH_RISK→消除 | **SWAP** ✅ |
| S02-B01 | 行人穿过城市十字路口 | REAL_METAPHOR | Strand crossing(0.60) | 同一素材(0.60) | GENERIC | KEEP(等值) |
| S24-B01 | 黎明城市天际线 | REAL_METAPHOR | HCMC sunrise(0.55) | 同一素材(0.55) | MISMATCH_RISK | KEEP(等值) |
| S13-B02 | 人群围坐讨论 | REAL_EVENT | Camp Foster(0.60) | 同一素材(0.60) | GENERIC | KEEP(等值) |
| S29-B02 | 学生平板课堂 | REAL_EVENT | Abi Hanifa(0.55) | 同一素材(0.55) | GENERIC | KEEP(等值) |
| S16-B01 | 调度中心人员面对数据墙 | INDUSTRY_SITE | Traffic control map(0.50) | 同一素材(0.50) | MISMATCH_RISK | KEEP(等值) |
| S34-B01 | 人与机器人并肩操作 | REAL_METAPHOR | 花朵隐喻图(0.70) | HRC 锯木(0.20 NOT_USABLE,17.3 冻结验证) | MISMATCH_RISK | KEEP(质量未过) |
| S12-B02 | 一名工人在工作现场 | REAL_EVENT | Empty plaza(0.35) | Mumbai 工人(0.20 NOT_USABLE,17.3 冻结验证) | MISMATCH_RISK | KEEP(质量未过) |
| S33-B02 ⚠️地缘敏感 | 学生举手课堂 | REAL_EVENT | Classroom Activities(0.40) | Gaza 课堂(0.10 NOT_USABLE) | MISMATCH_RISK | KEEP(双重复核不放行) |
| S08-B03 | 控制室操作员面对屏幕墙 | INDUSTRY_SITE | Toronto TV 控制室(0.60) | pexels 操作员(0.55 CU 但缩略图未持久化,零下载约束下不可用) | MISMATCH_RISK | KEEP(等值偏下+不可取回) |

## 2. 门槛核对

| 门槛 | 要求 | 实测 | 结果 |
|---|---|---|---|
| 严格优于 | ≥7/10 | **1/10**(S30-B01) | ❌ |
| HIGH 密度 | ≥3/10 | **1** | ❌ |
| 明显退化 | 0 | **0**(无合格候选一律回退原素材) | ✅ |
| reuse 不增加 | 不增 | **30→29**(S30-B01 换图消除了 Tesla 图的一处复用;max_reuse 3 不变;相邻同素材对 0→0) | ✅ |
| correspondence | 不降 | **不变**(唯一 SWAP 仍为对应拍;56/309.26s/60.86%) | ✅ |
| 工程审计 | 无回归 | 未触发渲染(PASS 才渲染) | n/a |

**→ `STAGE18 = FAIL · STOP`**(1/10 < 7/10),不进入渲染,不扩大范围。

## 3. 结构性发现(本轮实验的核心价值)

1. **约束内不可测**:现有候选池是**在旧复合 intent 下抓取的**,每拍仅持久化 6 条判定。新 intent 只能在这个池内重选——池里没有新 intent 想要的现实证据素材,这从结构上决定了 7/10 不可达。解耦假设本身未被证伪,而是**未被测试**:S30-B01(池内恰好存在兼容素材)与 17.3(0.9 USABLE)是仅有的两个正样本,均支持设计有效性。
2. **冻结链行为与 17.3 一致**:intent 解耦后,4 拍的"新最佳"就是原素材本身(等值)——解耦 focus 没有伤害任何拍;所有退化风险为 0。
3. **复用约束实验通过**:swap 后复用反而下降(30→29),相邻同素材 0;证明该约束可与替换流程并存。
4. 唯一允许替换:S30-B01 → Martin 吉他厂机械臂(USABLE 0.90 / HIGH)。**留档**,不渲染。

## 4. 边界结论

当前授权边界(零新检索)下,Top-10 的可改善上限 = 1 拍。要真正验证解耦设计,需要授权**同一素材源、新查询**的重新检索(不新增源、不改冻结模块)——这是下一阶段唯一值得做的实验;若无此授权,Stage 17 线与 18 线的结论合并为:**现有成片(60.86%,运动 8.9%,无假切换)在不新增检索与不修改冻结链的前提下已达上限**。

```
STAGE18 = FAIL · STOP
A/B: 1/10 严格优于(S30-B01 0.9 USABLE HIGH,唯一 SWAP,留档不渲染) · HIGH 1/10 · 退化 0 · reuse 30→29 不增 · correspondence 不变 · 工程审计 n/a(未渲染) · 结构性发现:旧 intent 抓取的池在零新检索约束下无法验证解耦假设
STOP——等待下一步授权
```
