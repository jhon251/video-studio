# Stage 12 前置审计：视觉叙事缺失根因与 Material Alignment 设计

> 性质:**仅 Audit + Design,不改任何代码、不执行 Stage 12、不改 CV-2/V1/Gold/冻结边界。**
> 主题:《如果 AGI 在 2035 年出现，人类社会会发生什么？》
> 结论先行:**根因不是 CV-2,而是"Visual Intent 层完全缺失 + Retrieval Query 过宽 + 渲染链未复用已有的 motion/subtitle 能力"。** CV-2 被喂入了错误候选池,无法(也不应)靠它解决主题对齐。

---

## 1. 根因树(基于真实代码审计)

```
成片"PPT/检索结果感"
├─ 直接可见问题(症状)
│   ├─ 连续文档/论文截图       → 症状
│   ├─ 无字幕                 → 症状(H)
│   └─ 统一微弱 zoom / 无相机意图 → 症状(G)
└─ 根因(按层级)
    ├─ [缺层] Visual Intent 层完全缺失
    │    证据: final_production_plan.json 每 shot 只有
    │          {shot_id, narration, role, material_query, tts_est_s, cv2_top1, vision_fit}
    │          —— 无 visual_intent/subject/action/context/asset_type/avoid
    ├─ [实现缺陷] material_query 是"按 role 硬编码的 8 个宽泛英文关键词"
    │    证据: query ∈ {future technology AGI abstract, robotics computer brain,
    │          human civilization future, ...},与逐镜旁白语义无映射
    │    → 这是 B(Retrieval Query 过宽)的直接来源
    ├─ [数据质量] Commons 候选池被宽泛 query 污染
    │    证据: S01 "future technology AGI abstract" 检索回
    │          "littoral combat ship / PDA military / EMI resistivity" —— 无主题关系
    │    → 这是 C(候选池污染)
    ├─ [缺层] 无 Candidate Quality Gate(主题对齐门)
    │    证据: 检索 → V1 → Top-5 → CV-2 之间无任何"主题相关性"检查
    ├─ [缺层/未接入] Camera Motion 未复用现有 motion.py 能力
    │    证据: stage10_longform.py 用统一 zoompan;项目已有 motion.py(整数帧
    │          pan/zoom/HOLD)、realizer、planner_fallback._motion_for(按 shot type)
    ├─ [缺层/未接入] Subtitle 未接入渲染链
    │    证据: agents/subtitle/agent.py 已能生成 SRT,但 stage10/11 渲染链未调用
    └─ [非本层] Composition 无"连续 asset_type 去重 / 分章节视觉语言"策略
```

---

## 2. 九类问题定位(A-I)

| 类别 | 是否存在问题 | 归属 | 证据 |
|---|---|---|---|
| A. Visual Intent 缺失 | **是(最严重)** | **缺层** | shot 无 visual_intent 字段 |
| B. Retrieval Query 过宽 | **是** | 实现缺陷 | 硬编码 8 个宽泛词 |
| C. Candidate Pool 污染 | **是** | 数据质量(下游) | Commons 宽 query 命中无关材料 |
| D. V1 Semantic Ranking 错误 | **否(未判定)** | — | V1 只在污染池内排序;池错则 V1 无法救 |
| E. CV-2 Vision Rerank 错误 | **否** | — | CV-2 正确执行了"池内视觉适配";池错则无能为力 |
| F. Shot Composition 错误 | **是** | 缺层/策略缺失 | 连续 PDF 截图无去重 |
| G. Camera Motion 错误 | **是** | 未接入现有能力 | 统一 zoompan,未用 motion.py |
| H. Subtitle/Timeline 缺失 | **是** | 未接入现有能力 | subtitle agent 有 SRT 生成,渲染链未调用 |
| I. Renderer 问题 | **否** | — | Stage 11 已证明能渲染真实素材(15MB MP4) |

### 关键回答(用户点名)
> **"如果 CV-2 输入的 Top-5 候选本身全部是 AI 相关但主题错误的素材,CV-2 是否无法解决?"**

**是,CV-2 无法解决,也不应让它解决。** CV-2 的契约(已冻结)是:"在给定候选池中,视觉上哪个更适配镜头"。当候选池本身与旁白主题无关时:
- CV-2 只能在"无关素材"之间选"相对最不突兀"的,无法无中生有主题相关性;
- 根因在 CV-2 **上游**(Visual Intent → Query → Retrieval → Quality Gate),不在 CV-2;
- **把"选出错误素材"等价为"CV-2 错误"是误判。** CV-2 的输出在 Stage 11 已被证明"renderer selected == CV-2 top-1"精确成立(数据链正确),问题在输入池。

---

## 3. 缺层 vs 实现缺陷 vs 数据质量 vs CV-2(归类)

| 问题 | 归类 |
|---|---|
| Visual Intent 层不存在 | **缺层**(需新增) |
| material_query 硬编码宽泛词 | **实现缺陷**(需重写为 intent-aware) |
| 无 Candidate Quality Gate | **缺层**(需新增) |
| Commons 宽 query 污染 | **数据质量**(下游结果,随 query 修复缓解) |
| 连续 PDF/文档截图 | **缺层**(Composition policy 缺失) |
| 统一 zoom / 无 camera intent | **实现缺陷**(未复用 motion.py) |
| 无字幕 | **实现缺陷**(未接入 subtitle agent) |
| Renderer | **无问题**(Stage 11 已验证) |
| **CV-2** | **无问题,且绝不能改** |

---

## 4. Stage 12 最小架构(目标链,冻结边界内)

```
Narrative → Shot Segmentation → Visual Intent → Material Query
   → Retrieval → Candidate Quality Gate → V1 → Top-5
   → CV-2 Vision Rerank(FROZEN) → Material Asset Contract(Stage 11)
   → Shot Composition → Camera Motion → Subtitle → Renderer
```

- **CV-2 只做**:"候选素材中,哪个视觉上更适合?"(已冻结,不动);
- **新增层(Stage 12 范围)**:
  1. Visual Intent(逐镜,LLM 生成,结构化 schema);
  2. Intent-aware Query Generation(确定性/可解释);
  3. Candidate Quality Gate(轻量主题对齐,复用现有 LLM,非关键词黑名单);
  4. Shot Composition Policy(连续 asset_type 去重 + 分章节视觉语言);
  5. Camera Motion Policy(复用 `stage33/motion.py` 的整数帧 pan/zoom/HOLD,按 asset_type);
  6. Subtitle 接入(复用 `agents/subtitle` 的 SRT 逻辑 + 渲染链烧录)。

---

## 5. Visual Intent Schema(最小可行,基于代码库真实需求)

按代码库现状,逐镜需区分"画面表达什么"而非"重复旁白"。字段(不机械照抄,取舍理由见注释):

```json
{
  "shot_id": "S01",
  "narration_segment": "…(旁白原文,逐字)",
  "core_claim": "AGI 接管日常后人类选择权被侵蚀",
  "visual_intent": "现代家庭清晨,人类醒来查看 AI 已代劳的生活场景,人与自动化共存的日常",
  "visual_subject": "现代室内 / 人与智能设备",
  "visual_action": "人查看手机/屏幕上的 AI 已处理事项",
  "visual_context": "当代城市家居,清晨",
  "time_period": "near-future (2035)",
  "asset_type_hint": "IMAGE",
  "avoid_types": ["DOCUMENT", "SCREENSHOT"],
  "preferred_style": "cinematic realistic",
  "query_seed": ["smart home morning AI assistant", "human smartphone AI daily life"]
}
```

**字段取舍理由**:
- `core_claim`:供 Quality Gate 做主题对齐判定(不是给检索用);
- `visual_subject/action/context`:决定 query 的语义颗粒度(解决 B/C);
- `time_period`:历史/当下/未来分段的视觉语言依据(Composition 用);
- `asset_type_hint/avoid_types`:**偏好+回避是"意图级"不是"硬黑名单"**——例如历史文献段 asset_type_hint=DOCUMENT 允许文档,社会影响段 avoid DOCUMENT;
- `query_seed`:由 Intent 派生的检索词,替代硬编码宽泛词。

**核心原则**:visual_intent 必须描述"画面应该表达什么",而非复述旁白。验收标准:新流程的 visual_intent 能回答"这一镜观众应该看到什么画面"。

---

## 6. Query Generation Schema(稳定、可解释)

**输入**:`visual_subject` + `visual_action` + `visual_context` + `time_period` + `asset_type_hint`。
**输出**:有序 query 列表(≤3 条,可解释为何这样组合)。

**机制(确定性优先,LLM 仅做语义泛化,不用关键词黑名单)**:
```
query_seed = [ "{visual_subject} {visual_action}",            // 主体+动作
               "{visual_subject} {visual_context}",           // 主体+场景
               "{visual_context} {time_period} {subject}" ]   // 场景+时期+主体
```
- 每条 query 由 Intent 字段组合,**可追溯来源**;
- 对照旧流程:旧 = 硬编码 "robotics computer brain";新 = "modern office knowledge work AI automation"(由 S04 就业段的 subject/action 派生);
- **禁止**:query="AI" 或 query=narration 全文(既过宽又过窄);
- 抽象主题(如"未来文明")需 `visual_subject` 落到可检索的具象(如 city skyline, human crowd),这是 Intent 层的职责。

---

## 7. Candidate Quality Gate(轻量主题对齐,非关键词黑名单)

**位置**:Retrieval → **Quality Gate** → V1 → Top-5 → CV-2。

**目标**:在 CV-2 之前拦截"主题污染"(旁白讲 AGI 就业,候选是"风灾 ANN 论文"),**不做视觉审美**。

**机制(复用现有 LLM,结构化语义判断,不引入 `if "tornado" reject`)**:
- 对每个候选,用**已有 deepseek-chat(Stage 9 B 硬化策略)**做一次轻量二元判定:
  ```
  输入: core_claim + visual_intent + candidate.title + candidate.visual_description
  输出: {"relevant": true/false, "reason": "…", "confidence": 0-1}
  ```
- **阈值(预注册,不调参)**:`relevant=true ∧ confidence ≥ 0.5` 才进 V1;
- **不引入类型黑名单**:PDF/SVG 是否相关由语义判断(讲 AI 历史的 1956 Dartmouth 文档 = 相关;讲就业的 PDA 军事论文 = 不相关);
- **成本**:每 shot 候选数 ×1 次轻量 LLM,与 Stage 9 的 latency(~3.7s)同量级;
- **fallback**:Quality Gate 本身失败 → 该候选保守保留(relevant=true),进入 V1(避免 gate 引入新失败点)。

---

## 8. Subtitle Pipeline(接入现有能力)

**现状审计**(真实):
- `agents/subtitle/agent.py` **已能生成 SRT**(脚本时基 `ts()` 时间轴),依赖 Engine(需 script_output artifact);
- `stage32b/assemble.py` 明确"不烧字幕(P0-3 已独立生成)"——即字幕是**独立环节**;
- Stage 10/11 渲染链**未调用** subtitle,导致无字幕。

**缺失步骤**:① 渲染链未接 SRT 生成;② 未烧录(burn-in)。

**最小方案(复用现有)**:
1. **sentence segmentation**:已有 `stage32b/vo.split_sentences`(按标点切句);
2. **TTS duration**:F5 `vo_manifest.segments[].duration`(真实时长,已生成);
3. **timeline**:复用 `agents/subtitle/agent.py` 的 `ts()` + cursor 累加逻辑,但**改用 TTS 实际 duration**而非脚本估算;
4. **SRT 生成**:输出 `.srt`;
5. **burn-in**:渲染 concat 后,用 ffmpeg `subtitles=xx.srt` 滤镜烧录(若字库支持),或 ASS + `libass`。**注意**:burn-in 依赖 msyh.ttc 字体与中文字形,ffmpeg 的 `subtitles` 滤镜需 libass;若环境 libass 不支持中文,回退为"SRT 文件随片外挂 + 明确声明未烧录"。

**同步策略**:
- 若 TTS 未完成 → 用估算 duration(`tts_est_s`)+ 明确标记"估算时基,待 TTS 后对轴";
- 若 TTS 已完成(Stage 10 有 4 段 VO)→ 用 `vo_manifest.segments[].duration` 真实对轴。

---

## 9. Camera Motion Policy(复用现有 motion.py,最小)

**现状**:项目已有 `stage33/motion.py`(整数帧 pan/zoom,`plan_pan`/`plan_zoom`,`HOLD` 静止优先)、`realizer.py`(motion.intent→轨迹)、`planner_fallback._motion_for`(按 shot type)。**Stage 10/11 渲染链未复用。**

**最小 policy(按 asset_type + narrative section,确定性映射)**:

| asset_type / 场景 | Camera Motion | 复用 |
|---|---|---|
| 人物/生活场景 | subject focus + slow zoom(≤6%) | motion.plan_zoom |
| 地图/宽幅图 | region pan(方向由 visual_context) | motion.plan_pan |
| 历史文献/档案 | detail zoom + controlled scan | plan_zoom(小幅度) |
| 图表/数据 | **mostly STATIC(HOLD)** | 静止优先 |
| 普通照片 | subtle zoom | plan_zoom |
| 未来城市/概念图 | slow cinematic pan | plan_pan |
| 不确定素材 | **STATIC** | HOLD |

**核心原则**:**宁可静止,不无意义运动**(与项目 `schemas.CAPS["motion_band"]="LOW"` 一致)。不引入 CV 模型;asset_type 来自 Stage 11 `material_asset_contract`(已可追踪)。

---

## 10. Shot Composition Policy(最小,防连续 PPT 感)

**目标**:避免"连续论文截图"的检索结果感,**但不为多样性强行塞无关素材**。

**最小策略(确定性,基于 narrative section + asset_type)**:
1. **连续 asset_type 去重**:相邻 shot 若同 asset_type(DOCUMENT/SVG)连续 ≥2,则第 3 个若 Quality Gate 通过但同型,优先选次优的 IMAGE 候选(仅当池内有 IMAGE 且语义相关);
2. **分章节视觉语言**(由 `time_period`/`narrative_role` 驱动):
   - 历史段(history)→ documentary/archive(文献/档案合法);
   - 当前技术段(tech)→ technology/product/示意图;
   - 社会影响段(social)→ human/workplace/city;
   - 未来推演段(future)→ conceptual/futuristic visual;
3. **绝不**为了多样性把无关素材塞入——若池内无合适 IMAGE,宁可保留 DOCUMENT 也不引入主题污染。

---

## 11. STAGE12_MATERIAL_ALIGNMENT_TEST 测试方案

**范围**:不跑完整 8-12 分钟。**6 个不同叙事功能 shot**,全链路可追踪。

| shot | 叙事功能 | visual_intent 方向 |
|---|---|---|
| 1 | AGI/AI 历史 | 1956 Dartmouth 会议/早期计算机历史(允许 DOCUMENT/archive) |
| 2 | AI 当前能力 | 现代大模型/数据中心/技术产品 |
| 3 | 工作/就业 | 现代办公室知识工作 + 自动化 |
| 4 | 人机协作 | 人类与机器人/屏幕协作 |
| 5 | 社会基础设施 | 城市/交通/电网等公共系统 |
| 6 | 未来社会 | 未来城市/概念视觉 |

**每 shot 记录完整链路**:
```
visual_intent → query → candidate_pool → quality_gate(pass/fail)
→ v1_top_k → cv2_top_k → final_asset → camera_motion → subtitle(timeline)
```

**对比指标(旧 vs 新)**:
- 主题对齐率(人工对 6 shot 逐条评"素材与旁白相关/无关");
- 旧流程(query 硬编码)→ 基线;
- 新流程(Intent + gate)→ 候选;
- **不修改 CV-2**;只对比上游变化。

**验收标准(预注册)**:新流程 6 shot 中,≥5 个 final_asset 与旁白主题相关(旧流程当前 ≈1-2/6,见审计)。

---

## 12. 需要新增/修改的文件(仅 Design,本轮不写)

**新增(集成层,不碰冻结)**:
1. `src/video_studio/stage33/visual_intent.py` —— Visual Intent schema + LLM 生成(复用 Stage 9 B 硬化);
2. `src/video_studio/stage33/query_generator.py` —— Intent→query 派生(确定性);
3. `src/video_studio/stage33/candidate_quality_gate.py` —— 主题对齐轻量 gate(LLM 二元判定);
4. `src/video_studio/stage33/camera_motion_policy.py` —— asset_type→motion 映射(复用 motion.py);
5. `src/video_studio/stage33/composition_policy.py` —— 连续去重 + 分章节视觉语言;
6. `src/video_studio/stage33/subtitle_pipeline.py` —— 复用 subtitle agent 逻辑 + TTS duration 对轴 + SRT 输出。

**修改(仅渲染链,不碰冻结)**:
7. `stage10_longform.py` 的 material_query 段 —— 替换硬编码 query 为 Intent 派生;(非冻结文件)
8. Stage 11 `material_asset_contract.py` —— 不动(已验证接口保留)。

**绝不修改**:`vision_controlled.py` / `asset_cache.py` / `sanitizer.py` / `schemas.CAPS` / `motion.py`(只读复用)/ `ranking.py` / Gold / CV-2 prompt。

---

## 13. 回归测试方案

1. **CV-2 冻结回归**:跑 Stage 11 的 4-shot(asset contract→renderer)确认仍 PASS;校验 `renderer selected == CV-2 top-1` 不变;
2. **Stage 9 文本回归**:新 Visual Intent 生成走 hardened_call,确认 schema valid 100%(不引入 template 伪装);
3. **Stage 11 集成回归**:asset contract 接口不变,新 Quality Gate 只在其上游,不影响 contract;
4. **字幕回归**:subtitle SRT 时基与 TTS duration 一致(4 段 VO 已知时长);
5. **Motion 回归**:复用 motion.py 的 HOLD/pan/zoom 输出仍通过 stage33 visual_qc 的帧差审计(若接 v3 管线)。

---

## 14. 风险清单

| 风险 | 级别 | 缓解 |
|---|---|---|
| Visual Intent 仍复述旁白(未到"画面语义") | 高 | Intent schema 强制 subject/action/context 三字段;验收抽查 |
| Quality Gate 误杀相关素材 | 中 | gate 失败默认保留(relevant=true);threshold 预注册不调 |
| LLM 二元判定成本 ×候选数 | 中 | 每 shot 候选数 ≤6;Stage 9 已证 ~3.7s/次 |
| Commons 池本身缺合适素材 | 高 | 若池内全不相关,gate 后仍空→确定性 fallback 并如实报告(不伪装) |
| 字幕 burn-in 中文 libass 支持 | 中 | 若 libass 无中文,回退外挂 SRT + 声明 |
| Camera motion 过度 | 低 | 静止优先 + motion.py 幅度下限(不达则 HOLD) |
| 新层引入新失败点 | 中 | 每层确定性 fallback,不阻断下游 |

---

## 15. 最终结论

1. **根因**:Visual Intent 层缺失 + Query 硬编码过宽 → 候选池污染 → CV-2 无法(也不应)救。CV-2 正确且冻结。
2. **归属**:缺层(A/F)+ 实现缺陷(B/G/H)+ 数据质量(C)。**CV-2(E)与 Renderer(I)无问题。**
3. **Stage 12 范围**:新增 Visual Intent + Query Generation + Quality Gate + Composition + Camera Motion(复用 motion.py)+ Subtitle 接入。**不改 CV-2/V1/Gold/冻结边界。**
4. **验证**:STAGE12_MATERIAL_ALIGNMENT_TEST(6 shot 可追踪链路,旧 vs 新对比)。

---

## STOP —— 等待人工授权

**本轮只做了 Audit + Design,未修改任何代码,未执行 Stage 12,未动 GPU/TTS/CV-2/前端/EXE。** 请人工裁决是否批准 Stage 12 实施(按上述最小架构)。
