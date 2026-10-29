# Stage 3.3 Capability Validation-1：本地素材视觉理解 PoC（方案 / 预检）

> 状态：**仅方案与预检，不实现**。等待授权后实施。
> 定位：`3.3 V3-MVP → FAILURE（抖动已修、绿幕感未消）→ CAPABILITY VALIDATION-1`
> 依据：`docs/STAGE33_V3_GREENSCREEN_FAILURE_ANALYSIS.md`（已裁决：素材理解缺失 × 素材供给不足，第一优先级=素材视觉理解）。

---

## 1. CV-1 要回答的唯一问题

> **视觉理解加入以后，系统能否明显区分"语义相关但视觉不适合"的素材？**

判断方式：对同一批候选做 `文本检索 → semantic ranking`（现状 A）与 `文本检索 → visual understanding → visual suitability reranking`（B）的 A/B，检验 **已知人工负例能否被排到候选集后半段、已知正例是否被保留**。不生成成片。

## 2. 成功标准（可判 FAIL 的硬指标）

| 指标 | 标准 |
|---|---|
| **R1 负例下沉率** | ≥80% 的已知人工负例（(beat, material) 对）在 rerank 后位于候选集**后半段**（负例共 ≥10 个） |
| **R2 正例保留率** | ≥80% 的已知人工正例在 rerank 后仍位于候选集**前半段** |
| R3 特征可靠性 | 逐属性报告（模型标签 vs 人工标签一致性），不设硬线但必须如实公开 |
| 判定 | R1 且 R2 达标 → 授权进入素材理解层建设；R1 或 R2 不达标 → **STOP，不继续加规则/加模型堆叠，重新判断素材供给/检索架构** |

"模型能生成描述"**不是**成功标准。

## 3. 模型选择（本地、小、CPU 可行，不引入 VLM）

| 方案 | 说明 | 优先级 |
|---|---|---|
| **A. CLIP 图像编码器 + 零样本属性分类 + 嵌入 rerank** | `openai/clip-vit-base-patch32`（~350MB，hf-mirror 获取，沿用重试下载模式）。一张图 ≈2–5s CPU（Radeon 780M iGPU 可选 Vulkan 加速，先 CPU）。零样本分类提示词覆盖 11 个视觉类型 + subject/scene/style/text_presence 等属性；图像嵌入用于 narration↔image 相似度与"不适配特征"（油画/剧照风格惩罚） | **首选** |
| B. 小型 VLM（Qwen2.5-VL-3B） | 能写 caption 但 CPU 每图分钟级、内存 ~6GB+，超出"稳定特征提取"需求 | 备选（仅当 A 的属性分类不可靠时评估） |
| C. 传统 CV 特征（直方图/边缘/人脸检测启发式） | 无需模型，但"油画 vs 照片/剧照 vs 实拍"区分能力差 | 对照基线（A 必须显著优于 C 才有意义） |

**原则**：目标不是漂亮 caption，而是稳定的 `visual_type / subject / scene / shot_scale / composition / dominant_color / text_presence / people_count / orientation / visual_style / confidence`。若纯 encoder + embedding/reranker 足够，就不引入 VLM。

## 4. Benchmark 数据（Coral 真实素材，不修改任何 SEALED 素材）

### 4.1 候选集（≥20，全部来自 3.1.4 白名单真实候选，保存 SHA）

| group | candidates |
|---|---|
| 人物/剧照类 | M-S03-162（1957 电影剧照）、M-S19-954 / M-S19-953（沙滩孩子） |
| 油画/绘画类 | M-S12-607（RMG 渔民油画） |
| 海洋/珊瑚类 | M-S04-224 / M-S04-222 / M-S04-221、M-S05-276 / M-S05-251、M-S08-407、M-S09-456、M-S17-825 |
| 动物类 | M-S14-687（小丑鱼） |
| 图表/科学画面类 | M-S06-303 / M-S06-307、M-S07-358 / M-S07-357 |
| 实验/修复类 | M-S11-552（潜水员修复） |
| 城市类 | M-S20-1041（城市夜景） |
| 视频类 | M-S06-323（海温动画）、M-S20-1034（城市延时） |
| 干扰对照 | 由 3.1.4 历史"语义负例"补充（如 S01 的 Didyma 神庙候选等，仅作对照、不入白名单） |

本地缺失的候选在 CV-1 工作区下载（`stage33/capability_validation/` 内，不触碰 SEALED 素材目录）。

### 4.2 人工标签（留档，标注人=人工裁决记录 + 本轮人工确认）

- **人工正例（≥10）**：M-S04-224/222/221、M-S05-276/251、M-S06-303/307、M-S07-358、M-S08-407、M-S09-456、M-S11-552、M-S14-687、M-S17-825（"语义相关且视觉上适合其 beat"）；
- **人工负例（≥10，以 (beat, material) 对标注）**：
  1. `S03 × M-S03-162`（珊瑚骨架 ← 电影剧照）【本轮裁决】
  2. `S12 × M-S12-607`（油画，执行方式不成立）【本轮裁决】
  3. `S19 × M-S19-954`（水下世界 ← 沙滩孩子，半句匹配）【本轮裁决】
  4. `S01 × M-S03-162`（褪色的城市 ← 电影剧照）
  5. `S06 × M-S19-954`（温度发烧 ← 孩子照片）
  6. `S08 × M-S12-607`（1% vs 25% ← 油画）
  7. `S03 × M-S20-1041`（珊瑚骨架 ← 城市夜景）
  8. `S14 × M-S06-303`（小丑鱼 ← 温度图表）
  9. `S19 × M-S17-825`（潜水面镜 ← 彩色珊瑚）
  10. `S17 × M-S19-953`（长回颜色 ← 沙滩孩子）
  （1–3 为人工裁决负例，4–10 为构造对照，最终以人工确认留档）

每素材记录：material_id、SHA256、原始 URL、semantic_match、内容类型、人工视觉类型标签、人工"正/负/中性"标签、beat 语境。

## 5. A/B 实验协议

```
A（baseline）：候选按 3.1.4 semantic_match 排序（当前系统行为）
B（visual rerank）：
  per-beat visual_suitability = 0.5×semantic_norm
      + 0.25×CLIP_similarity(narration_text, image)
      + 0.25×type/style_fit(beat 期望视觉类型 vs 模型分类；油画/剧照在纪实风格 beat 上重罚；
         图表 beat 上 text_presence 加分、人物类候选重罚；人物 beat 上 people_count 加分…)
  final_score = w×semantic + (1−w)×visual（w 扫 0.3/0.5/0.7 报告三档）
输出每候选：candidate_id / semantic_score / visual_features / visual_suitability_score /
final_score / reason / human_label；并给出排序变化对照表。
```

**关键检验点**：S03/S12/S19 三个裁决负例在 B 排序中是否下沉（R1）；珊瑚/图表类正例是否保持前列（R2）。

## 6. 交付物与文件布局（独立于 V3 pipeline，零污染）

```
src/video_studio/stage33/capability_validation/
  __init__.py           # CV-1 版本标记（独立命名空间，不 import 3.3 运行链）
  fetch_model.py        # hf-mirror 重试下载 CLIP ViT-B-32（沿用 _fetch_* 模式）
  extract_features.py   # 视觉类型/主体/场景/风格/文字存在性/主色 零样本分类 + 嵌入
  rerank.py             # A/B 排序与评分
  benchmark.py          # 组装候选集+标签+报告
data/cv1_benchmark.json # 候选 SHA + 人工标签（留档）
output/cv1_report.json/md
docs/STAGE33_CAPABILITY_VALIDATION_1_REPORT.md  # 实施后报告
```

不修改：3.3 运行链（director/validator/realizer/executor）、3.2b、3.1.4、2.x、P1/V3 基线、任何 Gate 阈值。

## 7. 实施顺序与预检清单（获授权后）

1. 网络预检：hf-mirror 可达性、`openai/clip-vit-base-patch32` 可下载（HEAD 检查）；失败 → STOP 上报（不换云 API）；
2. 模型落地 + 冒烟：`models/clip/`（~350MB），CPU 单图推理实测（时间/RAM 记录）；
3. 候选集本地化 + SHA + 标签留档（人工负例 1–3 直接采用本轮裁决，4–10 待人工确认）；
4. 特征提取 + 属性可靠性表（模型标签 vs 人工标签，逐属性准确率）；
5. A/B rerank（w=0.3/0.5/0.7）+ R1/R2 判定；
6. 报告（§9 九问逐项回答）+ STOP 等待裁决。

## 8. 报告必须回答的 9 问

1. 当前本地模型实际能看懂什么（属性级准确率实测）；
2. 哪些视觉特征可靠（准确率 ≥85% 列）；
3. 哪些不可靠（<70% 列，如实）；
4. S03/S12/S19 是否能被识别（负例的 visual_type/style 判定 + 排序位次）；
5. visual reranking 相比 semantic-only 提升多少（R1/R2 + 排序变化表）；
6. 正例误杀率（1−R2）；
7. CPU/RAM/推理时间（逐图实测）；
8. 是否值得继续（对照 §2 判定线）；
9. 下一步是视觉理解还是素材供给（基于证据二选一）。

## 9. 非目标（本轮及 CV-1 全部禁止）

不重写 3.3 Director / Visual Statement；不新增视觉模板；不进 P2/P5；不做正式盲测；不接云端 API；不扩素材库；不改 3.2b/3.1.4/2.x；不改 P1/V3 基线；不重新生成 Coral V3；**不执行正式成片**。

## 10. 停止线

- 本文件 = 方案/预检交付；**待授权后才实施 CV-1**；
- CV-1 实施后：R1∧R2 达标 → 授权进入"素材理解层"建设决策；任一不达标 → STOP，不允许继续加规则/加模型堆叠解决。
- **STOP。**
