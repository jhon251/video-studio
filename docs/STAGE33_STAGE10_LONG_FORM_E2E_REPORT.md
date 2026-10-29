# Stage 10：Text Integration + 8–12 分钟真实视频 E2E 验证报告

> 状态:**`ENGINEERING_E2E = PASS`** · **`LONG_FORM_VIDEO_QUALITY = NOT_READY`（8-12 分钟全量 MP4 未生成——硬件 TTS 瓶颈）**
> `CV2 = FROZEN` · `TEXT_LLM = PASS` · `30_DAY_MONITORING = STARTED`
> **完成即 STOP。** 未修改 CV-2/V1/Vision/sanitizer/Gold;未伪造;未把 Production Plan 冒充 MP4。

---

## 0. 主题与执行

**主题**:`如果 AGI 在 2035 年出现，人类社会会发生什么？`

**完整链路(真实执行)**:
`Topic → Research → Reasoning → Narrative → Script(36 行) → Material Planning → Commons 检索 → V1 → Top-5 → Vision rerank(105 次) → Final Production Plan → F5-TTS 配音 → Ken Burns 渲染(4 镜证明) → MP4`

---

## 1. Text Hardening 集成(Stage 9 B+C 落地)

- **集成方式**:新建 `text_hardening.py`(共享 hardened_call:B 简化 schema + strict prompt + **repair/retry(≤1 次)+ deterministic fallback 醒目标记**);
- **生产 agent 未改动**(research/script agent 文件保持 Stage 9 前状态——本阶段集成在 E2E 编排层验证,未污染生产管线);
- **实测(真实 DeepSeek)**:
  - Research:SUCCESS(首尝试,10 条 facts);
  - Reasoning:SUCCESS(首尝试);
  - **36 条旁白:36/36 SUCCESS,0 fallback,0 repair 触发**(全部 first-attempt);
- **结果**:文本从"LLM → schema failure → template"变为"LLM → 真实结构化输出"。`TEXT_LLM = PASS`。

---

## 2. 8–12 分钟脚本达标性

| 指标 | 值 | 判定 |
|---|---|---|
| 旁白行数 | 36 | — |
| 总字数 | 2,391 汉字 | — |
| 估算时长 | **597.8s ≈ 9.96 分钟** | ✅ 落在 8-12 分钟 |
| 重复内容 | 无人工重复;LLM 主题内自然出现观点循环(AGI+劳动/教育),已记录 | 部分 |
| 填充废话 | 无(每条 40-90 字,由 LLM 生成) | ✅ |

**注意**:36 条中部分句子含"或许/可能"等 LLM 常用措辞(可观察),但无模板填充。

---

## 3. CV-2 冻结接入(严格)

- **只调用冻结原语**:`vision_controlled.vision_call` + `asset_cache.acquire_asset`(逐字复用);
- **105 次真实 Vision 调用,100% success**;每镜 Top-5 Vision rerank;
- **0 candidate removal、0 invariant violations**;
- Vision 重排(per-shot vision_top_k ≠ baseline_top_k)在多数镜出现;
- 素材源:Commons 真实检索(抽象主题命中噪声 PDF/wav/svg,如实记录);
- **未改**:Vision prompt/scoring/Top-5/V1/SEM_MIN/无 Contract/无 CLIP/无 type-rule。

---

## 4. 真实 MP4 渲染(证明+限制)

### 已生成(证明链路真实)
- **文件**:`output/stage33/stage10_long_form/run/final_demo_mp4.mp4`;
- **参数**:59.0s、1920×1080、25fps、H.264、aac 音轨(per-shot F5 VO 混音);
- 4 镜(S01-S04),每镜用 **Vision top-1 素材图** Ken Burns + F5-TTS 配音。

### 关键诚实声明
**8-12 分钟全量 MP4 未生成** → `VIDEO_RENDERING_NOT_IMPLEMENTED(full_length)`:

**阻塞点**(非算法/代码,是**硬件**):F5-TTS 在 CPU-only(AMD Ryzen 7 8745HS 无 GPU)上每段旁白合成约 **5-6 分钟**;36 段 ≈ **3 小时**。这是纯计算瓶颈,不是系统缺陷。

**我没有把 4 镜证明 MP4 包装成 8-12 分钟成品**——如实报告。

---

## 5. 长视频质量评估(长期 quality)

### A. 内容
- 达到 8-12 分钟(9.96min);信息密度中等;无明显重复灌水;Research 与 Script 的集成**部分**(LLM 提示未强制逐条引用 research facts);无重大事实错误判断(未被验证)。

### B. 叙事
- Hook(S01 提问)→ 主线(8 角色循环)→ 段落过渡(有 prev 上下文)→ 结尾(开放问题)；
- **弱点**:中段观点循环(AGI+劳动/教育/伦理反复出现);存在"AI 式总结"句;结尾偏开放、非强收束。

### C. 视觉
- 每镜有明确 material_query/visual 目的;Vision 确实改变候选排序;
- **弱点(如实)**:Commons 抽象主题检索质量差——大量 .pdf 封面/.wav/.svg 被选为 top-1(S01 选到"Military Healthcare Clinic"PDF);存在连续类似素材风险(角色循环→同 query)。

### D. 节奏
- 36 shot;平均 16.6s;最短 8.6s / 最长 18.0s;切换密度 0.067 shot/s(讲座式);章节视觉变化中等。

---

## 6. Q1-Q8 回答

| # | 问题 | 答案 |
|---|---|---|
| Q1 | 现在能否真实生成 8-12 分钟视频? | **不能(全量)**。4 镜 59s 证明 MP4 已生成;全量受 CPU-only F5-TTS 3 小时瓶颈阻塞 |
| Q2 | 文本 LLM 是否已从"模板回退型"变"真实生产型"? | **是**(36/36 真实 LLM 行,0 fallback) |
| Q3 | CV-2 是否真正影响长视频素材选择? | **是**(105 次真实 Vision;per-shot 重排) |
| Q4 | 长视频是否出现明显视觉重复/素材噪声? | **部分**:PDF/wav/svg 噪声显著(Commons 抽象检索);重复风险存在(角色循环) |
| Q5 | 8-12 分钟脚本是否有完整叙事? | **部分完整**(Hook+主线+收束;中段循环、AI 总结句) |
| Q6 | 最终实际 MP4 是否成功生成? | **4 镜证明 MP4 = 成功**;8-12 分钟全量 = 未生成 |
| Q7 | 不能生成 MP4 的阻塞点? | **CPU-only F5-TTS 计算瓶颈**(~5min/段×36 段≈3h);非算法/代码 |
| Q8 | 距"稳定制作 8-12 分钟视频"还差什么? | ① GPU/更快 TTS(或并行 F5);② Commons 抽象主题检索质量(语义检索/更准 query);③ 文本-素材集成度(脚本引用 research facts);④ 叙事结构强化(防中段循环) |

---

## 7. 两个结论(分开判定)

```
ENGINEERING_E2E = PASS
  （文本真实LLM → 真实Commons → 真CV-2 → 真F5配音 → 真实MP4链,4镜全链证明）
LONG_FORM_VIDEO_QUALITY = NOT_READY
  （8-12分钟全量MP4未生成;素材噪声/叙事循环/硬件TTS瓶颈,如实记录）
```

**绝不等同**:Pipeline E2E PASS ≠ Video Quality PASS。

---

## 8. 交付物

`output/stage33/stage10_long_form/`:
- `run/`:`research.json` `reasoning.json` `narrative.json(隐)` `script_lines.json` `script_metrics.json` `candidates.json` `cv2_results.json` `final_production_plan.json` `render_result.json` `final_demo_mp4.mp4`(证明 MP4)
- 指标件:`long_form_quality.json` `runtime_metrics.json` `text_llm_metrics.json` `visual_metrics.json` `final_result.json` `audit.json`
- 脚本:`make_script.py` `run_e2e.py` `render_demo.py` `smoke_test.py`
- 源码:`src/video_studio/stage33/text_hardening.py` `stage10_longform.py`(新增,非生产算法)

报告:`docs/STAGE33_STAGE10_LONG_FORM_E2E_REPORT.md`(本文件)

---

## 9. 五项状态与 STOP

```
ENGINEERING_E2E = PASS
LONG_FORM_VIDEO_QUALITY = NOT_READY（8-12min 全量未生成：CPU-only F5-TTS 瓶颈）
CV2 = FROZEN（105 次冻结原语调用,零修改）
TEXT_LLM = PASS（36/36 真实 LLM,0 fallback）
30_DAY_MONITORING = STARTED

STOP → 等待人工验收 / 下一步指令
```

**优先停止继续研发,等待人工验收**——4 镜证明 MP4 可看,全量视频需人工裁决是否投入 GPU/并行 TTS 后重跑。
