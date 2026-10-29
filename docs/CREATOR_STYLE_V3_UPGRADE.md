# Creator Style v3 升级报告（红线 + 留存工程 · 内容创作层）

> 版本：Creator Style v3 ｜ 权威文本：`config/script_style_guide.md`（v3）
> 依据：Phase 8 授权书（2026-09-30）｜ v2 全文快照：`docs/regression_2x/phase8_style_v2_snapshot.md`
> （sha256 `17e6439271dcfed835581cf04d2119d8a773c30191baf10ad53f610dbdfd8465`）
> 边界：本阶段**只改内容创作层**（规范文本 + script/structure 两个 agent 的 schema 与提示词）；
> 未改管线结构、未改渲染、未改评测栈、未替换任何素材、未重渲、未发布。

## 1. 问题（v2 的实证后果）

v2 把优先级写成**单条线性链**：

```
Truth/Evidence > Claim 边界 > 事实准确性 > 逻辑完整性 > 叙事效果 > 文风 > 华丽表达
```

实践结果是所有项都可被拿来互相权衡，"严谨"压过一切：
p_96efdc03e1aa v9（1532 s，真实素材 + 真实旁白）**无情绪节拍、无互动引导、结尾刻意反高潮**，
人工验片 **FAIL**（`docs/KNOWN_ISSUES.md` **#67**："不得作为发布候选"，与工程门禁 PASS 并存不矛盾）。
一句话：**严谨但没人看完**。

## 2. v3 的改造思路：红线层 + 优化层

| 层 | 内容 | 性质 |
|---|---|---|
| **红线层** | Truth/Evidence、Claim 边界、事实准确性 | **准入条件**，不可违反、不可交易 |
| **优化层** | 完播/留存 > 叙事张力 > 文风 | 红线内**最大化**，按序优化 |

总纲：**宁可少说，不可说错；在不说错的前提下，一切技巧为留存服务。**
红线**没有变严也没有放松**（条文逐条保留），只是**不再参与权衡**：v2 的"逻辑完整性"并入
优化层的"叙事张力"，"留存"从缺位提升为优化层第一位。

## 3. 实现（改动清单）

| 文件 | 改动 | 性质 |
|---|---|---|
| `config/script_style_guide.md` | 升级 v3：两层优先级 + 留存工程（Hook 纪律 / 情绪节拍 / CTA 纪律 / 留存不得越界）+ v2 全部条款逐条保留（3.1–3.16） | 覆盖式升级（v2 快照另存） |
| `src/video_studio/agents/script/agent.py` | **加法**：`segments[].emotion_beat`（enum 5 值）、`segments[].retention_device`、顶层 `cta_plan[]`、`hook_map[]`；提示词载入 v3 并新增"留存元数据纪律"（4 条，含"绝不写进 narration"） | 既有字段/required 一律未改未删 |
| `src/video_studio/agents/structure/agent.py` | **加法**：每章 `hook`、`hook_interval_ok`；提示词新增"章节钩子衔接 + 连续 90 秒无信息增量点视为结构缺陷（如实标注、不得改数据凑通过）" | 既有约束（不改人类已确认核心观点）保留 |
| `tests/strip_v2_test.py` | **扩展**断言：脚本夹具加入 v3 元数据 + 哨兵；新增 7 项下游隔离检查（voice/SRT/SRT 文件/ASS/metadata/发布稿/朗读稿） | 不新造链路 |
| `tests/pipeline_mock.py` | **扩展**断言：管线级扫描全部用户可见产物 + ASS，断言无 v3 元数据字段名 | 不新造链路 |
| `tests/creator_style_v3_test.py` | 新增（§4 主测试） | 新文件 |

## 4. 留存工程（v3 新增章节摘要）

1. **Hook 纪律**：前 20-40 秒认知冲突（沿用 v2）+ **每 60-90 秒必须出现信息增量点/悬念/反转**；
   信息增量点必须是内容性的（新事实/新证据/被推翻的直觉/代价/限制/反转），空泛悬念不算。
2. **情绪节拍**：`emotion_beat ∈ {curiosity, tension, payoff, calm, surprise}`；
   **全篇不得连续 3 个同类节拍**；节拍是元数据，不写进 narration。
3. **CTA 纪律**：全片 **1-2 处**、必须与内容强绑定；**禁止裸话术**（感谢观看/一键三连/记得点赞关注/
   我们下期再见…）；结尾由"纯反高潮"改为"**收束观点 + 至多 1 句内容型互动**"。
4. **留存不得越界**：禁止假钩子、夸大证据、把推测写成事实、删关键限定词、制造不存在的因果。

## 5. 下游隔离证明（硬性，§3.4）

机制：v3 元数据只存在于 script 内部产物；`core/narration.py::narration_text` 只读 `narration`
（并剥离 `[CLAIM:…]`）；subtitle 由 `narration` → `build_cues` → SRT/ASS；metadata/publish/narrate
均从 narration 派生。**证据**：

| 证据 | 内容 | 结果 |
|---|---|---|
| `tests/creator_style_v3_test.py` | 哨兵值（`V3SENTINEL_*`）经真实 agent 链路：voice 计划 / SRT / SRT 文件 / ASS / metadata 正文 | **27/27 PASS** |
| `tests/strip_v2_test.py`（扩展） | 夹具脚本含 v3 元数据；voice/SRT/SRT 文件/ASS/metadata/发布稿/朗读稿 + "内部产物保留元数据可追溯" | **21/21 PASS** |
| `tests/pipeline_mock.py`（扩展） | 26 任务全管线：扫描全部用户可见产物 + ASS 断言无 v3 字段名 | **14/14 PASS** |

**诚实边界**：`pipeline_mock` 的 mock 脚本默认不含 v3 字段，因此它的守卫证明的是"管线不会把 v3
元数据搬进用户可见文本"（防回归）；"**带 v3 取值的脚本**仍不泄漏"由 `strip_v2_test` 的哨兵用例与
`creator_style_v3_test` 的哨兵链路证明。

## 6. 机器可校验性（为下一阶段 retention-critic 预留）

`tests/creator_style_v3_test.py` 内含纯函数 `validate_script_v3(script)`，逐条机器判定：

| 违规码 | 含义 |
|---|---|
| `V3_BEAT_ENUM` | 非法 emotion_beat |
| `V3_BEAT_RUN3` | 连续 3 个同类节拍 |
| `V3_CTA_TOO_MANY` | cta_plan > 2 |
| `V3_CTA_BARE` | 出现裸话术 |
| `V3_CTA_NO_TYPE` | CTA 缺类型 |
| `V3_HOOK_MAP_SIZE` | hook_map ≠ 3 项 |
| `V3_META_IN_NARRATION` / `V3_BEAT_NAME_IN_NARRATION` | 元数据写进正文 |

该函数当前位于测试文件内（授权书 §5 的交付物清单未包含新工具模块）；下一阶段若接入
retention-critic，可原样提取为 `tools/creator_style_v3.py`（本阶段不动）。

## 7. 真实 LLM 离线 A/B（§4）

见 `docs/regression_2x/PHASE8_REPORT.md` 与 `docs/regression_2x/logs/phase8_ab_v2.json` /
`phase8_ab_v3.json`（含两臂全文、提示词全文、tokens/费用/时延、同一套指标）。
**A/B 过程中的真实技术发现**：`deepseek-flash` 是**推理模型**，`reasoning_content` 与 `content`
**共享 `max_tokens`**；尝试 1（4096）与尝试 2（8192）的预算被推理吃满 ⇒ `content` 为空
（两次尝试均已留档，成本已计入台账）。这是**LLM 档位与预算的诊断发现**，不是规范差异
（两臂同样受影响）——档位配置本身**未被修改**。

## 8. 与既有冻结边界的关系

- **未触碰**：`core/mm_*.py`、`core/semantics.py`、`core/multimodal.py`、mm truth 夹具、词表、
  历史 baseline 与不可变快照（含 Phase 7 的 proposal register / execution ledger /
  `P7_WORKING_TIMELINE` / `visual_binding` 两份 artifact）、`core/integrity.py` 的 PI/DQ 门禁逻辑、
  `core/visual_binding.py`、`ops/visual_binding.py`、素材 provider 配置、**LLM 档位配置**。
- **未做**：自动换素材（含 S05 的 REPLACE 提案——保持提案态）、自动重渲 v9、自动发布、
  critic 改造、选题数据接入、视觉层改动。
- **台账纪律**：本阶段新增产物只增不改历史；v2 规范文本另存快照（未覆盖式丢失）。

## 9. 产物

- `config/script_style_guide.md`（v3 权威规范）
- `src/video_studio/agents/script/agent.py`、`src/video_studio/agents/structure/agent.py`（加法 schema + v3 提示词）
- `tests/creator_style_v3_test.py`（新增）、`tests/strip_v2_test.py` / `tests/pipeline_mock.py`（扩展断言）
- `docs/CREATOR_STYLE_V3_UPGRADE.md`（本文件）
- `docs/regression_2x/PHASE8_REPORT.md`、`docs/regression_2x/phase8_style_v2_snapshot.md`
- `docs/regression_2x/logs/phase8_ab_v2.json`、`phase8_ab_v3.json`（+ 两次失败尝试的留档）
