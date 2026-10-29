# Stage 3.1.4 Retrieval Upgrade —— 实施报告（FAIL，未 SEALED）

## 1. 实施内容（按批准设计）
- 新增 `query_plan.py`：短语提取 + R1 Wikidata 实体 / R2 分类 / R3 中文全文本 / R4 旧词库 / R5 情绪 **五路由并行召回**（非串行 fallback），每路记录 query/route/returned；
- `sources.py`：新增分类搜索 + categorymembers 文件召回 + retrieve_multi 编排（merge→dedupe→rights gate→ranking 不变）；
- 分析器实现四分类：**retrieval_miss / no_safe_match / semantic_reject / rights_reject** + relevant recall@K + query/source diversity；
- 3.1.3 基线已锁存 `output/stage31_testpkgs/baseline_313.json`；
- 未修改：ranking 权重、rights gate、semantic threshold 45、negative penalty、词库、2.x 任何文件。

## 2. 核心 A/B（recall@K 与 Primary，3.1.3 → 3.1.4）
| 主题 | recall 3.1.3 | recall 3.1.4 | Primary 3.1.3 | Primary 3.1.4 |
|---|---|---|---|---|
| coffee | 0.0 | 0.125 | 0 | **3** ✓ |
| freedom | 0.375 | **0.75** ✓ | 1 | 1 |
| yuan | 0.375 | 0.375 | 0 | 0 |
| busy | 0.667 | 0.889 | 5 | 4 |
| phone | 0.875 | 0.75 | 5 | 4 |
| study | 0.625 | 0.625 | 3 | 2 |
| nightcity | 0.5 | 0.5 | 5 | 4 |
| **jarvis** | 1.0 | **0.0 ✗** | 3 | **0 ✗** |

新主题（无 3.1.3 基线）：zhenghe 0.375/0、darkmatter 0/2、drip 0.125/1、bread 0.125/1、chongqing 0.625/4、qinghai 0.125/3、marathon 0.25/1、homesick 0.625/1、tea 0.125/0。

## 3. 安全与质量指标（全部达标）
- 明显错误 Primary：**0/全部**（≤5% ✓）
- adversarial 假匹配：**0**（含对抗单测 6/6：打字机/宇航员/古籍/数据中心全被压到低分）
- rights 违规：**0**；provenance 缺失：**0**
- NO_SAFE_MATCH 未被覆盖率压力压低（大量诚实 NO_SAFE + 自制建议；四分类统计可用）
- 无主题硬编码（queryplan 单测断言词库无 rice/coffee/freedom/yuanlongping 等词）
- 2.x：13/13 套件全绿 + SHA 一致；单元测试 rights/intent/package/queryplan/semantic 全 PASS

## 4. 失败根因（证据确凿，三个实现缺陷）
- **D1 短语提取缺陷**：整句保留而非内容词 n-gram。jarvis 的 R2/R3 实际查询为「钢铁侠里的」「但真把」「拆开」等垃圾短语（search_log 实录），88 条查询全部 EMPTY → jarvis 回归 0 recall 崩坏；yuan/coffee 的短语虽部分可用但质量同样受损。
- **D2 中文→英文翻译未实现**：设计预留"Wikidata label 或本地翻译"，实际仅实现 Wikidata（只覆盖实体类短语）。场景短语（"烘焙炉里/豆子爆裂"）无英文 → R2 英文分类搜索空转 → coffee/tea/bread/drip/marathon/qinghai 的 recall 均停留在 0.125–0.25，未达"显著高于 3.1.3"。
- **D3 运行末段 Commons 限流**：jarvis 为 18 主题中最后一个，88/88 EMPTY 含限流因素（与 D1 叠加）。
- 成功面：Wikidata 实体路由有效（freedom 0.375→0.75、coffee 获 3 个正确 Primary、chongqing/homesick 0.625）；多路架构与四分类指标落地正确。

## 5. 验收判定：FAIL（未达标）
- 达标：门槛 1/2/3/4/5/7/8/9 ✅
- 未达标：**门槛 6（新主题 Recall 显著高于 3.1.3）**——12 新主题中 7 个 recall ≤0.25；**门槛 10（旧主题回归）**——jarvis 因 D1+D3 从 3 Primary 崩到 0。
- 未为 PASS 修改任何阈值/词库/rights；未 SEALED；未进入 3.2。

## 6. 修复方向（供裁决，本轮不实施）
1. 短语提取改为"逐字停用词过滤 + 2–4 字内容 n-gram + 中文分词近似"，消灭功能词垃圾短语（修 D1）；
2. 接入本地 zh→en 翻译（Helsinki-NLP/opus-mt-zh-en，~300MB，hf-mirror 可下）驱动 R2/R3 英文查询（修 D2）；
3. 检索层加 429 退避重试与全局速率控制（修 D3）；
4. 重跑 18 主题 A/B 与 jarvis 回归。
