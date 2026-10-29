# Stage 3.1.4 SEAL 报告（FINAL）

- **状态：SEALED / FINAL**
- 版本：**3.1.4**（`src/video_studio/stage31/__init__.py`：`STAGE31_VERSION="3.1.4"`、`STAGE31_STATUS="SEALED"`）
- 验收依据：`docs/STAGE31_4_FIX_GATE.md`（最终 Gate PASS）
- 封包时间：2026-08-29

---

## 一、版本信息与修改范围
- 上游冻结基线不变：2.0.0 / 2x-final-8q；Truth/Evidence、Creator Style v2、`V2_FINAL_SCRIPT_JARVIS.md`、2.x 生产链全部未改。
- 3.1.4 修改范围（仅 Stage 3.1.x）：
  - `stage31/query_plan.py`（新增，v2）：内容词短语提取 + Wikidata 实体路由 + 本地 MT 翻译 + 查询来源/优先级记录 + `_backoff_get` 退避重试
  - `stage31/sources.py`：五路由多路召回编排（R1 Wikidata 实体 → R2 分类 → R3 全文本 → R4 legacy fallback → R5 情绪）、分类搜索 + categorymembers、RATE_LIMIT 状态、路由隔离
  - `stage31/visual_intent.py` / `intent_extract.py` / `ranking.py` / `package.py` / `semantic.py` / `rights.py`：3.1.3 遗留（本版本未再改动，见 SHA）
  - `scripts/run_stage31.py`：接 query_plan + retrieve_multi；`scripts/_fetch_mt_model.py`、`scripts/_fetch_semantic_model.py`：模型下载脚本
  - 测试：`tests/stage31_queryplan_test.py`（新增）、`tests/stage31_semantic_test.py`、`stage31_intent/package/rights` 更新

## 二、本地模型依赖（离线）
1. **语义模型**：`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`（~470MB）→ `models/semantic/`；transformers + mean-pooling 加载；embedding 按文本 SHA256 落盘 `models/semantic/embed_cache.json`。
2. **翻译模型**：`Helsinki-NLP/opus-mt-zh-en`（~300MB）→ `models/mt/opus-mt-zh-en/`；需 `sentencepiece`；MarianMT 懒加载、失败不阻塞其他路由。
- 均经 hf-mirror 下载（`HF_ENDPOINT` 环境变量）；完全离线运行，无第三方 API。

## 三、retrieval 五路由 + legacy fallback + gate 顺序
```
narration → 短语提取 → R1 Wikidata 实体 / R2 分类 / R3 中文+MT 全文本 / R4 legacy / R5 情绪
  → merge → dedupe → rights hard gate（先于一切评分）→ hybrid ranking → 负域惩罚
  → 复用惩罚 → semantic threshold 45 → Top-3 / NO_SAFE_MATCH
```
- rights gate 顺序：UNSAFE/UNKNOWN 在评分前淘汰，embedding 绝不推翻。
- ranking 配置：embedding 0.55 + concept 0.25 + action 0.10 + overlap 0.10；负域惩罚 -30/词；RELEVANCE_MIN=45。
- rate-limit/backoff：429/5xx/超时分类；指数退避（base 1.5s）+ jitter；重试 2 次；RATE_LIMIT 独立状态；路由级隔离。

## 四、17 主题最终 Gate 数据（recall@K / Primary / Miss / NO_SAFE）
| 主题 | recall | Primary | Miss | NO_SAFE | | 主题 | recall | Primary | Miss | NO_SAFE |
|---|---|---|---|---|---|---|---|---|---|---|
| jarvis | 1.0 | 4 | 0 | 4 | | chongqing | 1.0 | 7 | 0 | 1 |
| yuan | 1.0 | 3 | 0 | 5 | | qinghai | 0.875 | 6 | 1 | 2 |
| freedom | 1.0 | 4 | 0 | 4 | | marathon | 0.75 | 4 | 1 | 4 |
| coffee | 0.75 | 7 | 1 | 1 | | homesick | 1.0 | 5 | 0 | 3 |
| busy | 1.0 | 5 | 0 | 4 | | tea | 0.25 | 1 | 6 | 7 |
| phone | 0.875 | 6 | 1 | 2 | | zhenghe | 0.875 | 7 | 1 | 1 |
| study | 0.875 | 5 | 0 | 3 | | darkmatter | 1.0 | 6 | 0 | 2 |
| nightcity | 1.0 | 8 | 0 | 0 | | drip | 0.875 | 7 | 1 | 1 |
|  |  |  |  |  | | bread | 0.625 | 4 | 3 | 4 |

- 明显错误 Primary = 0（全 17 主题）；adversarial 假匹配 = 0（+ 语义对抗单测 6/6）；rights violation = 0；provenance missing = 0。
- 均值 recall ≈ 0.87；JARVIS recall = 1.0 ≥ 3.1.3 baseline；新主题 yuan/freedom/coffee/nightcity 相较 3.1.3 实质提升。
- Retrieval Miss 与 NO_SAFE_MATCH 严格区分（retrieval_miss / no_safe_match / semantic_reject / rights_reject 四分类，search_log 全量留痕）。

## 五、已知限制（如实保留）
1. **tea（泡茶）recall 0.25**：Commons 中文描述少 + "泡茶"类场景翻译/分类命中有限 → 数据源覆盖问题，7 镜诚实 NO_SAFE，非错误推荐。
2. **MT 人名翻译偏差**（袁隆平→"Yuan Ryuhei."）：R1 Wikidata 实体路由给出正确名兜底，不影响实体主题。
3. **17 主题批次在"自由"单字停用词 bug 修复之前运行**：该修复只增不删短语（freedom 已满 recall），不会使结果变差——按裁决要求如实保留，不重跑、不改验收标准、不改算法。

## 六、SHA 基线
### 2.x 冻结基线（19 文件）
以 `docs/PRODUCTION_MANIFEST_2X.json` 为准；封包前 SHA 校验通过（15/19 与 8R manifest 一致；4 个为 2026-08-19 人工裁决 Creator Style v2 升级版，本轮零改动）。

### 3.1.4 文件 SHA（封包前）
```
src/video_studio/stage31/__init__.py       B33B7310991A5E30AD108EEEC4949DB4F51C26DB0F6F6D464E5A32E4204754AA  # SEALED 状态写入后
src/video_studio/stage31/intent_extract.py 73B374A5063B187B8609A0C9B1969C8CA90A7A015E0C53702C936C9DE18B08EB
src/video_studio/stage31/package.py        3A0B7D44EAD2E9F64B62F55F5ACE0FEF582A27ACFB822E42F1DD351E9DEAB495
src/video_studio/stage31/query_plan.py     829A43FD7D2064714E00A2002CBCEF7C9BC03F29712E1D7221A37A45FF70E2B5
src/video_studio/stage31/ranking.py        BC94B12D2983EF9FB1BCAACE56D16085597810B362CEA357298EC0A138C88FF9
src/video_studio/stage31/rights.py         1BE6894B6774664E4872D7FD794A00C41D607AFF9251DEB0C6B3FA696372E97C
src/video_studio/stage31/semantic.py       003DC52CE9918C855DD6CAD28C8C132EA1ACD78DB126AE913C5B8744F26B1B44
src/video_studio/stage31/sources.py        6790518143ED863A978C814AE7FD753EC52732B699E6431D28D1485B15D97D6A
src/video_studio/stage31/visual_intent.py  402E81CB4F4C6EF8F00CA422FC6C1B2286B6F6A6B9972B14E00D7DE3C0D0EA88
scripts/run_stage31.py                     D4D59E9A18F62E28BBDC0CD5E85A883EE50BE9379EEEFA7D1C563742A14BB68D
scripts/_fetch_mt_model.py                 E43329D9CD1BB64CB901698BC78396A874243ABC63D1CC462A03B598F18A3F3E
scripts/_fetch_semantic_model.py           6FE5FD2FB95451B70A3B947263356E9A16AEC926ED68FDFD3E55F8D71EDCBFBB
```
> 注：`__init__.py` 在写入 `STAGE31_STATUS="SEALED"` 后 SHA 会变化，以封包后实测为准。

## 七、封包前回归结果
（见运行日志；2.x 13/13 全绿 + SHA 一致；Creator Style v2 acceptance + Truth/Evidence + stage31 五套测试 + JARVIS + 17 主题完整性全部 PASS）

## 八、范围声明
- 未修改 2.x 冻结物、Creator Style v2、Truth/Evidence、口播稿。
- **不进入 Stage 3.2**；本轮不新增任何功能，仅封包。
