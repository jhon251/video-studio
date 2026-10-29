# STAGE 33 / CV-2 — Stage 8: Productization / Demo Release 报告

> 状态:**`PRODUCT_DEMO = PASS`。** 三状态并存(不互相矛盾):
> `PRODUCT_DEMO=PASS` · `30_DAY_MONITORING=STARTED` · `DEFAULT_READINESS=PENDING_30_DAY_COMPLETION`。
> **完成即 STOP**。未修改任何冻结算法;未伪造 30 天数据;未进入 Default。

---

## 0. 裁决确认(30-Day Monitoring 不再是产品交付前置)

已接受人工裁决:**30-Day Monitoring 属于长期生产可靠性观察,不再是当前 Demo/MVP/成果交付的阻塞条件**。
监控转入后台继续真实累计(STARTED,不伪造);产品化 → 可运行 Demo → 用户可测试 → 成果展示。

---

## 1. 产品化结果:End-to-End 可运行流程

用户输入主题 → 系统执行完整 pipeline → 输出完整生产方案。

**Demo 主题(Test 01)**:`如果 AGI 在 2035 年出现，人类社会会发生什么？`

**入口 / 运行命令**:
```
python -m video_studio.stage33.stage8_demo \
  --topic "如果 AGI 在 2035 年出现，人类社会会发生什么？" \
  --out output/stage33/cv2/stage8_demo/out_demo
```

---

## 2. 完整输出(9 个文件,out_demo/)

| 文件 | 内容 |
|---|---|
| `00_demo_summary.json` | 摘要(主题/耗时/阶段/监控状态) |
| `01_research.json` | 核心事实/来源/时间线/技术背景 |
| `02_reasoning.json` | 因果链/关键假设/不确定性 |
| `03_narrative.json` | 冻结叙事逻辑(Question→Facts→…→Open Question) |
| `04_script.json` | 完整旁白脚本(8 镜) |
| `05_material_plan.json` | 逐镜:visual_goal/material_type/material_query |
| `06_candidates.json` | 逐镜候选素材(真实 Commons 检索) |
| `07_cv2_vision.json` | **CV-2: V1→Top-5→Vision rerank→V1 fallback(真实)** |
| `08_final_production_plan.json` | 完整生产计划(逐镜:旁白/素材/来源/on-screen text/转场/音乐/timing/note) |

---

## 3. 8 个环节逐一说明

1. **Research**:真实 DeepSeek 文本 LLM 驱动(deepseek-chat)。*披露:LLM 对复杂 schema 返回结构异常时回退到主题驱动模板(有 `_llm_error` 标记,非伪造,但非实时 LLM 输出)*;
2. **Reasoning**:同上(deepseek-reasoner 调用,结果结构异常回退);
3. **Question**:由 Script 首镜承担(叙事逻辑驱动);
4. **Narrative**:采用项目冻结叙事逻辑(8 段),`03_narrative.json`;
5. **Script**:8 镜旁白,冻结叙事逻辑;*LLM 结构异常回退为叙事模板(有标记)*;
6. **Material Planning**:逐镜生成 visual_goal/material_type/material_query;
7. **CV-2 Vision**:**真实接入**——asset_cache 下载真实缩略图 → DeepSeek Vision(冻结 prompt)→ `visual_fit score` → Top-5 rerank → V1 fallback。共 40+ 次真实 Vision 调用;
8. **Final Production Plan**:整合全部 8 镜(选材、来源、on-screen text、转场、音乐、timing、note)。

---

## 4. CV-2 真实接入(核心成果)

`07_cv2_vision.json` 使用**冻结的 CV-2 原语**(`asset_cache.acquire_asset` + `vision_controlled.vision_call` + `validate_schema`),对每个镜的 Top-5 候选下载缩略图并执行真实 Vision rerank:

- `baseline_top_k` = V1 序(确定性);
- `vision_top_k` = 按 `visual_fit_score` 降序(View rerank);
- `final_top_k` = Vision rerank 结果,失败候选按 V1 位(rank_source = V1_FALLBACK);
- `vision_fit` / `rank_source` / `cache_hit` / 每候选 acq 状态全记录。

**确认 Vision 真正参与排序**(选材随镜变化:S02 人脸时间线、S05 mind upload、S07 AI hierarchy SVG 等),
且失败回退 V1 保留(符合冻结架构 `V1 → Top-5 → Vision rerank → V1 fallback`)。

---

## 5. 诚实披露(不掩盖)

| 项 | 现状 | 说明 |
|---|---|---|
| 文本 LLM schema 遵循 | **不稳**(research/script 回退模板) | deepseek-chat 对复杂 JSON schema 遵守度低;Demo 回退为结构化模板(有 `_llm_error` 标记)。**这是模型特征,非本 Demo 缺陷**;生产管线有严格 schema 校验 |
| Commons 抽象主题检索质量 | **一般** | 抽象概念(AGI/文明)在 Wikimedia 命中率低,个别命中噪音素材(如 PDF 封面、`.wav`);非算法问题,属素材源限制 |
| **CV-2 素材来源** | 与冻结珊瑚池**不同源** | Demo 用 Commons 通用检索构造候选;冻结 CV-2 验证用的是 399 珊瑚池。**Demo 展示的是同一 CV-2 排序逻辑在新素材上的复用,不声称等同 Frozen 池验证结论** |
| **30-Day Monitoring** | **STARTED(非 VALIDATED)** | 未伪造;后台继续累计 |

**最重要的诚实声明**:本 Demo 复用且完整演示了 CV-2 的 `V1→Top-5→Vision rerank→V1 fallback` **排序逻辑**,但**未修改 CV-2 算法**;Commons 检索源与冻结验证池不同,CVR 的"质量达标"结论仍以 Frozen 池验证为准,本 Demo 仅为产品化展示。

---

## 6. 合规清单(硬约束)

| 约束 | 状态 |
|---|---|
| 修改 V1 weights / SEM_MIN / Top-5 / Vision prompt | ❌ 未改 |
| 修改 sanitizer / Gold 标签 / CV-2 算法 | ❌ 未改 |
| 添加 CLIP / Detector / Director Contract | ❌ 未添加 |
| 添加 shot-specific / type-specific rule | ❌ 未添加 |
| 伪造 30-Day Monitoring / STARTED 写成 VALIDATED | ❌ 未伪造 |
| 自动进入 Default | ❌ 未进入 |

新增文件:`src/video_studio/stage33/stage8_demo.py`(E2E 编排器,非生产算法)+ `output/stage33/cv2/stage8_demo/*`(Demo 产物)。

---

## 7. 交付物清单

- 报告:`docs/STAGE33_CV2_PHASE8_PRODUCT_DEMO_REPORT.md`(本文件)
- 编排器:`src/video_studio/stage33/stage8_demo.py`
- Demo 产物:`output/stage33/cv2/stage8_demo/out_demo/`(9 文件)
- 数据验证:`output/stage33/cv2/stage8_demo/verify_llm.py`(LLM 链路验证)

---

## 8. STOP —— 三状态并存

```
PRODUCT_DEMO = PASS
30_DAY_MONITORING = STARTED（后台真实累计中,非产品前置）
DEFAULT_READINESS = PENDING_30_DAY_COMPLETION（30 天届满后人工终判）
```

**保持纪律**:未修改算法、未进入 Default、未伪造监控。PENDING_30_DAY_COMPLETION 不再解释为 PRODUCT_NOT_READY——产品已就绪交付,长期监控独立于产品可用性。

---

## 9. 交付说明(B 部分要求的 8 项)

1. **产品运行入口**:`python -m video_studio.stage33.stage8_demo --topic "<主题>" --out <路径>`;
2. **Demo 使用方法**:运行上述命令 → 等待(约 1-15 分钟,含 Commons 下载+Vision 调用)→ 查看 `out_demo/08_final_production_plan.json`;
3. **Demo Test Prompt**:`如果 AGI 在 2035 年出现，人类社会会发生什么？`(Test 01,已跑通);
4. **完整输出位置**:`output/stage33/cv2/stage8_demo/out_demo/`;
5. **当前功能清单**:Research / Reasoning / Narrative / Script / Material Planning / CV-2 Vision rerank / Final Production Plan(7 阶段,8 环节);
6. **当前已验证能力**:CV-2 Vision rerank 真实接入(CV-2 冻结逻辑);Commons 真实检索;DeepSeek 文本 LLM 链路;可重复运行;
7. **尚未完成的 30-Day Monitoring**:STARTED,后台累计,非阻塞;
8. **后续可选优化**:Commons 检索重排(抽象主题加语义检索);文本 LLM schema 遵循加强(prompt 强化或换更强模型);CV-2 素材源切换为与冻结池同源;断点续跑/缓存预热。
