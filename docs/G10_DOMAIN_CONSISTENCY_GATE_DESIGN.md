# G10 Domain Consistency Gate — 设计文档（v1.0 DESIGN FREEZE 候选）

- 日期: 2026-09-10 · 阶段: DESIGN ONLY（零生产代码 / 零 Retrieval/CV2 / 零渲染）
- 依据: EXP-DC1 = PASS（`docs/EXP_DC1_REPORT.md`）· 三个核心反例 S08-B01 / S32-B02 / S16-B02
- 本文 = 完整设计 + 数据结构/IO + 判定规则 + 失败降级 + 自动域信号方案 + 离线验证指标 + 下一轮实验条件

## 0. 一句话定义

G10 是一道**语义域一致性硬门**：把"这一拍需要什么域的证据"（Evidence Core）与"这个候选实际是什么域的内容"（Candidate Domain Signal）在同一张**版本化域本体**上对账；不一致即拒绝进入 CORRESPONDING，任何信号缺失都 fail-closed。

## 1. 完整链（五个显式阶段，各自版本化产物）

```
[B] Beat Claims/Narration
     │  build: claim_inventory + narrative → 逐拍证据核心
     ▼
[E] Evidence Core Table (ECT)        ← e.g. S02-B01: core="本片五层结构阶梯",
     │                                  type=SELF_STRUCT, primary=[self_structure]
     │  build: 域本体展开（同义归一 + 近域边）
     ▼
[X] Expected Domains = primary ∪ near(primary)   ← tech_industry 类伞形域被废除
     │
[C] Candidate Domain Signal (run-time, 授权信号源)
     │  每候选: content_domain + confidence + signal_evidence
     ▼
[G] G10 Verdict = PASS / REJECT / LOW / REVIEW / NO_EXPECTATION
     │  (候选级判定一次；上屏级在 pre-render 复核一次)
     ▼
[P] Policy 消费: 非 PASS 一律不得进入 CORRESPONDING（REJECT→HN/空位, LOW→HN+角标,
    REVIEW→默认 HN 直至人工放行）
```

要点：**G10 不是"末端过滤器"**——它在候选级就判定，Policy 的合格池由"Gate + CV2 + G10 PASS"三者构成；pre-render 仅复核（防止候选级信号与上屏选择之间发生漂移）。

## 2. 数据结构（输入/输出 schema）

### 2.1 Domain Ontology（`domain_ontology.json`，版本化，哈希锚定）

```json
{
 "ontology_version": "1.0",
 "domains": ["vr_ar","bci_neuro","neuroscience","human_perception_science","haptics",
             "somatosensory_science","mocap","gaming","ai_ml","medicine_clinical",
             "tech_hardware","science_nature","history","body_illustration",
             "self_structure","generic_stock_text","generic_stock_concept"],
 "synonym_sets": [
   {"canonical": "body_illustration", "members": ["wellness","yoga","diving","physical_activity"]},
   {"canonical": "generic_stock_text", "members": ["word_tiles","scrabble","letter_blocks"]}],
 "near_edges": [
   ["haptics","somatosensory_science"],
   ["neuroscience","human_perception_science"],
   ["bci_neuro","human_perception_science"],
   ["bci_neuro","neuroscience"],
   ["vr_ar","gaming"], ["ai_ml","gaming"],
   ["medicine_clinical","bci_neuro"]],
 "abolished_umbrellas": ["tech_industry","any","generic"]
}
```

设计规则：
- **伞形域废除**（DC1 反例 S16-B02 的直接教训）：`tech_industry`/`any` 不得出现在 Expected 里。旧行为下 E-Prix 赛车因 `tech_industry` 假性 KEEP；新本体下该候选 `tech_hardware(赛车)` 与 primary `bci_neuro/clinical_trial` 无边 → REJECT。
- **同义归一**：PASS 2 的 wellness/diving 类标注归一进 `body_illustration`（DC1 两起词表归一的固化）。
- **近域边**（DC1 两起 clear FP 的固化）：`haptics↔somatosensory_science`（救 S08-B01）、`human_perception_science↔neuroscience/bci_neuro`（救 S32-B02）。

### 2.2 Evidence Core Table（`evidence_core_table.json`，按拍收紧）

```json
{"S02-B01": {
   "evidence_core": "本片自建五层结构阶梯(自指)",
   "type": "SELF_STRUCT",
   "primary": ["self_structure"],
   "near": [],
   "expectation": "DOMAIN_BOUND"},
 "S16-B02": {
   "evidence_core": "Neuralink Telepathy 试验存在, 植入者>10",
   "type": "REAL_EVENT_CLINICAL",
   "primary": ["bci_neuro", "medicine_clinical"],
   "near": ["human_perception_science"],
   "expectation": "DOMAIN_BOUND"},
 "S08-B01": {
   "evidence_core": "第二层(触觉)只是部分实现",
   "type": "REAL_STATE",
   "primary": ["haptics", "somatosensory_science"],
   "near": ["neuroscience", "vr_ar"],
   "expectation": "DOMAIN_BOUND"},
 "S29-B03": {"evidence_core": "完整 FullDive 需一代人以上(展望)",
   "type": "META", "primary": [], "near": [], "expectation": "NO_EXPECTATION"}
}
```

- `primary` 按拍**收紧**：宽伞域消失；REAL_DEVICE/REAL_EVENT 拍给具体设备/事件域（如 `clinical_trial`）。
- `expectation` 两态：`DOMAIN_BOUND`（进入 G10 判定）与 `NO_EXPECTATION`（META/纯展望拍——G10 判 NO_EXPECTATION，交由证据价值层/Routing 处理，**不冒充域一致**）。
- 构建方式：离线（claim_inventory + narrative 驱动的 LLM 辅助草案 + 人工确认），产物哈希锚定进 run manifest；版本化，改表 = 新版本。

### 2.3 Candidate Domain Signal（run-time，`candidate_domain_signals.json`）

```json
{"material_id": "r3_S02-B01_1",
 "content_domain": "energy",
 "confidence": 0.86,
 "signal_source": "cv2_rubric_v2",      // cv2_rubric_v2 | semantic_classifier | editorial
 "signal_evidence": "图表为氢能源经济阶梯, 含'Hydrogen'与能源路径要素",
 "signal_version": "v2.1"}
```

### 2.4 G10 Verdict（输出，`g10_verdicts.json`）

```json
{"beat": "S02-B01", "material_id": "r3_S02-B01_1",
 "verdict": "REJECT", "rule": "R5_DOMAIN_MISMATCH",
 "expected": {"primary": ["self_structure"], "near": []},
 "actual": {"domain": "energy", "confidence": 0.86, "signal": "cv2_rubric_v2"},
 "reason": "证据核心=本片自建五层结构阶梯(自指); 候选内容域=energy(氢能源阶梯图表); "
           "自指结构仅接受本片结构可视化, 外来内容域一律拒绝"}
```

## 3. 判定规则（优先级序，每条输出 rule_id + 双侧证据）

| 序 | 规则 | 条件 | 判定 |
|---|---|---|---|
| R1 | SELF_REF_EXTERNAL | expectation=DOMAIN_BOUND 且 self=true 且 actual≠self_structure | **REJECT** |
| R2 | SIGNAL_MISSING | expectation=DOMAIN_BOUND 且无有效域信号（或 confidence<0.5） | **REVIEW**（生产默认 HN，fail-closed，绝不静默 KEEP） |
| R3 | WORD_SPELLING | 信号含 word_spelling=true | **LOW** |
| R4 | GENERIC_CONCEPT_STOCK | 信号含 generic_stock=true | **LOW** |
| R5 | PRIMARY_MATCH | actual ∈ primary | **PASS** |
| R6 | NEAR_MATCH_ONLY | actual ∈ near(primary) 但 ∉ primary | **REVIEW**（人工放行可升 PASS，记录放行人） |
| R7 | DOMAIN_MISMATCH | 其余 | **REJECT** |
| R8 | NO_EXPECTATION | expectation=NO_EXPECTATION | **NO_EXPECTATION**（交证据价值层/Routing；不冒充域一致） |

状态语义：
- **PASS**：域一致，可作 CORRESPONDING 证据。
- **REJECT**：域不一致/自指外来——生产转 HN（角标）或空位；禁止以 CORRESPONDING 上屏。
- **LOW**：域不错但零证据价值（拼词/泛化概念库存）——生产转 HN/角标或替换；不得作为 CORRESPONDING 计数（DC1 后收紧：原 DC1 中 LOW 仍计 CORRESPONDING 的口径废止）。
- **REVIEW**：近域命中/低置信/信号冲突——默认 HN，人工放行后可升 CORRESPONDING（放行记录进 manifest）。
- **NO_EXPECTATION**：本拍无域期望（META/展望）——不参与域一致统计；生产建议 HN/低强调处理。

## 4. 失败与降级策略（fail-closed 全覆盖）

| 情形 | 行为 |
|---|---|
| 域信号源不可用（未授权/额度耗尽/服务失败） | **mode=DEGRADED_NO_DOMAIN**：所有 expectation=DOMAIN_BOUND 拍一律不得判 CORRESPONDING（全转 HN/空位）；qa 显式标记 `domain_signal=absent`；或整 Run STOP（授权时二选一，默认降级模式）。**绝不静默 KEEP** |
| 信号 confidence < 0.5 | REVIEW → 默认 HN |
| Ontology/ECT 缺失或哈希不符 | Preflight FAIL → 整 Run STOP |
| PASS-3 类分歧复现（人工复判推翻门判定） | 以人工复判为准并把该例写回"本体/ECT 修订队列"（版本化，不得热改） |
| REVIEW 队列积压（>10% 拍数） | STOP，要求人工批量裁决后再继续 |

## 5. 自动域信号方案（明确来源与授权路径）

| 方案 | 说明 | 授权/成本 | 采纳序 |
|---|---|---|---|
| S1 CV2 rubric v2 | 在冻结 rubric 上**增加字段** `content_domain`(本体词表内) + `domain_confidence` + `domain_evidence`（判定理由），对候选做一次重判 | 需 CV2 线授权（rubric 属冻结件，扩字段=新版本 rubric）；候选级一次性成本（~440 候选） | **首选**（与现行 CV2 判定同源、同审计体系） |
| S2 独立语义分类调用 | 文本 LLM 读 title+CV2 reason+可读元数据 → 输出域 + 依据（不读图） | 需 LLM 线授权；便宜但弱于看图 | 备选（S1 不可用时的降级信号，置信上限调低） |
| S3 人工编辑标注 | 人工逐候选标域 | 人力 | 仅 REVIEW 队列与仲裁 |
| 禁止 | 关键词白名单/标题子串规则 | —— | 明确排除（DC1 已证：'Hydrogen'靠侥幸，power-line ladder 与拼写正确的 RECAP 均漏） |

fail-closed 铁律：S1/S2/S3 三者皆不可用 → DEGRADED_NO_DOMAIN / STOP，二选一人工决定。

## 6. 诚实代价预算（不得假装）

对 Run04 种子数据、按 DC1 人工标注 + 本设计规则（含近域扩展救回 S08-B01/S32-B02 两例）重算：

| 指标 | Run04 现状 | G10 开启后（预计） | Δ |
|---|---|---|---|
| CORRESPONDING | 81（80.2%） | **≈61–64（60–63%）** | **约 -18 至 -20 拍** |
| HN/FALLBACK | 19.8% | **≈37–39%** | **约 +17 至 +19pp** |
| 自指拍伪证据 | 8 拍外来图 | **0** | 质量修正 |
| 域错配上屏 | 27 拍（含 P0） | **0（PASS 才可上屏）** | 质量修正 |

- 已知错配 6/6 消失；代价是 **CORRESPONDING 口径从"形式相关"重定义为"域一致证据"**。
- 现行 "+5pp 变更预算" 是为编排接线定的，**不适用于 G10**——G10 的采用必须伴随一次显式验收口径重定义（人工决策）：建议新下限 = `域一致 CORRESPONDING ≥ 60` 且 `误导性覆盖 = 0` 且 `HN/空位 100% 诚实角标`，旧的裸 ≥51 废止。
- 11 个 REVIEW 拍（近域命中/低置信）默认 HN，人工放行可回升——回升量不预设。

## 7. 三个核心反例在 G10 下的走向（worked examples）

| 反例 | DC1 结果 | G10 结果 | 关键机制 |
|---|---|---|---|
| S08-B01 体感系统图解（第二层触觉部分实现） | REJECT（误伤） | **PASS**（R5） | 本体 v1 含 `somatosensory_science` 且 ECT primary 直接写入（构建期近域扩展前置） |
| S32-B02 晕动症机制图（理解/模拟/写入感知） | REJECT（误伤） | **PASS**（R5） | 本体新增 `human_perception_science` + 近域边 neuroscience/bci_neuro |
| S16-B02 Neuralink Telepathy + E-Prix 赛车 | KEEP（假阳性） | **REJECT**（R7） | 伞形域 `tech_industry` 废除；primary 收紧为 `bci_neuro/medicine_clinical`，赛车无近域边 |

## 8. 离线验证指标（G10 实现后、任何生产前必须全过）

| # | 指标 | 门槛 |
|---|---|---|
| V1 | 三反例走向 | S08-B01=PASS、S32-B02=PASS、S16-B02=REJECT（逐一断言） |
| V2 | 已知错配 | DC1 已知 6/6 仍全拒（R1/R2/R3 路径） |
| V3 | 误伤 | 对 DC1 人工 KEEP 集：G10 误拒 ≤2/101 且不含 DC1 clear-FP 复发 |
| V4 | 一致性 | 信号域 vs 人工域 ≥85%（EXP-DS1）；判定可复现（两次运行逐字节一致） |
| V5 | 自指外来 | =0 |
| V6 | 可审计 | 101/101 决策含 rule_id + 双侧证据 |
| V7 | 零回归 | R1–R8 8/8 · 模块单测 12/12 · 冻结 14/14 · Run01–04 artifact 哈希不变 |
| V8 | fail-closed | 信号缺失/低置信/本体缺失三场景 = REVIEW/STOP，零静默 KEEP（单测断言） |

## 9. 是否具备进入下一轮自动信号实验（EXP-DS1）的条件

**设计侧：具备。** 本设计闭环了 DC1 全部四个遗留（同义归一、近域扩展、域信号授权路径、诚实代价预算），三反例走向逐一可判定，fail-closed 全覆盖。

**进入 EXP-DS1（自动域信号原型）的前置条件（需授权/资源，均非本阶段可做）：**
1. 构建产物两件（离线，可先行）：`domain_ontology.json` v1 + `evidence_core_table.json` v1（LLM 辅助草案 + 人工确认 + 哈希锚定）；
2. CV2 线授权：rubric v2 字段扩展 + 对 101 上屏候选（可扩至 433 候选）的一次重判额度；
3. 人工决策一项：**验收口径重定义**（域一致 CORRESPONDING ≥60 / 误导性覆盖=0，废止裸 ≥51 与 +5pp 旧预算）；
4. 评分者（可选，REVIEW 队列仲裁用）。

EXP-DS1 成功判据（预注册）：信号域与 DC1 人工域一致 ≥85%；三反例走向全对（V1）；Hydrogen Ladder 信号级捕获 1/1；REVIEW 率 ≤25%；信号缺失场景 fail-closed 单测通过。任一失败 → 信号源迭代，G10 保持 DESIGN 状态不得投产。

```
G10 DESIGN = COMPLETE（v1.0 候选冻结于本文）
本轮 = 纯设计 · 零代码 · 零 Retrieval/CV2 · 零渲染 · 零冻结件触碰
STOP——等待授权（下一步 = EXP-DS1 前置构建 + CV2 线授权决策）
```
