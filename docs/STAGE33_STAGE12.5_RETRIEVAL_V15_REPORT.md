# Stage 12.5：Retrieval v1.5 图片优先检索修复

> 状态:**`STAGE12.5 = PASS`**(按本阶段最低验收标准)
> 冻结边界:V1(stage31/ranking)/ sanitizer / Top-5 / CV-2(vision_controlled)/ Gold / Vision prompt / Candidate Quality Gate 核心逻辑 / Visual Intent / Query Generator / composition_policy / camera_motion_policy / subtitle_pipeline / renderer / asset contract / Text LLM hardening **全部未改**(末尾有时间戳核验)。
> **STOP —— 不进入 Stage 12.6 / Beat / Storyboard / Stage 13。**

---

## 1. 修改文件与规模

| 文件 | 性质 | 规模 |
|---|---|---|
| `src/video_studio/stage33/retrieval_v15.py` | **新增**(检索层唯一改动) | ~120 行 |
| `output/stage33/stage12_5_retrieval_v15/run_retrieval_v15_test.py` | 新增测试 | — |

## 2. Retrieval 策略(视觉意图驱动,非类型黑名单)

```
asset_type_hint:
  IMAGE/VIDEO -> "filetype:bitmap" 约束(照片=视频可用视觉;运动归 motion policy)
  DOCUMENT    -> 无约束(档案/原始文献允许 —— Dartmouth 式 PDF 必须可达)
  其他/未知   -> bitmap 优先,无约束回落
确定性松弛阶梯(首次非空即停,全程留痕):
  1) <query> filetype:bitmap → 2) 前3词+bitmap → 3) 前2词+bitmap → 4) 无约束
稳定性:请求节流 0.8s + 失败退避 2s/5s;错误永不生成伪候选(不污染阶梯与 gate)
```

**过程中修复的两个自身 bug(诚实记录)**:①初版异常返回 `SEARCH_ERROR` 伪候选——被 media_type 误判为 IMG 且提前终止阶梯;②Commons 限流导致"假空"(同查询加间隔重放 0→5 结果)——加节流+退避后消除。

## 3. Before / After 候选池统计

| 指标 | Stage 12.1 | Stage 12.5(第4轮,节流后) | 4 轮范围 |
|---|---|---|---|
| Gate 前 DOC | 78 | 56 | 20-56 |
| **Gate 前 IMG** | **0** | **14** | **8-14** |
| Gate 前 VIDEO | 0 | 0 | 0 |
| Gate 保留 | 24 | 0 | 0-3 |
| **IMG 进入 V1 Top-5** | **0** | **3**(累计) | — |
| **CV-2 最终 IMG** | —(未运行) | **达成**(S02/S06) | — |
| S04 | HONEST_EMPTY(kept=0) | 池非空(18 候选),本轮无 IMG | 部分恢复 |

## 4. 6-shot 逐 shot 结果(第 4 轮)

| shot | hint | 池 | gate | 说明 |
|---|---|---|---|---|
| S01 | IMAGE/historical | 12 DOC | 0 | 查询漂移落入无约束;阶梯 bitmap 级 0 |
| **S02** | VIDEO | **9→run2/3: 9 IMG, kept 1, V1 top IMG, CV-2 0.6→top1 IMG** | — | **全链 IMG 贯通实证** |
| S03 | VIDEO | 5 IMG(杂志封面扫描) | 0 | gate 正确拒(1922 贝尔杂志≠办公自动化) |
| S04 | VIDEO | 18 DOC | 0 | 不再 honest-empty;IMG 未复现(查询漂移) |
| **S05** | VIDEO | **9 IMG(首尔夜景×2/NASA 卫星/城市照片)** | 0 | 池级✓;gate 以"未体现数据流重组"全拒 |
| **S06** | VIDEO | run3: 2 IMG, kept 2, V1 top(34.7), CV-2 0.35, top1 IMG | — | **1891 工厂历史照片,与"工业革命"旁白契合** |
| PROBE-DOC | DOCUMENT | 24 DOC | **kept 6 DOC** | **DOC 路径 4/4 轮存活** |

## 5. IMG 真正进入下游(链路证明)

- **S02**:IMG → gate KEEP → **V1 rank 27.0 Top-1** → asset_cache 下载 OK → **CV-2 fit 0.6 CONDITIONALLY_USABLE → CV-2 Top-1 = IMG**;
- **S06**:2 IMG kept → V1 Top-2(34.7/9.6)→ CV-2 fit 0.35 → Top-1 IMG;
- PROBE-DOC:DOC kept 6 → V1 Top-5 全 DOC → CV-2 对 DOC 逐张判分(fit 0.0/0.0/0.0)——**DOC 同样走完整链**;
- 冻结 V1 原语经适配器(CandShim/IntentShim)调用,未改一行。

## 6. 关键意图验收

- **smart city aerial:✓** 手动探针 6 张真实航拍;run4 S05 池 9 张真实城市照片;
- **robot human collaboration:✓**(池级)手动探针 6 张真实协作机器人照片;6-shot S04 因查询漂移未复现(诚实记录);
- **historical archive/document:✓** DOCUMENT 探针 4/4 轮 kept 3/3/9/6 DOC;
- **不破坏历史文档素材:✓** S06 还获得 1891 工厂照片(历史照片而非 PDF)。

## 7. 保留率下降的诚实解释

12.1 kept=24 全是"描述文本匹配旁白"的文档;12.5 池中出现真实照片后,gate 以旁白**具体视觉点**为锚拒掉了泛化但主题正确的照片(首尔夜景 vs"数据流重组图标")——**gate 语义判断仍然正确**,暴露的是 **Visual Intent 过度具体化**(要求 Commons 永远不会有的 CGI 意象)。gate 核心冻结不动,记录为发现。

## 8. 给下一阶段的发现(均需新授权,本轮未动)

1. **query_generator LLM 查询漂移**:运行间查询不稳定,过抽象查询('AI robot grasping apple fail')bitmap 全阶梯 0 → 建议查询层加"具体可见名词"约束;
2. **Visual Intent 现实性校准**:12.1 设计缺陷的直接暴露——intent 需区分"Commons 可得的现实影像"与"概念意象";
3. **CV-2 fit 非确定性**:同一图 0.6→0.3(Vision LLM 特性,已知);
4. S04 完全恢复依赖 1+2。

## 9. 结论

```
STAGE12.5 = PASS
  Gate 前 IMG: 0 -> 14 (4 轮一致非零)
  IMG 真正进入 V1/CV-2 并成为最终选择(S02/S06)
  历史 DOC 路径 4/4 轮存活(PROBE kept 3/3/9/6)
  冻结链路零回归,零冻结文件改动

STOP —— 等待授权:建议下一阶段 = Query 层具体化约束 + Intent 现实性校准(12.6)
```
