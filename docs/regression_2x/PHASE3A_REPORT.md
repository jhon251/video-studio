# 3.x Phase 3-A 报告：真实链路端到端验收 + 许可合规交付

- 日期：2026-09-13（首轮）／2026-09-15（续做闭合）
- 授权范围（逐字）：**"现在授权执行 3.x Phase 3-A：真实链路端到端验收 + 许可合规交付。只做本阶段，不进入 3-B/3-C/3-D。"**
- 阶段判定：**PASS**——一个真实项目跑通 真实 LLM → Wikimedia Commons（真实搜索）→ 真实下载/校验 →
  真实 TTS → 旁白闸门 → 时间轴 → 渲染 → 解码 → 抽帧核验；`attribution`/credits 台账与 4 条自动断言全部成立。
  - 过程说明（如实记录）：首次执行时 Wikimedia 被网络链路阻断（TLS 握手超时，§5），该项当时按纪律记 **PENDING**；
    网络恢复后续做，**真实搜索又暴露并修复了第 2 个查询整形缺陷**（跨镜头品牌被 AND 到一起 → 0 命中，§7 缺陷 9），
    随后全链路 **16/16 PASS**（`logs/phase3a_real_chain.json`）。**PENDING 是在条件具备后重新跑通才转成 PASS 的，不是改写。**
- 真实项目：`p_f4b466a4a024`（真实链路；最终 render 任务 `t_539c107ab85e`）；
  `p_a2fe33da8739`（Phase 2-E 真实下载字节，补充验证 §6）。

---

## 0. 判定摘要（逐项）

| # | 项 | 判定 | 证据 |
|---|---|---|---|
| 1 | 新增只读交付物 `attribution`（署名/许可台账）+ `credits_<task>.txt` | **PASS** | `tests/attribution_compliance_test.py` **24/24**；真实链路 6 条台账 + 随片 credits（§1/§4） |
| 2 | 许可证机械分类（`PUBLIC_DOMAIN`/`FREE_ATTRIBUTION`/`RESTRICTED`/`UNKNOWN`） | **PASS** | 同上 A1–A8；`material_taxonomy_test` 40/40、`material_provider_test` 46/46 |
| 3 | 断言①：`RESTRICTED`/`UNKNOWN` **绝不入片**（外部素材） | **PASS** | 套件 B/C 组 + 池级纵深防御；真实链路 `restricted_or_unknown_in_film == []`，入片 6 条全为 `FREE_ATTRIBUTION` |
| 4 | 断言②：台账 ⟷ `material_timeline` **逐条 1:1** | **PASS** | 套件 B 组逐字段比对；真实链路 C1/C2（6 vs 6） |
| 5 | 断言③：外部素材**真的在画面上**（`appears_in_film=true` 且 corr ≥ 阈值） | **PASS** | 真实链路 6/6：corr **0.459 / 0.921 / 0.348 / 0.736 / 0.471 / 0.732**（阈值 0.30） |
| 6 | 真实 LLM 全链路 | **PASS** | 26/26 任务、脚本 $0.00371196、无 MockLLM |
| 7 | 真实 TTS + 旁白完整性闸门 | **PASS** | **6/6 COMPLETE**、`narration_duration_s=112.728`、段级状态齐全、闸门通过 |
| 8 | 时间轴权威时长 + 渲染 + 解码 | **PASS** | **104.000s**、2 流、`ffmpeg` 解码 **rc=0**、`delta_ratio 0.0839 ≤ 0.1` |
| 9 | **真实**搜索 → 真实下载 → 校验 → 上屏 | **PASS** | `material_mode=external`、**真实下载 11,543,130 字节**、4 候选通过校验、6/6 镜头用上外部素材（D1/D2） |
| 10 | 回归不退化 | **PASS** | **32/32 套件 rc=0**；E2E/ingest/2-C/2-D/2-A·B 全绿（§8） |

## 1. 交付物①：署名 / 许可台账（`attribution` + `credits_<task>.txt`）

- 位置：渲染任务新增 artifact `attribution`（**只读**，由 `render_output.material_timeline` 逐条派生，
  **不重新推断、不重新打分、不重新挑素材**）；人可读文本落盘 `projects/<pid>/output/credits_<task_id>.txt`。
- 产物顺序契约**未变**：`render_output` 仍是渲染任务 `artifacts[0]`；`attribution` **先写文件、后挂载**
  （这样 `render_output.attribution_artifact` 能直接引用其 id，同时不破坏既有消费者按 `[0]` 取成片的约定）。
- 逐条字段（与授权要求逐项对应）：`scene_id / window_s / fallback_state / scope / provider / source_id /
  source_url / license / license_class / usage_restrictions / attribution / selected_asset{asset_id,name,sha256,
  path,relative_path,bytes,width,height} / appears_in_film / film_evidence`；汇总字段：`entry_count /
  distinct_assets / external_entry_count / local_user_material_entry_count / license_classes_used /
  restricted_or_unknown_in_film(+_scope) / licence_blocked_candidates / license_policy / credits_file`。

**真实样例**（`p_a2fe33da8739`，Phase 2-E 真实下载的 Commons 字节；节选自
`projects/p_a2fe33da8739/artifacts/a_3f45053226a6.json`）：

```json
{"scene_id": "S01", "window_s": [0.0, 4.0], "scope": "external",
 "provider": "wikimedia_commons", "source_id": "752249",
 "source_url": "https://upload.wikimedia.org/wikipedia/commons/b/b0/Virtual_reality_headset_and_wired_gloves%2C_Ames_Research_Center.jpg?...",
 "license": "Public domain", "license_class": "PUBLIC_DOMAIN",
 "usage_restrictions": "Public domain",
 "attribution": "National Aeronautics and Space Administration .",
 "selected_asset": {"asset_id": "asset_3518ae2ed046",
   "name": "Virtual reality headset and wired gloves, Ames Research Center.jpg",
   "sha256": "3518ae2ed046b9cb3be8499dfe696467419e5d256342e7ac90c20cae4a842c74",
   "bytes": 21772, "width": 464, "height": 416},
 "appears_in_film": true,
 "film_evidence": {"sample_t": 2.0, "best_asset_id": "asset_3518ae2ed046",
                   "corr": 0.486, "match": true, "corr_expected": 0.486, "corr_best": 0.486}}
```

对应 `output/credits_t_36cc6ee3df8f.txt`（随片交付）：

```
- 镜头 S01（0.0-4.0s）：Virtual reality headset and wired gloves, Ames Research Center.jpg
  - provider: wikimedia_commons
  - source_id: 752249
  - source_url: https://upload.wikimedia.org/...
  - license: Public domain（类别 PUBLIC_DOMAIN）
  - attribution: National Aeronautics and Space Administration .
  - usage_restrictions: Public domain
  - sha256: 3518ae2ed046b9cb3be8499dfe696467419e5d256342e7ac90c20cae4a842c74
  - 本地文件: external/3518ae2ed046….jpg（sha256 与上相符即字节未被替换）
```

## 2. 交付物②：许可机械分类与门禁（单一事实源）

- `core/materials.py` 现为唯一实现：`LICENSE_CLASSES`、`classify_license()`、`license_block_reason()`、
  `license_gate_applies()`、`is_external_candidate()`；`tools/material_provider.py` 复用（消除两份实现漂移）。
- 分类规则（**机械字符串映射，不做法律判断**）：`CC0/PD` → `PUBLIC_DOMAIN`(清权)；`CC BY*` → `FREE_ATTRIBUTION`(清权，须署名)；
  `fair use / non-free / all rights reserved / copyright / permission` → `RESTRICTED`(不清权)；
  空 / `unknown` / `unchecked` → `UNKNOWN`(不清权)。**只有前两类放行**。
- **门禁适用范围 = 外部 provider 素材**（`license_gate_applies`）：3-A **新增的两道门禁**（`classify_scene`
  分类阶段、渲染池）**只作用于外部候选**；默认路径（`provider=none`）下本地 `local_ingest` 自带素材不在范围内
  ——管线拿不到任何提供方声明，只原样记录声明值（台账 `scope=local_user_material`）。理由与证据见 §7 缺陷 1
  （该范围界定同时是 2.x/3.x 本地素材契约不回归的前提）。
  **精确边界（逐字核对 2-E 基线源码得出）**：provider 层**既有**门禁（Phase 2-D/2-E）本次**未改**——
  2-E 的 `_license_flags` 为"非空且非 unknown/unchecked 即清权"，空许可证同样被拒（`ASSET_LICENSE_MISSING`），
  3-A 只是把清权判据换成 `classify_license`（新增 `fair use/non-free/…` → `ASSET_LICENSE_RESTRICTED`）。
  即：**空/未声明许可证在 2-E 与 3-A 下结果相同**；变化的只有"非空但受限"的字符串。
  合规断言 `restricted_or_unknown_in_film` 的 scope 明确写为 `external_provider_assets`，避免被误读为"全量素材已审查"。
- 纵深防御：provider 层拒收（`excluded_candidates` + `needs_hitl`）→ `classify_scene` 分类阶段再查一次
  （`usable=false` + `unusable_reason=ASSET_LICENSE_*`）→ 渲染池再查一次（`licence_blocked` 留痕）。

## 3. 交付物③：自动断言（全部可复现）

| 断言 | 实现位置 | 验证 |
|---|---|---|
| `RESTRICTED`/`UNKNOWN` 绝不进成片 | `classify_scene` 门禁 + 池级门禁 + 台账 `restricted_or_unknown_in_film` | 套件 A5–A8/B/C；真实链路 `[]`；真实字节 13/13 |
| 台账 ⟷ 时间轴逐条一致 | `_build_attribution` 同一份数据派生 + 套件逐字段比对 | 套件 B1–B14；真实链路 C1/C2（6 vs 6） |
| 外部素材真的在屏（`appears_in_film=true`，corr ≥ 0.30） | 抽帧 Pearson 48×48 + `film_evidence.corr_expected/corr_best` 写回 | 套件 B12/B13（0.698/0.699）；真实链路 6/6（0.348–0.921） |
| 台账字段完整（provider/source_id/source_url/license/attribution） | `_build_attribution` + 套件 B8 | 套件 + 真实链路 credits（§4） |
| credits 文件落盘且含关键字段 | `output/credits_<task>.txt` | 套件 B9；真实链路 C3；真实字节 A10/A11 |

## 4. 真实链路（真实 LLM + 真实 Wikimedia 搜索/下载 + 真实 TTS + 渲染）

命令：`python docs/regression_2x/phase3a_real_chain.py`（真实 LLM + 真实 TTS + 真实 provider；
配置 `config/config.real.provider.json`）。证据：`logs/phase3a_real_chain.json` / `.log`（**VERDICT: PASS，PASS=16 FAIL=0 PENDING=0**）。

| 环节 | 实测 |
|---|---|
| 真实 LLM | 26/26 任务完成，脚本成本 **$0.00371196**，无 mock |
| **真实搜索（Wikimedia Commons）** | 查询阶梯 `["Quest 3", "PICO 4", "PSVR2"]`，**实际发出 2 次请求**：`Quest 3`→8 条、`PICO 4`→8 条（累计 16 图像候选，`mode=latin_clusters`） |
| **真实下载 + 校验** | **11,543,130 字节**；16 候选 → 4 个通过全部校验（容器完整性/ffprobe/ffmpeg 解码/PIL/尺寸/**许可证**）；6 个被拒且带明确错误码（`ASSET_OVERSIZE` ×1、`PROVIDER_RATE_LIMITED` ×5，媒体主机 429 实测 15 次，退避重试 15 次后仍成功的部分照常入片） |
| 许可证 | 16 条候选全为 `FREE_ATTRIBUTION`（`CC BY-SA 4.0`）；入片 6 条全部 `FREE_ATTRIBUTION`，`restricted_or_unknown_in_film == []` |
| 真实 TTS | **6/6 COMPLETE**，`narration_duration_s=112.728` |
| 旁白闸门 | 通过（`narration_state=COMPLETE`） |
| 时间轴权威时长 | `timeline_duration_s=104.0`、`delta_ratio 0.0839 ≤ 0.1`、`within_tolerance=true` |
| 时间轴素材 | `timeline=6 有素材=6`、`assembly=SUCCEEDED`、4 个不同素材（2 个素材各复用 2 个镜头） |
| 渲染 + 解码 | 成片 **104.000s**、2 流、`ffmpeg -f null` **rc=0** |
| **抽帧核验（真的在屏）** | 6/6 `appears_in_film=true`：corr **0.459 / 0.921 / 0.348 / 0.736 / 0.471 / 0.732**（阈值 0.30） |
| 署名台账 | `attribution` 6 条、`license_classes_used={"FREE_ATTRIBUTION":6}`、`credits_t_539c107ab85e.txt` 随片落盘 |

真实样例（`credits_t_539c107ab85e.txt` 节选，均为真实下载并校验过的 Commons 字节）：

```
- 镜头 S01（0.0-12.0s）：Visitor using a Meta Quest 3 VR headset at IPP Greifswald 2025.jpg
  - provider: wikimedia_commons | source_id: 177258402
  - license: CC BY-SA 4.0（类别 FREE_ATTRIBUTION） | attribution: Siarhei Besarab
  - sha256: 4f49f4c7edd0fda931ce4ff1cd859ca920d308ad8173c95fdc89dcfcc21190a6
- 镜头 S02（12.0-32.0s）：Meta Quest 3 front View.jpg
  - provider: wikimedia_commons | source_id: 139518203
  - license: CC BY-SA 4.0（类别 FREE_ATTRIBUTION） | attribution: Roy.wonder.cohen
```

> **首轮（2026-09-13）的失败与修复也已留档**：首次执行时 `used="画面并置 Quest PSVR2 PICO"`、
> Commons 检索 **0 命中**（`raw_head={"batchcomplete":true}`、`items=0`）→ `material_mode=external_configured_no_candidate`、
> `downloaded_bytes=0`，`A2/C3/D1/D2` 未过。根因是**查询整形**（见 §7 缺陷 6 与缺陷 9），修复后重跑即全绿。

## 5. 过程阻断：Wikimedia 曾被网络链路阻断（环境，非代码；已恢复）

首轮修复查询整形后重试时，网络已不可达；**这就是当时把第 9 项记为 PENDING 的原因**。诊断证据（全部落盘）：

| 证据文件 | 结论 |
|---|---|
| `logs/phase3a_net_probe.txt` | `commons/upload.wikimedia.org`：**TCP 0.2s 可连，TLS 握手超时**；同机 `api.deepseek.com`(0.16s)、`speech.platform.bing.com`(0.40s)、`www.baidu.com`、`www.example.com` **TLS 均正常** |
| `logs/phase3a_tls_probe.txt` | `commons/upload/api.wikimedia.org`、`en.wikipedia.org`：TLS1.2 / TLS1.3 / 默认 **全部握手超时**（与版本无关） |
| `logs/phase3a_dns_probe.txt` | 解析结果 `103.102.166.224 / .240` = **真实 Wikimedia 网段**（非 DNS 污染），TCP 443 可连 |
| `logs/phase3a_network_wait.txt`、`logs/phase3a_network_watch_long.txt` | 连续 90+ 次重试（每次间隔 25–30s，跨 ~50 分钟）**全部失败**，无一次成功 |
| `logs/phase3a_net_probe_resume.txt`（次日） | **已恢复**：`commons` TLS 1.74s OK、`upload` TLS 4.62s OK → 随即完成真实链路（§4） |

判读：**域名级 TLS 阻断（中间盒丢弃 ClientHello）**，与本机代码/配置/凭据无关（Phase 2-E 当日同一代码可达）。
按授权要求"如真实 TTS、外部素材或环境导致无法证明，必须如实标记 PENDING/BLOCKED/FAILED，不得用缓存、Mock 或
驱动脚本冒充完整真实链路" → 当时第 9 项记 **PENDING（环境）**，未做任何替代性伪造；网络恢复后**重跑**才转为 PASS。

> **收工/续做的操作口径（已纠正）**：`phase3a_real_chain.py --resume <pid>` **只做核验**（它只推进未结算任务，
> 不重做已 SUCCEEDED 的任务）。要真正重跑取数链，必须显式重做：
> `run.py --config config/config.real.provider.json redo <retrieval_task>` → `run.py … run <pid> --limit 4`
> → `redo <render_task>` → `run.py … run <pid> --limit 4` → 再 `--resume` 核验。
> （次日实际的续做命令与任务 id 见 `PHASE3A_CHECKPOINT.md` §3 的更正说明。）

## 6. 补充验证：真实下载字节上的外部素材链路（**来源如实标注**）

在 **Phase 2-E 真实下载并校验过的 Commons 字节**上重做渲染（`redo render` → v2 `t_36cc6ee3df8f`），
核验 3-A 的外部素材链路断言（这是**独立于 §4 的第二个证据点**；字节来源为 2-E 下载，标注清楚）：

| 检查 | 结果 |
|---|---|
| attribution 产物存在（3-A 新增） | PASS（`a_3f45053226a6`） |
| A1/A2 台账 ⟷ 时间轴 1:1、`scene_id`/`asset_id`/`sha256` 一致 | PASS（2 vs 2） |
| A3/A4 外部条目含 `provider/source_id/source_url/license` | PASS（`wikimedia_commons` / `752249` / `Public domain`） |
| A5/A6 无 `RESTRICTED`/`UNKNOWN` 入片 | PASS（`[]`，scope=`external_provider_assets`） |
| A7 许可类别已记录 | PASS（`{"PUBLIC_DOMAIN": 2}`） |
| A8 台账 `sha256` == 磁盘字节（字节未被替换） | PASS（`3518ae2ed046…` / 21,772 B） |
| A9 `appears_in_film=true` 且 `corr ≥ 0.30` | PASS（corr **0.486**） |
| A10/A11 credits 文本含关键字段 + 文件落盘 | PASS |
| A12 成片存在 | PASS（10.000s） |

**口径声明（不得误读）**：这些字节是 **Phase 2-E 真实从 `upload.wikimedia.org` 下载**的（内容寻址
`media/external/<sha256>.jpg`，sha256 可核），但**下载动作发生在 2-E**，本次只重做了下游（选择/门禁/台账/渲染/抽帧）。
因此它证明的是"**外部素材链路的下游与合规交付物**"，本身**不能替代** 3-A 要求的"本次真实搜索 + 下载"
（该要求后来已由 §4 的真实链路**独立**满足：11,543,130 字节为本次真实下载）。

## 7. 本阶段发现并修复的缺陷（10 项，含 1 次真实回归）

| # | 缺陷 | 发现方式 | 修复 |
|---|---|---|---|
| 1 | **许可门禁过度适用（真实回归）**：分类阶段门禁把 `local_ingest` 自带素材（`license="unchecked"`、无 provider）判为 `ASSET_LICENSE_MISSING` → 冻结套件 `material_taxonomy_test`/`scene_assembly_test`/`pipeline_mock` 失败（**29/32**） | `run_all_suites.py` | 新增 `license_gate_applies()`/`is_external_candidate()`，门禁**收窄为外部 provider 素材**；恢复 **32/32** |
| 2 | **artifact 顺序破坏**：`attribution` 先挂载 → `render_output` 不再是 `artifacts[0]` → `pipeline_mock` `KeyError: 'output'` | `run_all_suites.py` | 改为**先写 attribution 文件、后挂载**；`render_output` 保持 `[0]`（已在真实渲染任务上验证顺序） |
| 3 | 通用 provider 对 `fair use` 误放行（基类"非空即清权"） | 新套件 A3/A5 | 基类 `_license_flags()` 改用 `classify_license` |
| 4 | `selected_asset` 投影缺 `license_class` | 新套件 B 组 | 补齐（交付物与断言所需） |
| 5 | `film_evidence` 缺 `corr_expected/corr_best` | 新套件 B13 | 写回证据字段 |
| 6 | **中文查询对 Commons 0 命中**（真实链路首轮暴露） | 首轮 A2/C3/D1/D2 | 查询整形改为**按语料取词**（优先拉丁/数字词，`logs/phase3a_shaping_rules.txt`） |
| 7 | credits 文本把本地路径标为 `license_url/来源页` | 人读样例复核 | 改为"本地文件" |
| 8 | `phase2d_provider_e2e` D3 断言未接受 `ASSET_TRUNCATED`（2-E 完整性检查引入） | 回归批次 | 断言更新为接受该错误码（非放宽：截断仍是拒收） |
| 9 | **跨镜头品牌被 AND 成一个查询（第二个查询整形缺陷）**：retrieval 把全部镜头文本拼成 2,000 字符查询，整形后 `Quest PSVR2 PICO Valve` 四词 AND → Commons **0 命中**（实测 `logs/phase3a_query_ladder.txt`：4 词 0、3 词 0、2 词 1(非图片)、单词 8） | 网络恢复后的**真实搜索**实测 | 新增 `shape_queries()`：把文本切成**拉丁词簇**（源码位置上连续才算一簇 = "品牌+型号"），多词簇优先逐条查询、拿到足够候选即停；`search()` 逐条尝试并记录 `query_shaping.attempts[]`。实测 `["Quest 3","PICO 4","PSVR2"]` → 2 次请求 16 条候选（§4） |
| 10 | 自查文档错误：`PHASE3A_CHECKPOINT.md` 曾写"`--resume` 会自动 redo retrieval/render" | 次日续做实测 | **更正**：`--resume` 只核验、不重做；已在报告 §5 与 checkpoint §3 写明正确的 redo 命令序列 |

缺陷 6 的离线证明（`logs/phase3a_shaping_rules.txt`）：同一段首轮查询（2,000 字符）
旧规则 → `"画面并置 Quest PSVR2 PICO"`（0 命中）；只取拉丁词 → `"Quest PSVR2 PICO Meta"`。
缺陷 9 说明**光取拉丁词还不够**：不同镜头的品牌不能 AND 在一起，必须**按簇分开查**（真实数据支撑见
`logs/phase3a_query_ladder.txt` 与 `logs/phase3a_query_ladder_live.txt`）。

## 8. 回归（全部在**最终代码 + 网络可用**下重跑）

`docs/regression_2x/phase3a_regression_batch.py`（原始结果 `logs/phase3a_regression_batch.json`，
分类判读 `logs/phase3a_regression_batch_classified.json`：**17/17 项 rc=0，非预期结果 = 0**）。

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **32 total / 32 rc=0 / FAILED: []**（新增 `attribution_compliance_test` **24/24**） |
| 新交付物合规套件 | `tests/attribution_compliance_test.py` | **24/24**（A1–A8 分类/门禁；B1–B14 真实 ffmpeg 渲染全链路；C1–C2 池级纵深防御） |
| 素材分类学 | `tests/material_taxonomy_test.py` | **40/40**（未退化） |
| Provider 契约 | `tests/material_provider_test.py` | **46/46** |
| 旁白契约 | `tests/narration_contract_test.py` | PASS |
| 3 机械 E2E | `run_all_tests.py --fresh` | A/B/C **全 SETTLED**（成片 17.000s / 24 kHz / 1280×720 h264+aac） |
| 真实 LLM 小测 | `real_small_test.py` | **PASS**，**MockLLM=0**（2 调用 / 5,394 tokens / $0.002915） |
| 二进制真实性 | `check_binaries.py` | **PASS**（真 ffprobe 且非 ffmpeg 副本） |
| 本地 ingest | `run_ingest_test.py` | **PASS**（抽帧 t=8.5s 命中 **0.747**） |
| Phase 2-C 追溯 | `phase2c_trace.py` | **38/38** |
| Phase 2-C 故障矩阵 | `phase2c_fault_matrix.py` | A/C **出片**、B/D **BLOCKED 且无成片** |
| Phase 2-D 边界矩阵 | `phase2d_boundary_matrix.py` | **40/40** |
| Phase 2-D Provider E2E | `phase2d_provider_e2e.py` | **12/12** |
| **Phase 2-E 真实链路** | `phase2e_real_provider.py` | **13/13**（网络恢复后真实搜索/下载/上屏全部通过） |
| **Phase 2-E 失败路径** | `phase2e_failure_paths.py` | **29/29**（首轮离线时 23/29：6 项需真实搜索；网络恢复后全绿——**未因查询阶梯改动而退化**） |
| Phase 2-A/B 验收 | `phase2_accept.py --verify p_ab2b352e06b8` | **PASS**（成片 438.0s、12/12 在屏） |
| **3-A 真实链路项目复核** | `phase2_accept.py --verify p_f4b466a4a024` | **PASS**（首轮离线时 FAIL——负对照；补齐外部素材后转 PASS） |
| 3-A 真实字节核验 | `phase3a_cached_real_check.py p_a2fe33da8739` | **13/13** |

> 首轮（Wikimedia 被阻断期间）该批次有 3 项非 0，均为**环境**且已逐条标注；网络恢复后在**同一份最终代码**上
> 重跑，**17/17 rc=0**。这条演进如实保留在 `logs/phase3a_regression_batch_classified.json` 与本节。

## 9. 未解决项 / 已知限制（如实列出）

1. **词法匹配会选到语义无关的外部素材（3-A 明确不做语义改选材）**：真实链路里 6 个镜头中
   有 2 个（S04/S06）选中了 `Tiburón azul … canal Fayal-**Pico** …`（一张鲨鱼照片）——因为旁白里的品牌
   `PICO` 与该西班牙语标题里的 `Pico`（山峰/地名）**词法同形**。合规侧完全成立（许可清晰、署名完整、抽帧证实在屏
   corr 0.736/0.732），但**内容相关性不对**。这属已知限制（原 ⑱/语义级对齐），需 4.x 或受限版处理；
   3-A 授权明确禁止"语义级自动改选材"，故本阶段**不动**判据与阈值，只如实留档（样例见 §4 时间轴）。
2. **本地自带素材不在许可门禁范围**（有意设计）：管线无提供方声明可查，只原样记录（台账 `scope=local_user_material`）；
   若将来要对本地素材做许可审查，需要新的输入通道（不属 3-A）。
3. **中文-only 查询对 Commons 命中率低**（已知限制 ⑱）：`cjk_only` 模式下仍可能 0 命中，如实记录、不做翻译/语义猜测。
4. **媒体主机限流是常态**：本次真实下载 11.5 MB 期间 `rate_limited=15`、`retries=15`、`download_ms=481,245`（≈8 分钟），
   5 个候选最终因 429 被拒（错误码如实记录，未当成功）。要提升吞吐需改节流策略，不在 3-A 范围。
5. **响度契约不一致**（3-B 处理）：agent 路径仅产出 `audio_plan`（声称 −14 LUFS + BGM ducking，但无 `loudnorm`），
   而 `stage32b/{vo,render}.py` 用 `loudnorm I=-16:TP=-1.5:LRA=11` + `alimiter`，`qc.py` 断言 −18…−14 LUFS。
   本阶段**未动**（授权禁止响度统一）。
6. **成本残差 ≈¥3.24**：provider 异步结算延迟所致，3-C 对账阶段处理。
7. BGM、第二 Provider、`run.py report`、UI、Git tag：**未做**（超出 3-A 授权）。

## 10. 阶段基线

### 10.1 基线身份

| 项 | 值 |
|---|---|
| 标签 | `3.x-phase3a-baseline` |
| ZIP | `docs/regression_2x/baseline/3.x-phase3a-baseline.zip`（5,812,246 字节） |
| zip sha256 | `296dd44b31020e718ab239d521630b2dcf13b2ca41a7c16cf3961673a8e4e74e` |
| 文件数 / 源码字节 | **335 文件 / 7,333,842 字节**（代码/配置/测试/脚本 + 根文件，**排除 `docs/`**） |
| manifest | `baseline_manifest_3.x-phase3a-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 校验 | `verify_baseline.py 3.x-phase3a-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、**0 缺失、0 漂移**） |
| 断点归档 | `snapshots/3.x-phase3a-final-20260915.{zip,db,json}`（DB sha256 `39a8f35558e4e2b5…`，7,647,232 B） |

关键指纹（相对 2-E 基线）：`core/materials.py 253b628c2d0b1348…`（许可单一事实源）、
`tools/material_provider.py 2607f35049716528…`、`tools/provider_wikimedia.py f5ee1f6a4183ae45…`
（查询阶梯 `shape_queries()` + 分簇搜索）、`agents/editing/agent.py 40d2d27728e3358f…`（attribution/credits + 断言）、
`tests/attribution_compliance_test.py 5dc20f8937768749…`（新）、
`config/config.real.provider.json e74b8da5fbf55fa3…`（新）；

关键指纹（相对 2-E 基线）：`core/materials.py 253b628c2d0b1348…`（许可单一事实源）、
`tools/material_provider.py 2607f35049716528…`、`tools/provider_wikimedia.py f5ee1f6a4183ae45…`
（查询阶梯 `shape_queries()` + 分簇搜索）、`agents/editing/agent.py 40d2d27728e3358f…`（attribution/credits + 断言）、
`tests/attribution_compliance_test.py 5dc20f8937768749…`（新）、
`config/config.real.provider.json e74b8da5fbf55fa3…`（新）；
**未改动**：`config/config.json b264644539b2adbb…`（仍 `provider=none`）、`agents/retrieval/agent.py 32de908c26a8ab90…`、
`agents/voice/agent.py 9f102d2b78b8ba91…`、`core/engine.py becfdd8e56dd0e8b…`、`tools/ffmpeg_tool.py 7b62ab0f628da874…`。

- 快照内容 = 最终代码 + 最终根文档（README/CHANGELOG/STATUS 均在包内）；`docs/` 排除，故本报告可继续更新。
- 收工时的中间态快照 `3.x-phase3a-wip` 与归档 `snapshots/3.x-phase3a-wip-20260913.{zip,db,json}` **保留**，
  仅作历史追溯（它对应"真实链路尚未补齐"的那个时点）。

## 11. 复现命令（全部在本报告所述代码上执行过）

```bat
:: 1) 合规单测 + 全量套件（离线，无需网络）
python tests\attribution_compliance_test.py            :: 期望 24/24
python docs\regression_2x\run_all_suites.py            :: 期望 32 total / 32 rc=0

:: 2) 非网络回归批次（含 E2E / ingest / 2-C / 2-D / 2-A·B / 真实小测）
python docs\regression_2x\phase3a_regression_batch.py
python docs\regression_2x\phase3a_classify_batch.py    :: 期望"非预期结果 = 0"

:: 3) 真实链路（需要 Wikimedia 可达）
python docs\regression_2x\phase3a_real_chain.py                       :: 全新真实项目（真实 LLM 花额度）
::    已有项目要**重跑取数链**必须先显式 redo（--resume 只核验）：
::    python run.py --config config\config.real.provider.json redo <retrieval_task>
::    python run.py --config config\config.real.provider.json run <pid> --limit 4
::    python run.py --config config\config.real.provider.json redo <render_task>
::    python run.py --config config\config.real.provider.json run <pid> --limit 4
python docs\regression_2x\phase3a_real_chain.py --resume p_f4b466a4a024  :: 只核验（期望 16/16 PASS）
python docs\regression_2x\list_tasks.py p_f4b466a4a024                 :: 取 redo 用的 task_id

:: 4) 真实下载字节上的外部素材链路核验（只读）
python docs\regression_2x\phase3a_cached_real_check.py p_a2fe33da8739   :: 期望 13/13

:: 5) 网络诊断三件套（判断"是环境还是代码"）
python docs\regression_2x\phase3a_net_probe.py
python docs\regression_2x\phase3a_tls_probe.py
python docs\regression_2x\phase3a_dns_probe.py

:: 6) 查询整形实测（离线 + 实时）
python docs\regression_2x\probe_shaping_rules.py         :: 离线：旧规则 vs 新规则
python docs\regression_2x\probe_query_ladder.py          :: 实时：哪些机械查询能命中
python docs\regression_2x\probe_query_ladder_live.py     :: 实时：真实查询文本走 provider.search（不下载）

:: 7) 基线校验
python docs\regression_2x\verify_baseline.py 3.x-phase3a-baseline
```

## 12. 停止点

按授权"只做本阶段，不进入 3-B/3-C/3-D"：**未**做 BGM、**未**接入第二个 Provider、**未**做语义级自动改选材、
**未**做响度统一、**未**做成本对账、**未**实现 `run.py report`、**未**改 UI、**未**建 Git tag、**未**推翻重构。
Claim/HITL 闸门、append-only 产物、断点恢复、旁白完整性、时间轴权威时长、Phase 2-C 分类学、Provider 验证顺序、
默认 `provider=none`、不自动法律判断——全部保持不变（32/32 套件回归）。**在此停止，等待下一阶段授权。**
