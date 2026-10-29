# Stage 18 最终收口审计(只读)

> 审计性质:只读。未修改任何生产代码、Prompt、权重、阈值、Gate、V1、CV2、Retrieval、Reuse Policy。所有数字由 `stage18_experiment/closure_audit.py` 从落盘证据件程序化复核,非人工转述。

## 1. 证据链汇总(Stage 18 → 18.1 → 18.2)

| 阶段 | 授权变量 | 交付件 | 结论 |
|---|---|---|---|
| 18(intent 解耦,零新检索) | 仅重选现有池 | `stage18_experiment.json`(intent sha `b9b3460c3775ed94`) | FAIL 1/10:池由旧 intent 抓取,结构上不可测 |
| 18.1(单主体新 Query 重检索) | 仅检索 Query/Intent | `stage18_1_results.json` + `verdict_store_181.json` + `stage18_1_decision.json` | FAIL 6/10(差 1 拍):新合格候选 6/6 全部严格优于且 HIGH;S24-B01 被相邻复用规则拦截 |
| 18.2(复用触发替代检索) | 仅 reuse-blocked 拍的替代 Query | `stage18_2_results.json` + `verdict_store_182.json` + `stage18_2_decision.json` | PASS:恢复 1/1,合并 7/10 |

每拍候选完整经过冻结生产链 `retrieval → pool_precision → Gate head-6 → V1 → CV-2 top-3 → eligibility`(原样调用 `two_pass_material.acquire_beat_material`,pass-2 pexels 配额片按冻结条件触发)。

## 2. Intent Decoupling 假设:已验证 ✅

- **判定依据**:解耦后的单主体 Visual Focus 驱动新 Query 后,凡检索到**新的合格候选**,7/7 全部严格优于原素材(fit Δ ≥ +0.05)且 semantic_relevance 全 HIGH——命中率 100%,无一例外;
- **对照**:旧复合 intent 下同批拍的最高合格 fit 仅 0.35–0.70,且 9/10 带 GENERIC/MISMATCH 标记;
- **未证伪项**:无。三个阶段中没有任何一拍因 Intent 本身失败(18.1 归因 Intent 失败 = 0)。

## 3. 最终合并验收数字(程序化复核结果)

| 项 | 要求 | 复核值 | 结果 |
|---|---|---|---|
| 严格优于 | ≥7/10 | **7/10**(Δ 全部 ≥ +0.05) | ✅ |
| HIGH | ≥3/10 | **7/7 SWAP 全 HIGH** | ✅ |
| 退化 | 0 | **0**(无合格候选一律回退原素材) | ✅ |
| correspondence | 56/309.26s/60.86% 不降 | 复核 = **56 beats / 309.26s**;7 处 SWAP 全部落在对应集内(NONE outside),覆盖时长 47.13s;对应集本身不变 → 60.86% 不降 | ✅ |
| 相邻同素材 | 0 | **0** | ✅ |
| multi_use | 不增 | **30→26**(标题口径:基线 30 → 7 处 SWAP 后 26;18.2 步内 27→26);被换入素材无一多占用;Cleveland 恰 1 次;Milwaukee 保持 1 次(S23-B01) | ✅ |
| 冻结代码 | 零改动 | `src/` 最新 mtime(11:28)早于 18 线启动(19:45) | ✅ |

## 4. 7 处最终替换清单(留档,未渲染)

| Beat | 旧(fit) | 新(fit / label / relevance) |
|---|---|---|
| S12-B02 | 0.35 | Westmoreland 纪实工人肖像(0.72 CU / HIGH) |
| S30-B01 | 0.50 | Robot arm operates machine in factory(0.70 CU / HIGH) |
| S02-B01 | 0.60 | Zamboanga 十字路口实景(0.72 CU / HIGH) |
| S13-B02 | 0.60 | Garner Complex 社区会议(0.90 USABLE / HIGH) |
| S34-B01 | 0.70 | 实验服女子与机械臂协作(0.75 CU / HIGH) |
| S08-B03 | 0.60 | CERN 控制室多屏监控(0.95 USABLE / HIGH) |
| S24-B01 | 0.55 | Cleveland 黎明天际线(0.90 USABLE / HIGH) |

保留原素材 3 拍:S33-B02(⚠️地缘敏感,真证据候选被质量链拒绝)、S29-B02、S16-B01。当前成片(`render_162/final_long.mp4`,508.29s)未被替换;上述替换为授权范围内的实验留档。

## 5. 已知边界(3 个 Retrieval 失败,关闭不再优化)

1. **S33-B02**:单主体查询回收同质候选;真证据候选(Gaza)被冻结质量链拒绝——同源查询空间薄 + 内容敏感双重约束;
2. **S29-B02**:主体命中但动作错位(交接仪式 ≠ 课堂使用)——单主体查询的动作精度不足;
3. **S16-B01**:新查询空间塌缩至与旧查询相同候选集,零新候选。

三类失败最终归类:**Intent 失败 0 / Reuse Policy 失败 1(已由 18.2 解决) / Retrieval 失败 3(记为已知边界)**。

## 6. 结论

Stage 18 实验线三个阶段累计验证:Visual Intent 解耦(单主体 Visual Focus + 单主体 Query)在冻结生产链下可稳定产出严格优于旧复合 intent 的素材选择;复用硬规则与质量门槛可并存且零退化;剩余提升空间仅受同源检索覆盖限制,不构成继续实验的理由。

**Stage 18 CLOSED / NO FURTHER EXPERIMENT REQUIRED**

```
STAGE18 CLOSED · 7/10 strict(+0.05 全达标) · 7 HIGH · 0 退化 · correspondence 56/309.26s/60.86% 不变 · 相邻同素材 0 · multi_use 30→26 · 冻结代码零改动 · Retrieval 边界 3 项归档 · Cleveland 替代检索解决唯一 reuse-blocked case
STOP——不进入 Stage 19
```
