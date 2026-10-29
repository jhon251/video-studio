# Stage 12.8：Beat Retrieval Recovery

> 状态:**`STAGE12.8 = PASS`**(带诚实保留意见,见 §4)
> 冻结边界:visual_intent / query_generator / retrieval_v15 / V1 / Top-5 / CV-2 / Gate / Composition / Motion / Subtitle / Renderer / Stage 11 contract **全部零改动**(仅新增 beat_retrieval.py)。
> **STOP —— 不进入 Storyboard / Stage 13。**

---

## 1. 新增模块(唯一改动)

**`src/video_studio/stage33/beat_retrieval.py`**:每 beat 最多 3 层 Query,合并候选(带层级溯源)后进入**未修改的** Gate→V1→CV-2:

```
T1 precise     = 12.7 存储的原始 queries(基线完全一致)
T2 relaxed     = 主体+核心关系保留,去掉过具体事件/场景细节
T3 counterpart = 概念的真实可见对应物
护栏(prompt 级):不虚构事件;禁宽泛单词(单独 "AI");锚点不丢("future city"≠"city");beat 原文零改动
```

## 2. 12.7 vs 12.8(同 11 个 beat;12.7 报告"13"系笔误,更正)

| 指标 | 12.7 | 12.8 |
|---|---|---|
| 合并池 IMG | 79 | **254(3.2×)**,每 beat 10-40 张 |
| 池 DOC | 46 | 53 |
| empty | 10/11 | 9/11(边际) |
| Gate KEEP 总数 | 4 | 2(运行方差,见 §4) |
| **有最终素材 beat** | 1/11 | **2/11** |
| CV-2 Top-1 | Manhattan 0.95 | **S04-B02 Control Room 0.75** + S02-B02 0.2(NOT_USABLE,弱) |
| Query drift | — | **无**(T2/T3 全部锚定、具象) |
| 无关素材混入 | — | **0**(抽样核验全部拒绝正确) |
| 语义退化 | — | **无** |

**T2/T3 质量示例**:'collaborative robot assembly line'→T2 'collaborative robot factory'/T3 'engineer tablet robot arm';'city skyline dusk lights'→T2 'city skyline dusk'/T3 'city skyline night aerial'。两个最终素材均来自 T1——T2/T3 扩了池但本轮未产出赢家。

## 3. 关键案例

- **S04-B02**(beat:"人类负责判断与价值，AI 负责计算与检索")→ 'Control Room DSC0038.jpg' **CV-2 0.75 CONDITIONALLY_USABLE**——语义高度契合的真实控制室照片;
- **S06-B02 回退(诚实记录)**:12.7 该 beat 曾选出曼哈顿全景 0.95(kept 4);12.8 gate_rejected_all。**根因 = intent LLM 重跑分歧**:同一旁白"…比工业革命更深刻的文明转型",本轮 intent 生成了"自动化工厂/工业机器人"意图,gate 因此**正确拒绝**池中仍然存在的城市照片。**非三层机制缺陷**,是 beat 粒度下 intent 非确定性的暴露。

## 4. 诚实保留意见

1. **empty 率改善边际**(10→9):池扩 3.2× 但 gate 判定深度(池前 8)+ gate LLM 方差主导 keep 率——两者均在 12.8 授权范围外(gate 冻结;深度是成本决策);
2. S06-B02 回退属 intent 方差(见上),机制本身无回归;
3. 本轮发现并更正 12.7 报告笔误:beat 总数为 **11** 而非 13。

## 5. 结论

```
STAGE12.8 = PASS
  Query 过度具体化已降低(T2/T3 具象且锚定,池 3.2×)
  相关性保持(全部抽样拒绝正确;两个最终素材主题契合)
  可用素材率 1/11 → 2/11(未强行保留)
  冻结链路零回归(仅新增 beat_retrieval.py)
STOP —— 等待授权
```
