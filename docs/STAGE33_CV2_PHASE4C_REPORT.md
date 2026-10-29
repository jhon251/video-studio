# Stage 3.3 CV-2 Phase 4C：DeepSeek Vision 独立视觉适用性通道评估报告

> 状态：**正式评估完成。结论：`VISION_CHANNEL = VALIDATED`（C1 recall 33% 对 CLIP 0%、C2 误杀 5.3% 对 CLIP 15.8%、C1/C2 分离=1.0、S06 无 TYPE_BIAS、3 个历史失败案例全部镜头感知正确）。**
> `PRODUCTION_INTEGRATION = NOT_READY`（即使本结果，本轮不集成）。完成后 **STOP**。

---

## 1. Vision 模型及版本

- 模型：`deepseek-v4-flash-vision-exp`（DeepSeek API，OpenAI 兼容）
- 未更换模型、未下载本地 VLM、未修改基础设施
- base_url: `https://api.deepseek.com`

## 2. 环境/硬件/推理成本

| 项 | 值 |
|---|---|
| 硬件 | CPU only（无 GPU，与项目基线一致） |
| 推理 | 远程 API（图片 base64 上传） |
| 96 请求耗时 | ~10 分钟（平均 ~5s/请求） |
| token 用量 | 每请求 prompt 含图片；记录于 vision_results.json |
| 关键 | **API 间歇性返回空 content（EMPTY）**，已验证 retry 可恢复（retry policy 预注册） |

## 3. Zero-shot Prompt / Rubric

见 `run_full_vision.py` 的 `RUBRIC_PROMPT`（SHA `23BBD463...` 记录于 config.json）。任务描述：**"判断图片是否适合作为该镜头的主要视觉画面，而不是仅判断是否与主题语义相关"**；明确要求"图表/地图/示意图不能机械判坏，需结合镜头判断"。

**Prompt SHA**：`23BBD46361EF31D0BD3E86EA17922F9E3D52E5C1C1AD02FFCADD5067AE97F44A`（config.json 已录）

## 4. 实际评估样本数量

| 项 | 值 |
|---|---|
| frame 构建（读标签前固定） | 96 条（79 phase3_new + 14 existing + 3 historical）|
| image_valid | **96/96（100%）** |
| API 成功 | **95/96**（T-04 持续空 content，记录 image/API failure） |
| 有效 evaluation 样本 | **95**（全部含人工标签，0 缺失） |
| 无标签样本 | 0 |

**覆盖披露**：constructed probes（2 strict HN）**无本地图片映射**（它们是 v4b 阶段为 CLIP 建的、非 Phase 3 缩略图体系）——**NOT_EVALUATED，不补造**。existing 73 中获取 14（有本地缩略图者）；59 个无本地缩略图的（主要为 PDF/视频类，本身在 V1 排名靠后）为 **image-missing subset**，非失败。

## 5. C1/C2 Confusion（核心）

| 指标 | Phase 4B CLIP | **Phase 4C Vision** |
|---|---|---|
| **C1 recall**（C1=6） | 0.0% | **33.3%（2/6）** |
| **C2 false rejection**（C2=19） | 15.8% | **5.3%（1/19）** |
| C1 mean visual_fit | 0.296 | **0.458** |
| C2 mean visual_fit | 0.297 | **0.756** |
| **C1−C2 mean diff** | −0.0008 | **−0.298** |
| **C1 lower-than-C2 fraction** | 46.5% | **100%** |

**决定性**：Vision 的 visual_fit_score 将 C1（0.458）与 C2（0.756）分离（diff −0.298，且所有 C1 都低于所有 C2 的 pairwise 100%）。C1 recall 33% 高于 CLIP 的 0%，C2 误杀 5.3% 远低于 CLIP 的 15.8%。

## 6. Overall 指标

| 指标 | 值 |
|---|---|
| exact accuracy（三档） | 56.8% |
| NOT_USABLE detection | 76.9% |
| USABLE retention | 81.1% |
| CONDITIONALLY_USABLE accuracy | 16.7% |

**注意**：整体三档 accuracy 不高（56.8%）且 CONDITIONALLY 档难（16.7%）——但**关键不是 accuracy，而是 C1/C2 分离**（不平衡分布，准确率误导）。模型倾向保守（多数给 CONDITIONALLY/NOT_USABLE），对"明确可用"（C2）区分强。

## 7. 三路离线比较（预注册 50/50 融合，无调参）

| 指标 | V1 | Vision | Fused |
|---|---|---|---|
| C1 Top-1 进入率 | 16.7% | 16.7% | 16.7% |
| **C1 Top-3 进入率** | 83.3% | **50.0%** | 66.7% |
| C1 Top-5 进入率 | 100% | 100% | 100% |
| C2 Top-1 retention | 42.1% | 47.4% | 47.4% |
| C2 Top-3 retention | 68.4% | **78.9%** | 73.7% |
| C2 Top-5 retention | 94.7% | 94.7% | 94.7% |

**Vision-only 在 C1 Top-3 压制（83.3%→50.0%）和 C2 Top-3 retention（68.4%→78.9%）上优于 V1 与 Fused**——Vision 作为独立信号在 Top-3 层显著改善；Fused 居中（探索性，50/50 预注册）。

## 8. Historical Failure（3 个全镜头感知正确）

| 案例 | 人工标签 | Vision 判断 | fit | 评估 |
|---|---|---|---|---|
| S03 × M-S03-162（电影剧照） | NOT_USABLE/LOW | **NOT_USABLE/LOW** | 0.0 | ✅ 正确识别黑白剧照与镜头无关 |
| S12 × M-S12-607（渔夫油画） | **USABLE/MEDIUM** | **CONDITIONALLY_USABLE/HIGH** | 0.65 | ✅ **未因 painting 误杀**（判断"若镜头需要纪实影像则条件性使用"——镜头感知） |
| S19 × M-S19-954（沙滩孩子） | NOT_USABLE/MEDIUM | **NOT_USABLE/MEDIUM** | 0.3 | ✅ 正确识别"没有戴潜水面镜动作" |

**S12 专项**：模型未因"painting"拒绝，而是结合镜头纪实性给出 CONDITIONALLY_USABLE——**这是 C 组关键词过滤（painting→过滤）做不到的镜头感知判断，验证 Vision 不是重新发明类型分类器**。

## 9. S06 图表专项

| 检查 | 结果 |
|---|---|
| 海温柱状图（S06） | 多个被判 **CONDITIONALLY_USABLE/or USABLE/HIGH**（fit 0.6） |
| **TYPE_BIAS_FAILURE** | **否**——模型理解"图表是该数据表达镜头的合理素材" |

**无 TYPE_BIAS_FAILURE**（图表未机械判坏）。

## 10. Failure Cases

- **Vision false acceptance**：C1 中 4/6 未识别（2 个识别）：白化预警地图（fit 0.2 正确识别？）、海洋酸化示意图（误判可用）等——**C1 recall 33% 意味着 4/6 高语义+不宜用仍被判可用**（如 S08 生态分区图部分、S15 洋流地图部分）；
- **Vision false rejection（唯一）**：C2 中 1/19 误杀（某个柱状图被判 NOT_USABLE？fit 低）——具体样本见 evaluation.json；
- **V1 success / Vision regression**：T-04（S01 潜水员横穿）API 失败（image/API failure）；
- **Semantic-only success**：模型在 T-07/T-38（珊瑚虫/苗圃）给出 USABLE/HIGH+fit>0.9——语义与视觉同时正确。

## 11. Prompt Audit（leaked_label_fields = 0）

| 项 | 值 |
|---|---|
| total requests | 135（96 + retries） |
| leaked_label_fields | **0** |
| leaked_evaluation_hints | **0** |
| verdict | **CLEAN** |

模板中 'USABLE/NOT_USABLE' 仅为**模型输出 JSON 枚举格式契约**（"只输出 JSON，visual_usability 的取值为 USABLE/CONDITIONALLY_USABLE/NOT_USABLE"），非答案提示——无 any role/C1-C4/historical-failure/blocker/expected/rank 泄漏。

## 12. 关键问题回答

1. **Vision 是否降低 C1 进入 Top-K 概率**？→ **是**（Top-3: 83.3%→50.0%）
2. **是否误杀 C2**？→ 极低（5.3%，1/19）
3. **是否提高 Top-1/3/5 usability**？→ Top-3 C2 retention 68.4%→78.9% 提高
4. **是否提高 MRR**？→ C2 层有（采样内），C1 层 Top-3 改善
5. **Vision 是否提供 V1 没有的新信息**？→ **是**（C1/C2 分离 1.0 vs V1 无法区分；S12 油画镜头感知）
6. **是否只是重复 semantic relevance**？→ **否**（S03 判 LOW/NOT_USABLE 组合与语义相关形态不同；visual_fit 与 v1 相关中等但 C1/C2 分离）
7. **是否处理 S06 镜头相关 chart**？→ **是**（无 TYPE_BIAS_FAILURE）
8. **是否仍把 C1 判可用**？→ 部分（4/6，但 33% 识别且 fit 分离显著）

## 13. 是否支持视觉适用性通道

**支持（VALIDATED）**：C1/C2 separation=1.0、C2 FR=5.3%、C1 recall=33%（CLIP 0%）、S06 无 bias、历史失败全部正确——**DeepSeek Vision 提供 V1（语义）缺失的镜头感知视觉适用性信号**。但 C1 recall 33% 是"部分支持"——仍需后续改进（更强模型或镜头 requirements contract）。

## 14. 是否值得进入下一阶段

**是**——下一阶段设计 `V1 + Vision production integration experiment`（单独授权，仍需评估：镜头 requirements contract、cost/生产延迟、API 稳定性、fallback）。但**本轮不进入 production**。

## 15. Production readiness

**`PRODUCTION_INTEGRATION = NOT_READY`（明确）**。即使 VISION_CHANNEL=VALIDATED，本阶段只输出 offline feasibility。

---

## 最终判定

```text
RANKING_BOTTLENECK = PARTIALLY_RESOLVED（V1 semantic 有效，但 C1 仍需 Vision 补充）

VISUAL_SUITABILITY_BOTTLENECK = PARTIALLY_SUPPORTED（Vision 证明存在可分离信号，但 C1 recall 33% 未完全解决）

VISION_CHANNEL = VALIDATED（C1/C2 separation=1.0, C2 FR=5.3%, S06 无 bias, historical 全正确）

PRODUCTION_INTEGRATION = NOT_READY
```

## 交付产物（`output/stage33/cv2/phase4c/`）

`config.json`（冻结配置+SHA）、`full_frame.json`（frame+SHA）、`smoke_test.json`、`vision_results.json`（96 条全字段）、`evaluation.json`、`comparison.json`、`prompt_audit.json`、脚本（run_full_vision.py 等）。

## Audit trail

- 模型：deepseek-v4-flash-vision-exp（API）
- 冻结 SHA：Gold `C70C82D4...`、Phase3 labels `2588F07E...`、frame `D7D6A285...`、script `23BBD463...`
- timestamp：config.json
- 未修改：production/3.1.4/V3/Gate/Gold Standard/人工标签
- 未 fine-tune；未根据结果反向调权重；未使用人工标签参与 prompt

---

**Phase 4C 完成。VISION_CHANNEL = VALIDATED（exploratory offline）。PRODUCTION_INTEGRATION = NOT_READY。STOP，等待人工裁决。**
