# Stage 33 — RUN 02 失败归因 + EXP-A 检索优化实验注册

> **性质**:EXP-A 仅做检索优化实验注册与数据审计,暂不进入生产。零生产修改。
> 机器可读:`output/prod02/run02_fail_attribution.json` · `exp_a_registration.json`

## RUN 02 正式失败(已确认,不重写)

Run 02 correspondence = 51/101 = **50.5%**(< 60% 标准,< 85% 安全线)→ **FAIL**。
Safety 六项全 0 ✓。Experiment integrity ✓。诚实性达成 ✓。
核心发现:**Run 01 的 98% 对应率被 generic 充斥虚高;Run 02 诚实暴露了真实缺口(约 50% narration 具备照片可证据主张)。**

## 50 非对应拍归因

| 归因 | 拍数 | 性质 |
|---|---|---|
| 结构性诚实(HN 路由正确) | 26→21 真正确 + 5 HN→VIZ 候选 | 元陈述/问句/推测 |
| 检索失败(可修复) | 7 | 主张可摄影但 query/池未命中 |
| 池覆盖缺口 | 6→部分并入检索失败 | BCI/临床免费图库不足 |
| VIZ 正确路由 | 11 | 结构/定量/对比主张 |

## EXP-A:7 拍检索优化

| Beat | 原始 query | 池 | 失败模式 | 治疗方向 | 恢复评估 |
|---|---|---|---|---|---|
| S03-B03 | room scale VR | 7/5 | STOCK_POOL_GAP | 放宽为 play space | UNCERTAIN |
| S05-B01 | VR headset remove | 11/5 | QUERY_TOO_NARROW | 去掉 person 前缀 | UNCERTAIN |
| S06-B01 | motion capture suit studio | 12/5 | SEARCH_ENGINE_MISMATCH | 用 mocap studio/performance capture | LIKELY |
| S06-B03 | motion capture film production | 11/5 | HISTORICAL_NOISE | 用 performance capture/digital character | UNCERTAIN |
| S29-B02 | rehabilitation robot hospital | 19/3 | QUERY_TOO_BROAD | 聚焦 robotics/physical therapy | LIKELY |
| S04B-B02 | VR boxing workout | 8/4 | SEARCH_ENGINE_NOISE | 改用 workout/exercise/game player | LIKELY |
| S32-B02 | deep brain stimulation device | 20/1 | LEXICAL_MISHIT(DBS=汽车) | 用完整手术术语 | LIKELY |

## 恢复评估

- **LIKELY_RECOVERABLE 4/7**:动捕/影视动捕/康复机器人/VR 健身——照片确定存在但需精确 query
- **UNCERTAIN 3/7**:房间尺度/摘下头显——概念存在但 stock 可能不足

## 安全约束(不变)

pseudo=0 · LOW=0 · B2=0 · Tempi=0 · provenance failure=0 · generic-as-evidence=0

## 冻结边界

Run 01 / render_163 / 冻结件 14/14 / Gate/CV2 / correspondence / P-2 seal / Run 02 正式结果:全部不变。

```
EXP-A REGISTERED · 7 拍/失败模式 5 类 · 恢复评估 4 LIKELY + 3 UNCERTAIN · 零生产修改
STOP——等待 DeepSeek 充值 + 检索实验授权
```
