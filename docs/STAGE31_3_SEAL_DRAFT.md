# Stage 3.1.3 封包前 Gate 报告（SEAL 草稿）

- 状态：**FAIL —— 不满足封包条件，未 SEALED**（根因与证据见 §10）
- 版本：3.1.3 DEV-UNSEALED
- 执行时间：2026-08-28（全部测试真实重跑，无引用历史结果）

## 1. 默认模式核验 ✅
- `RANK_MODE = "hybrid"`（默认）；hybrid 权重 = embedding 0.55 + concept 0.25 + action 0.10 + overlap 0.10
- 负域惩罚（-30/词）、`RELEVANCE_MIN = 45.0` 保持
- `gate_and_score` 中 rights 判定先于一切评分：UNSAFE/UNKNOWN 直接淘汰，embedding 无法推翻版权门禁 ✅

## 2. 全量测试真实重跑 ✅
| 测试 | 结果 |
|---|---|
| stage31_rights_test | PASS（69/69） |
| stage31_intent_test | PASS |
| stage31_package_test | PASS（22/22） |
| stage31_semantic_test（对抗） | PASS（6/6：打字机 0.086 / 宇航员 0.254 / 古籍 0.349 / 数据中心 0.224） |
| 5 泛化主题（busy/phone/study/nightcity/jarvis，hybrid 重跑） | 全 PASS，0 明显错误、0 假匹配 |
| JARVIS 回归（8 镜 hybrid） | PASS（0 错误，3 Primary + 5 诚实 NO_SAFE） |
| 2.x 冻结回归 | 13/13 全绿 + SHA（v2 白名单外）一致 |

## 3. 全新主题实战（3 个新主题）❌ —— 失败点
| 主题 | 类型 | 结果 |
|---|---|---|
| 袁隆平与杂交水稻 | 人物/事件 | **8/8 NO_SAFE_MATCH** |
| 什么是真正的自由 | 抽象概念 | 7/8 NO_SAFE_MATCH（1 Primary） |
| 一杯咖啡的旅程 | 动作/流程 | **8/8 NO_SAFE_MATCH** |

证据（search_log 实录）：
- coffee S03「烘焙炉里，豆子在高温下爆裂」实际查询 = `[literal] office worker desk (bitmap)`
- yuan S02「风吹过稻田」实际查询 = `[literal] office worker desk (bitmap)`
- freedom S01 同样落入 office 兜底
→ 检索词全部落到错误概念域（办公室），embedding 门禁诚实拒绝全部候选 → NO_SAFE_MATCH。

**根因**：intent 词库（FAMILY_KEYS）未覆盖水稻/稻田/种子/咖啡/烘焙/研磨/自由等词 → 兜底"办公室"→ 检索即错域。Commons 为关键词检索源，embedding 只能重排"已检索到"的候选，**无法补救从未被检索到的素材**。这印证 3.1.3 报告"已知限制 #2"，本轮以量化方式在全新领域复现：**对词库覆盖外的任意新主题，3.1.3 无法实际找到素材**（安全、诚实，但不具备"任意主题"能力）。

（遵守规则：未针对测试主题添加任何词库条目或特殊规则。）

## 4. NO_SAFE_MATCH 验证 ✅
23 个 NO_SAFE 全部带"存在 SAFE 但语义不相关候选，已拒绝凑数"记录与自制建议；未为覆盖率放宽阈值。

## 5. 跨主题解绑 ✅
同一镜号 S01 在不同主题下 intent 完全随 narration 变化：
busy→time,crowd / phone→smartphone / yuan→office(兜底) / coffee→travel / freedom→office(兜底) / jarvis→ai。镜号无语义。

## 6. 复用 ✅
复用惩罚（URL -12 + 语义重合 -10）生效；5 主题 hybrid 复用率 9.5%（≤10%）；新主题 0 复用。

## 7. 版权链抽查 ✅
全部候选/ Primary：source/license/attribution/download URL/provenance 18 字段完整；池内 0 条 UNKNOWN/UNSAFE；semantic 得分高也不绕过 rights gate（代码顺序核验 + 数据抽查双重确认）。

## 8. 交付包清单 ✅（12/12）
代码（stage31/ 7 模块）｜模型加载说明（semantic.py docstring + `scripts/_fetch_semantic_model.py`）｜模型文件（models/semantic/…/pytorch_model.bin 470MB）｜embedding cache 说明（semantic.py + models/semantic/embed_cache.json）｜material metadata｜rights｜shot mapping｜search log｜Top-3 preview（busy 包 10 张预览）｜preview.html｜README｜测试报告（benchmark_summary.json + 本报告）｜SEAL 报告草稿（本文件）。

## 9. 性能 ✅
- 模型冷加载：**8.7s**（CPU）
- 100 条冷 embedding：**0.7s**；100 条缓存命中：**0.06s**
- 44 镜全量 hybrid 冷跑总耗时：**654.9s**（≈11 分钟，其中网络检索与限速等待占绝对大头，embedding 部分 <10s）
- 单主题 8 镜：100–210s（含每次进程的模型加载与检索）

## 10. 最终结论：**FAIL**
- 达标项：1/2/4/5/6/7/8/9 全 ✅
- 失败项：**§3 全新主题实战**——3 个新主题中 2 个 100% NO_SAFE、1 个 87.5% NO_SAFE，系统在词库未覆盖的新领域**无法找到素材**（尽管 Commons 上明显存在水稻田/咖啡相关素材）。
- 失败根因：检索层为关键词检索（Commons），intent 词库覆盖有界；embedding 重排无法补救未检索到的候选。这是确定性词库方案的架构上限，非本轮可修的参数问题。
- 未为了通过指标调整任何算法/阈值/词库。

**因此：3.1.3 不得进入 SEALED。** 若要达到"任意主题"目标，需要检索层升级（如对 Commons 的语义向量检索索引、或接入支持语义搜索的源、或允许对未命中镜头做 embedding 引导的查询生成），属下一轮人工裁决范围；本轮 STOP。
