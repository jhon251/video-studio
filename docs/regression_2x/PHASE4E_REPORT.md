# 4.x Phase 4-E 报告：检索质量量化与 A/B 基准（2026-09-16）

**授权**：进入 4-E 检索质量；以 `4.x-phase4d-baseline.zip` 为基线；不使用 Git；保持 4-A/4-B/4-C/4-D 与
既有许可门禁、HITL、redo、append-only 不变；**只做检索质量量化，不进入自动改选材**；
建立中文/多语言检索 A/B 基准；指标可复算并明确 TP/FP/UNKNOWN 或等价指标；覆盖中文、英文、同义/多语言、
无结果/弱结果；建立固定测试集与人工可解释的期望语义域；不把"检索到候选"等同于"语义正确"；
不接第二 Provider；不做 BGM/UI/节奏/自动发布；不改数据库结构；不改 4-B 真值 `a_2ed5f41d6b58`；
4-D 的缓存/重试/fail-closed 行为不变；默认 `provider=none` 行为不变。完成后 STOP，不进入 4-F。

**前置校验（基线）**：`docs/regression_2x/baseline/4.x-phase4d-baseline.zip`
sha256 `f2c783d493a9cb9fe0e2b1601e22a9eaa117d07a2ef885103e0fd2b2d0a51641`（实测一致，5,918,783 字节）。

**结论：PASS**（固定测试集上 A/B 可比、指标可复算；中文检索从"0 命中/低命中"提升为域命中 100%；
无结果不再造假匹配；检索改进**未绕过** 4-B、许可门禁与素材校验；默认行为与 `provider=none` 不变）。

---

## 1. A/B 测试数据与固定测试集

| 项 | 值 |
|---|---|
| 固定测试集 | `tests/retrieval_bench_v1.json`（**入基线 zip**，sha256 `73fc61d47b044d68…`，10,311 字节） |
| 语料 | **23 个素材名称记录**（检索打分只看 `name+ext`，与生产链路一致），覆盖 4-B 的 **12 个语义域** |
| 语料来源标注 | `real_*` = 本仓库真实下载/登记过的素材名（可在 `projects/video_studio.db` 产物中逐条核对，如 Meta Quest 3 / Tiburón azul 蓝鲨 / 脑电头环 / 皮肤界面截图）；`label_only` = 为覆盖其余语义域而构造的名称（**不声称**真实下载） |
| 期望语义域 | 每条语料带 `domain` 与 `label_basis`（人工可解释，如"Tiburón azul / Prionace glauca = 蓝鲨（西语/学名）→ wildlife"） |
| 查询 | **21 条**，分 6 组：`zh` 5（中文输入）/ `en` 5（英文输入）/ `syn` 5（同义·多语言）/ `weak` 2（弱结果）/ `none` 2（无结果）/ `amb` 2（歧义） |
| k | 5（top-5） |
| A 侧 | **v1 = 既有实现**（`agents/retrieval/agent.py` 的 `kw_tokens` + `score`），**冻结未改**，由 `score_v1()` 直接 import 调用 |
| B 侧 | **v2 = 4-E 新增**（`core/retrieval_quality.py`：多语言归一 + 概念扩展 + **词边界**匹配）；`core/lexicons/retrieval_synonyms_v1.json`（sha256 `853e2b888663840d…`）提供"概念 → 中英（含少量西语）表面形式"表，12 概念对齐 4-B 的 12 域 |
| 复算命令 | `python docs/regression_2x/phase4e_ab_benchmark.py` → `logs/phase4e_ab_results.json`（含**指标定义** + 完整结果 + 逐查询逐候选明细）、`logs/phase4e_ab_summary.txt` |

**A/B 的公平性**：两侧由**同一段代码**（`evaluate()`）在**同一固定集合**上计算，唯一差异是打分函数；
测试集与词典**同源**（词典覆盖了测试集的概念），因此**域命中率不可外推为通用准确率**，
只能作为"同一集合上的相对改进"证据（见 §9 限制）。

**变更文件（相对 4-D 基线）**：新增 `core/retrieval_quality.py`、`core/lexicons/retrieval_synonyms_v1.json`、
`tests/retrieval_bench_v1.json`、`tests/retrieval_quality_test.py`；修改 `agents/retrieval/agent.py`
（**默认 v1、默认不扩展**的 opt-in 接线 + 检索配置的加法留痕）；`CHANGELOG.md` / `STATUS.md`（文档登记）。
**未改**：`core/semantics.py` 与 `semantics_v1.json`（4-B）、`core/materials.py`（许可门禁）、
`core/selection_review.py`（4-C）、`core/supply.py` 与 `tools/supply.py`（4-D）、`db/schema.py`、`config/config.json`。

## 2. 指标定义（写进结果文件，可逐条核对）

| 指标 | 定义 |
|---|---|
| `TP` | 候选素材的语义域 ∈ 该查询的期望域集合 |
| `FP` | 候选语义域 ∉ 期望域；**或**查询期望无结果却返回了候选（假匹配） |
| `UNKNOWN` | 查询被标记为歧义（如 `pico` = 品牌/地名）：命中**一律记 UNKNOWN、不计 TP** —— 这正是"检索到候选 ≠ 语义正确"的落地 |
| `FN` | 查询级：期望域中没有任何域被 TP 覆盖（逐条列出 `FN_domains`） |
| `precision_strict` | `TP / (TP + FP + UNKNOWN)` |
| `precision_excl_unknown` | `TP / (TP + FP)`（参考口径，把 UNKNOWN 排除在分母外） |
| `unknown_rate` | `UNKNOWN / (TP + FP + UNKNOWN)` |
| `domain_hit_rate` | 非歧义且期望域非空的查询中，至少命中 1 个 TP 的比例 |
| `top1_correct_rate` | 同上查询中，排名第 1 的候选为 TP 的比例 |
| `empty_correct_rate` | 期望无结果的查询中，确实返回空候选的比例 |
| `weak_result` | 期望域非空但一条候选都没有（检索过弱） |

## 3. 完整结果（A vs B，固定测试集）

| 指标 | A（v1 冻结） | B（v2 改进） | 差值 |
|---|---|---|---|
| TP（候选级） | **19** | **43** | **+24** |
| FP | **39** | **18** | **−21** |
| UNKNOWN | 10 | 10 | 0（**未把歧义洗成正确**） |
| `precision_strict` | 0.2794 | **0.6056** | +0.3262 |
| `precision_excl_unknown` | 0.3276 | 0.7049 | +0.3773 |
| `unknown_rate` | 0.1471 | 0.1408 | −0.0063 |
| `domain_hit_rate` | 0.6875（11/16） | **1.0（16/16）** | **+0.3125** |
| `top1_correct_rate` | 0.5625 | **1.0** | **+0.4375** |
| `empty_correct_rate` | 0.6667（2/3） | **1.0（3/3）** | +0.3333 |
| FN 查询 | `zh_02, zh_03, zh_05, en_02, weak_01` | **无** | −5 |
| 假匹配查询 | `none_02` | **无** | −1 |

**分组结果**（域命中率 / TP / FP / UNKNOWN）：

| 组 | A | B |
|---|---|---|
| `zh`（中文输入，5 条） | 命中 0.40；TP 3、FP 2 | **命中 1.00；TP 14、FP 6** |
| `en`（英文输入，5 条） | 命中 0.80；TP 7、FP 18 | **命中 1.00；TP 10、FP 5** |
| `syn`（同义·多语言，5 条） | 命中 1.00；TP 9、FP 12 | 命中 1.00；**TP 18、FP 4** |
| `weak`（弱结果，2 条） | 命中 0.00；TP 0、FP 3 | 命中 0.50；**TP 1**、FP 3 |
| `none`（无结果，2 条） | 命中 —；**FP 4（假匹配）** | 命中 —；**FP 0** |
| `amb`（歧义，2 条） | TP 0、**UNKNOWN 10** | TP 0、**UNKNOWN 10** |

**数值冻结**：以上 A/B 数值已在 `tests/retrieval_quality_test.py`（C2/C3/C4/C5/D1–D6）中写成断言，
**任何漂移都会让套件失败**（要改必须新建 `retrieval_bench_v2` 并同时给出两侧结果）。

## 4. 中文 / 多语言案例

**离线（固定测试集）**：

| 查询 | 期望域 | A（v1） | B（v2） |
|---|---|---|---|
| `zh_01` 虚拟现实头显的镜片特写 | xr_device | TP 1 / FP 1 | **TP 5 / FP 0** |
| `zh_02` 蓝鲨在亚速尔群岛海域 | wildlife + geography_nature | **0 候选（FN）** | **TP 2** / FP 3（见 §5 残余 FP） |
| `zh_03` 量子计算机芯片的结构 | computing_device | **0 候选（FN）** | **TP 3** / FP 1 |
| `zh_04` 游戏角色的皮肤立绘 | art_culture | TP 2 / FP 1 | TP 2 / FP 1（中文名素材，v1 本就能命中） |
| `zh_05` 长城与古建筑 | architecture | **0 候选（FN）** | **TP 2** / FP 1 |
| `syn_01` VR 头戴设备 | xr_device | TP 4 / FP 1 | TP 4 / FP 1 |
| `syn_02` HMD 眼镜 立体显示 | xr_device | TP 2 / FP 3 | **TP 5 / FP 0** |
| `syn_03` 脑机接口 电极帽 | computing_device | TP 1 / FP 0 | **TP 3** / FP 1 |
| `syn_04` tiburón azul Azores（西语+地名） | wildlife | TP 1 / FP 4 | TP 1 / FP 2 |
| `syn_05` goggles and stereoscopy | xr_device | TP 1 / FP 4 | **TP 5 / FP 0** |

**真实网络（环境相关，`logs/phase4e_network_probe.json`，本轮 `status=OK`）**：对 3 条**中文**查询在真实
Wikimedia Commons 上比较"原查询形状（`cjk_only`）"与"加 4-E 扩展词后的形状（`latin_clusters`）"：

| 中文查询 | A 形状：候选数 | B 形状：候选数 | 扩展词（词典给出） | B 的候选示例（如实） |
|---|---|---|---|---|
| 虚拟现实头显的镜片特写 | **0** | **8** | `augmented reality` / `virtual reality` | Mixed Reality Scale.png、Virtual-Fixtures-USAF-AR.jpg |
| 蓝鲨在亚速尔群岛海域 | **0** | **8** | `azores` / `beach` / `prionace glauca` | Tiburón azul (Prionace glauca)…（正是目标素材）；**同时出现 `Picea glauca Fairbanks.jpg`（云杉，词形伪友）** |
| 量子计算机芯片的结构 | **0** | **8** | `brain-computer interface` / `quantum computer` | Personal computer, exploded.svg 等（**同域但不精确**：都是计算设备，不是量子计算机） |

结论（如实）：**中文查询在真实语料上原本 0 命中，扩展后能命中目标域**；但"命中"不等于"精确"，
也不等于"语义正确"——第 2 条的伪友与第 3 条的域内泛化都要靠下游 4-B 验证器 + 许可门禁 + 人工复核处理。

## 5. false positive / false negative / UNKNOWN 分析

**根因 1（v1 的字符级关键词缺陷，最严重）**：`kw_tokens` 先把文本去空格再做 `set(text)`，
于是**拉丁文本贡献单字母**（z/q…）、中文贡献单字（面/在/的…），且 `score()` 对单字符按 1 分计。
直接后果：无意义输入也能命中。实测两例（已写进套件 B1）：`score_v1("Meta Quest 3 front View.jpg",
"zzzq 不存在的主题内容") == 1`（命中字母 `q`）；`score_v1("VR头显_侧面_展示.jpg", "咖啡与面包的早餐") == 1`
（命中单字 `面`）。这解释了 A 侧 39 个 FP 中的绝大多数（`en` 组 18 个、`none_02` 4 个、`weak` 组 3 个）。

**根因 2（中文查询 ↔ 英文命名语料无桥）**：v1 只做**字面**匹配，中文词无法命中英文素材名，
故 `zh_02/zh_03/zh_05` 与 `en_02`（跨语言：语料是西语/学名）出现 **FN + 弱结果（0 候选）**。
v2 用词典把两边映射到**同一概念**，FN 归零。

**根因 3（无词边界的子串匹配）**：v1 用 `in` 判子串，`es` 会命中 `Azores` 这类碎片桥（4-B 已在语义层发现同类缺陷）。
v2 对拉丁形式一律按**词边界**匹配（A5 断言），并拒绝单字符关键词。

**B 侧残余 FP（18 个，如实登记，不掩饰）**：
- `zh_02` 3 个：`鲸鱼娘皮肤展示_02.jpg`（鲸鱼在此是**角色名**，域为 art_culture）——词典里 `skin` 是歧义形式，
  这正是 4-B 已登记的同类问题；另 1 个是 `Steam locomotive on a mountain railway`（经 `mountain` 命中地理语义，
  但素材域是 vehicle）。
- `zh_03` 1 个：游戏皮肤界面截图（`界面` 与计算设备域共词）。
- `syn_01`/`syn_03` 各 1 个：`设备`/`界面` 与 computing_device 共词导致的跨域命中。
- `en_05`/`syn_04`/`weak_01`：`geography_nature`/`art_culture` 与期望域部分重叠（`galaxy` 命中 `geography` 的
  "vista" 类词、`咖啡` 命中 `art_culture` 的 "cup" 语境等）。
 → 这些残余说明：**域级匹配只能提高"候选质量"，不能替代语义判定**；判定仍归 4-B + 人工。

**UNKNOWN 分析**：`amb_01`（Pico 4 头显）与 `amb_02`（galaxy 设备）在 A/B 两侧都是 **5/5 候选记 UNKNOWN**。
B 的 top-5 在 `amb_01` 上其实**全是 xr_device**（看起来"对"），但因为有 `pico`（品牌/地名）歧义，
仍**不记为 TP**——这是本阶段最重要的纪律点：`检索到候选 ≠ 语义正确`。

**无结果 / 弱结果**：`weak_02`（深海热泉管虫）与 `none_01`（波斯地毯修复）在 A/B 两侧均**空候选**（正确）；
`none_02` A 侧 4 个假匹配 → B 侧 **0**。**不制造假匹配**这一点由 B 达成，并由套件 E1/E2 固定。

## 6. 检索改进不绕过 4-B / 许可 / 素材校验（引擎级证据）

`tests/retrieval_quality_test.py` H 组（真实图片 + 真实校验链，离线）：

| 断言 | 结果 |
|---|---|
| H1 中文查询 + 查询扩展 → **英文命名**素材被检索到并通过全量校验 | `external_verified=1`（`Virtual reality headset demo.jpg`，CC BY-SA） |
| H2 同批候选里 `fair use` 被**许可门禁**拦下、截断文件被**素材校验**拦下 | 拒绝码 `ASSET_LICENSE_RESTRICTED` + `ASSET_TRUNCATED`，两者均**未入候选池** |
| H3 默认配置（v1，无扩展）对同一中文查询 | `external_verified=0`（改进确实来自 4-E 的 opt-in，不是偷偷改默认） |
| H4 检索配置如实留痕 | 产物含 `retrieval_config{scoring, query_expansion, expanded_terms, lexicon 指纹}` |
| F1–F4 | 4-B 词表 sha256 未变、真值仍钉 `a_2ed5f41d6b58`、检索层**不导入 semantics/不产出 verdict**、侵权素材在检索层仍只是"候选" |

## 7. 回归：4-A / 4-B / 4-C / 4-D

| 项 | 命令 | 结果 |
|---|---|---|
| 4-A 指标 | `tests/metrics_test.py` | **18/18**（确定性、只读、`provider=none` 证据） |
| 4-B 验证器 | `tests/semantic_check_test.py` | **29/29**（真值仍钉 `a_2ed5f41d6b58`，**未改**） |
| 4-C 机制 | `tests/human_selection_test.py` | **18/18** |
| 4-C 现状复核 | `phase4c_evidence.py` | 版本链 v1–**v5 `t_b8f866ddc062`**；语义 `MATCH=6/MISMATCH=0/UNKNOWN=0`；attribution ⟷ 时间轴 1:1；鲨鱼素材仍释放未用 |
| 4-D 供给韧性 | `tests/supply_resilience_test.py` / `phase4d_evidence.py` | **55/55** / 八条路径 **fail-closed 8/8**、不污染检查全部为真 |
| 套件总量 | `run_all_suites.py` | **39 total / 39 rc=0 / FAILED: []**（38 + 新增 `retrieval_quality_test` **35/35**） |
| 回归批次 | `phase3a_regression_batch.py` | **24/24 rc=0，非预期结果 = 0** |

## 8. 回归：3-A / 3-B 与 `provider=none`、网络 PENDING

| 项 | 结果 |
|---|---|
| 3-A 真实链路（离线复核） | `phase3a_real_chain.py --resume p_f4b466a4a024` → **16/16 PASS / FAIL 0 / PENDING 0**（抽帧 S01 0.459 / S02 0.921 / S03 0.348 / S04 0.472 / **S05 0.355** / S06 0.919） |
| 3-B 响度契约 / 失败路径 | **32/32** / **12/12** |
| **`provider=none` 回归** | `config/config.json` sha256 `b264644539b2adbbf0f6897b5a118b2a` 与基线 manifest **一致**；`tools.retrieval` 缺省 → `scoring=v1` + `query_expansion=false`（G1 断言）；`provider_from_config(none)` 仍为纯 no-op；4-D 的 `supply_cache` 仍默认关闭 |
| **网络 PENDING 原样保留** | `phase2e_failure_paths` / `phase2e_real_provider`（及标注依赖网络的 `phase3a_run1_verify`）**状态与期望值未改写**，仍记 `PENDING（环境）`；本轮真实网络探针 `status=OK` **仅作记录**，不改任何状态 |

## 9. 未做与已知限制（如实登记）

1. **未做自动改选材**：4-E 只量化与改进**候选质量**；选材仍由既有 2-C 策略 + 4-C 人工闭环决定。
2. **测试集与词典同源**：B 的域命中率 100% 是"字典覆盖到的概念"上的结果，**不可外推**为通用准确率；
   词典未覆盖的概念（如"深海热泉管虫"）B 会**如实返回空候选**而不是硬凑。
3. **域级粒度**：指标衡量"语义域是否命中"，不衡量"这一张图是否最佳"；同域泛化（如"量子计算机"→ 通用 PC 图）
   会在域级指标里算 TP，需要下游 4-B + 人工进一步收敛。
4. **真实网络探针的伪友**：扩展词 `prionace glauca` 在真实检索中带出 `Picea glauca`（云杉）；
   说明"查询扩展"本身也有假阳性风险，需靠 4-B / 许可门禁 / 人工复核兜底。
5. **两套打分不可混用**：v1 的分数被字符级关键词抬高，**A/B 分数不可直接比较**，只能比较指标。
6. **默认仍为 v1**：本阶段没有改变默认行为（授权要求"保持既有不变"）；要启用需在
   `tools.retrieval.scoring="v2"` / `tools.retrieval.query_expansion=true` 显式配置（RUNBOOK 已写明）。
7. 4-C/4-D 与 3.x 的既有限制**不变**（见 `PHASE4C_REPORT.md` §8、`PHASE4D_REPORT.md` §9、`KNOWN_ISSUES.md`）。

## 10. 新 baseline（ZIP + manifest + SHA256）

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4e-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4e-baseline.zip`（5,942,274 字节） |
| **zip sha256** | **`275f9a1aa5f4f2f493df10dabcbfd544438146d40679ff47951433d90eb0f55b`** |
| 文件数 / 源码字节 | **355 文件 / 7,684,598 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/`**，与前序基线同口径） |
| manifest | `baseline/baseline_manifest_4.x-phase4e-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4e-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移） |
| 断点快照 | `snapshots/4.x-phase4e-20260916.{zip,db,json}`（DB sha256 `d0539635690bb4b9…`，14,315,520 字节） |
| 上一冻结基线（未动） | `4.x-phase4d-baseline.zip` sha256 `f2c783d4…1641` |
| 相对上一基线 | 代码 **修改 1 / 新增 4 / 删除 0**（另 `CHANGELOG.md`、`STATUS.md` 两处文档登记；`config`/DB schema **未变**） |

**回归批次**：`phase3a_regression_batch.py` → **24 项全部 rc=0，非预期结果 = 0**（其中 2 项真实网络用例本轮实测通过，**状态仍记 `PENDING（环境）`，未改写**）。

**停止点**：按授权**只做检索质量量化即 STOP**，不进入 4-F。
