# Creator Style v2 升级报告（2.x 冻结架构内 · Style 层修正）

> 版本：Creator Style v2 ｜ 依据：`config/script_style_guide.md` v2（长期系统级写作规范）
> 本次为 2.x Creator Style 层升级；未进入 3.x、未新增 Agent、未修改 Truth/Evidence、未改变 Production Entry。

## 1. 实现定位（旧 Style 分析）

| 位置 | 旧规则 | 与新规范的冲突 |
|---|---|---|
| `config/script_style_guide.md`（v1） | 权威写作规范 | 允许固定结构逐段组织 → 升级为 v2（叙事逻辑驱动，覆盖冲突规则） |
| `creator_style.py` STYLE_PROFILES | "离谱但真实/咱们聊聊…其实啊/是不是有点意思～/综合现有证据…可以谨慎作答" | 二.4 口头禅、二.5 机械反问、二.8 句式重复 |
| `narrative_generation.py` | "关于「X」，事实是：…""…呼应开场，落回核心命题" | 二.1 模板感、二.3 机械章节化 |
| `content_planning.py` plan_hcq | "有一个你可能没想过的答案""如果X这件事成立，它会怎样改变你的判断？" | 二.4/二.5 |
| `production2x` 转场 | "进入下一部分：…" | 二.3 机械章节化 |

保留的 v1 有效规则：信息密度/个人观点/事实-推断-观点-争议区分/幽默服务内容/段落功能单一 —— 全部并入 v2 文档 §〇。

## 2. 新实现（修改内容）

| 文件 | 修改 |
|---|---|
| `config/script_style_guide.md` | 升级为 v2 长期规范（17 节：叙事逻辑驱动 / 问题意识 / 禁机械章节 / 口头禅清单 / 反问价值 / 不凑时长 / 口语不低幼 / 句式变化 / 思考过程感 / 长视频原则 / 开头 / 中段 / 结尾 / Truth 优先级 / AI 味自检 / 架构关系） |
| `creator_style.py` | ① 删除 hook_wrap/body_intro/body_closer 固定包装；② 四风格仅以"收束语 + 观点强度"区分，**收束语每片只追加一次**（`final` 参数，仅最后一章）；③ 新增 `style_qa()`（10 项 AI 味自检：重复句式/过渡重复/机械章节/无意义反问/无意义排比/空泛总结/凑时长/套话/像不像人话/引用计数） |
| `narrative_generation.py` | 正文引入语/段落收束按 **claim 成熟度标记 + 内容哈希取变体**（"已商业化/工程化早期/接近商业化/实验到工程化/工程化阶段/尚无可靠路线"各 2 变体），不再各章同一句式 |
| `content_planning.py` | hook 默认改"先从{entity}说起"/"先看一个数字：{n}"；提问改"{entity}，离真正的 JARVIS 还差什么？"（有信息价值） |
| `production2x/__init__.py` | 转场按下一 claim 成熟度逻辑过渡（"先看一个已经落地的——/再往下，难度就上来了——/真正难的，在后面——"），删除"进入下一部分" |

## 3. JARVIS Style-only 对照测试（A/B，只改表达）

| 核验项 | 结果 |
|---|---|
| 引用表（26 条 URL） | **不变** ✅ |
| claim 覆盖（numbers 1/1, entities 7/8） | **不变** ✅ |
| 逐镜 evidence_refs / fact_refs | **不变** ✅ |
| 场景数 / source_paragraphs 结构 | 44→44 / 一致 ✅ |

| 表达差异 | 旧稿 | 新稿 |
|---|---|---|
| 模板腔命中 | 咱们聊聊×11、其实啊×11、是不是有点意思×11、离谱但真实×11、综合现有证据×10、谨慎作答×10、进入下一部分×9、没想过的答案×6、你有没有想过×1 | **0** |
| style_qa 评分 | **0**（过渡句机械重复 + 无信息价值反问×8+） | **10（无违规）** |
| 正文抽样（S07） | "咱们聊聊「该命题」，其实啊：自然语言理解…" | "这件事，其实已经落地了。 自然语言理解…" |
| 正文抽样（S11） | "咱们聊聊「记忆」，其实啊：AI 长期记忆…" | "这一块，说实话还很早期。 AI 长期记忆…" |

## 4. 回归与冻结

- 15 套件回归 **0/15 失败**。
- Truth/Evidence/Claim/provenance/Production Entry **全部不变**（A/B 核验表）。
- 未进入 3.x、未新增 Agent、未改变 2.x 功能边界。

## 5. 诚实边界说明

- 2.x 文案链是**确定性模板生成器**（无 LLM）；v2 已把固定口头禅清零、改为"成熟度内容感知 + 变体"表达，并通过 style_qa 10/10。
- "完全自由的叙事散文"（像真人写作的无限变化）在确定性架构下无法 100% 达成——那需要 LLM 文案生成（属 3.x）。v2 的 `config/script_style_guide.md` 已同时作为**未来 LLM 文案器的系统提示词**（§十六自检清单可编程化），3.x 接入时直接复用。

## 6. 产物

- `config/script_style_guide.md`（v2 长期规范）
- `src/video_studio/tools/creator_style.py`（v2 + style_qa）
- `src/video_studio/tools/narrative_generation.py`（内容感知引入/收束）
- `src/video_studio/tools/content_planning.py`（hook/提问去模板）
- `src/video_studio/production2x/__init__.py`（逻辑转场）
- `output/production_002/style_v2_ab.json`（A/B 核验记录）

已完成，停止，等待人工审核。
