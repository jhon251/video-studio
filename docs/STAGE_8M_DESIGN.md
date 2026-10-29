# Stage 8M：Visual Planning Layer Stress Test — 设计

> 状态：**设计待裁决**。本文档只定义测试设计，未执行任何测试。
> 本阶段不进入自动视频生成；不接 TTS；不接发布流程；不修改 Truth/Evidence Layer；不扩大系统边界。

## 1. 目标与范围

### 1.1 目标

验证 Visual Planning Layer（Stage 8L，已验收 49/49 映射、49/49 引用保持、756/756 可执行性）在**复杂内容条件**下是否仍然稳定：

- **长度压力**：10 分钟级、15 分钟级长视频的 Scene 序列；
- **内容复杂度**：多人物、多时间线、高事实密度、多来源引用。

### 1.2 测试边界（与 8L 一致的硬约束）

| 允许 | 禁止 |
|---|---|
| 构造压力测试数据（新 claims + 构造 evidence，落盘 `_drafts`） | 自动视频生成 / 剪辑 / 发布 / TTS 接入 |
| Test-side 编排：把多条 claim 的风格化脚本拼接为长脚本（含全局引用重编号） | 修改 Truth/Evidence Layer（8D-8F 冻结） |
| 复用既有 8G→8L 管线（不改任何层） | 修改 Visual Planning Layer 本身（`visual_planning.py` 不动） |
| 计算既有 8L 指标 + 4 项新增指标，报告并停止 | 扩大系统边界（不新增生产能力，只做测试编排） |

**关键原则**：压力测试通过"更长的输入"考验既有层；任何在压力下暴露的问题**只报告、不自动调参**，等裁决。

## 2. 测试数据设计（label-first，数据无关，不触碰冻结集）

压力数据落盘 `projects/_drafts/s8m_stress_claims.json`。**不含 truth 标签**——本测试只覆盖 8G→8L 下游创作链（Brief→Plan→Blueprint→Draft→Style→Visual），不经过聚合/truth 判断（冻结层不参与，也不被修改）。

### 2.1 四类复杂度 stress claims（各 1 条 + 1 条四合一综合）

| ID | 复杂度 | Claim 文本（构造） | 关键元素 |
|---|---|---|---|
| SC-MP | 多人物 | 传送机思想实验：1775年苏格兰哲学家托马斯·里德提出"拆解重组"之问；20世纪帕菲特在《理与人》中重提"复制+原身"；普特南以功能主义、丹尼特以多重草稿各自回应，四人从未达成一致 | 人物×4：里德/帕菲特/普特南/丹尼特；年份 1775；实体：传送机/意识/人格 |
| SC-TL | 多时间线 | 脑图谱时间线：2013年美国启动脑计划，2018年果蝇部分图谱完成，2023年成年果蝇全脑连接组（约十四万神经元）发表于《科学》，2024年《自然》系列论文完善，2025年中国团队发布毫米级小鼠全脑图谱 | 时间线×5：2013/2018/2023/2024/2025；数字：十四万 |
| SC-HD | 高事实密度 | 规模与成本：成年果蝇大脑约139,255个神经元与五千万个突触；人脑约860亿神经元、百万亿级突触；OpenWorm 模拟302个神经元的线虫跑了十余年；AI 芯片功耗突破1000瓦后，散热占数据中心电费四成以上 | 数字×8：139,255/五千万/860亿/百万亿/302/十余年/1000/四成；实体：果蝇/人脑/线虫/AI芯片 |
| SC-MS | 多来源引用 | 果蝇连接组已成为脑科学基准数据：其绘制依赖 AI 自动追踪与人工校对合力完成，并被多团队独立复用验证 | 证据×6（构造，见 2.2）；实体：果蝇/连接组/AI/脑科学 |
| SC-ALL | 四合一 | 从2013年脑计划到2025年小鼠图谱：托马斯·里德与帕菲特的"复制之问"至今无解；果蝇约139,255个神经元的连接组由 AI 与人工合力绘成，而人脑860亿神经元、百万亿级突触的模拟受限于1000瓦级芯片的散热成本——这条十二年的时间线由多家团队接力推进 | 人物×2 + 时间线×5 + 数字×7 + 来源×6 |

### 2.2 构造 evidence（数据无关、确定性）

- 每条 stress claim 配 **6 条构造 evidence**（`url/title/snippet/body/source_quality.tier`），body 为确定性构造文本，分别覆盖 claim 的不同元素子集（数字/人物/时间线/实体），tier 覆盖 high/medium/low（官方/学术/主流媒体/专业媒体/聚合/未知）。
- SC-MS 与 SC-ALL 额外要求：6 条证据中 ≥4 条 body 含 claim 核心数字/实体（供多来源引用压力）。
- 构造文本不引用任何真实网站抓取内容，仅作为压力输入（与 `s8_dev2_samples.json` 同一构造口径）。

### 2.3 两部长视频（长度压力）

长视频 = 主题连贯的多 claim 风格化脚本拼接（test-side 组装，见 §3）。时长以 B站节奏（6s/镜）估算，目标 ±10%：

| 视频 | 主题 | Claim 构成 | 目标时长 |
|---|---|---|---|
| VIDEO-10 | 《从果蝇到永生：大脑上传的科技与法律》 | 5 条 = SC-TL + SC-HD + SC-MP + 既有 claim（2023 果蝇连接组、数字人法律地位） | 540–660s（10 分钟级） |
| VIDEO-15 | 《脑科学与数字人格全景》 | 8 条 = SC-MP + SC-TL + SC-HD + SC-MS + SC-ALL + 既有 claim（2025 小鼠图谱、人脑 860 亿、意识上传） | 810–990s（15 分钟级） |

既有 claim 的 evidence 复用 8D/8E 已存回放数据（`r1_stage8d_full.json` / `r1_stage8e_full.json`），**不重新抓网**（网络非本测试变量）。

## 3. 长视频组装规则（test-side，不改任何层）

对每部视频：

1. **逐 claim 走既有管线**：`build_research_brief`(8G) → `build_content_plan`(8H) → `build_script_blueprint`(8I) → `build_narrative_draft`(8J) → `apply_style`(8K，风格统一取 `casual`)，得到各 claim 的 styled paragraphs 与 references。
2. **全局引用重编号**：合并全部 claim 的 evidence，按 URL 去重得全局参考表 `[1..N]`；把每条 paragraph 文本中的 `[k]` 行内引用与 `evidence_refs` 重写为全局编号（确定性字符串替换，仅测试编排）。
3. **块拼接**：按主题顺序拼接 paragraphs；每条 claim 前插入一个 `transition` 段落（role=transition，文本="进入下一部分：{claim 主题}"），transition 不携带 evidence（不虚增引用）。
4. **喂给既有 8L**：`build_production_plan(长脚本, 对应 brief 合并体, platform)` 原样执行（不改 `visual_planning.py`；scene_id `S{i:02d}` 支持到 S99，两部视频场景数 <90，够用）。
5. **平台对照**：两部视频各生成四平台 Production Plan；节奏指标取 B站（6s/镜）作时长基准，其余平台仅验证结构完整。

## 4. 验收指标

### 4.1 保持 Stage 8L 指标（对全部 stress claims + 两部长视频）

| # | 指标 | 判定 |
|---|---|---|
| 1 | Script-Scene 映射完整性 | 段落数 == scene 数（1:1），100% |
| 2 | Evidence-Visual 引用保持 | body 段证据引用 + 参考来源逐 scene 保持，100%；长视频下全局编号无重复/无丢失 |
| 3 | Production Plan 可执行性 | 每 scene 含画面目标/字幕重点/时长提示，100% |
| 4 | 字幕重点标注准确性 | 对 4 类 stress claims 逐条人工抽查：数字/人物/时间线/最高级/否定词命中全对；"是不是"反问不误标；漏标≤1/条 |
| 5 | 冻结回归 | 15 套件 0 失败 + `semantic_judge.py` SHA256 不变 |

### 4.2 新增指标

| # | 指标 | 定义与判定 |
|---|---|---|
| 6 | 长视频 Scene 一致性 | (a) scene_id 唯一且严格连续 S01..SN；(b) 全局引用编号 [1..N] 唯一、连续、与参考表一一对应；(c) 块内情绪曲线连续（相邻 scene 情绪强度跳变 ≤2，块边界除外）；(d) 每条 transition 段落定位正确。四查全过为 PASS |
| 7 | 重复视觉风险 | 计算连续同 visual_target 的最大连串长度与"连串≥3 的 scene 占比"。**报告型指标**：输出风险值（阈值提示 max≤5 且占比≤40%），不因超标自动改层，只报告 |
| 8 | 信息密度与镜头节奏匹配 | 每 scene 事实密度 = 字幕重点数 + len(text)/50；"高密度"=上四分位，"短时长"=下四分位。高密度且短时长的 scene 占比 ≤10% 为 PASS；违规 scene 逐条列出（含 hook 30s/低密度这类反向失配，一并报告） |
| 9 | 人工制作成本估算 | 按视觉类型单场景工时：口播卡 5min / 结论大字卡 5min / 待补提示卡 5min / 事实核查卡 10min / 证据截图 15min / 数据可视化 30min / 概念动画 45min。输出每部视频总工时 + 按类型分布 + 每千秒工时比。**报告型指标** |

## 5. 测试流程（裁决后执行，一次性，只报告不调参）

1. 构造 `s8m_stress_claims.json`（5 条 stress claims + 6×5 构造 evidence，落盘 `_drafts`）。
2. Test-side 组装 VIDEO-10 / VIDEO-15（§3 全局重编号 + transition + 既有 claim 回放数据）。
3. 跑既有 8G→8L 管线（stress claims 单独 + 两部长视频），输出四平台 Production Plan，落盘 `r1_stage8m_full.json`（回放）。
4. 计算 4.1 五项 + 4.2 四项指标，逐项给出 PASS/FAIL/风险值。
5. 15 套件回归 + `semantic_judge.py` SHA256 校验。
6. 产出 `r1_stage8m_report.md`，停止，等待裁决。

## 6. 预期风险与诚实承诺

- 长视频下 hook 段时长（6s×强度5=30s）对快节奏平台偏长、高密度场景可能时长不足——此类失配由指标 8 如实暴露，**只报告，不自动改 duration 公式**。
- 重复视觉风险（多 claim 拼接后同型 scene 连串）由指标 7 如实量化，不自动插入变化。
- 若任何指标未达判定，报告原始数据与根因，不自行调整任何层。

## 7. 不做什么（约束重申）

- 不自动生成视频、不自动剪辑、不自动发布、不接 TTS。
- 不修改 Truth/Evidence Layer（8D–8F）、不改 EvidenceSignal/Aggregation/Semantic Judge/Fact_check/冻结测试。
- 不修改 `visual_planning.py` 及任何既有层；不扩大系统边界（长视频组装纯属 test-side 编排）。
- 不针对具体网站/domain 写规则；不做任何针对具体 claim 的特例。
