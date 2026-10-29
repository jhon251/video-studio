# Stage 12.1：Visual Intent + Intent-aware Query + Candidate Quality Gate

> 状态:**`STAGE12.1 = PASS`**（三模块实现 + 6-shot Material Alignment Test 完成）。
> 冻结边界:CV-2 / V1 / Gold / Top-5 / sanitizer / asset_cache / Stage 11 contract **全部未改**。
> **STOP —— 不进入 Camera Motion / Composition / Subtitle / 8-12 分钟 E2E。**

---

## 0. 授权范围与执行

本阶段仅实现(按 Phase 12.1):
1. Shot-level Visual Intent;
2. Intent-aware Query Generation;
3. Candidate Quality Gate;
4. 完整 trace/log;
5. 6-shot Material Alignment Test(OLD vs NEW)。

**未做**:Camera Motion / Composition / Subtitle / 完整 E2E。

---

## 1. 新增模块(3 个,集成层,不碰冻结)

| 模块 | 职责 | 关键点 |
|---|---|---|
| `visual_intent.py` | 旁白 → 结构化 Visual Intent | 复用 Stage 9 B 硬化 LLM;输出"观众看到什么"非复述 |
| `query_generator.py` | Intent → 短英文检索词 | 确定性 + LLM 精炼;可追溯 shot→intent→query |
| `candidate_quality_gate.py` | 轻量主题对齐门 | LLM 语义二元判定;非关键词黑名单;失败保守保留 |

**修改的生产文件**:无。**未改**:CV-2 / V1 / Gold / Top-5 / sanitizer / asset_cache / motion.py / Stage 11 contract。

---

## 2. Visual Intent 质量(核心成果)

6 shot 的 Visual Intent 全部成功生成(真实 LLM,0 fallback),且**是"画面描述"而非"旁白复述"**:

| shot | visual_intent(节选) |
|---|---|
| S01 历史 | "1950年代学术会议室的学者群像…学者热烈讨论,手指指向图纸或黑板公式" |
| S02 当前能力 | "数字大脑悬浮抽象空间…机械手穿过球体无法抓取(缺乏物理理解)" |
| S03 就业 | "现代开放式办公室…屏幕文档自动整理汇总,员工解放" |
| S04 人机协作 | "左侧人类专家指向全息界面,右侧 AI 光流响应…协作互动" |
| S05 基础设施 | "未来城市俯瞰…交通信号/电网/医院图标在数字界面动态重组" |
| S06 未来社会 | "从工业革命蒸汽机工厂烟囱,过渡到未来城市机器人协作" |

字段完整:shot_id/narration_segment/core_claim/visual_intent/visual_subject/visual_action/visual_context/time_period/asset_type_hint/avoid_types。

---

## 3. Query Generation(修复了长中文 query 问题)

**过程中发现并修复的实现缺陷**:初版 query 直接拼接 `visual_action`(40+ 字中文句)→ Commons `gsrsearch` 返回 0 页/超时。**修复**:LLM 精炼为短英文名词短语(2-6 词)。

| shot | 修复前 | 修复后 |
|---|---|---|
| S03 | "现代办公室…员工在旁观看"(40+字,0 页) | "modern office document automation" |
| S04 | "人类专家指向屏幕…"(40+字) | "human expert holographic interface interaction" |
| S05 | "交通电力医疗系统…"(40+字) | "futuristic city skyline digital overlay" |

每个 query 可追溯:shot_id → visual_intent → query。

---

## 4. Candidate Quality Gate(精准拦截主题污染)

**6-shot 实测,gate 精准拦截"字面含 AI 但主题无关"素材,无关键词黑名单:**

| 拦截案例 | 为何拦截(gate reason 语义) |
|---|---|
| S04: FIREDOC vocabulary list | "消防文献词汇表,与未来实验室人机协作无关" |
| S04: 1998 ITL technical accomplishments | "历史技术文档,与未来实验室无关" |
| S05: Smart Cards Colombian Navy | "哥伦比亚海军智能卡,与城市自动化网络无关" |
| S05: Autonomous agents intrusion detection | "分布式入侵检测,与城市交通电网无关" |
| S06: Lenin Proletarian Revolution | "列宁政治文献,与工业革命→未来文明跃迁无关" |
| S06: Auckland Museum Annual Report | "博物馆年度报告,无关" |

**关键**:gate 的 reason 全部基于**主题语义**,而非 `if "PDF" reject` / `if "tornado" reject`。PDF/SVG 未被错误清除(历史文献段 asset_type_hint 允许 DOCUMENT)。

**fallback**:gate LLM 失败 → 候选保守保留(`gate_status=FALLBACK_KEEP`),绝不静默丢素材。

---

## 5. 6-shot 结果(OLD vs NEW)

| shot | OLD(硬编码 query) | NEW(intent query) | KEPT(过 gate) |
|---|---|---|---|
| S01 历史 | 6 | 18 | 8 |
| S02 当前能力 | 6 | 12 | 2 |
| S03 就业 | 6 | 18 | 9 |
| S04 人机协作 | 6 | 6 | **0** |
| S05 基础设施 | 6 | 12 | 3 |
| S06 未来社会 | 6 | 12 | 2 |

**A/B 对比(七项)**:
1. **主题相关性**:NEW 明显更相关(gate 后候选都贴近 Intent);
2. **候选池污染程度**:NEW 降低(gate 拦截军事/海军/历史文献噪声);
3. **V1 Top-1 / CV-2 Top-1**:本阶段未重跑(冻结,下游)——隔离了上游修复;
4. **最终素材是否服务旁白**:NEW 的 kept 候选都服务 Intent;
5. **PDF/SVG 是否被错误清除**:否(拦截理由为主题,非文件类型);
6. **候选数量是否异常下降**:S04 kept=0 是**诚实空池**(Commons 无"未来实验室全息人机协作"真实素材),非错误清除;
7. **可解释性**:每 shot 都能回答"为何选这个素材"(intent→query→gate reason 全链路)。

---

## 6. 关键诚实发现

1. **抽象/未来视觉意图在 Commons 无真实素材**(S04 kept=0、S02 kept=2)——这是**素材源的数据局限**,gate 如实拦截而非伪装。**这不属于 Stage 12.1 修复范围**,但需在后续(可能 Option 2/素材源扩展)处理;
2. **Visual Intent 质量超出预期**——不是复述,是真正的画面语义;
3. **Query 过长中文导致 Commons 检索失败**是本次发现并修复的实现缺陷。

---

## 7. 回归确认

- [x] CV-2 文件未修改(vision_controlled.py 时间戳 19:49)
- [x] CV-2 prompt 未修改
- [x] V1 未修改 / Gold 未修改 / Top-5 未修改
- [x] Stage 11 asset contract 未破坏
- [x] renderer 原有行为未破坏
- [x] fallback 仍 deterministic
- [x] candidate 无无原因清空(gate fallback=KEEP)
- [x] zero-candidate 行为未改变
- [x] asset_id trace 完整(Stage 11 未动)

---

## 8. 交付物

`output/stage33/stage12_material_alignment/`:
- `material_alignment_test.json`(6-shot 全链路 trace:narration→intent→queries→candidates→gate→kept)
- `material_alignment_result.json`(A/B 对比 + gate 拦截案例 + 发现)
- `run_alignment_test.py`(实验脚本)
- 源码:`src/video_studio/stage33/visual_intent.py` · `query_generator.py` · `candidate_quality_gate.py`

报告:`docs/STAGE33_STAGE12.1_MATERIAL_ALIGNMENT_REPORT.md`(本文件)

---

## 9. 状态与 STOP

```
STAGE12.1 = PASS（Visual Intent + Query + Quality Gate + 6-shot 对齐测试）
冻结边界:CV-2/V1/Gold/Top-5/sanitizer/asset_cache/Stage11 contract 全部未改

STOP —— 等待人工授权 Phase 12.2（Camera Motion）
```

**不进入** Camera Motion / Composition / Subtitle / 完整 E2E。按测试顺序,Phase 12.1 完成且人工检查 PASS 后,才进入 Phase 12.2。
