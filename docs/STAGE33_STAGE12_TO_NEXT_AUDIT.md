# Stage 33 Stage 12 → 下一阶段:终局纯审计(零代码 · 零 API · 零实验)

> 审计范围:12.11–12.25 全部已完成阶段。目的:固化生产能力与边界,给出唯一核心问题与下一阶段建议。
> **`AUDIT = PASS · STOP`**

## 1. Stage 12 全部最终生产能力与冻结边界

### 1.1 生产链(冻结模块,本次全程未动)

| 层 | 模块 | 状态 |
|---|---|---|
| 分拍/意图 | beat_segmentation / visual_intent / intent_stability | 冻结(12.10 状态) |
| 查询 | beat_retrieval.generate_query_tiers(T1/T2/T3 词表) | 冻结(T3 线已关闭) |
| 检索 | retrieval_v15.search_with_media_preference | 冻结 |
| 排序 | **pool_precision.rerank**(precise +2.0 / relaxed +1.0 / counterpart +1.0 / 类型惩罚) | **冻结,零改动** |
| 筛选 | candidate_quality_gate(head-6 切片) | 冻结(prompt/阈值/Gold/sanitizer) |
| 排序/一致性 | V1 semantic_match_score → CV-2 vision_call | 冻结(Top-3 定稿) |
| 手动入口 | asset_render_resolver.resolve_renderable(本地素材指定) | **保留未动** |
| 下游 | Composition / Motion / Renderer | 冻结 |
| **源** | pexels_source.py(12.23 新增,Pexels 照片;key 外读) | 生产可用 |
| **切片** | source_quota.py(12.24 新增,纯切片构造) | 生产可用 |
| **流程** | two_pass_material.py(12.25 新增,两遍制 + VerdictCache 持久化) | **Production Default** |

### 1.2 Production Default(已标记:`output/stage33/production_defaults.json`)

1. **两遍制**:第一遍 = 现行冻结管线;
2. **仅 EMPTY beat 进入第二遍**(ok 拍构造性不重跑 → 素材零回归);
3. 第二遍切片 = Commons 前 4 席(冻结序)+ **非 Commons 最多 2 席**;
4. **Pexels 优先**;
5. 所有候选(含 Pexels)仍经 **Gate → V1 → CV-2**,quota 永不直接产生素材;
6. **VerdictCache 持久化**(`verdict_store.json`,前缀容错,运行内 fresh 零重复已验证)。

## 2. 数据现状:已验证 vs 未验证(严格区分)

### 2.1 已入账(生产真实状态)

- **33/90** 素材已 banked:12.11 基线 10 + 12.13(T1 修复)+10 + 12.16(Top-2)+6 + 12.18(Top-3)+4 + 12.20(Gate Top-12)+2 + 12.23(S08-B03 副产物)+1;
- EMPTY = **57/90**(12.21 归类:gate_rejected_all 31 + cv2_not_usable 27,其中 S08-B03 于 12.23 翻出 → 26)。*(注:任务书"58"为口径笔误,按 33 已入账应为 57)*

### 2.2 推演结果(验证池证据,未入账)

- **38/90 为 12 拍验证池推演**:12.24 q2 在 12 空拍上 5 翻转(12.25 生产模块 12/12 复现),**尚未对全量空拍执行生产跑,5 个增益未 banked**;
- 12.23 覆盖臂:7/12 空拍存在直判 USABLE 的 Pexels 素材(含 hook 域)——上界证据,非入账。

### 2.3 尚未验证(下一阶段空间)

- **45 个空拍**(57 − 12)从未接触两遍制 + quota 流程;
- 12.23 覆盖臂可用率(58%)仅测于 12 拍,外推全量无依据;
- 成片级贡献:新增素材从未走完整 Storyboard→Renderer 对比验证(12.11 的成片验证早于全部新增素材);
- 生产默认在**全规模**下的成本曲线(gate/CV-2/Pexels API 用量)只有 12 拍样本。

## 3. 已关闭路线(不建议重新打开)

| 路线 | 关闭于 | 证据 |
|---|---|---|
| T3 对应物查询扩容 | 12.22 | 0/51 曝光,376 候选 63% DOC;12.23 证实堵点在排序非查询 |
| NASA 第二源 | 12.14 | SOURCE_NOT_USEFUL(无可用候选) |
| Gate Top-12 默认化 | 12.20 | 98 gate 调用/素材,增益递减;Top-3 后再诊断无新增益 |
| CV-2 深度 >Top-3 | 12.18 | Top-3 边际收益 2.0/素材,再深不经济 |
| Query/Gate/V1/CV-2 参数微调 | Final Audit / 12.21 | 全部管内杠杆测尽,瓶颈结构性 |
| **单遍制 quota** | 12.24 | 金丝雀实证:S23-B02 获胜者挤出至第 11 位,不可接受 |
| pool_precision 权重直接修改 | 12.23→12.24 决策 | 由独立 quota 模块方案替代(已完成),不再回头 |
| Pixabay / 未授权新源 | 授权约束 | 用户明确排除 |
| 冻结组件任何改动 | 全程 | 唯一授权新增均为独立旁路模块 |

## 4. 下一阶段唯一核心问题

**两遍制 + 2 席 Production Default 在全量 57 个空拍上的真实产能,及其对最终成片的实际贡献。**

- 为什么是它:Stage 12 的全部证据停在 12 拍样本(38/90 为推演)与素材清单层面;45 个空拍未接触新流程,成片贡献为零证据。继续调 Query/Gate/V1/CV-2/Quota 均属优化已冻结层,且 Stage 12 已证明其边际收益枯竭;
- 为什么不是别的:覆盖问题已被 Pexels+quota 路线解决(结构性瓶颈闭环),剩余唯一未知量是**规模化产出与端到端价值**,这正是"生产能力"与"已验证生产能力"之间最后的缺口。

**最小验证实验定义(下一阶段授权时执行,当前不做)**:
1. 全量 57 空拍生产级两遍制跑(verdict store 全程持久化,记录逐拍成本与释放率;预期上限 ≈38–45/90);
2. 成片 A/B:同一 90 拍脚本,基线(33 素材)vs 新增(两遍制释放集),走完整 Storyboard→Renderer 各出一版,量化新增素材在成片中的实际占用与叙事贡献;
3. 金丝雀照常(两遍制构造性零回归 + 干跑留痕)。

## 5. 结论

```
AUDIT = PASS · STOP
Stage 12 终态:33/90 入账 · 两遍制+2席 Production Default · 8 条路线已关闭且不重开
下一阶段建议:全量空拍生产跑 + 成片 A/B(唯一核心问题:规模化产能与成片贡献)
冻结边界:Query/Gate/V1/CV-2/pool_precision/Composition/Motion/Renderer 全部不再触碰
```
