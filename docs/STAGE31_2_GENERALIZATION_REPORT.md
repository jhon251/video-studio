# Stage 3.1.2 主题解绑修复报告（未 SEALED，待人工裁决）

## 1. 根因
`visual_intent.py` 的 `SECTION_SHOTS` 把镜号 S01–S44 硬映射到 JARVIS 段落，`TOPIC_INTENTS` 是 JARVIS 主题词表；新主题镜头全部被套用 JARVIS 意图 → 新主题实战测试 RED。

## 2. 修改文件（仅 3.1.x 内部，未触碰任何 2.x 冻结物）
- 新增 `src/video_studio/stage31/intent_extract.py`（主题无关确定性意图提取层）
- 重写 `src/video_studio/stage31/visual_intent.py`（删除 SECTION_SHOTS/TOPIC_INTENTS，逐镜口播动态推导）
- `src/video_studio/stage31/ranking.py`（语义相关度下限 RELEVANCE_MIN=40；媒体契合改用 preferred_media_type）
- `src/video_studio/stage31/package.py`（相关度下限→真 NO_SAFE_MATCH；跨镜复用惩罚 REUSE_PENALTY=12）
- `src/video_studio/stage31/__init__.py`（3.1.2 DEV-UNSEALED）
- 测试数据/脚本：`scripts/_gen_stage31_testpkgs.py`、`output/stage31_testpkgs/{busy,phone,study,nightcity,jarvis}/`

## 3. 架构变化
```
镜号(ID 无语义) → narration 口播文本 → intent_extract(通用概念族/动作/隐喻/抽象/情绪/时间标记)
→ subject/action/object/environment/concept/mood/temporal/abstraction/media
→ 查询阶梯(literal→conceptual→metaphorical) → 检索 → 概念域匹配+负域惩罚+词重叠弱特征
→ 相关度下限(硬) → 复用惩罚 → Top-3 + NO_SAFE_MATCH + preview.html
优先级：口播语义 > role > 时长/媒体偏好 > 通用知识。
能力边界（诚实声明）：intent_extract 是"词库+启发式"，不具备真正语义理解。
```

## 4–8. 五主题真实测试结果

| 主题 | 镜数 | Primary 明显错误 | 假匹配数 | NO_SAFE_MATCH | 复用对数 | 可用率（可/可接受） |
|---|---|---|---|---|---|---|
| busy 时间焦虑 | 9 | 1（S06 一战老照片） | 1 | **2（S04/S05 正确触发）** | 0 | 6/9 |
| phone 手机依赖 | 8 | 0 | 0 | 0 | 1 | 8/8（但手机素材同质×4） |
| study 长期学习 | 8 | **5（古籍手稿插图×5）** | 5 | 0 | 5 | 3/8 |
| nightcity 城市夜生活 | 8 | **2（S02/S04 兜底错配为办公室照片）** | 2 | 0 | 4 | 5/8 |
| jarvis 回归 | 8 | **2（S07 椅子、S24 抗议新闻照）** | 2 | 0 | 1 | 4/8 |

- 版权违规：**0**（全部 SAFE/CONDITIONAL，无 UNKNOWN/UNSAFE 入池）
- provenance 缺失：**0**（18 字段 + attribution 全量）
- 各主题 preview.html + Top-3 预览均已生成于对应 material_package_test/

## 9. 版权 / provenance
全绿：G 项达标；硬门槛未降低。

## 10. 2.x 回归
13/13 冻结套件全绿；19 冻结文件 SHA（v2 白名单外）全部一致；stage31 三套测试全 PASS（rights 69 / intent 全过 / package 22）。

## 11. 是否达到封包标准：**未达标（不 SEALED）**
- ✅ C（无主题硬编码）、D（主题间意图确实动态分化：busy→clock/time、phone→smartphone、study→book、nightcity→night、jarvis→robot）、E（NO_SAFE_MATCH 真实触发 2 次）、G、H、I
- ❌ A（study 63%、nightcity 25% 明显错误，超 10% 上限）、B（假匹配 10 处）、F（复用 study 5、nightcity 4）、J（JARVIS 回归 2/8 明显错误）

**根因（能力边界，非继续堆词表能解决）**：确定性概念族词库的覆盖与粒度上限——"书"族被 15 世纪手稿垄断、"夜"族被单一夜景照片垄断、未命中词的镜头（霓虹/出租车/任务/幻觉/数字）落入办公室/夜兜底。按裁决，不通过堆关键词黑名单修复。

## 12. 结论与建议（不自动进入下一阶段）
3.1.2 已完成架构级解绑（意图真正来自口播），但确定性词库无法可靠覆盖任意主题语义。可选路径（供人工裁决）：
A. 接受词库边界：3.1.x 定位为"辅助+人工从 Top-3 挑选"，标准降为 YELLOW 型；
B. 引入可嵌入语义模型（本地 embedding/小型多模态模型做概念匹配）——需要网络下载模型与新一轮开发；
C. 保持现状，只对词库做有限度扩充（会触碰"不堆规则"边界，需明确授权）。
