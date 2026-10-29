# Stage 3.1.4 Retrieval Upgrade —— 设计文档（待人工确认后实施）

## 1. 根因确认（Gate 实证）
- 链路缺陷：narration → 有限词库 query → Commons **关键词文件检索** → embedding 重排。
- 失败机制：词库未覆盖（水稻/咖啡/自由）→ 兜底"办公室"→ **检索阶段即错域召回** → embedding 只能重排已召回候选，**无法找回从未召回的目标素材**（coffee S03 实际查询 "office worker desk" 为证）。
- 结论：问题在 **retrieval 阶段**（召回率），不在 ranking/阈值；扩词库只能缓解、不能根治（且被裁决禁止）。

## 2. 方案对比（A/B/C/D）

| 方案 | 思路 | 优点 | 缺点/风险 | 环境实测 |
|---|---|---|---|---|
| A. Query Expansion（叙述内短语提取） | 从句法切分叙述、提取 2–6 字短语与拉丁词，直接作中/英 query | 零新依赖、完全 open-vocabulary、query 来自当前口播 | 中文短语直搜 Commons 文件全文本，召回依赖文件的中文描述覆盖率 | 待测（Commons 全文本支持中文，概率高） |
| B. 多路召回（文件全文本 + 分类搜索 + categorymembers） | 除文件搜索外，对 query 搜 **Category 命名空间**，命中分类后拉取其全部文件 | **大幅提升召回**（分类是 Commons 的高质量结构化入口）；已实测 "rice fields"→Category:Rice fields ✓ | 分类名以英文为主；需要英文 query | ✅ 已实测可用 |
| C. 实体/知识图谱（Wikidata 替代 Wikipedia） | narration 短语 → **Wikidata wbsearchentities**（中英皆可）→ 实体 sitelink（enwiki/commonswiki）→ Commons 分类 → categorymembers | 解决"袁隆平"类实体/人物/事件主题；真正 open-vocabulary；无词库 | Wikidata 对非实体短语（"烘焙炉里豆子爆裂"）返回弱或无；Wikipedia 被墙但 **Wikidata 实测可达 ✓** | ✅ 已实测 "袁隆平"→"Yuan Longping" |
| D. 本地语义索引 | 下载 Commons metadata 建 embedding 索引 | 语义检索最强 | 数百万文件规模不现实；只能索引已下载子集，不能假装覆盖全网 | ❌ 本轮排除（明示边界） |

## 3. 推荐方案：C + B + A 组合（多路召回 + 实体路由），不扩词库
```
narration
 → 短语提取（标点切分 + 停用词过滤 + 拉丁词/2-6字中文短语，附原文）
 → semantic query planning（3 条路由，全部来自当前叙述，无主题词表）：
    R1 实体路由：Top-K 短语 → Wikidata wbsearchentities(zh+en)
        → sitelinks(enwiki/commonswiki) → Commons Category:X → categorymembers（文件）
    R2 分类路由：短语英文（Wikidata label 或本地翻译）→ Commons ns=14 分类搜索
        → 前 3 分类 → categorymembers（文件）
    R3 文本路由：中文短语直搜 Commons 文件全文本（gsrsearch，ns=6）
    R4 辅助路由：现有 FAMILY 阶梯（降级为次要信号，不再兜底主导）
    R5 情绪路由：EMOTIONAL 镜的情绪词池（保留）
 → 去重合并候选（同一 file 只取一次，标注来源路由）
 → rights hard gate（不变，先于一切评分）
 → hybrid embedding ranking（不变：0.55/0.25/0.10/0.10，负域惩罚，阈值 45）
 → reuse penalty → Top-3 / NO_SAFE_MATCH（不变）
```
- 每路由限流（WikiData ≤3 请求/镜、分类拉取 ≤3 分类 × ≤10 文件、总候选 ≤40/镜），sleep ≥1.2s；
- 所有请求结果与路由来源记入 search_log（含 Retrieval Miss 明细）；
- 未命中任何路由时：NO_SAFE_MATCH 照旧，附"路由级"记录（哪些路由空了）。

## 4. 修改文件清单（仅 3.1.x）
- 新增 `src/video_studio/stage31/query_plan.py`（短语提取 + 三路由规划 + Wikidata 客户端）
- 修改 `src/video_studio/stage31/sources.py`（新增 commons_category_search / categorymembers / 中文全文本检索；retrieve_multi 编排多路由）
- 修改 `scripts/run_stage31.py`（调用 retrieve_multi；--routes 开关）
- 新增 `tests/stage31_queryplan_test.py`（对 袁隆平/咖啡/自由 叙述断言：query plan 含 yuan longping/coffee/rice/freedom 类 query，且这些词**不出现在任何词库**——证明 open-vocabulary）
- 新增 `scripts/_analyze_stage31_14.py`（recall@K / false-match / NO_SAFE precision / query diversity / source diversity 指标）
- 不修改：ranking.py、rights.py、threshold、intent_extract 词库、2.x 任何文件。

## 5. 测试设计
1. **12 个全新主题**（覆盖：人物=袁隆平/历史事件=郑和下西洋/科学=暗物质/农业=滴灌节水/食物=面包发酵/城市=重庆山城/旅行=青藏铁路/体育=马拉松撞墙/抽象哲学=自由/情绪=乡愁/日常动作=泡茶/流程生产=咖啡烘焙），每主题 6–10 镜，30% 以上含系统未见过实体；全部新主题不进入任何词库/fixture。
2. 回归：busy/phone/study/nightcity/jarvis + 3 个 Gate 失败主题（yuan/freedom/coffee）。
3. 新指标：**retrieval recall@K**（以"安全源存在且被召回"计：路由命中 + 候选 embedding≥0.40 为召回成功）、Retrieval Miss 记录（目标素材存在于 Commons 但路由全空 → 记为 Miss 而非 NO_SAFE_MATCH 的功劳）、NO_SAFE_MATCH precision（无路由命中且无相关候选时才输出 NO_SAFE）、query diversity（每镜路由/查询词去重数）、source diversity。
4. 全部单元测试 + 2.x 冻结回归 + 对抗测试重跑。

## 6. 验收标准（用户 §九，原样执行）
明显错误 Primary ≤5% ｜ adversarial 假匹配 = 0 ｜ rights 违规 = 0 ｜ provenance 缺失 = 0 ｜ NO_SAFE_MATCH 不被覆盖率压力压低 ｜ 新主题 Recall 显著高于 3.1.3（3.1.3 基线：yuan 0/8、coffee 0/8、freedom 1/8 有 Primary）｜ 镜号不决定主题 ｜ 无测试主题专用规则 ｜ 2.x 100% 不变 ｜ 5 旧主题全回归。
不达标不修绿，如实报告。

## 7. 已知边界（诚实声明）
- 本地语义索引（方案 D）不在本轮范围；系统只覆盖"所查询来源中实际存在且可被路由召回"的素材；
- Wikidata 可达但 Wikipedia 被墙（若 Wikidata 对某实体无 sitelink，R2/R3 兜底）；
- Commons 分类/全文本仍为关键词机制，本轮通过"多路由 + 实体映射"提升召回，不声称语义级全量召回。
