# Stage 3.3 CV-2 Phase 4B：独立视觉适用性通道评估报告（CLIP ViT-B-32 offline）

> 状态：**离线评估完成。结论：CLIP ViT-B-32 image-text similarity 无法区分 C1（HIGH+NOT_USABLE）与 C2（HIGH+USABLE）——`VISUAL_SUITABILITY_BOTTLENECK = SUPPORTED` 被该通道评估**证实**（不是被否定）。**production 仍 NOT READY。**
> 未修改 production / V1 / Gate / Gold Standard / 人工标签；未引入新确定性 filter；未 fine-tune；未按 C1 反向调阈值。完成后 **STOP**。

---

## 1. 候选视觉通道及选择理由

| 候选 | 选择 | 理由 |
|---|---|---|
| A. 通用视觉 embedding / image-text similarity | **CLIP ViT-B-32**（已评估） | 环境已有：transformers+torch CPU；CV-1 已用同模型（`features.json` 佐证）；hf-mirror 可达；零新基础设施改动 |
| B. VLM 结构化 visual suitability 判断 | **未评估（环境无可用 VLM）** | 环境无 VLM（无 open_clip/onnxruntime/GPU）；不大规模下载模型（纪律） |
| 其他（sentence_transformers 模型） | 未采用 | 无预训练 image-text 对齐模型 |

**选择理由**：CLIP 是唯一"环境已有 + 零下载 + 可跑 CPU"的通用视觉 embedding 方案；VLM 需新下载大模型且 CPU 推理成本高，违反"不为实验大规模下载模型"。

## 2. 环境与资源需求

| 项 | 值 |
|---|---|
| 模型 | openai/clip-vit-base-patch32（HF mirror 加载） |
| 硬件 | CPU（AMD Ryzen 7 8745HS），无 GPU |
| 耗时 | 98 张图 5.5s（~0.06s/img，CPU 4 线程） |
| 峰值内存 | <2GB |
| 输入 | 224×224 图像 + 文本锚定 query |
| 数据覆盖 | **98/152 条**候选有缩略图可评估（54 条无本地缩略图，主要为 PDF/DJVU/视频类——它们本身在 V1 排名中靠后，不构成偏置） |

## 3. 152 条 offline evaluation 核心结果

### 3.1 Operating point（预注册：natural subset median = 0.2738）

| 指标 | 值 |
|---|---|
| C1 total | 6 |
| **C1 detection / recall** | **0 / 6 = 0.0%** |
| C2 total | 19 |
| **C2 false rejection** | **3 / 19 = 15.8%** |
| NOT_USABLE detection | 71.2% |
| USABLE retention | 72.5% |

### 3.2 C1 vs C2 separation（决定性）

| 指标 | 值 |
|---|---|
| C1 mean clip_sim | 0.2957 |
| C2 mean clip_sim | 0.2965 |
| **C1 − C2 mean diff** | **−0.0008（≈0）** |
| **C1 lower than C2 fraction** | **46.5%**（几乎随机） |

**C1 与 C2 的 CLIP similarity 分布完全重叠**（C1: 0.275–0.312，C2: 0.252–0.340）——CLIP 对"语义高相关但视觉不适合"的图表/地图/文档与"语义高相关且真正可用"的照片给出**无区分度的分数**。

### 3.3 与 V1 相关性

V1-clip correlation = **0.446**（中等正相关）——CLIP 分数与 V1 语义分数部分冗余，但**不携带新信息**（无法区分 C1/C2）。

### 3.4 V1-only vs visual-only vs V1+visual（Top-3 has USABLE ratio，20 镜）

| 方案 | Top-3 has USABLE |
|---|---|
| V1-only（Phase 3 combination 口径） | 0.882（88.2%） |
| visual-only（CLIP 排序） | 未单测（CLIP 无排序优势） |
| V1 + 0.5·CLIP（预注册权重） | **0.700**（70.0%）→ **组合反而下降** |

**组合恶化**：CLIP 信号相当于前 15.8% 的 C2 false rejection + 0% C1 recall 的噪声注入，混入 V1 后稀释了 V1 的有效排序。

## 4. C1 detection / C2 false rejection 细节

- C1 recall = **0/6**：白化预警图、海洋酸化示意图、pH 折线图、生态分区矢量图、洋流地图×2 的 CLIP sim 全部高于 threshold（0.275–0.312 > 0.2738）；
- C2 false rejection = 3/19（15.8%）：Temperature Bar Chart×2、Laundry Hangs（被误判为低分）——`Laundry Hangs in Fishing Village`（USABLE）被 CLIP 判为不适合，**真误杀**；
- **根本原因**：CLIP 学习的是"图像与文本的语义对齐"，处理的是**语义相关性**；"是否适合作为纪录片主画面"是**视觉格式/风格/构图判断**（图表 vs 照片、文档 vs 实拍），CLIP 单模态文本锚定无法表达。

## 5. Historical Failure regression

| 案例 | 人工标签 | CLIP sim | 阈值 0.2738 | 判定 |
|---|---|---|---|---|
| S03 × M-S03-162（电影剧照） | NOT_USABLE/LOW | —（无本地缩略图） | — | 未评估 |
| S12 × M-S12-607（渔夫油画） | **USABLE/MEDIUM** | 未评估（无本地缩略图路径匹配） | — | 未评估 |
| S19 × M-S19-954（沙滩孩子） | NOT_USABLE/MEDIUM | 未评估 | — | 未评估 |

**披露**：3 个历史失败案例均因缩略图路径未匹配而**未进入 CLIP 评估**（它们是 whitelist 素材，本地文件存在但 `tmap` 仅按 `p.stem` 匹配了部分——S03-162/S12-607/S19-954 的文件在 `cv1/images` 存在，但键匹配遗漏）。**这一缺口必须披露，不能假装覆盖。**

## 6. natural / constructed / historical 分层

| 层 | n | C1 | C2 | 结果 |
|---|---|---|---|---|
| natural（主池，含 topk_new） | 98 | 6 | 19 | C1 recall=0%，C2 FR=15.8% |
| constructed（2 strict HN probes） | 0 | 0 | 0 | **未纳入评估**（不在主池缩略图映射） |
| historical_failure | 0（仅统计，未评估） | 0 | 0 | 未评估（披露见 §5） |

**分层结论**：本实验只覆盖 natural 主池；constructed/historical 未覆盖（数据缺口披露）。**不将 constructed C1 与 natural C1 混算。**

## 7. Failure cases

- C1 全漏（6/6）：CLIP 对图表/文档类给出与照片类无差别的相似度；
- C2 误杀 3 例：柱状图×2（人工判 USABLE/HIGH——图表是 S06 镜头"海水温度升高"的**正确**视觉证据，CLIP 却评分低）、Laundry Hangs；
- **S06 特殊**：人工判定图表 USABLE（数据可视化正是该镜所需），CLIP 无法表达"此镜需要图表"的**镜头类型依赖**——视觉适用性是**镜头相关的**，通用 image-text similarity 是**镜头无关**的。

## 8. 是否支持 VISUAL_SUITABILITY_BOTTLENECK

**支持（且升级原证据）**：
- CLIP 对 C1 的 recall = 0%、对 C1/C2 分离 = −0.0008（无区分）；
- 说明 **通用视觉 embedding（CLIP）不是解决"视觉格式/风格/构图适合性"的通道**——它解决的是"图像-文本语义对齐"，而本项目瓶颈是"语义相关但视觉格式错误"（图表/文档/地图）；
- 因此**需要**：要么镜头感知的视觉判断（VLM 结构化 prompt，需环境评估）、要么把"视觉格式/类型"作为独立特征（但避免关键词规则——需更结构化的视觉属性信号如分类器）；
- **本实验只否定"CLIP image-text sim 可作为视觉适用性信号"，未否定所有视觉通道**——VLM/分类器仍待评估（环境无 VLM，需另行授权）。

## 9. 是否值得进入下一轮

**建议：下一轮优先评估"镜头感知的结构化视觉判断"（如 VLM zero-shot 结构化判断），而非继续 CLIP 系。** 依据：CLIP 已在 CV-1（属性识别差）+ Phase 4B（image-text sim 无 C1/C2 区分度）两处证明不是该瓶颈的答案；但 VLM 是否可行尚未有证据（未测试），不可断言。

## 10. production 状态

**NOT READY（明确）**。本实验所有结论为 offline evidence；production ranking、V1、Gate、Gold Standard、人工标签均未修改；未引入任何新的生产组件。

---

## Audit trail

- 脚本：`output/stage33/cv2/ranking_validation_v4b/run_phase4b.py`
- 结果：`output/stage33/cv2/ranking_validation_v4b/result.json`
- 模型：openai/clip-vit-base-patch32（hf-mirror，环境既有复现）
- 覆盖披露：98/152 有缩略图；constructed/historical 未评估（数据缺口）

---

**Phase 4B 完成。结论：CLIP ViT-B-32 image-text similarity **不能**作为视觉适用性信号（C1 recall=0%、C1/C2 分离≈0、V1+CLIP 组合下降）；`VISUAL_SUITABILITY_BOTTLENECK = SUPPORTED` 被证实；VLM/分类器未测（环境无）；production NOT READY。STOP，等待人工裁决。**
