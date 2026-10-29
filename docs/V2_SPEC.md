# V2 架构规格（AI 视频生产多 Agent 系统）

> 版本：V2（在 V1 可运行架构上迭代，不推翻重来）
> 状态：待人工确认后开发
> 前置决策（已确认）：
> 1. 抬杠 Agent 内部 role 保留 `critic`，显示名升级为 Skeptic / 抬杠 Agent，不做 role 名迁移
> 2. 文案内部标记 `[CLAIM:nnn]` + 独立 claims_map；朗读稿/字幕/发布稿/TTS 输入自动剥离标记；claim 可追溯到 Evidence→Source→Verification Status
> 3. Search 采用 Provider 接口 + 配置位；无 Key 自动降级离线模式（资料卡/项目资料/人工来源），系统照常运行
> 4. Agent 数量 22 → 25：仅新增 claim_extractor / evidence / conflict_detector

---

## 1. 25 个 Agent 最终列表

| # | role | 显示名 | 职责 | 输入 | 输出 | 模型档 | 通信方式 | 人工审批 |
|---|---|---|---|---|---|---|---|---|
| 1 | orchestrator | 总调度 | 任务规划/派单/状态机/异常 | 项目状态+事件流 | 任务 DAG、派单 | M(R 用于重规划) | 全事件+派单 | 否 |
| 2 | pm | 项目经理 | 计划/排期/风险 | 目标+任务清单 | 里程碑计划 | M | ↔orchestrator | 计划可审 |
| 3 | topic | 选题 | 选题提案 | 方向+经验库 | 选题提案 | M | →research | **必审** |
| 4 | research | 研究 | 资料搜集/来源记录 | 资料需求 | 资料卡 | M | →source_verify | 否 |
| 5 | source_verify | 来源核查 | 来源可信度分级 | 资料卡 | 可信度报告 | R | →critic/structure | 可打回 research |
| 6 | structure | 内容结构 | 章节/层级 | 选题+资料 | 结构 | M | →script | **必审** |
| 7 | script | 文案 | 文案/旁白（含 [CLAIM] 标记） | 结构+资料 | 带标记文案+claims_map | M | →claim_extractor | **必审** |
| 8 | **claim_extractor** | **声明提取** | **拆解断言/风险分级/绝对化识别/标注** | **script 产物** | **claims 表+claims_map+内部稿** | **M** | **→skeptic/fact_check；事件 CLAIMS_EXTRACTED** | **否** |
| 9 | critic | Skeptic / 抬杠 | 红队：7 类攻击（时间/人物机构/数字/因果/过度推断/标题vs事实/幻觉），指向 claim_id | claims+文案 | 挑战报告(含 claim_ids) | R | →orchestrator；CHALLENGE_RAISED | 可要求重做 |
| 10 | fact_check | 事实核查员 | 逐 claim 找证据、给结论；离线降级 | claims+evidence+SearchProvider | claim 核查记录（结论/置信度/证据引用） | R | →conflict_detector；CLAIMS_VERIFIED | 否（结论只建议） |
| 11 | **evidence** | **证据管理** | **证据登记/归一化/可靠性分级/检索** | **资料卡+人工来源+核查需求** | **evidence 表+证据索引** | **-**（免 LLM） | **→fact_check；EVIDENCE_INDEXED** | **否** |
| 12 | **conflict_detector** | **冲突检测** | **多源冲突识别/权威度时效比较/提交人工** | **claims+evidence** | **conflicts 表+冲突报告** | **M** | **→人工；CONFLICT_DETECTED(human)** | **冲突必审** |
| 13 | asset | 素材管理 | 素材登记索引 | 素材文件 | 素材索引 | - | →retrieval | 否 |
| 14 | retrieval | 素材检索 | 关键词匹配候选 | 需求+索引 | 候选清单 | - | →editing | 否 |
| 15 | visual | 视觉规划 | 镜头清单 | 脚本 | 镜头清单 | M | →editing | 关键素材必审 |
| 16 | editing | 剪辑 | 剪辑方案+渲染执行 | 镜头+素材 | 时间线/成片 | M+工具 | →qa | 方案可审 |
| 17 | voice | 配音 | TTS 合成（输入剥离标记后文本） | 脚本 | 音轨 | - | →audio | 否 |
| 18 | audio | 音频 | 混音方案 | 音轨 | 混音方案 | - | →render | 否 |
| 19 | subtitle | 字幕 | SRT 生成（剥离标记） | 脚本+音轨 | SRT | - | →render | 否 |
| 20 | thumbnail | 封面 | 封面方案 | 成片+标题 | 封面候选 | M | →人工 | 方案可审 |
| 21 | platform | 平台适配 | 多版本方案 | 成片 | 版本方案 | M | →metadata | 否 |
| 22 | metadata | 元数据 | 标题/标签（剥离标记） | 成片+方案 | 元数据 | M | →发布 | 否 |
| 23 | compliance | 合规 | 版权/医学表述/授权 | 全链路 | 合规报告 | R | →人工 | 可一票拦截 |
| 24 | qa | 质检 | 成片技术+内容核对 | 成片 | QA 报告 | -+M | →人工 | **成片必审** |
| 25 | analyst | 数据复盘 | 数据回收/经验入库 | 平台数据 | 复盘报告 | M | →经验库 | 否 |

> V2 变更标记：**加粗**为新增或职责重大升级。其余 20 个职责不变。
> 抬杠 Agent（#9）：V1 的 critic 保留，职责从"找文案漏洞"升级为"7 类定向攻击+指向 claim_id"；
> 事实核查（#10）：从"输出 verdict 列表"升级为"逐 claim 证据核查"。

---

## 2. 核心数据结构（V2 新增）

### Claim
```json
{
  "claim_id": "c_023",
  "project_id": "p_xxx",
  "task_id": "t_script",
  "segment_ref": "S07",              // 所在段落
  "text": "2024年1月，Neuralink完成第一例人体植入",
  "type": "FACT",                     // FACT|INFERENCE|OPINION|PREDICTION|UNKNOWN
  "risk": "CRITICAL",                 // LOW|MEDIUM|HIGH|CRITICAL（"第一/唯一/首次"等自动 CRITICAL）
  "markers": ["第一例"],              // 命中的绝对化表述
  "status": "NEEDS_HUMAN",            // UNVERIFIED|CHECKING|VERIFIED|DISPUTED|UNSUPPORTED|FALSE|NEEDS_HUMAN
  "conclusion": "Confirmed",          // Confirmed|Mostly Confirmed|Disputed|Unsupported|False（核查后填）
  "confidence": "High",               // High|Medium|Low
  "source_count": 2,
  "human_review_required": true,
  "created_at": "...", "updated_at": "..."
}
```

### Evidence
```json
{
  "evidence_id": "e_118",
  "project_id": "p_xxx",
  "source": "Neuralink 官方新闻稿",
  "source_type": "official",          // official|academic|media|secondary|unknown
  "publication_date": "2024-01-29",
  "reliability": "high",              // high|medium|low|unknown
  "excerpt": "...原文摘录...",
  "url": "https://...",
  "added_by": "fact_check",
  "task_id": "t_fc",
  "created_at": "..."
}
```
关联：`claim_evidence(claim_id, evidence_id)` 多对多。

### Conflict
```json
{
  "conflict_id": "f_007",
  "project_id": "p_xxx",
  "claim_id": "c_023",
  "source_a": "e_118",
  "source_b": "e_119",
  "description": "植入日期：A 称2024-01-29，B 称2024-01-28",
  "authority_comparison": "A 官方 > B 媒体",
  "recency_comparison": "B 更晚发布",
  "recommended": "以 A 官方日期为准，标注时区差异",
  "confidence": "High",
  "human_review_required": true,      // 冲突永远必审
  "status": "OPEN",                   // OPEN|RESOLVED|SUPERSEDED
  "created_at": "..."
}
```

### Changelog（版本管理）
```json
{
  "change_id": 12,
  "project_id": "p_xxx",
  "target_type": "claim|artifact|task|config",
  "target_id": "c_023",
  "changed_by": "human",              // agent role 或 human
  "reason": "人工裁定来源日期",
  "before_summary": "UNVERIFIED",
  "after_summary": "VERIFIED",
  "human_confirmed": true,
  "created_at": "..."
}
```

### 文案标记与剥离
- 内部工作稿/结构化脚本：`[CLAIM:023]` 嵌在旁白文本中
- `claims_map`：`{claim_id: {segment_ref, char_offset, text}}`
- **剥离层**（函数 `strip_claims(text)`，正则 `\[CLAIM:\d+\]`）：作用于
  - voice Agent 的 TTS 输入文本
  - subtitle Agent 的 SRT 文本
  - editing Agent 的烧录字幕
  - 朗读稿导出、发布稿、metadata 文案
- 用户可见任何输出**不含标记**；`[CLAIM:023]` → claims 表 → evidence → source → status 可追溯

---

## 3. SearchProvider 接口

```python
class SearchProvider(Protocol):
    name: str
    def search(self, query: str, max_results: int = 5) -> list[SearchResult]
    def fetch(self, url: str) -> FetchedPage
    def extract_evidence(self, page: FetchedPage, claim: dict) -> EvidenceCandidate | None

# SearchResult  {url, title, snippet, date}
# FetchedPage   {url, title, text, fetched_at, ok}
# EvidenceCandidate {excerpt, source, source_type, publication_date, reliability}
```

- **注册表**：`SEARCH_PROVIDERS = {"none": OfflineProvider, "tavily": ..., "bocha": ..., "custom": ...}`，`config.tools.search.provider` 切换
- **OfflineProvider（无 Key 自动降级）**：`search/fetch` 返回空；`extract_evidence` 仅从项目资料卡（research/source_verify 产物）与人工提供的来源中提取 → 系统照常运行；此时 fact_check 对无证据 claim 输出 `Unsupported + human_review_required=true`
- 有 Key：在线检索 → fetch 原文 → 提取证据片段 → 登记 evidence 表

---

## 4. Memory V2（8 层）

| 层 | 存储 | 说明 |
|---|---|---|
| Conversation | memories(kind=conversation) | 对话轮次摘要 |
| Project | projects/tasks 表 + 决策摘要 | 沿用 V1 |
| Decision | decisions 表 | 沿用；新增 claim 级决策（node=`claim_<id>`） |
| Knowledge | memories(kind=knowledge) | 已验证知识卡、可信来源表 |
| Evidence | **evidence 表（新）** | 证据库 |
| Task | tasks 表 | 沿用 |
| Error | memories(kind=error) | 失败原因沉淀 |
| Rejected | memories(kind=rejected) | 被否方案+原因（反例库） |

- changelog 表为以上各层的**变更审计层**（谁改/为什么/前后/是否人工确认）
- 全局规则统一入口：`config/rules.json`（权限）+ `config/factcheck_rules.json`（绝对化词表/逻辑跳跃清单/强制人工规则）+ `config/script_style_guide.md`（文案规范），由 memory.repo 统一加载注入

---

## 5. V2 事实核查子流程（接入现有管线）

```
script(带标记) ──▶ claim_extractor ──▶ claims 表
                       │
        ┌──────────────┼──────────────────┐
        ▼              ▼                  ▼
   skeptic 挑战    evidence 索引      fact_check 逐claim核查
   (7类攻击,     (资料卡+人工来源    (SearchProvider 在线/离线
    指向claim_id)   转证据登记)        + 逻辑跳跃清单)
        │              │                  │
        └──────────────┴──────┬───────────┘
                              ▼
                     conflict_detector（多源冲突→人工）
                              ▼
                    人工 Claim 审核闸门
        （CRITICAL/HIGH/冲突/无原始来源/医疗/科技突破/历史/法规/预测 必审）
                              │
             通过 ──▶ 放行生产    未通过 ──▶ 打回 script ──▶ 复检循环
```

管线位置：插入在 p2_script 之后（新阶段 `p2b_verification`），依赖链：
`claim_extract←script`；`evidence_index←research`；`skeptic_check←claim_extract`；
`fact_check←claim_extract+evidence_index`；`conflict_check←fact_check`；随后原有 p3 视觉继续。
p6 的 `critic_final` 终审挑战保留。

---

## 6. V1 → V2 具体修改点

### 新增文件
| 文件 | 内容 |
|---|---|
| `agents/claim_extractor/agent.py` | 声明提取 Agent（词表规则+LLM 复核） |
| `agents/evidence/agent.py` | 证据管理 Agent（确定性） |
| `agents/conflict_detector/agent.py` | 冲突检测 Agent |
| `tools/search_provider.py` | SearchProvider 接口 + OfflineProvider + 注册表 + provider 实现位 |
| `config/factcheck_rules.json` | 绝对化词表、逻辑跳跃清单、强制人工规则、风险分级规则 |
| `tests/verification_mock.py` | V2 核查流程端到端测试 |
| `docs/V2_SPEC.md` | 本文档 |

### 修改文件
| 文件 | 修改内容 |
|---|---|
| `db/schema.py` | +claims/evidence/claim_evidence/conflicts/changelog 五表（迁移兼容，旧数据不动） |
| `agents/fact_check/agent.py` | 新 schema：逐 claim 输出结论/置信度/证据引用；接 SearchProvider；离线降级；逻辑跳跃清单 |
| `agents/critic/agent.py` | 升级为 Skeptic：7 类攻击 + 指向 claim_id + NEED_EVIDENCE 触发证据补查；role 名不变 |
| `agents/script/agent.py` | 提示词要求旁白内嵌 `[CLAIM:n]` 标记（风格规范继续加载） |
| `agents/voice|subtitle|editing/agent.py` | 输入经 `strip_claims()` 剥离标记 |
| `pipeline/lifecycle.py` | 新增 p2b_verification 阶段与依赖 |
| `hitl/service.py` | +claim 级审核（pending_claim_reviews / decide_claim / 强制人工规则） |
| `cli.py` | +`claims`（查看）/`approve-claim` 命令 |
| `memory/repo.py` | 8 层 kind 规范 + 全局规则统一加载 + 证据检索辅助 |
| `core/engine.py` | 写入 changelog 钩子（redo/approve/claim 决策时）；CLAIMS_EXTRACTED/CONFLICT_DETECTED 事件 |
| `config/rules.json` | +3 个新角色权限 |
| `config/config*.json` | +tools.search provider 配置位 |

### 保持不动
- engine 状态机/重试/回退/崩溃恢复核心
- 事件总线、工具层（除 search 升级）、任务级 HITL
- 20 个未升级 Agent 本体
- 现有测试（smoke/pipeline 作为回归基线）
- 所有历史项目数据（新增表、不迁移旧表）

---

## 7. V2 验收标准（开发完成后逐项验证）

1. 25 个 Agent 全部注册；22 个 V1 角色行为回归通过（smoke/pipeline 测试不破坏）
2. 文案→claim 提取：绝对化表述自动 CRITICAL；claims_map 与内部稿一致
3. fact_check 离线模式可运行（无任何 API Key），有证据输出 evidence 记录
4. conflict 流程：两条冲突证据 → CONFLICT + human_review_required
5. 人工 claim 审核：approve/reject/modify 落 decisions+changelog，可打回 script 复检
6. 剥离验证：朗读稿/TTS/字幕/成片字幕中无任何 `[CLAIM:` 字符串
7. 追溯验证：claim_id → evidence → source → status 全链路可查
