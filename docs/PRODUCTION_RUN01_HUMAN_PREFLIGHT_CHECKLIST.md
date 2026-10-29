# Production Run 01 人工前置项清单

> 性质:人工前置项处理说明。本文档不修改任何冻结模块、规则、阈值或数据;不构成任何 APPROVED 记录。
> 三项确认记录必须由项目负责人本人签发;系统/Agent 不得代写、不得自动批准。
> 三项全部存在正式记录之前:`PRODUCTION PRE-FLIGHT = BLOCKED`。

---

## 前置项 1 — B2 / S20–S22 抽象叙事段编辑审核

**需要审核的内容**(仅限 B2 范围,不扩大):
- Stage 20 普查中标记为 S20–S22 co-existence 的抽象叙事拍:这些拍的 narration 承担什么叙事功能、当前画面(Honest Neutral / fallback 氛围)是否可接受;
- 若后续启用任何 Tempi 相关素材:其与 S20–S22 各拍叙事功能的对应关系与呈现方式。

**审核结论**(三选一,写入记录):
- `APPROVED`:现状(诚实留白)可接受,允许带 B2 状态进入生产;
- `REJECTED`:相关段落/素材不得进入 Production Run 01;
- `NEEDS_REVISION`:列出需修改的拍与原因,修改本身仍需另行授权,不自动执行。

**禁止**:系统自动代替本审核;为通过审核而重算/重解释 correspondence。

**完成后留下的最小可审计记录**:一份人工签发的编辑审核记录(建议路径 `output/pre_flight_signoff/B2_editorial_review.md`),包含:
1. 审核人(项目负责人)签名/姓名;
2. 审核日期(真实日期);
3. 审核对象:S20–S22 各 beat 清单(引用 stage20_diagnostic.json 的拍号,不改写其数据);
4. 结论:APPROVED / REJECTED / NEEDS_REVISION;
5. 逐拍一句理由(可简短,但须具体到拍);
6. 对 Tempi 素材的明确表述:允许/不允许/待议(该表述不替代前置项 2)。

---

## 前置项 2 — S28-B02 / Tempi 内容风险人工签核

**需要人工确认的具体风险**:
- `abstract_analogue_ledger.json` 中 S28-B02 为 CONDITIONAL,risk lock = false:候选为真实灾难试选素材(real-disaster trial),存在内容敏感性/观感风险;
- 需人工判断:该画面在成片语境中是否可被观众接受、是否符合发布平台的内容规范、是否与旁白语义匹配。

**审核结论**(三选一,写入记录):
- `APPROVED`:该拍解除 CONDITIONAL,按 ledger 记录使用;
- `REJECTED`:该拍维持/转为拒绝,该素材不进入生产;
- `NEEDS_REVISION`:指出需何种修改(如替换镜头片段、调整时长、加提示),修改另行授权。

**禁止**:`REJECTED` 或 `NEEDS_REVISION` 时,系统不得自动寻找替代素材绕过该风险锁;不得修改 ledger 既有记录,只能以新签核记录追加。

**完成后留下的最小可审计记录**:一份人工签发的签核记录(建议路径 `output/pre_flight_signoff/S28-B02_tempi_signoff.md`),包含:
1. 签核人签名/姓名;
2. 签核日期;
3. 风险描述(真实灾难试选素材)与所查看的具体素材标识(引用 ledger / asset_cache 标识);
4. 结论:APPROVED / REJECTED / NEEDS_REVISION + 一句理由;
5. 若 REJECTED:明文声明"不得自动寻找替代内容"。

---

## 前置项 3 — 508.29s 母片全片字幕/时序 QA(人工)

**人工需要检查什么**(对象:`output/stage33/stage16_audit/render_162/final_long.mp4`,508.29s,从头到尾全片,不抽样):
1. **字幕完整性**:全片字幕无漏字、无缺行、无截断、无乱码/方框字;
2. **字幕与口播同步**:字幕出现/消失与旁白起止无肉眼可感的提前或滞后(尤其拍切换处);
3. **明显错位/异常时间轴**:字幕对应错拍、长时间无字幕、字幕停留过短(<可读时长)、时间轴跳变。

**辅助证据(可用,但不得冒充人工 QA)**:
- 自动化 A/V delta 0.14s / 508.29s(stage162_metrics)、字幕烧录验证(17.x)、20.1 三窗复验——这些只能作为旁证写入记录,QA 结论必须是人工全片观看后作出。

**QA 结论**(写入记录):`PASS` / `FAIL`(发现项逐条列出:时间点 + 问题描述);发现项的处理(修复/接受)另行决策,不自动重渲染。

**完成后留下的最小可审计记录**:一份人工签发的 QA 记录(建议路径 `output/pre_flight_signoff/master_subtitle_timing_qa.md`),包含:
1. QA 执行人签名/姓名;
2. QA 日期;
3. 被检对象:文件路径 + 时长(508.29s)+ 观看方式(全片/倍速声明);
4. 检查项逐项结果(上述 1/2/3 三项);
5. 引用的自动化旁证(A/V delta 0.14s 等,标注"辅助证据");
6. 结论:PASS / FAIL + 发现项清单(如有)。

---

## 通用约束(适用于全部三项)

- 记录必须由项目负责人本人签发;Agent/系统不得代写结论、不得自动写入 APPROVED;
- 旧 HITL decisions 表(239 条,Stage 31/V2 管线)与本三项审核无关,不得引用作为本次证据;
- 三项记录齐备后,由人工明确下达生产授权,才可进入 Production Run 01;授权前保持 `PRODUCTION PRE-FLIGHT = BLOCKED`;
- 本清单不扩大审核范围:B1 维持 HONEST_NEUTRAL,不因任何一项审核触发素材寻找;B3 维持 MONITOR;冻结规则不动。
