# Stage 18.2:受复用约束触发的替代候选检索实验报告

> 范围:仅 18.1 中"严格优于但被 reuse 拦截"的拍(触发条件经程序验证)。替代 Query 保持同主体(城市天际线)+ 同证据类型(REAL_METAPHOR / 黎明),仅更换具体素材,单主体、无概念拼装。候选完整经过冻结生产链 `retrieval → pool_precision → Gate → V1 → CV2 → eligibility`(`acquire_beat_material` 原样调用);Gate/V1/CV2/阈值/权重/Gold/缓存协议零改动;复用约束零放宽。

## 1. 触发集验证(程序判定,非人工挑选)

对 18.1 决策件逐行检查 `strictly_better AND reuse_block`:

| Beat | strictly_better | reuse_block | 触发? |
|---|---|---|---|
| **S24-B01** | True(0.95 USABLE) | True(与相邻 S23-B01 碰撞) | ✅ **唯一触发** |
| S33-B02 | False(0.4=旧,等值) | True | ❌ 拦截原因是质量/无改善,非 reuse → 不在授权范围 |
| 其余 8 拍 | — | False | ❌ 不触发 |

## 2. 替代检索记录(S24-B01)

| 项 | 18.1 | 18.2(替代) |
|---|---|---|
| Query(单主体) | `city skyline sunrise` / `skyline dawn city` | **`sunrise city skyline silhouette` / `city skyline dawn mist`** |
| 首选候选 | Milwaukee 天际线 0.95 USABLE → 被相邻复用规则拦截 | **Cleveland skyline above the coal slag(0.90 USABLE)** |
| 池/进 Gate | 6 | **6 进 Gate(5 keep)/ 1 进 CV-2 / pass-2 未触发** |
| CV2 fit / label | — | **0.90 / USABLE** |
| relevance | — | **HIGH**(冻结 vision_call 测量:0.95,USABLE,"剪影与晨光契合口播希望意境") |
| reuse | Milwaukee 已被 S23-B01 使用 | **Cleveland 全片零占用**;HCMC 保留于 S25-B02 不受影响 |
| 判定 | KEEP(被拦) | ✅ **SWAP**(冻结链自身终选即为 Cleveland,无需选择层覆盖) |

关键过程事实:替代查询改变了检索池——Milwaukee 不再进入 CV-2 判定集,新候选 Cleveland 经完整链判定 0.90 USABLE 并成为链终选;复用排除仅在验证层执行(确认全片无占用),未干预链内选择。

## 3. 合并 Top-10 状态(18.1 六处 SWAP + 18.2 一处 SWAP)

| 门槛 | 要求 | 实测 | 结果 |
|---|---|---|---|
| 恢复 reuse 拦截拍 | ≥1/4 | **1/1**(S24-B01) | ✅ |
| 严格优于 | ≥7/10 | **7/10**(S12/S30/S02/S13/S34/S08/S24) | ✅ |
| HIGH | ≥3/10 | **7** | ✅ |
| 退化 | 0 | **0** | ✅ |
| correspondence | 不降 | 56/309.26s/60.86% 不变 | ✅ |
| 相邻同素材 | 0 | **0** | ✅ |
| multi_use | 不增 | **27→26**(Cleveland 单次占用;HCMC 退回单占用) | ✅ |
| provenance | 完整 | stage18_2_results.json 全量 trace(pass1/gate/cv2/final) | ✅ |

未渲染(本阶段授权不含渲染;7 处 SWAP 留档)。

## 4. 失败归类(Intent / Retrieval / Reuse Policy)

- **Reuse Policy 失败:1 → 已解决 1**(S24-B01,替代查询即恢复);
- **Retrieval 失败:3,均不在本阶段授权范围(非 reuse 触发),维持 18.1 结论**:S33-B02(查询回收同质候选+真证据被质量链拒绝)、S29-B02(主体命中动作错位)、S16-B01(查询空间塌缩零新候选);
- **Intent 失败:0**(累计 7/7 新合格候选全部严格优于原素材且 relevance HIGH)。

## 5. 结论

替代查询机制有效:同主体、同证据类型、不同具体素材的单主体查询,一次即恢复被复用规则拦截的高质量替换,且不触碰任何冻结环节、不放宽任何约束。Top-10 在当前约束组合下的严格改善达到 7/10,HIGH 7,退化 0,复用不增,correspondence 不变。剩余 3 拍属检索覆盖问题(同源查询空间),按验收条款 9 的边界原则:本轮不做超出授权的搜索深度扩展。

```
STAGE18.2 = PASS · STOP
恢复 1/1(S24-B01 Cleveland 0.90 USABLE / HIGH,全片零占用) · 合并严格优于 7/10 · HIGH 7 · 退化 0 · correspondence 不变 · 相邻同素材 0 · multi_use 27→26 · provenance 完整 · 未渲染
Intent 失败 0 / Reuse Policy 失败已解决 1/1 / Retrieval 失败 3(范围外,维持 18.1 归因)
STOP——等待下一步授权
```
