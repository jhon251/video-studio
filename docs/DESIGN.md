# AI 视频生产多 Agent 系统 —— 总体设计（V1）

> 定位：**人类主导创意，AI Agent 负责视频生产流程管理**。系统是"AI 视频生产团队"：
> 人类是老板与最终决策者；Orchestrator 是生产总调度；22 个专职 Agent 是各岗位；
> Tool Layer 是执行工具；Critic 是专门抬杠的同事；Memory/DB 是团队长期记忆；
> Message Bus 是团队通信系统。它既不是"一句话自动剪视频"，也不是"AI 自动生成纪录片"。

---

## 0. 核心原则与边界（一切设计的基准）

| 人决定 | Agent 决定 |
|---|---|
| 做什么、为什么做、内容方向、核心观点 | 目标如何拆成任务 |
| 视频风格、最终创意、是否采用方案 | 任务分配、执行顺序、依赖关系 |
| 最终发布 | 工具调用、完成检查、错误重试/回退/重规划 |
| — | 质量控制、生产状态管理 |

**红线（不可动摇）**：
1. 任何"改变人类已确认决策"的动作必须重新走审批，Agent 无权直接改。
2. Agent 不创作核心观点，只负责"生产管理 + 执行工具调用"。
3. 一切落盘。系统任何时刻断线/崩溃，磁盘状态即全部进度。

---

## 1. 整体架构（选型 D：Orchestrator + Message Bus + Shared State）

```
┌─────────────────────────────── 人类 ───────────────────────────────┐
│  CLI / Web UI · 审批中心 · 项目仪表盘 · 决策录入                       │
└───────────────┬───────────────────────────────────────────────────┘
                │ 目标 / 决策 / 审批（自然语言 + 结构化决策记录）
┌───────────────▼───────────────────────────────────────────────────┐
│                    Orchestrator Agent（总调度）                     │
│    任务规划 · 依赖解析 · 调度 · 异常处理 · 成本控制 · 状态机推进          │
└──────┬──────────────────┬──────────────────────┬──────────────────┘
       │ 派单              │ 事件                 │ 读写
┌──────▼───────┐   ┌───────▼────────┐   ┌─────────▼──────────────────┐
│ Project      │   │  Message Bus   │   │      Shared State (DB)      │
│ Manager      │   │ 任务队列+事件总线│   │  项目库: 任务/决策/产物/审批/  │
│ Agent        │   │ (SQLite 驱动)   │   │  事件/记忆 —— 唯一权威状态    │
└──────────────┘   └───────┬────────┘   └────────────────────────────┘
                           │ dispatch / events
┌──────────────────────────▼────────────────────────────────────────┐
│                 Agent Pool（22 个专职 Agent）                       │
│  每个 Agent = 角色提示词 + 输入/输出 Schema + 工具权限 + 自我记忆        │
│  ┌ Topic ┐┌ Research ┐┌ SrcVerify ┐┌ Structure ┐┌ Script ┐ ...     │
│  └───────┘└──────────┘└───────────┘└───────────┘└────────┘         │
│  Critic Agent 横切：可在任意闸门向任何 Agent 发起挑战                   │
└──────────────────────────┬────────────────────────────────────────┘
                           │ 只允许通过 Tool Interface（权限校验/成本/审计）
┌──────────────────────────▼────────────────────────────────────────┐
│    Tool Layer：统一接口（name/input_schema/output_schema/execute/   │
│    estimate_cost/permission）— 工具可替换，Agent 无需重写             │
│  File │ FFmpeg │ ASR │ TTS │ Search │ Browser │ Image │ Video │    │
│  Subtitle │ DB │ NLE │ Export │ Publish                             │
└──────────┬──────────────────┬───────────────────┬──────────────────┘
           ▼                  ▼                   ▼
      本地工具            云端 API            Artifacts
   (ffmpeg/whisper)  (DeepSeek/TTS/图像视频)  (素材/脚本/字幕/成片)

横切服务（贯穿所有层）：
  Memory 服务（短期/长期/经验库） · Knowledge Base（事实卡/来源表/授权清单）
  Logger（append-only 审计日志） · HITL 审批服务 · 成本计量
```

**为什么选 D 而不是 A/B/C？**

| 方案 | 问题 |
|---|---|
| A. Agent 两两直连 | N 个 Agent = O(N²) 连接；加一个 Agent 要改一堆代码；失败追踪难。几十个 Agent 时变成蜘蛛网，直接排除。 |
| B. 全部经由 Orchestrator | Orchestrator 成为唯一瓶颈和单点；它要转发所有自然语言，上下文爆炸、成本失控；但**调度决策**必须中心化。 |
| C. 纯 Message Bus | 通信解耦了，但没有"权威状态"：谁都能发消息但状态不一致，回滚/重放困难，调试要到处追消息。 |
| **D. Orchestrator + Bus + Shared State** | **调度中心化（Orchestrator 只做决策与派单，不转发大文本）+ 通信解耦（Bus，可扩展/可重放/可审计）+ 状态权威（DB，可恢复/可查询/可回滚）**。B 的瓶颈被"结构化任务消息 + 产物引用"消除——Orchestrator 收到的是任务状态事件，不是长篇大论。 |

关键机制：**Agent 之间不传自然语言闲聊，只传"结构化任务 + 产物引用"**。所有自然语言产出都是 Artifact 文件（JSON/MD），消息里只有 `artifact_id` 和结论摘要。这让每个环节都可审计、可回放、可恢复。

---

## 2. Agent 清单总表（22 个）

| # | Agent | 职责一句话 | 模型档 | 上游 | 下游 | 人工审批 | 可发起否决 |
|---|---|---|---|---|---|---|---|
| 0 | Orchestrator 总调度 | 规划/拆解/调度/依赖/状态机/异常 | R+M 混合 | 人类、全部事件 | 全部 | 否（调度） | 是（终止/重规划） |
| 1 | Project Manager 项目经理 | 计划/排期/优先级/资源冲突 | M | 人类、Orchestrator | 全部 | 计划可审 | 否 |
| 2 | Topic 选题 | 选题提案/可行性/资料需求 | M | 人类方向、PM | Research、Structure | **必须** | 否 |
| 3 | Research 研究 | 资料搜集/整理/来源记录 | M | Topic | SrcVerify、Structure | 否 | 否 |
| 4 | Source Verification 来源核查 | 来源可靠性/引用真实性/冲突 | R | Research | Critic、Structure | 否 | 是（打回资料） |
| 5 | Structure 内容结构 | 章节/信息层级/结构 | M | Topic、Research | Script | **必须** | 否 |
| 6 | Script 文案 | 旁白/解说/台词 | M | Structure | FactCheck、Critic | **必须** | 否 |
| 7 | Fact-check 事实核查 | 事实/数字/人名/时间/地点 | R | Script | Critic、人工 | 否 | 是（打回脚本） |
| 8 | Critic 反对者 | 对抗性压力测试 | R | 任意闸门 | Orchestrator | 挑战需记录 | **是（要求重做）** |
| 9 | Asset Manager 素材管理 | 素材登记/标签/授权/生命周期 | 免 | 各 Agent | Retrieval、剪辑 | 否 | 否 |
| 10 | Retrieval 素材检索 | 按脚本/镜头匹配素材 | 免+embedding | VisualPlanning、EditingPlanning | EditingPlanning | 否 | 否 |
| 11 | Visual Planning 视觉规划 | 镜头/图表/动画需求清单 | M | Script | Retrieval、EditingPlanning | 关键素材**必须** | 否 |
| 12 | Editing Planning 剪辑规划 | 时间线结构/镜头安排方案 | M | VisualPlanning、Retrieval | 剪辑执行 | 方案**可审** | 否 |
| 13 | Voice 配音 | TTS 生成/音色管理/音频检查 | 免+小模型 | Script | Audio、Subtitle | 音色选择可审 | 否 |
| 14 | Audio 音频 | 降噪/响度/混音/BGM | 免 | Voice | QA | 否 | 否 |
| 15 | Subtitle 字幕 | ASR/生成/校对/时间轴 | 免+小模型 | Script、Voice | 剪辑执行 | 否 | 否 |
| 16 | Thumbnail 封面 | 封面方案+生产任务 | M+图像工具 | Script、成片 | 人工、Platform | 方案**可审** | 否 |
| 17 | Platform Adaptation 平台适配 | 横/竖/长短/各平台版本方案 | M | 成片 | Metadata、发布 | 否 | 否 |
| 18 | Metadata / SEO | 标题/简介/标签/章节 | M | 成片、Platform | 发布 | 否 | 否 |
| 19 | Compliance 合规 | 版权/敏感/授权/字体音乐风险 | R | 全链路产物 | 人工、QA | 风险报告必达人工 | 是（阻止发布） |
| 20 | QA 最终质检 | 技术+内容验收清单 | 免+M | 成片 | 人工 | **必须（成片）** | 是（打回生产） |
| 21 | Data Analyst 数据分析 | 发布后数据回收/复盘/经验入库 | M | 平台数据 | Memory 经验库 | 否 | 否 |

> **为什么是 22 个而不是 10 个或 30 个？**
> 每个都满足"独立职责可解释"测试。拆分的理由：生产流程里每一段都有独立的**失败模式、专业判断、工具集和审批时机**（例如"来源核查"和"事实核查"分属资料层和脚本层，前者管来源可信度、后者管陈述正确性，失败时回退的目标节点不同）。合并会制造"一个 Agent 既当运动员又当裁判"的冲突（如 QA 若兼 Critic，就没人质疑 QA 自己的标准）。没有为凑数而拆分：如"字幕校对"不单列，因为它是 Subtitle Agent 的内部子任务。

---

## 3. 每个 Agent 的完整定义（8 要素）

> 通用约定：所有 Agent 的输出都是**结构化 JSON + 落盘 Artifact**；`模型档` 含义见 §13。
> "免" = 该 Agent 本体不需要 LLM，只执行确定性逻辑/工具（其任务可被规则化）。

### 0. Orchestrator（总调度）
1. **负责**：把人类目标分解为任务 DAG；按依赖派单；维护任务状态机；处理失败（重试/降级/回退/重规划）；推进审批闸门；成本预算控制。
2. **不负责**：任何内容创作与创意判断；不直接操作素材与成片。
3. **输入**：人类目标、项目状态、任务事件流、Critic 挑战、审批结果。
4. **输出**：任务计划（DAG + 依赖 + 优先级）、派单指令、状态推进、异常处置方案、给人类的进度摘要。
5. **模型**：日常派单用 M（deepseek-chat，结构化输出）；**规划/异常重规划用 R（deepseek-reasoner）**。
6. **工具**：DB、File（读）、Message Bus、HITL 服务。**无媒体工具权限**。
7. **通信**：接收所有 Agent 的 TASK_* 事件与 Critic 的 CHALLENGE；向所有 Agent 派单；向人类发进度/审批请求。
8. **独立存在的理由**：需要唯一权威做全局调度与异常仲裁；它是状态机的推进者，缺了它多 Agent 就退化为散乱脚本。

### 1. Project Manager（项目经理）
1. **负责**：总计划与排期、任务优先级、资源与预算冲突预警、里程碑管理、风险登记。
2. **不负责**：内容决策；不直接派单（派单是 Orchestrator，PM 只产出计划供其执行）。
3. **输入**：项目目标、任务清单、各阶段产出规模估计。
4. **输出**：生产计划（阶段/里程碑/优先级/预估耗时成本）、风险清单、变更建议。
5. **模型**：M。
6. **工具**：DB、File（读）。
7. **通信**：与 Orchestrator 双向；接收各 Agent 的进度事件（只读）。
8. **独立存在的理由**：Orchestrator 管"此刻怎么执行"，PM 管"整体何时完成、成本多少、风险在哪"——时间维度与执行维度分离，长项目才有人盯盘。

### 2. Topic（选题）
1. **负责**：按人类方向提出选题候选、选题可行性分析、资料需求清单。
2. **不负责**：最终选题决定；不擅自开始深研。
3. **输入**：人类方向/兴趣域、历史项目经验（经验库）、可选约束（时长/平台）。
4. **输出**：选题提案（每个含：角度、受众、价值主张、可行性、风险、资料需求）。
5. **模型**：M。
6. **工具**：Search（浅检索摸底）、DB、File。
7. **通信**：→ Research；选题经 **人工审批#1**。
8. **独立存在的理由**："做什么"的提案权与"怎么做"的执行权必须分开，否则后续所有 Agent 都会在错误前提上狂奔。

### 3. Research（研究）
1. **负责**：按资料需求搜集、整理、归纳资料；每条资料记录来源与检索路径。
2. **不负责**：判断来源是否可信（交给 SrcVerify）；不写脚本。
3. **输入**：选题 + 资料需求清单。
4. **输出**：资料卡集合（每条：内容摘要/原始来源/检索方式/时间/页码引用）+ 疑点清单。
5. **模型**：M（归纳）＋ 检索工具。
6. **工具**：Search、Browser（可选）、File、DB。
7. **通信**：→ Source Verification；被 SrcVerify/Critic 打回时重搜。
8. **独立存在的理由**：搜集与判断分离——搜集者天然倾向"找到就收"，必须由他人裁判质量。

### 4. Source Verification（来源核查）
1. **负责**：逐一核查资料卡：来源是否一手/权威、引用是否真实存在、多源是否冲突、是否存在被驳斥的信息。
2. **不负责**：补充新事实（那是 Research/Fact-check 的活）；不判断"用不用"（那是 Structure）。
3. **输入**：资料卡集合。
4. **输出**：来源可信度分级表 + 冲突报告 + 不可用资料清单（附理由）。
5. **模型**：R。
6. **工具**：Search（交叉验证）、Browser、File、DB。
7. **通信**：→ Critic 闸门 → Structure；可**否决**资料（打回 Research）。
8. **独立存在的理由**：AI 检索会一本正经地引用不存在的来源；必须有专职裁判，且它要用高推理模型做交叉验证。

### 5. Structure（内容结构）
1. **负责**：把已确认的选题与资料整理成视频结构：章节、信息层级、节奏、时长分配。
2. **不负责**：改变核心观点；不写最终文案。
3. **输入**：选题（已批）+ 可信资料卡。
4. **输出**：结构文档（章节树 + 每章目标/时长/信息点 + 过渡逻辑）。
5. **模型**：M。
6. **工具**：File、DB。
7. **通信**：→ Script；结构经 **人工审批#1**。
8. **独立存在的理由**：结构决定信息骨架；单独成岗是为了让"观点→骨架"这一步被人看见并可改，而不是埋在文案里。

### 6. Script（文案）
1. **负责**：按已确认结构产出旁白/解说/台词（分场、标注画面提示、时长控制）。
2. **不负责**：改结构、改观点；不自行决定事实。
3. **输入**：结构（已批）+ 资料卡。
4. **输出**：脚本（分场文本 + 语气标注 + 预估时长 + 画面提示）。
5. **模型**：M。
6. **工具**：File、DB。
7. **通信**：→ Fact-check ∥ Critic；脚本经 **人工审批#2**。
8. **独立存在的理由**：文案是"事实+观点"的载体，必须与事实核查分离且单独被人审批。

### 7. Fact-check（事实核查）
1. **负责**：逐条核对脚本中的事实、数字、人名、时间、地点、引语。
2. **不负责**：改文风、改结构；只报问题不改写（改写由 Script 打回后执行）。
3. **输入**：脚本 + 可信资料卡。
4. **输出**：核查报告（每条断言：通过/存疑/错误 + 依据 + 修正建议）。
5. **模型**：R。
6. **工具**：Search、File、DB。
7. **通信**：→ Critic → Script（打回）；→ 人工审批。
8. **独立存在的理由**：脚本是成片事实错误的源头；事实核查与来源核查分层，分别盯"陈述"与"出处"。

### 8. Critic（反对者 / Devil's Advocate）——详见 §9
1. **负责**：主动对抗性找问题；挑战任何 Agent 的结论与前提；识别"集体共识陷阱"。
2. **不负责**：提出替代方案（可以提示方向，但方案由原岗重做）；不直接改任何产物。
3. **输入**：任意闸门的产物 + 相关证据链 + 其他 Agent 的结论。
4. **输出**：挑战报告（问题分级：致命/重要/建议；每条附依据与反问；可要求"重做/补充/打回"）。
5. **模型**：R。
6. **工具**：Search（验证质疑）、File、DB。
7. **通信**：→ Orchestrator（由其执行打回/重排）；挑战记录永久存档。
8. **独立存在的理由**：同质化 LLM 之间会互相"自我确认"；必须有一个制度化的反对者角色，把质疑变成流程而非偶然。

### 9. Asset Manager（素材管理）
1. **负责**：素材登记入册（本地视频/图片/音频/文档）、打标签、生成 embedding 索引、记录来源与授权、生命周期（归档/删除申请）。
2. **不负责**：挑选素材（Retrieval）；不决定素材用途。
3. **输入**：素材文件、素材元数据。
4. **输出**：素材库索引（DB）、标签、embedding、授权状态。
5. **模型**：免（embedding 模型算工具不算 Agent 大脑）。
6. **工具**：File、DB、Embedding 工具、FFmpeg（提取元数据/缩略图/波形）。
7. **通信**：向 Retrieval 提供索引；素材删除必须人工确认。
8. **独立存在的理由**：素材是唯一"删了就没了"的资产，必须集中登记、授权留痕，任何 Agent 不得直接翻磁盘。

### 10. Retrieval（素材检索）
1. **负责**：按脚本/镜头清单/剪辑方案，从素材库检索匹配素材，输出候选清单（含匹配理由与时间片段）。
2. **不负责**：最终选用（Editing Planning 定方案、人工可审）；不生成新素材。
3. **输入**：检索需求（语义描述/镜头类型/时长/横竖屏）+ 素材索引。
4. **输出**：候选素材清单（每条：素材ID/片段起止/匹配度/理由/授权状态）。
5. **模型**：免（语义检索用 embedding + 规则）。
6. **工具**：DB、Embedding、FFmpeg（抽帧）。
7. **通信**：→ Editing Planning；向 Asset Manager 反馈缺什么。
8. **独立存在的理由**：检索质量决定成片素材质量；独立成岗才能持续优化索引与检索策略。

### 11. Visual Planning（视觉规划）
1. **负责**：把脚本映射为视觉需求：哪些镜头、图片、图表、动画、AI 生成素材；输出镜头清单与生成提示词。
2. **不负责**：生成素材本身（工具执行）；不决定剪辑节奏（Editing Planning）。
3. **输入**：脚本（已批）+ 现有素材清单。
4. **输出**：镜头清单（每镜：画面描述/景别/时长/来源=素材库或AI生成/生成提示词/风格约束）。
5. **模型**：M。
6. **工具**：File、DB、（生成需求交由 Image/Video 工具）。
7. **通信**：→ Retrieval（找素材）、→ Editing Planning；**关键/AI 素材经人工审批#3**。
8. **独立存在的理由**：视觉需求是"创意→生产"的翻译层；它产出的是**可执行的规格**，不是主观建议。

### 12. Editing Planning（剪辑规划）
1. **负责**：制定剪辑执行计划：时间线结构、镜头排列、转场点、字幕/配音/音效落点、包装节点。
2. **不负责**：动手剪辑（工具执行）；不推翻已批脚本；最终创意判断属于人。
3. **输入**：脚本 + 镜头清单 + 素材候选。
4. **输出**：剪辑方案（时间线 JSON：轨道/片段/转场/时长 + 特效与包装点 + 回退标注）。
5. **模型**：M。
6. **工具**：File、DB、FFmpeg（只读探测：时长/分辨率）。
7. **通信**：→ 剪辑执行（工具层）→ QA；方案可送人工审批#3。
8. **独立存在的理由**：剪辑计划是成片的施工图；"规划"与"执行"分离后，执行层可以是纯工具（ffmpeg/NLE），人工也能直接审图改图。

### 13. Voice（配音）
1. **负责**：按脚本选择/生成旁白音轨：音色方案、TTS 调用、分段生成、时长与语速检查、音轨交付。
2. **不负责**：混音/BGM（Audio）；不改脚本文字（如需改字 → 打回 Script）。
3. **输入**：脚本 + 音色偏好（用户偏好记忆）。
4. **输出**：旁白音轨（分段 + 时间戳 + 音色/模型记录）。
5. **模型**：免（TTS 工具执行；只做参数决策）。
6. **工具**：TTS、File、FFmpeg（时长/采样检查）。
7. **通信**：→ Audio、Subtitle；音色方案可送人工确认。
8. **独立存在的理由**：TTS 有独立的失败模式（超时/音色质量/多音色拼接），且音色是品牌资产，需要专职管理。

### 14. Audio（音频）
1. **负责**：降噪、响度标准化（-14 LUFS 等平台标准）、BGM 选择与打点、音效对齐、混音输出。
2. **不负责**：生成旁白（Voice）；不决定 BGM 的授权（Compliance 复核）。
3. **输入**：旁白音轨 + 剪辑方案 + BGM 素材。
4. **输出**：混音母带 + 混音报告（各轨参数）。
5. **模型**：免（确定性 DSP + 规则）。
6. **工具**：FFmpeg、File、DB。
7. **通信**：→ QA；BGM 授权清单 → Compliance。
8. **独立存在的理由**：音频质量是技术活（响度/降噪/同步），完全可由确定性工具+规则完成，独立成岗避免 LLM 空转。

### 15. Subtitle（字幕）
1. **负责**：ASR 转写（如需）、按脚本生成字幕、校对、按实际音轨对齐时间轴、字幕样式方案、产出 SRT/ASS。
2. **不负责**：修改旁白内容（不一致时报 Subtitle 差异 → Script 裁决）；不负责烧录（剪辑工具执行）。
3. **输入**：脚本 + 旁白音轨（或成片音频）。
4. **输出**：字幕文件（SRT/ASS）+ 校对报告 + 时间轴对齐记录。
5. **模型**：免+小模型（ASR 本地；校对用 cheap 模型；纯规则对轴）。
6. **工具**：ASR、File、DB、Subtitle 工具。
7. **通信**：→ 剪辑执行；与 Voice 的音频对齐。
8. **独立存在的理由**：字幕同时依赖文本与音频两端，且有自己的工具栈（ASR/对轴/样式），合并进任何一方都会职责混乱。

### 16. Thumbnail（封面）
1. **负责**：按成片/脚本产出封面方案（构图/文案/风格）并生成封面候选（图像工具执行）。
2. **不负责**：决定是否采用（人工审批）；不负责平台尺寸适配（Platform Adaptation）。
3. **输入**：成片关键帧 + 标题候选 + 用户风格偏好。
4. **输出**：封面候选图（多方案）+ 设计说明。
5. **模型**：M + 图像生成工具。
6. **工具**：Image、FFmpeg（抽帧）、File。
7. **通信**：→ 人工审批 → Platform Adaptation。
8. **独立存在的理由**：封面是点击率的独立战场，有自己的生产节奏（可与音频生产并行），且高度依赖人类审美审批。

### 17. Platform Adaptation（平台适配）
1. **负责**：按平台规则产出各版本方案：横版/竖版/长短版/B站/YouTube/视频号等（分辨率、时长、封面尺寸、安全区、片头片尾）。
2. **不负责**：发布操作（Publish 工具 + 人工批准）；不决定内容。
3. **输入**：成片 + 平台参数配置。
4. **输出**：多版本生产方案（每版：目标平台/规格/裁剪策略/时长策略）。
5. **模型**：M。
6. **工具**：FFmpeg（执行各版本导出由工具层完成）、File。
7. **通信**：→ Metadata、导出工具。
8. **独立存在的理由**：平台规则频繁变化（如 B 站横屏 vs 抖音竖屏安全区），集中管理避免每个项目重复踩坑。

### 18. Metadata / SEO（元数据）
1. **负责**：标题、简介、标签、关键词、章节、描述等元数据方案（多平台）。
2. **不负责**：标题党（受 Critic/Compliance 约束）；不决定发布。
3. **输入**：成片 + 脚本 + 平台适配方案。
4. **输出**：元数据方案（每平台一套）+ 关键词依据。
5. **模型**：M。
6. **工具**：File、DB、Search（关键词热度可选）。
7. **通信**：→ 人工（随发布审批#5 一并确认）。
8. **独立存在的理由**：SEO/元数据是独立专业知识域（平台算法、关键词），且有独立合规风险（标题党），单列便于专项治理。

### 19. Compliance（合规）
1. **负责**：全链路合规检查：版权（素材/音乐/字体/图像授权）、敏感内容、平台规范、品牌安全。
2. **不负责**：修改内容（只报风险与替代建议）；不替代法律意见。
3. **输入**：全链路产物（脚本/素材清单/成片/元数据）。
4. **输出**：合规报告（风险分级 + 处置建议：可用/需替换/需授权/禁发）。
5. **模型**：R。
6. **工具**：File、DB、授权登记表（知识库）。
7. **通信**：→ 人工；**有权阻止发布**（把发布任务置 BLOCKED）。
8. **独立存在的理由**：合规问题会造成下架/侵权/封号；必须独立于生产链，且拥有"一票拦截"权。

### 20. QA（最终质检）
1. **负责**：对成片做验收：技术质检（黑帧/爆音/音画同步/时长/编码/分辨率，确定性工具自动跑）+ 内容质检（对照脚本与方案核对完整性）。
2. **不负责**：挑战创意本身（那是 Critic）；不决定通过（通过=人工审批#4）。
3. **输入**：成片 + 脚本 + 剪辑方案 + 各阶段规格。
4. **输出**：QA 报告（技术指标实测值 + 内容核对表 + 结论：通过/需返修项清单）。
5. **模型**：免（技术项）+ M（内容核对）。
6. **工具**：FFmpeg/FFprobe、File、DB。
7. **通信**：→ 人工审批#4；返修 → Orchestrator 回退到对应生产节点。
8. **独立存在的理由**：验收必须是独立第三方；QA 与 Critic 分工见 §9。

### 21. Data Analyst（数据分析）
1. **负责**：发布后回收各平台数据，产出复盘报告（完播/互动/流量来源），把可复用经验写入经验库。
2. **不负责**：实时运营响应（V3 再说）；不替人类定下一期选题（只提供数据事实）。
3. **输入**：平台数据（手动导出/API）+ 项目过程数据。
4. **输出**：复盘报告 + 经验条目（写入 Memory 经验库）。
5. **模型**：M。
6. **工具**：DB、File、Search（行业基准可选）。
7. **通信**：→ 人类、经验库。
8. **独立存在的理由**：闭环的关键——没有数据回收，系统就永远是"一次性流水线"而不是"会变强的团队"。

---

## 4. 通信协议（Agent Message / Task Message）

### 4.1 数据结构（SQLite 表 = 权威状态；JSON 仅作为 API/展示格式）

**TaskRecord（任务）**
```json
{
  "task_id": "t_8f3a...",           // 全局唯一
  "project_id": "p_0001",
  "parent_task_id": null,            // 依赖链根
  "lineage": ["t_1", "t_5"],         // 回退定位用：完整祖先链
  "task_type": "research",
  "agent_role": "research",
  "status": "RUNNING",               // 见状态机
  "priority": 3,
  "dependencies": ["t_4"],           // 前置任务 ID
  "inputs": {                        // 全部为引用，不内嵌大文本
    "brief_ref": "a_brief_002",
    "source_cards_ref": ["a_src_017"]
  },
  "expected_output": {
    "schema": "research_output.v1",
    "artifact_types": ["source_cards", "doubt_list"]
  },
  "artifacts": ["a_src_021"],        // 本次产出（引用）
  "evidence": ["query_x", "url_y"],  // 证据链引用
  "confidence": 0.0,                 // 0-1，Agent 自评
  "model": {"name": "deepseek-chat", "tokens": 8231, "cost_usd": 0.004},
  "tools_used": ["search", "file.read"],
  "retry_count": 0,
  "max_retries": 2,
  "error": null,                     // {code, message, trace_ref}
  "requires_approval": false,
  "approval": null,                  // {state, by, comment, at}
  "created_at": "...", "updated_at": "...",
  "version": 1                       // 每次重做 +1；下游引用版本号
}
```

**EventRecord（事件，append-only 日志 = 消息总线的持久形态）**
```json
{
  "event_id": 10023,
  "ts": "...",
  "project_id": "p_0001",
  "task_id": "t_8f3a",
  "type": "TASK_FAILED",            // 枚举见下
  "actor": "research",
  "payload": {"error_code": "SEARCH_TIMEOUT"},
  "human_visible": true             // 是否推送给人的仪表盘
}
```
事件类型：`TASK_CREATED / TASK_DISPATCHED / TASK_STARTED / TASK_PROGRESS / TASK_SUCCEEDED / TASK_FAILED / TASK_RETRYING / TASK_BLOCKED / TASK_ROLLED_BACK / ARTIFACT_CREATED / ARTIFACT_UPDATED / CHALLENGE_RAISED / REVIEW_REQUESTED / REVIEW_DECIDED / HUMAN_NOTE`

**ArtifactRecord（产物，append-only，永不覆盖）**
```json
{
  "artifact_id": "a_src_021",
  "project_id": "p_0001",
  "task_id": "t_8f3a",
  "type": "source_cards",
  "path": "projects/p_0001/artifacts/a_src_021.json",
  "sha256": "...",
  "size": 12345,
  "provenance": {"agent": "research", "tools": ["search"]},
  "license": {"status": "checked", "ref": "lic_008"},
  "version": 1,
  "superseded_by": null
}
```

**DecisionRecord（已确认决策——系统的"法律"）**
```json
{
  "decision_id": "d_0012",
  "project_id": "p_0001",
  "node": "TOPIC_APPROVED",
  "made_by": "human",                // human | agent
  "state": "APPROVED",               // APPROVED / REJECTED / CHANGES_REQUESTED
  "rationale": "...",
  "artifact_snapshot": ["a_brief_002", "a_topic_003"]
}
```

### 4.2 任务状态机

```
                  ┌──────────────┐  人工裁定    ┌─────────────┐
        ┌─────────│ NEEDS_REVIEW │─────────────▶│  APPROVED   │──▶ SUCCEEDED
        │         └──────────────┘  APPROVE     └─────────────┘
        │                │ REJECT / CHANGES_REQUESTED
        │                ▼
PENDING ─▶ DISPATCHED ─▶ RUNNING ─┬─▶ SUCCEEDED
        ▲                         ├─▶ FAILED ──▶ (retry_count<max) ──▶ RUNNING
        │                         │                 │
        │                         │                 └──(超限)──▶ BLOCKED ──人工介入──▶ 重规划/回退
        │                         └─▶ BLOCKED（等素材/等密钥/等人工）
        └────── ROLLED_BACK（上游重做，本任务标记 SUPERSEDED，重新派单）
```

### 4.3 消息纪律（如何避免 Agent 之间发无关自然语言）

1. **任务消息只允许结构化字段 + 引用**：输入/输出都是 artifact 引用，正文自然语言 > 2KB 必须落盘为 artifact。
2. **讨论即文档**：Agent 想"多说两句"必须写成结构化文档（如 Critic 的挑战报告），走 ARTIFACT_CREATED 事件。
3. **订阅制**：Agent 声明自己订阅的事件类型；不相关事件不投递，避免噪声。
4. **摘要即接口**：每个产物要求带 `summary` 字段（≤200 字），下游先读摘要再决定是否读全文。
5. **共享状态 = 唯一真相**：Agent 不互相"转告状态"；状态变化由 Bus 广播事件，谁关心谁订阅。这保证一个 Agent 修改内容后，其他 Agent 通过 `ARTIFACT_UPDATED + version+1` 事件立即知晓。

### 4.4 存储选型结论（JSON / DB / MQ / 事件总线 / 共享状态 → 组合）

| 层 | V1 选型 | 理由 |
|---|---|---|
| 权威状态（任务/决策/产物/审批） | **SQLite（WAL）** | 单机零运维、事务保证回滚一致、可查询可审计 |
| 消息总线 | **SQLite 队列（task 表 + event 表 + 轮询/触发器）** | V1 单机足够；表即队列，天然持久、可重放 |
| 大 payload（脚本/成片/素材） | **文件系统 + 引用** | 视频不进数据库；DB 存路径与校验和 |
| 事件日志 | **append-only 表** | 审计、复盘、调试 |
| 缓存/热数据 | 进程内存 | 加速派单，不承担持久化 |
| V2+ 可选升级 | Redis Streams / RabbitMQ、MySQL/PostgreSQL | 接口不变，替换总线与 DB 实现即可 |

---

## 5. 完整视频生产生命周期（含并行/串行/回退标注）

```
人类目标 "我想做一期…"
   │
   ▼
[P0 立项] Orchestrator 建项目 → PM 出生产计划 →（计划可审，非必须）
   │
   ▼
[P1 策划]  Topic 选题提案 ──▶ 人工审批#1（选题+核心观点）◀── 拒绝→回Topic
   │ 通过
   ├──▶ Research 搜集 ◀──┐          （并行）
   │        │            │ 打回
   │        ▼            │
   └──▶ Source Verification ──▶ Critic 挑战 ──▶ Structure 结构
            （可信资料卡）                        │
                                   人工审批#2（结构）◀── 拒绝→回Structure
   │ 通过
   ▼
[P2 脚本] Script 文案 ──▶ Fact-check ∥ Critic 挑战 ──▶（可循环打回）
   │
   ▼
人工审批#3（最终脚本）◀── 修改/拒绝→回 Script 或 Structure
   │ 通过
   ▼
[P3 视觉与素材]（三路并行）
   ├── Visual Planning 镜头清单 ─┐
   ├── Asset Manager 盘点 + Retrieval 检索 ─┤──▶ Editing Planning 剪辑方案
   └──（缺口）AI 图像/视频生成（工具层）──────┘            │
                                            人工审批#4（关键素材+AI素材+剪辑方案）
   │ 通过                                   ◀── 拒绝→回对应节点
   ▼
[P4 音频]（两路并行）
   ├── Voice TTS 旁白 ──┐
   └── Subtitle 初稿 ───┴──▶ Audio 降噪/混音/BGM ──▶ Subtitle 按音频对轴
   │
   ▼
[P5 装配] 剪辑执行（FFmpeg/NLE 工具按剪辑方案装配）──▶ 调色/包装 ──▶ Thumbnail 封面候选
   │
   ▼
[P6 质检]（三路并行）
   QA 技术+内容 ∥ Compliance 合规 ∥ Critic 终审挑战
   │ 全部通过
   ▼
人工审批#5（最终成片）◀── 返修→回退到对应生产节点（P3/P4/P5）
   │ 通过
   ▼
[P7 发布] Platform Adaptation 多版本 ──▶ Metadata/SEO ──▶ 人工审批#6（发布批准）
   │ 通过
   ▼
Publish 工具发布（V1 可"导出+清单"，实际发布由人执行）
   │
   ▼
[P8 复盘] Data Analyst 回收数据 → 复盘报告 → 经验入库 → 反哺下个项目
```

**并行性总结**：P3 三路并行（视觉规划/素材检索/生成）；P4 双路并行（配音/字幕初稿）；P6 三路并行（QA/合规/Critic）。
**串行硬依赖**：选题→研究→来源核查→结构→脚本（前一步是后一步的事实前提）；混音必须在配音后；成片装配必须在全部素材与音轨后。
**可重复执行**：Research、Script、剪辑执行、QA（幂等，重跑产生新版本）。
**失败回退锚点**：脚本失败→回 P2 起点；素材失败→回 P3 对应支路；质检失败→回 P4/P5 对应节点；**任何回退不越过最近的人工审批锚点**——已批决策除非人类同意，否则不回退。

---

## 6. 记忆系统（短期 + 长期 + 项目库 + 知识库）

| 层 | 存什么 | 谁写 | 生命周期 | 注入方式 |
|---|---|---|---|---|
| 1. 任务上下文（Working Context） | 本次任务装配：项目摘要+相关决策+输入产物摘要+该 Agent 自我记忆 | Orchestrator 装配 | 单次任务 | 直接进 prompt（≤预算上限） |
| 2. 项目记忆（Project DB） | 该项目的任务/决策/产物/审批/事件全集 | 全体 | 项目周期 | 按需查询（摘要/检索） |
| 3. Agent 自我记忆 | 每个 Agent 的心得/风格偏好/教训（如"上次 BGM 太响被退"） | Agent 自己（任务结束写心得字段） | 长期 | 装配时注入（≤1KB） |
| 4. 全局规则 | 系统规则/SOP/权限表/提示词版本/审批策略 | 管理员（人） | 长期 | 每次运行必读（只读） |
| 5. 经验库（Experience Library） | 历史项目复盘→可复用经验条目（带标签、评分、反例） | Data Analyst 沉淀 | 长期 | 检索式注入（相似项目 top-K） |
| 6. 用户偏好（User Profile） | 风格/品牌/音色/常用平台/审批习惯 | 人 + 系统记录 | 长期 | 相关 Agent 装配时注入 |
| 7. 知识库（Knowledge Base） | 已验证事实卡、可信来源表、授权素材/音乐/字体清单 | SrcVerify/Compliance 维护 | 长期 | 检索注入 |

**防"塞爆上下文"的纪律**：
1. 装配预算制：每任务 context 有 token 上限，超限走"摘要+检索"而非截断硬塞。
2. 里程碑摘要：每个审批闸门处由 Orchestrator 生成项目里程碑摘要，替代全量历史。
3. 长任务压缩：任务完成即固化产物与心得，过程细节只留事件日志（可查，不进 prompt）。
4. 记忆也走 Artifact 版本制：记忆条目可被新证据 supersede，但永不删除。

---

## 7. 工具层（Tool Layer）

**接口契约（Agent 唯一操作世界的入口）**
```python
class Tool(Protocol):
    name: str
    version: str
    input_schema: dict      # JSON Schema，LLM 据此生成参数
    output_schema: dict
    permissions: list[str]  # 需要的权限令牌
    def execute(self, inputs: dict, ctx: ToolContext) -> ToolResult
    def estimate_cost(self, inputs: dict) -> float
```
**设计理由**：Agent 与工具解耦——换 ffmpeg 实现、换 TTS 供应商、换数据库，Agent 代码与提示词零改动；权限、成本、审计在工具层统一强制（Agent 无法绕过）；工具可被 mock（测试/演示模式）。

**V1 工具清单与选型**

| 工具 | V1 实现 | 备注 |
|---|---|---|
| FileTool | 本地文件（沙箱路径白名单） | 只允许项目目录内读写 |
| FFmpegTool | 本地 ffmpeg/ffprobe | 剪辑/合成/字幕烧录/转码/探测 |
| ASRTool | faster-whisper 本地（或 API 可切换） | 字幕转写 |
| TTSTool | edge-tts 默认（免费），可切换云端 TTS | 接口统一 |
| SearchTool | 可切换 provider（默认用户填密钥的搜索 API） | 接口统一 |
| BrowserTool | V2（Playwright） | V1 用 Search 替代 |
| ImageTool | 云端图像生成 API（可切换） | 未填密钥=禁用并提示 |
| VideoTool | 云端视频生成 API（可切换，V1 可选） | 同上 |
| SubtitleTool | SRT/ASS 解析、对轴、样式 | 本地库 |
| DatabaseTool | SQLite 封装（即系统内部 DB 的受控视图） | Agent 不得绕过 |
| NLETool | V2：生成剪映/DaVinci 项目文件 | V1 用 FFmpeg 装配 |
| ExportTool | 多版本导出（分辨率/时长/格式） | 纯 FFmpeg |
| PublishingTool | V1="生成发布包+清单"，实际发布人工执行 | V3 接平台 API |

**权限模型**：每个 Agent 角色绑定能力令牌（如 `file.read:project`、`ffmpeg.render`、`search.web`）；工具层执行前校验令牌并写审计日志；敏感工具（删除/发布/覆盖已批产物）额外要求人工审批令牌。

---

## 8. Human-in-the-loop（人工审批节点）

**强制审批节点（6 个闸门）**：
1. **选题 + 核心观点**（Topic 提案后）
2. **内容结构**（Structure 后）
3. **最终脚本**（Fact-check/Critic 通过后）
4. **关键素材 + AI 生成素材 + 剪辑方案**（P3 后）
5. **最终成片**（QA/Compliance/Critic 通过后）
6. **发布**（元数据齐备后）

**审批流协议**：
```
Agent 提交（附：方案摘要 + 关键产物引用 + 风险提示）
   → HITL 服务生成 ReviewRequest（状态 NEEDS_REVIEW，任务挂起）
   → 人类三选一：Approve / Reject（附理由，回退锚点）/ Modify（附修改意见，原岗重做）
   → 结果写入 DecisionRecord（永久留痕）
   → Orchestrator 依结果推进 / 回退 / 重规划
```

**分级策略**：闸门内"必审项"（观点、脚本、成片、发布）不可跳过；"可审项"（计划、音色、封面方案）默认自动通过但人类可随时介入；所有审批决定进入项目记忆，供复盘。

---

## 9. Critic Agent 专项设计

**定位**：制度化的反对者。不产出内容，只产出"挑战"。

**运行时机**（闸门模式）：选题后、结构后、脚本后、素材方案后、成片终审前——至少 5 个固定挑战点；此外可被 Orchestrator 在任意异常时临时征召。

**挑战报告结构**：
```json
{
  "challenge_id": "c_0042",
  "target": {"task_id": "t_8f3a", "artifact_id": "a_script_009"},
  "verdict": "REWORK",            // PASS / REWORK / BLOCK / NEED_EVIDENCE
  "issues": [
    {
      "severity": "fatal|major|minor",
      "category": "logic|fact|source|narrative|omission|bias|redundancy|clickbait|copyright|echo",
      "claim": "第3段把‘A先于B’表述成‘A导致B’",
      "challenge": "两者只是时间相关，脚本却用了因果连词。有无控制变量证据？",
      "required_action": "rewrite|evidence|rollback|consult_human"
    }
  ],
  "meta_note": "全体 Agent 一致选方案A，但前提‘X成本高’来自同一份未核验资料——需要独立复核" 
}
```

**与 QA 的本质区别**：
| | QA | Critic |
|---|---|---|
| 立场 | 中立验收 | 有罪推定 |
| 依据 | 事先定义的清单/规格 | 清单之外的反例、前提、共识盲区 |
| 产物 | 通过/返修项清单 | 挑战报告（要求重做/补证/拦截） |
| 权力 | 打回具体技术项 | 可要求**重做上游任务**、质疑集体共识、建议人工介入 |
| 风格 | 全查 | 找最痛的点打 |

**权限**：Critic 无权直接修改任何产物；其"否决"通过 Orchestrator 生效（ROUND_TRIP：打回→重做→再挑战，最多 N 轮，N 轮仍不通过则升级人工裁决）。挑战记录与最终处置永久存档。

---

## 10. 故障恢复（Retry / Fallback / Rollback / Human Intervention）

**统一策略表**（按故障类别）：

| 场景 | 重试 | 降级/替换 | 回退 | 人工介入 |
|---|---|---|---|---|
| Research 失败（搜索超时） | 指数退避×2 | 换 Search provider | 不必要 | 超限→BLOCKED |
| LLM 输出不合 Schema | 同模型×1 | deepseek-chat→deepseek-reasoner→本地模型 | 回任务起点 | 仍失败→BLOCKED |
| TTS 失败 | 同源×2 | edge-tts→API TTS A→B | 保留音色方案，重跑生成 | 多源全败→BLOCKED |
| 剪辑执行失败 | —（确定性） | 换编码参数/简化转场 | **回 Editing Planning**（改方案）| 方案矛盾→人工审方案 |
| Agent 输出错误被 Critic 发现 | — | — | 回退到该 Agent 的输入锚点重做（版本+1） | N 轮循环→人工裁决 |
| 素材缺失 | — | Retrieval 换关键词/Visual 改需求 | 回 Visual Planning 补需求 | 需新素材→人工审批#4 |
| 合规拦截 | — | 替换素材/音乐/措辞 | 回对应生产节点 | 重大风险→人工定夺 |
| 崩溃/断电 | — | — | **WAL + MANIFEST 恢复**：重启后 Orchestrator 扫描 RUNNING 任务→标记 INTERRUPTED→按幂等规则重跑 | 状态摘要推给人 |

**回退实现**：任务 lineage + 版本号。回退 = 找到锚点任务，下游全部标记 `SUPERSEDED`，从锚点以 version+1 重派；产物 append-only，旧版本保留（随时可对比）。
**人工介入通道**：任何 BLOCKED 任务都进入人类仪表盘，支持三种指令：`继续原方案 / 换方案 / 终止`；人类可直接在任何闸门注入"人工备注"进入项目记忆。

---

## 11. 质量体系（多层，而非只有 QA）

| 层 | 负责者 | 手段 |
|---|---|---|
| 内容质量 | Structure + Script + 人工审批 | 结构评审、脚本审批 |
| 事实质量 | Source Verification + Fact-check | 分层核查（来源→陈述） |
| 逻辑质量 | Critic | 因果/反例/遗漏/共识盲区挑战 |
| 视觉质量 | Visual Planning + 人工审批#4 | 镜头规格与素材审批 |
| 音频质量 | Audio + QA | 响度/降噪/同步自动检测 |
| 技术质量 | QA（确定性工具） | 黑帧/爆音/同步/时长/编码 |
| 版权质量 | Compliance | 授权登记核对、一票拦截 |
| 平台质量 | Platform Adaptation + Metadata + QA | 规格校验、多版本检查 |

---

## 12. 权限边界（Agent 不允许做什么）

**系统级禁令（工具层强制 + Orchestrator 校验 + 审计日志）**：
1. 不得改变已确认决策（选题/观点/结构/脚本/成片）——修改=新提案+审批。
2. 不得发布视频（Publish 工具要求人工批准令牌）。
3. 不得删除/覆盖原始素材与已批产物（append-only；删除需人工审批）。
4. 不得修改已确认脚本（打回由 Script Agent 重做并重审）。
5. 不得绕过审批闸门（状态机强制 NEEDS_REVIEW）。
6. 不得把未验证信息当作事实（必须标注 evidence/confidence）。
7. 不得伪造来源、证据、引用。
8. 不得修改其他 Agent 的历史任务记录与事件日志（append-only 表，无 UPDATE 权限）。
9. 不得隐藏失败任务（FAILED 必须发事件并可见）。
10. 不得删除错误日志（日志是审计资产）。
11. 不得读取项目目录之外的文件（FileTool 沙箱白名单）。
12. 不得读取明文 API 密钥（密钥只存配置，工具层内部使用，Agent 只见 masked 引用）。
13. 不得自我修改权限令牌（权限表仅管理员可改）。
14. Critic 不得直接改产物（只能发起挑战）。

---

## 13. 模型选择与成本控制

| 档位 | 模型 | 用于 | 理由 |
|---|---|---|---|
| R（推理档） | deepseek-reasoner | Orchestrator 规划/异常重规划、Critic、Fact-check、Source Verification、Compliance | 需要多步推理/交叉验证/找漏洞 |
| M（平衡档） | deepseek-chat | Topic、Research 归纳、Structure、Script、Visual/Editing Planning、Thumbnail、Metadata、Data Analyst、QA 内容核对 | 结构化产出，性价比高 |
| F（快速/本地档） | deepseek-chat 或本地小模型 | Subtitle 校对、摘要生成、标签补全 | 低难度批量任务 |
| 免（无 LLM） | — | Asset/Retrieval（embedding+规则）、Voice（TTS 工具）、Audio（DSP）、Subtitle 对轴、QA 技术项、导出、FFmpeg | 确定性任务，用 LLM 是浪费 |

**成本纪律**：每任务记录 tokens/cost；每 Agent 有单任务预算；Orchestrator 监控项目总预算并预警；经验库记录"哪些任务其实不需要 R 档"。

---

## 14. 开发路线 V1 / V2 / V3

**V1（单机可用，现在就能开发）**
- Python 3.12+ / Windows / SQLite(WAL) / 本地 ffmpeg+faster-whisper / edge-tts / DeepSeek API
- 22 Agent 全量上线（骨架+提示词+Schema）；任务引擎/状态机/消息总线（SQLite）/工具层/HITL/Memory 全部实现
- CLI 交互 + 简单进度仪表盘（终端表格）；发布=导出+人工执行
- 端到端测试：mock LLM 全流程 + 真实 ffmpeg 成片

**V2（扩展）**
- 本地模型接入（ollama）替代部分 F 档；浏览器工具（Playwright）；NLE 工具（剪映/DaVinci 工程文件）
- Web UI（FastAPI）；多项目并行；Redis/RabbitMQ 可选；MySQL/PostgreSQL 可选
- 经验库检索增强（向量库）；平台数据 API 直连

**V3（规模化）**
- 多用户/权限体系；云端部署；媒体资产服务器；发布平台 API 自动化；运营看板；Agent 市场（自定义 Agent/工具插件）

---

## 15. 推荐项目目录结构（V1）

```
video-studio/
├── README.md                      # 总览、快速开始、断线恢复说明
├── STATUS.md                      # 建设进度清单（断点续做的依据）
├── pyproject.toml                 # Python 工程
├── config/
│   ├── config.example.yaml        # 密钥/模型档位/平台参数/审批策略
│   └── rules.yaml                 # 全局规则/SOP/权限表（管理员维护）
├── docs/
│   └── DESIGN.md                  # 本文档
├── src/video_studio/
│   ├── core/                      # 任务引擎、状态机、消息总线、调度器
│   ├── agents/                    # 每 Agent 一个模块：提示词+IO Schema+装配逻辑
│   │   ├── orchestrator/  pm/  topic/  research/  source_verify/
│   │   ├── structure/  script/  fact_check/  critic/
│   │   ├── asset/  retrieval/  visual/  editing/
│   │   ├── voice/  audio/  subtitle/  thumbnail/
│   │   ├── platform/  metadata/  compliance/  qa/  analyst/
│   ├── tools/                     # Tool Layer：接口 + 各工具实现（可 mock）
│   ├── memory/                    # 各记忆层 repository、装配器、压缩器
│   ├── hitl/                      # 审批服务
│   ├── llm/                       # 模型路由、成本计量、schema 校验
│   ├── pipeline/                  # 生产生命周期定义（阶段/依赖/闸门）
│   ├── db/                        # SQLite schema、迁移
│   └── cli.py                     # 命令行入口（创建项目/推进/审批/状态）
├── tests/                         # 单测 + mock 端到端
└── projects/                      # 运行时数据（每项目一个目录，gitignore）
    └── p_0001/
        ├── manifest.json          # 项目状态清单（断点恢复）
        ├── artifacts/             # 全部产物（append-only）
        ├── media/                 # 素材与中间文件
        └── output/                # 成片与发布包
```

---

## 16. 关键决策记录（ADR 摘要）

| # | 决策 | 理由 |
|---|---|---|
| 1 | 架构选 D（Orch+Bus+State） | 避免蜘蛛网/单点瓶颈，状态可恢复 |
| 2 | V1 用 SQLite 做总线 | 单机零运维、天然持久、够用 |
| 3 | 消息只传结构化+引用 | 成本可控、可审计、可回放 |
| 4 | Critic 单独成 Agent | 对抗性与验收是两种职能 |
| 5 | 来源核查与事实核查分设 | 盯"出处"与盯"陈述"的失败模式不同 |
| 6 | 模型分 R/M/F/免 四档 | 成本与质量平衡 |
| 7 | 6 个人工审批闸门 | 人在关键决策点，而非事事都审 |
| 8 | 产物 append-only + 版本化 | 回退与审计的基础 |
| 9 | 工具层统一接口 | Agent 与工具解耦，可替换可 mock |
| 10 | 发布 V1 由人执行 | 降低风险，V3 再自动化 |
