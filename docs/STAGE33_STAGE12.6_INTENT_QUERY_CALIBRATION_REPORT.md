# Stage 12.6：Visual Intent / Query Reality Calibration

> 状态:**`STAGE12.6 = PASS`**
> 冻结边界:retrieval_v15 / V1 / Top-5 / CV-2 / Gate 核心逻辑 / sanitizer / asset_cache / composition / motion / subtitle / renderer **全部零改动**(时间戳核验:本轮仅 visual_intent.py 与 query_generator.py 于 22:44 变更)。
> **STOP —— 不进入 Beat / Storyboard / Stage 13。**

---

## 1. 修改内容(prompt 级校准,schema/字段零变更,消费者零影响)

**visual_intent.py(+7 行提示)**:
- 画面必须是**真实世界可拍摄**场景,禁止 CGI/概念图/抽象数据流/全息意象;
- 未来/近未来 → **当下最接近的真实对应物**(2035 智能城市→当代天际线/交通控制中心;人机协作→真实工厂协作机器人工位);
- 结构固定:主体 + 核心关系/动作 + 场景;保留语义锚点不泛化失真;
- 历史段优先真实历史照片或原始档案文献。

**query_generator.py(+8 行提示)**:
- 查询以**可见名词**为核心;禁止虚构事件性短语(如 "robot grasping apple fail");
- 概念化→真实对应:"data streams reorganizing future city" → "smart city aerial"/"digital city";人机协作 → "human robot collaboration"/"industrial robot human";
- **不得泛化到失真**:"future city" ≠ "city";历史主题直接命名主体("dartmouth college campus")。

未新增 helper(无关键词黑名单、无硬规则)。

## 2. 12.5 vs 12.6 对比(同 6-shot + 5 探针,全链路)

| 指标 | 12.5(run4) | 12.6 |
|---|---|---|
| 池 DOC / IMG | 56 / 14 | 24 / **63** |
| Gate KEEP | 0 | **2**(6-shot)+ 探针 15 |
| V1 Top-1 | —(空) | S06 **IMG** |
| CV-2 Top-1 | shots 无 | S06 IMG **0.55**;探针 **DOC 0.8** / IMG 0.45 |
| honest-empty | 0 | 0(6+3 gate_rejected_all 全部核验为 gate 正确拒绝;0 检索失败) |
| **query drift** | 存在 | **11/11 管线消除** |
| 语义退化 | — | **无**("future city" 未塌缩为 "city",锚点全保留) |

## 3. 关键意图结果

| 探针 | queries(校准后) | 结果 |
|---|---|---|
| **Dartmouth/DOC** | '1956 Dartmouth proposal document'… | **链路终点 = 真实 Dartmouth 提案 PDF,CV-2 fit 0.8(全项目最高),V1 64.6** |
| **industrial revolution** | 'steam engine factory interior'… | 1902 蒸汽机车间照片,CV-2 0.45,池 18 IMG kept 6 |
| **smart city aerial** | 'city night aerial highway'… | 池 24 IMG kept 8,V1 top 65.0(CV-2 正确过滤 0.1 NOT_USABLE) |
| future city | 'traffic control center operators screens'… | 池 8 IMG;gate 正确拒(航母雷达≠城市控制中心) |
| robot human collaboration | 'collaborative robot assembly line'… | 池 6 IMG;Commons 相关性噪声(导弹'装配'文档),gate 正确拒 |

6-shot:S06 全链 IMG 贯通(池 24 IMG → kept 2 → V1 IMG → CV-2 0.55 Top-1);S01/S03/S04/S05 池命中但 gate 正确拒绝切题噪声。

## 4. 验收对照

✅ **query drift 明显减少**(11/11 消除,无任何虚构事件短语) · ✅ **Intent 更现实可检索**(0 CGI/数据流意象;未来→当下对应物) · ✅ **关键意图获得更合理素材**(Dartmouth PDF 0.8 / 蒸汽机车间 / 城市夜景 8 张) · ✅ **无明显无关泛化**(池主题收紧;每个 gate 拒绝人工核验为正确) · ✅ **历史 DOC 路径正常**(且选出语义完全正确的文档) · ✅ **12.5 冻结链路零回归**

**Honest-empty 分类**(按要求):gate_rejected_all ×9(逐条核验=正确拒绝:V-1 导弹≠协作机器人、航母雷达≠城市控制中心、废墟工人≠办公室职员);ok ×3;检索失败 ×0(节流保持);query 残留问题 ×1(S02 intent 把比喻"AI界面无法响应"过度字面化 → niche 查询 → DOC 池,已标记)。

## 5. 诚实发现(需新授权,本轮未动)

1. **管线瓶颈已转移**:intent/query 已修好;剩余摩擦 = Commons 全文检索相关性噪声(中等具体度短语命中切题但错误的匹配,如 'assembly line'→导弹文档)× gate 只判池前 10 条。下一阶段可选杠杆:加深 gate 判定深度 / 检索侧短语 A-B——均超出 12.6 范围;
2. S02 残留过度字面化(见上);
3. V1↔CV-2 分歧是设计行为(CV-2 是最终过滤器);
4. LLM 非确定性跨运行仍在(校准收窄但不能消除)。

## 6. 交付物

- `output/stage33/stage12_6_intent_query_calibration/calibration_test.json`(11 管线全 trace)
- `output/stage33/stage12_6_intent_query_calibration/final_result.json`
- `output/stage33/stage12_6_intent_query_calibration/run_calibration_test.py` + asset_cache
- 本报告:`docs/STAGE33_STAGE12.6_INTENT_QUERY_CALIBRATION_REPORT.md`

```
STAGE12.6 = PASS
  query drift 11/11 消除 · Intent 现实化 · Dartmouth PDF CV-2=0.8 · 语义零退化
  冻结链路零回归(仅 2 个允许文件变更)
STOP —— 等待授权
```
