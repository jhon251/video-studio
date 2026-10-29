# 已知问题台账（KNOWN ISSUES）— 3.x Final / Phase 3-C

> **纪律**：本台账只登记**未解决/受限**事项。**不得**把任何未解决项改写成 PASS；
> 每项都标注状态（`OPEN` / `LIMITATION` / `BY DESIGN` / `ENV`）与证据位置。
> 巡检命令：`python run.py report <project_id>`、`python docs/regression_2x/phase3b_audit.py`。

---

## 1. 语义误选（外部素材与画面内容不匹配）——— `LIMITATION`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#1** | 3-A 真实链路成片 6 个镜头中有 **2 个（S04/S06）** 选中 `Tiburón azul … canal Fayal-**Pico** …`（一张鲨鱼照片），因为旁白品牌 `PICO` 与西班牙语标题里的 `Pico`（山峰/地名）**词法同形** | `logs/phase3a_real_chain.json`、`projects/p_f4b466a4a024/output/credits_t_bc*.txt` |

- **性质**：词法匹配的固有局限；**合规侧完全成立**（许可清晰、署名完整、抽帧证实在屏 corr 0.732/0.736）。
- **为何不修**：语义级自动改选材属 4.x/受限版能力，3-A 授权**明确禁止**；3-B/3-C 亦未授权。
- **影响**：内容相关性可能不对（观众可见的错配），但不影响许可合规与时长/旁白/响度契约。
- **建议处置**：4.x 引入语义对齐（embedding/多模态核验）后，以"重选材"而非"改判据"的方式解决。

## 2. 2-E 历史成片音轨不可完全复原 ——— `LIMITATION`（历史取证污染，已记录）

| 编号 | 内容 | 证据 |
|---|---|---|
| **#2** | Phase 3-B 测试**首版**曾就地校正 `projects/p_a2fe33da8739/output/t_36cc6ee3df8f_draft.mp4` 的音轨（-22.0 → -16.0 LUFS）。测试已改为**只操作副本**，并把该成片的**集成响度还原为 -22.0 LUFS**；但原始音轨字节不可完全复原：真峰由 **-13.0 dBTP** 变为 **-3.5 dBTP**（AAC 有损重编所致） | `docs/regression_2x/phase3b_restore_2e_film.py`、`logs/phase3b_audit.json`（原始实测值） |

- **性质**：历史产物的**取证污染**，非产品缺陷；原始数值已留档，当前状态已如实说明。
- **影响**：该历史成片不能再用作"2-E 时点"的逐字节证据（其 JSON 产物与 DB 记录未受影响）。

## 3. `stage32b` 保留 +0.4 dB 限幅补偿 ——— `BY DESIGN`（保留，明确说明）

| 编号 | 内容 | 证据 |
|---|---|---|
| **#3** | `stage32b` 的母带链保留其历史 `volume=+0.4dB` 限幅补偿，因此其成片落在 **-16.8 LUFS**（统一契约 -16 ±1 LU 内，但非恰好 -16） | `src/video_studio/stage32b/render.py`、`logs/phase3b_audit.json` |

- **为何保留**：去掉补偿会改变该历史路径的既有验收口径（其 QC 曾以 ±2 LU 断言）；本阶段只做"统一契约"，不做行为重写。
- **影响**：路径间存在约 0.8 LU 的系统性差异（正式链 ≈ -16.1，stage32b ≈ -16.8），**两者都在契约内**。

## 4. 中文-only 查询对 Commons 命中率低 ——— `LIMITATION`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#4** | 查询整形按语料取词：有拉丁/数字词时用**词簇**查询（`latin_clusters`）；**没有拉丁词**时退回 CJK 词块（`cjk_only`），对英文语料的 Commons 命中率低（实测可为 0） | `logs/phase3a_query_ladder.txt`、`logs/phase3a_shaping_rules.txt`、`run.py report` 的查询阶梯小节 |

- **为何不修**：翻译/语义改写不做（属语义层能力）；CJK-only 场景目前只能降级为纯色底/本地素材。
- **缓解**：脚本/视觉计划里保留品牌型号等拉丁词（真实链路实测即可命中 16 条候选）。

## 5. 媒体主机限流是常态 ——— `ENV`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#5** | Wikimedia 媒体主机下载限流严重：单次真实链路 `rate_limited=15`、`retries=15`、`download_ms=481,245`（≈8 分钟）、5 个候选最终因 429 被拒；全库累计 429 达 144 次 | `run.py report` 素材小节、`logs/phase3c_cost_boundary.json` |

- **现状**：已内置节流 + 429 退避 + 重试预算，被拒候选带明确错误码且**不入片**。
- **影响**：真实链路的素材获取耗时波动大；极端限流下可能 0 素材 → `ASSEMBLY_BLOCKED`（如实阻断，不伪造）。

## 6. 本地自带素材不做许可门禁 ——— `BY DESIGN`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#6** | 许可门禁（`RESTRICTED`/`UNKNOWN` 不得入片）**只作用于外部 provider 素材**；`local_ingest` 用户自备文件只原样记录声明值（台账 `scope=local_user_material`） | `src/video_studio/core/materials.py::license_gate_applies`、`PHASE3A_REPORT.md` §2 |

- **为何如此**：管线拿不到提供方声明，不做法律判断；若对本地素材也拦截会破坏既有本地工作流（3-A 实测的真实回归）。
- **若需审查本地素材**：需要新的输入通道（用户声明许可/上传凭证），不属 3.x 范围。

## 7. 响度契约可被配置覆盖 ——— `BY DESIGN`（默认不放松）

| 编号 | 内容 | 证据 |
|---|---|---|
| **#7** | `tools.ffmpeg.loudness.{target_lufs,max_true_peak_dbtp,tolerance_lu,target_lra,apply_mastering}` 可覆盖默认契约；`apply_mastering=false` 会让渲染 **fail-closed**（不是绕过） | `src/video_studio/core/audio.py`、`tests/audio_loudness_test.py` D6、`docs/regression_2x/phase3b_failure_paths.py` 用例 1 |

- **风险**：显式改配置即可改变目标值（例如把目标放宽到 -20 LUFS）；**默认值即授权契约**，改动会记录在配置文件中。
- **未做**：配置变更审计/告警（可在 4.x 需求中提出）。

## 8. 成本仅有估算，没有真实账单 ——— `LIMITATION`（口径已固化）

| 编号 | 内容 | 证据 |
|---|---|---|
| **#8** | 所有金额都是 `token × 价目表` 的**估算**；账户余额由服务端**异步/批量结算**且可能含其它调用方用量，**不可逐笔归因**；Phase 1.1 残余 **≈¥3.24** 的正式结论是 `NOT_ATTRIBUTABLE_CLIENT_SIDE` | `docs/COST_BOUNDARY.md`、`logs/phase3c_cost_boundary.json`（含零本地调用窗口内余额仍变化的复验） |

- **纪律**：不得写成账单；不得为凑平修改本地数字。

## 9. 失败路径用例使用"合成契约" ——— `BY DESIGN`（仅用于验证 fail-closed）

| 编号 | 内容 | 证据 |
|---|---|---|
| **#9** | `phase3b_failure_paths.py` 用例 2 故意把真峰上限设为 **-40 dBTP**（不可能达到）以验证 TP 分支的 fail-closed；这是**测试合成契约**，不是产品建议值 | `docs/regression_2x/phase3b_failure_paths.py`、`logs/phase3b_failure_paths.json` |

## 10. 其它已知限制（历史台账，未解决）

| 编号 | 内容 | 状态 |
|---|---|---|
| **#10** | Claim 抽查 15 类任务在闸门后仍可能因事实性缺陷需人工介入（`CLAIM_GATE_BLOCKED` 设计使然） | `BY DESIGN` |
| **#11** | `visual_plan` 的镜头数与脚本段落数依赖 LLM 输出质量，偶发不齐（渲染按时间轴兜底） | `LIMITATION` |
| **#12** | 项目目录无自动清理策略（当前 471 个项目、缓存 ≈79 MB）；大库会拖慢全库扫描类脚本 | `LIMITATION` |
| **#13** | 无 Git（按用户指示），版本可追溯性依赖基线 ZIP + manifest + SHA256 | `BY DESIGN` |

---

## 11. 4.x 阶段新增/变更登记（4-A～4-G + 收口审计，2026-09-16）

> 纪律同上：**只登记未解决/受限事项**，不改写历史；4.x 各阶段的 PASS 结论见对应阶段报告。

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#14** | **`LRA=11` 的语义在历史文档中被与两个硬门槛并列写作"契约常量"，易被误读为门槛**。收口审计确认：它是 `loudnorm` 的**目标参数** + 契约字典的**参考/复现值**，**不参与 fail-closed 判定**（闸门只判集成响度 -16±1 LU 与真峰 ≤ -1.5 dBTP）。 | `BY DESIGN`（措辞已澄清） | `logs/phase4x_audit.json` → `lra_audit`；`docs/RUNBOOK.md` §4f |
| **#15** | **是否把 LRA 升级为硬门槛——待决策**。若要把"实测 LRA ≤/≈ 某值"变成门槛，属**契约变更**，需要新的授权；本轮**未改音频链、未改契约常量**。含 BGM 的混音 LRA 天然更大（预混输入 18.30 LU，交付成片实测 13.8 LU），一旦设门槛会直接影响 4-F 的 BGM 能力。 | `OPEN`（待授权决策） | 同上 + `PHASE4F_REPORT.md` §6 |
| **#16** | **4-F 的 BGM 路径使用两遍线性 loudnorm**（而非既有单遍动态）：单遍动态在该混音上输出 -19.5 LUFS（偏差 3.5 LU > 3 LU 收尾上限 → fail-closed）。方法与既有链不同，但**契约常量相同**、成片仍由既有 QC 把关；BGM 关闭时不启用该函数。 | `BY DESIGN`（已显式登记） | `core/audio.py::normalize_two_pass`、`logs/phase4f_bgm_evidence.json` |
| **#17** | **供给缓存是"搜索层元数据缓存"**：TTL（默认 900s）内可能返回过期候选清单；缓存键不含 provider 目录内容。安全性不受影响（命中后仍重新下载 + 校验 + 许可门禁），只影响新鲜度。 | `LIMITATION`（默认关闭） | `PHASE4D_REPORT.md` §9、`tests/supply_resilience_test.py` C 组 |
| **#18** | **检索词典 v1 覆盖有限**：4-E 的 A/B 域命中率 100% 是"词典覆盖到的概念"上的结果，**不可外推**为通用准确率；词典未覆盖的概念会如实返回空候选。真实网络扩展还存在伪友（如 `prionace glauca` 带出 `Picea glauca`）。 | `LIMITATION`（默认关闭） | `PHASE4E_REPORT.md` §5/§9、`logs/phase4e_network_probe.json` |
| **#19** | **节奏建议器的阈值是工程默认值**（3/20/15s、2/12 cuts·min⁻¹ 等），不自适应内容类型；静态判定只看素材类型（图片即静态），**不做画面运动检测**；片级问题以 `scope="film"` 挂在最相关镜头上。 | `LIMITATION` | `PHASE4G_REPORT.md` §8、`logs/phase4g_rhythm_evidence.json` |
| **#20** | **4-C/4-G 的人工决定身份是自填标识**（`--by`），无登录/签名；建议器的建议也**不会自动生效**，任何改动都必须人工决定 + 审批 + redo。 | `BY DESIGN`（已登记） | `PHASE4C_REPORT.md` §8、`PHASE4G_REPORT.md` §5 |
| **#21** | **4-F 的 BGM 夹具为自生成音频**：本仓库**未下载任何真实音乐作品**（未接第二 Provider、未授权音乐来源），但校验链（来源/sha256/许可/attribution/响度）对真实音乐文件同样生效。 | `LIMITATION` | `PHASE4F_REPORT.md` §4 |
| **#22** | **4-F 报告初版有一处不准确表述**（"实测 LRA 由 ebur128 给出并记录在 `audio_loudness` 证据中"）：`measure_loudness()` 只解析 I 与 TP，不解析 LRA。已在收口审计中**更正**并补实测数值。 | `RESOLVED (4.x 收口)` | `PHASE4F_REPORT.md` §6、`logs/phase4x_audit.json` |

---

## 12. 5.x 阶段新增登记（5-A 多模态语义验证，2026-09-16）

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#23** | **CLIP 文本塔只支持英文**：5-A 的"期望域"必须由**词表机械推导**（4-B 词表为主、4-E 检索词典回退），未接入机器翻译或 LLM。旁白若完全不含词表命中词 → `UNKNOWN / MM_UNKNOWN_DOMAIN`（**不猜、不伪造**）。 | `LIMITATION` | `PHASE5A_REPORT.md` §2/§11、`tests/multimodal_test.py` B7–B9 |
| **#24** | **域级粒度**：5-A 回答"画面最像的**语义域**是否就是旁白期望的域"，**不**判断"这张图是否最佳/是否专业级/是否有版权风险"；边际接近的镜头记 UNKNOWN（当前成片 S05 Δ=0.0175 < 0.02 即如此）。 | `LIMITATION` | `logs/phase5a_multimodal_evidence.json` |
| **#25** | **阈值为工程默认值**（`min_sim=0.20`、`margin=0.02`、每镜头 3 帧）：不同素材类型/画风下可能需要调整；调整会改变 UNKNOWN 与 MISMATCH 的比例（阈值可在 `tools.multimodal` 覆盖，**非法值回退、不放松**）。 | `BY DESIGN`（可配） | `src/video_studio/core/multimodal.py::MM_DEFAULTS`、测试 A2 |
| **#26** | **模型权重不在基线包内**：CLIP 权重位于 `models/`（基线口径排除），复算需本地存在同一目录；模型版本以 **sha256 钉定**（`model.safetensors` = `a63082132ba4f97a…`）。若模型/venv 缺失，5-A 一律 `UNKNOWN`（fail-closed），**不影响** 3.x/4.x 任何既有行为。 | `BY DESIGN`（fail-closed） | `logs/phase5a_multimodal_evidence.json` §fail_closed、测试 D1/D2 |

---

## 13. 5.x 阶段新增登记（5-B 多模态候选生成，2026-09-16）

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#27** | **候选排序 ≠ 决定**：候选按**视觉相似度**降序；真实项目里排序第一的是 `Meta Quest 3 side View.jpg`（0.2886），而 4-C 时人实际选的是 `Visitor…`(S04)/`front`(S06) —— 二者**都在候选内**。排序只是证据顺序，不构成推荐结论，选择权仍在人工。 | `BY DESIGN` | `PHASE5B_REPORT.md` §3/§9、`logs/phase5b_candidates_evidence.json` |
| **#28** | **候选池规模受限**：该项目只有 4 个已验证本地素材（另 6 个候选因 `ASSET_OVERSIZE`/`PROVIDER_RATE_LIMITED` 不可用），因此多个镜头共用同一组候选，且都带"已被其它镜头占用"的**复用风险**（替换会影响既有镜头）。 | `LIMITATION` | 同上 §9；`run.py mm-review` 的 rejected/risks 字段 |
| **#29** | **本地自带素材默认不算合格候选**（`require_license_clear=True`）：管线无法核验用户声明（与 3-A `license_gate_applies` 口径一致，见 #6）；如需放行，由人工在 4-C 闭环中决定（`select-candidate` 有自己的校验）。 | `BY DESIGN`（可配） | `core/mm_candidates.py::MMC_DEFAULTS`、测试 A2/B4 |
| **#30** | **候选视觉评分只用 1 帧**（候选是静态图），阈值为工程默认 `min_visual_sim=0.22`（可配、非法值回退）；视频类候选/多帧素材在此版本不覆盖。 | `LIMITATION` | `PHASE5B_REPORT.md` §9 |
| **#31** | **授权书里的基线文件名笔误**：`svg5.x-phase5a-baseline.zip` 不存在，实际为 `5.x-phase5a-baseline.zip`，SHA256 与授权书一致（`1f6bb106…2bac`）→ 按 SHA256 判定为同一基线；已如实登记，未据此做任何猜测性替换。 | `RESOLVED (5-B 登记)` | `logs/phase5b_candidates_evidence.json` → `baseline` |

---

## 14. 5.x 阶段新增登记（5-C 人工候选替换生效，2026-09-16）

> 5-C 是**运维/闭环**阶段：`src/` 零改动。下列为**如实登记的退化与限制**，不得改写成 PASS。

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#32** | **5-A 判定退化（已发生，未消除）**：S06 采用 5-B 排序第一的 `Meta Quest 3 side View.jpg` 后，5-A（CLIP）由 `MATCH`（Δ=0.0742）变为 **`UNKNOWN / MM_AMBIGUOUS`**（`xr_device 0.2248` vs `vehicle 0.2188`，Δ=0.0061 < 阈值 0.02）。**未产生 MISMATCH**，4-B 仍 `MATCH=6`；成片 v6 在 5-A 上比 v5 少一个 MATCH。**未通过调阈值/改逻辑消除**（阈值与规则一字未改）。 | `OPEN`（如实登记） | `logs/phase5c_mm_before_v5.json`、`logs/phase5c_mm_after.json`、`PHASE5C_REPORT.md` §5/§11 |
| **#33** | **候选排序口径 ≠ 成片判定口径**：5-B 用**素材原图**打分（side 0.2886 > front 0.2817），5-A 用**成片抽帧**（已 16:9 裁切 + 叠字幕）判定；本例两者方向不一致（资产级更高的候选在成片级更低）。故 5-B 排序**不能**当作"替换后 5-A 会更好"的预测。 | `LIMITATION` | 同上 §11 观察 2；`core/mm_candidates.py::score_candidates` vs `core/multimodal.py::verdict_for_scene` |
| **#34** | **复用连带**：替换后 `side` 被 S03/S05/S06 **三个镜头**共用（`front` 仅 S02），画面多样性下降；候选池仅 4 个可用素材（#28）使该风险在本项目内**无法通过换材规避**。5-B 已把"已被其它镜头占用"列入候选风险，人工在 reason 中明示接受。 | `LIMITATION` | `logs/phase5c_mmb_after.json`、`logs/phase5c_append_only.json` D 段 |
| **#35** | **`redo` 会就地重指下游任务依赖**：`redo` 把 6 个下游任务（thumbnail/qa/compliance/critic_final/platform/analytics）的 `dependencies` 由旧版本渲染任务改指到新版本渲染任务。这是**设计语义**（非历史篡改：只改该列、状态/版本不变），但**意味着"append-only"在 tasks 表上不是逐字节的**；5-C 用白名单精确断言（行集合+列集合+新旧取值）把它与任何非法改写区分开。 | `BY DESIGN`（已登记） | `logs/phase5c_db_append_only.json` → `allowed_dependency_rewire` |
| **#36** | **许可不合格分支未在真实素材上触发**：本项目 4 个可用素材全部 `FREE_ATTRIBUTION`（另 6 个被 `ASSET_OVERSIZE`/`PROVIDER_RATE_LIMITED` 拒于池外），因此 `HUMAN_SELECTION_LICENSE_BLOCKED` 只能由既有夹具测试覆盖（真实代码路径），5-C 的负向验证只覆盖了"不在池/无归属/无理由/模型不可用"四类。 | `LIMITATION`（覆盖边界） | `logs/phase5c_failclosed.json`、`tests/human_selection_test.py` |
| **#37** | **5-A 测试的"成片条数"校准过期（已在 5-C 修正）**：`tests/multimodal_test.py` F2 原断言写死 `len(films) == 5`；5-C 授权替换产生 v6（6 个成片）→ 首轮回归 **42/43**（`multimodal_test` 33/34）。已改为「成片字典逐字节未变 **且** 成片条数 == DB 中成功渲染版本数」，**断言更严**（未放宽只读规则、未改任何产品逻辑、未改任何阈值）。首轮失败证据留档 `logs/phase5c_rerun/PRESERVED_suite_multimodal_test_failed_20260916.log`、`PRESERVED_suites_summary_42of43.json`；修正后 **43/43**。 | `RESOLVED (5-C)` | `logs/phase5c_rerun/unit_suites.log`、`tests/multimodal_test.py`、`CHANGELOG.md` V2.5.3 |

---

## 15. 5.x 阶段新增登记（5-D 多帧/时序多模态证据增强，2026-09-17）

> 5-D 是**只读平行证据层**：不改 4-B / 5-A 结果、不换材、不 redo、不改时间轴。下列为**如实登记的限制**。

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#38** | **帧间一致性用"整帧"CLIP 嵌入，烧录字幕会贡献帧间差异**：本项目成片为静态素材 + 烧录字幕，S01–S05 实测相邻帧余弦 ≥0.999，而 **S06（side 视角、大面积平滑区域）mean=0.969 / min=0.814** —— 差异主要来自字幕区域变化，而非画面切换。因此 `min_stability_cos=0.75` / `split_cos=0.50` 是**工程默认值**；未做"字幕区域掩码/裁剪后再比"（属新能力，需新授权）。 | `LIMITATION` | `logs/phase5d_mmt_v6.json`（S06 stability）、`tests/mm_temporal_test.py` F4 |
| **#39** | **时序层不改变 5-A 的结论方向**：S06 仍为 `UNKNOWN`；时序证据把它从"单帧下的不确定"升级为**"稳定地不确定"**（`T7_AMBIGUOUS` / confidence=MEDIUM：7 帧逐帧 argmax 全为期望域、投票 1.0、无 split、中位边际 0.0061 < 0.02）。**不能**把 UNKNOWN 变成 MATCH —— 那需要调阈值或更换素材，本阶段均**未做**。 | `BY DESIGN`（如实登记） | `logs/phase5d_evidence.json` → `s04_s05_s06_explanation` |
| **#40** | **阈值均为工程默认、可配置且非法值回退**：`frames_per_scene=7`、`min_frames=3`、`min_vote_frac=0.60`、`min_stability_cos=0.75`、`split_cos=0.50`、`high_stability_cos=0.90`；`min_sim`/`margin` 与 5-A **同值**（不放松）。已做**阈值敏感性披露**（`margin` ±0.005/±0.01、一致性 ±0.05/±0.10 的扰动复算），未翻转即为不敏感。 | `BY DESIGN`（可配） | `logs/phase5d_evidence.json` → `threshold_sensitivity` |
| **#41** | **视觉嵌入使报告体积线性增长**：worker 在 `return_embeddings=true` 时返回 512 维（6 位小数）逐帧嵌入；42 帧约 150 KB。`frames_per_scene` 可配但**无上限保护**（仅 `min_frames` 有下限）；超时 900 s 只是等待预算，**不放松**任何判定。 | `LIMITATION` | `src/video_studio/core/mm_worker_clip.py`、`logs/phase5d_mmt_v6.json` |
| **#42** | **T1 时序切换 / T2 低一致性分支在本项目成片上不出现**：6 个镜头全为静态素材（stability ≥0.969 → 全部 `STABLE`）；该两条分支由**真实模型的受控夹具**（镜头内切图：相邻余弦 0.452 < 0.50 → `MMT_TEMPORAL_SPLIT`）与合成证据单测覆盖。真实"多镜头/含运动"素材尚无用例，**不可外推**。 | `LIMITATION`（覆盖边界） | `logs/phase5d_evidence.json` → `temporal_split_fixture`、`tests/mm_temporal_test.py` G1–G3 |

---

## 16. 5.x 阶段新增登记（5-E 证据质量校准与可解释性，2026-09-17）

> 5-E 是**只读评估层**：不改判定逻辑、不调阈值、不换材、不写库。下列为**如实登记的边界**。

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#43** | **真值集小且同质**：`mm_truth_set_v1` 仅 **14 例**，且全部来自**同一个静态素材项目**（`p_f4b466a4a024`）；`UNCERTAIN` 标签只有 4 例。**校准结论不可外推到多镜头/运动素材/其它题材**（与 #42 同源）。 | `LIMITATION` | `tests/fixtures/mm_truth_set_v1.json`、`logs/phase5e_quality.json` → `truth_set.coverage` |
| **#43（5-G 更新）** | **真值集 v2 已扩充**：`mm_truth_set_v2.json` **32 例 / 3 个真实项目**（v1 14 例原样并入 + p_ab2b352e06b8 12 段多镜头旁白成片 7 MATCH/4 MISMATCH 边界 + p_8f054c227bd4 6 段纯色底 UNKNOWN fail-closed）。**运动素材覆盖 = 0**（全库 1592 项目 0 视频资产，如实 LIMITATION）。校准结论外推范围扩至多镜头/域边界/零证据类；运动素材仍不可外推。 | `NARROWED (5-G)`（运动素材子项保留 LIMITATION） | `tests/fixtures/mm_truth_set_v2.json`（sha256 `8adc2985d7fa044c…`）、`logs/phase5g_quality_p_*.json` |
| **#44** | **MATCH 精确率 = 1.0 是"在这 14 例上"的结论**：三层都没有把 MISMATCH 判成 MATCH（零误报），但样本量小、且 UNKNOWN 被计为保守（不计入误报）；**不能**据此声称通用精确率。 | `LIMITATION`（口径已限定） | 同上 → `metrics.*.match_precision_on_truth` |
| **#44（5-G 更新）** | **v2 复验结果**：v1 14 例零回归（judge 14 行与 5-F 冻结一致：MATCH4/MISMATCH3/UNKNOWN6，0 违例）；新增 18 例中 **2 处真实层-人分歧**（p_ab2b S06/S12：人工域级 MATCH，5-A/5-D 判 MISMATCH——12 段复用 3 张静帧的实例粒度漂移检出，如实披露不调参）；纯色底 6 拍层全部拒绝发证（fail-closed 正确）。实例粒度分歧的处理（人工裁决/标注细化）转入后续决策。 | `NARROWED (5-G)`（实例粒度分歧 2 例如实保留） | `logs/phase5g_quality_p_ab2b352e06b8.json`、`logs/phase5g_judge_p_f4b466a4a024.json` |
| **#45** | **5-A/5-D 会在这类"内容正确但域区分度不足"的镜头上给 UNKNOWN**（T06/S05 边际 0.0171、T08/S06-side 边际 0.0061）；这是**保守设计**而非缺陷，但会降低"可判定覆盖率"（5-A MATCH 召回 0.667、5-D 0.667）。修它只能靠**换素材或改规则**（均需新授权）。 | `BY DESIGN`（如实登记） | `logs/phase5e_quality.json` → `metrics`、`cases T06/T08` |
| **#46** | **阈值敏感性显示"放宽即变 MATCH"**：`margin` 由 0.02 放宽到 0.01，T06(S05) 立刻由 UNKNOWN 变 MATCH；收紧 +0.02/+0.04 则会让 T01/T02/T03/T05 由 MATCH 变 UNKNOWN。**5-E 明确不采纳任何阈值改动**；该矩阵仅作披露（含"更松"一侧，用以说明不能靠调阈值提高通过率）。 | `BY DESIGN`（披露） | 同上 → `sensitivity`；`KNOWN_ISSUES.md` #24/#25 |
| **#47** | **top-1 域一致性只是解释性指标**：在本真值集上，内容-MATCH 用例的期望域**全部**是 top-1，内容-MISMATCH 用例的 top-1 是其它域（`wildlife`）—— 与内容标签 **100% 吻合**；但样本小且与 margin 规则高度相关，**不足以**作为新判定规则的依据（5-F R6 仅建议纳入报告展示）。 | `LIMITATION`（未采纳为规则） | 同上 → `cases[*].boundary.*.expected_in_top1` |
| **#48** | **真值集在开发期有一处修正**：首次校准运行暴露三处夹具缺陷（T11 过度约束语义、T12 旁白含词表命中词、T13 fault 名与实现不一致），修正后**重新定稿**（初稿 sha256 `1a138555…` → 定稿 `7eb952f2…`），两版哈希均记录在 `logs/phase5e_evidence.json` → `truth_set_history`；**定稿后未再修改**。 | `RESOLVED (5-E)` | `logs/phase5e_evidence.json`、`tests/mm_quality_test.py` A6 |

---

## 17. 5.x 阶段新增登记（5-F Judge 收敛与最终边界，2026-09-17）

> 5-F 是**只读裁决层**：不改判定逻辑/阈值，不换材/选材/redo，不写库。下列为**最终登记**（含对 #43–#48 的处置结论）。

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#49** | **Judge 未接入生产判定链**：`run.py mm-judge` 默认关闭、只读，只输出"最终三态 + 理由码 + DoD"供人工/报告使用；**不**驱动任何自动动作（不换材、不选材、不 redo、不改时间轴）。接入生产（例如在渲染前自动拦截 MISMATCH）属**新授权**范围。 | `BY DESIGN`（新增） | `src/video_studio/core/mm_judge.py`、`ops/mm_judge.py`、`PHASE5F_MULTIMODAL_DOD.md` §4 |
| **#50** | **最终 MATCH 需全层一致 → MATCH 数低于 5-A 单独判定**：本项目 14 例中最终 `MATCH=4 / MISMATCH=3 / UNKNOWN=6`；S05 与 S06(side) 由"4-B MATCH + 像素层 UNKNOWN"收敛为**最终 UNKNOWN**。这是**有意设计**（授权明确"不追求提高 MATCH 率"），不是缺陷；代价是人工需复核更多镜头。 | `BY DESIGN`（新增） | `logs/phase5f_judge.json` → `rows` / `summary`；`PHASE5F_REPORT.md` §2 |
| **#51** | **#43–#48 的处置结论已固化**：#45（保守 UNKNOWN）与 #46（阈值敏感性）在 5-F **解决**（分别固化为最终判据 J6、并以"Judge 无阈值参数 + DoD D7"写死禁止路径）；#43/#44/#47 **保留**为最终已知问题（受限于素材与样本量，见 R3/R6）；#48 **解决**（留痕 + 双指纹钉定）。 | `RESOLVED / LIMITATION`（分项见 §15/§16） | `logs/phase5f_evidence.json` → `dispositions` |

---

## 18. 5.x 收尾后维护阶段新增登记（5-K Post-Final Maintenance，2026-09-21）

> 5-K 为**收尾后维护**：只做授权清单内 10 项（形式采纳 2 处既有改动 + 采用当前官方模型默认配置 + 针对性回归
> （含"视频输入路径不受影响"反证）+ CHANGELOG 补齐 + 杂物清理 + **审计只登记** + 全量回归 + 新基线
> `5.x-post-final-maintenance-baseline` + 停止报告）。**禁止**新增视频能力，**禁止**修改 Judge、truth set、
> threshold、multimodal evaluator、human decision chain。
> 下表审计发现**只登记、不修复**（授权 item ⑦）；其中 #56 是 5-K **实测发现并修正**的缺陷（同属 item ①）。

| 编号 | 内容 | 状态 | 证据 |
|---|---|---|---|
| **#52** | **被删缓存文件在历史检索产物中留下 13 条悬空候选引用**（产物 `a_609ea7b3c895`、`a_71f77918bc8a`）：候选只剩元数据、**字节不可复核**。清理事件 `#101631 OPERATOR_POOL_CLEANUP` 只记 `removed_cache_files=11` 与理由，**未记**受影响产物 id / 候选 id。 | `OPEN`（5-K 登记，未修复） | `AUDIT_P96EFDC03E1AA.md` §3、审计 E §13d |
| **#53** | **`media/external/.index.json` 陈旧**：仍登记 11 个已删除的缓存文件（如 `5e990ebc…jpg`、`6ef2190fef07…jpg`）→ 下次检索可能"缓存命中但文件不存在"。 | `OPEN`（5-K 登记，未修复） | `AUDIT_P96EFDC03E1AA.md` §3、审计 D §13c |
| **#54** | **素材原地编辑缺一等溯源**：2 张中心裁剪只在 ingest 索引留**原始 sha**、在资产/时间轴留**当前 sha**，**无** `original_sha`/`edited_sha`/`tool`/`operator`/`decision_id` 显式字段，只能靠旁证比对推断。 | `OPEN`（5-K 登记，未修复） | `AUDIT_P96EFDC03E1AA.md` §3 |
| **#55** | **邮票素材 sha 变化原因不明**：ingest 索引 `03d1791e0d8b…` → 当前 `23e71bc8a864…`，**未被"裁剪 2 张"的声明覆盖**，且 **mtime 未变**（另 2 处 sha 不一致可由人工裁剪解释）。 | `OPEN`（5-K 登记，未修复） | 审计 G §24 + mtime 取证 |
| **#56** | **post-final 漂移形态 `-loop 1 -framerate 1 -t d -i 图` 会静默截短视频轨**：1fps 图片源在 `-t d` 下只产出约 d−1 帧（实测整数 d 每镜 **−0.967 s**；小数 d 每镜 −0.467…−1.367 s）；`p_96efdc03e1aa` v7 成片 **视频轨 1511.0 s vs 时间轴 1532.0 s（短 21 s）**，因容器时长由音轨 `apad` 占满而长期未暴露。5-K **正式采纳该改动并修正**（输入 `-t ceil(d)+2` + 每段 `trim=duration=d,setpts=PTS-STARTPTS`）；修正形态与冻结基线 S0 形态**逐例时长一致（Δ=0.000）**，帧数精确 = `round(d·30)`。 | `RESOLVED (5-K)` | `tests/maintenance_fixes_test.py` M2a–M2d / M3a–M3d（S0/S1/S4 三形态同条件对比）；原始测量 `phase5k_duration_probe.py`；成片探针 `logs/audit_p96efdc_film_check.json` |
| **#57** | **已渲染产物不回溯重制**：`p_96efdc03e1aa` 的 v7 成片 `t_898378f6b0f8_draft.mp4` 仍是**视频轨短 21 s** 的既有产物（容器 1532.0 s 由音轨决定）；5-K 只改渲染参数，**不重渲染、不改动该产物**。是否重渲染属人工决定（新授权）。 | `OPEN`（5-K 登记，需人工决定） | `AUDIT_P96EFDC03E1AA.md` §0；`logs/audit_p96efdc_film_check.json` |
| **#58** | **运维旁路与未终结分支**：3 类人工修复事件（`OPERATOR_REWIRE_FIX` `#101565`、`OPERATOR_SUPERSEDE_DUPLICATE` `#101593`、`OPERATOR_POOL_CLEANUP` `#101631`）绕过常规任务链直接改状态（均 `human_confirmed` 且带理由，可追溯，属运维旁路）；渲染 v3 `BLOCKED`、v5 `PENDING` **未显式终结**为 FAILED/SUPERSEDED。 | `OPEN`（5-K 登记，未修复） | `AUDIT_P96EFDC03E1AA.md` §3 |
| **#59** | **历史世代模型 id 仍硬编码在冻结模块与历史产物中**：`tools/sufficiency_judge.py`、`tools/llm_semantic_judge.py`、`tools/evidence_signal.py` 的 `MODEL_DEFAULT="deepseek-chat"`；`stage33/vision_shadow.py`、`stage33/vision_controlled.py` 的 `deepseek-v4-flash-vision-exp`；`output/**` 历史实验脚本中的 `deepseek-v4-flash`。5-K 只把**默认配置**切到当前官方模型（`config/config.json` tiers：M/F=`deepseek-flash`、R=`deepseek-v4-pro`；`llm/router.py` 回退不再指向 `deepseek-chat`，历史别名登记为 `LEGACY_MODEL_IDS`），**不改**这些冻结判定模块与历史记录（改判定模块违反 5-K 禁止项）。 | `BY DESIGN / OPEN`（5-K 登记，未修复） | 5-K 模型清册 `logs/phase5k_model_audit.json`；`tests/maintenance_fixes_test.py` M6a–M6c |
| **#60** | **回归覆盖缺口（如实登记）**：`phase3a_real_chain.py`（真实网络链重跑，**会改写 5 份冻结证据日志**）**未单独重跑**；5-K 通过项目自带电池（`phase5f_regression.py`，含自动备份/恢复冻结日志）与批次内只读复核（`phase2_accept.py --verify`）覆盖。2026-09-21 曾因误跑该脚本改写 5 份日志，已从 18:25:59 备份逐文件回拷（drift 0 / missing 0）。 | `BY DESIGN`（5-K 登记） | `AUDIT_WORKSPACE_20260921.md` §4；`logs/restore_logs_20260921.json` |
| **#61** | **5-G/5-H/5-I/5-J/5.x Final 五份阶段报告之间存在口径不一致**（5-K 补 CHANGELOG 时发现，**只登记、未回改历史文档、未判定任一方为错**）：① 电池计数 `25/25`（5-G/5-I/5-J/Final）与 `24/25`（5-H 两份文档）；② 5-H 红项根因两说（`phase2e_failure_paths` 网络依赖 vs runner 聚合 + `phase2e_real_provider` GBK stderr）；③ 5-H REPORT（读 Judge JSON / 14 例 / 汇总 `4/3/6`）与 CLOSEOUT（读 Quality JSON / 32 例 3 项目 / 57 行 / `35-19-13-6`）实现口径不同；④ v2 真值集 sha `8adc2985…`（5-G、5-J FD6）与 `a9fc7379…`（5-J §6、Final §6）；⑤ `p_ab2b` 域判定 `7 MATCH + 5 MISMATCH`（5-G）与 `7 + 4 + 1 UNKNOWN`（5-H CLOSEOUT）；⑥ v2 边界计数「UNKNOWN 边界 6」（5-G）与「多镜头 12 / 纯色 6 / 边界 4」（Final）；⑦ Run04 域一致 `60`（5-J）与 `67 (66.3%)`（Final 表，其 §8 又写 60）；⑧ 人工决策记录 `18`（5-J FD8）与 `19`（Final）；⑨ 5-J FD11 自相矛盾（§2「待更新」vs §8「✅」）；⑩ 5-G 改动文件数（§4「唯一改动」vs §9「修改 2」）；⑪ 5-I 改动范围（「一个文件」vs PLAN 列 `cli.py`）；⑫ 5-G `14 行` 与 `MATCH4/MISMATCH3/UNKNOWN6`（=13）算术不符、5-J「T1–T14」与 `17/17` 编号不符；⑬ 5-H/5-I 报告未给出基线 tag/sha。 | `OPEN`（5-K 登记，未回改） | 六份阶段报告；`CHANGELOG.md` 5-H…5.x Final 条目（两种口径**并列**记录）；`logs/phase5k_evidence.json` → `docs_registration` |
| **#62** | **采用新默认配置（`config/config.json` 去掉内联 `llm.mock.responses`）后，离线回归项 `run_ingest_test` 转红（根因已实测定位）**：旧配置的 `llm.mock` 使该离线用例以"1 条 claim"跑通；新配置走**真实模型**后产出 30 VERIFIED + **4 UNSUPPORTED** claim，而**冻结的生产闸门**（"全部 claim 处于 PASSED(VERIFIED/REJECTED) 才放行"，KNOWN_ISSUES #9 fail-closed）按其设计阻塞了 `retrieval/editing_plan/render/audio_mix/...` 共 **11 个生产任务（`retry_count=0`，从未派发）**；测试脚本的批准过滤器不覆盖 UNSUPPORTED 状态（其设计年代只有 1 条 mock claim），40 轮后判定 FAIL。**因果链已用 DB 只读证据闭合**：该失败**不是** 5-K ①②（图片输入参数、ffmpeg 超时）或 router 回退改动导致，而是 item ③"采用当前真实默认配置"的**代价**，且闸门行为符合冻结契约（**未放松任何规则**）。处置（**需人工授权**，5-K 未实施）：① 在 config 恢复仅供离线使用的 `llm.mock`（不动真实默认模型）；② 或更新 `docs/regression_2x/run_ingest_test.py`（在 `docs/`，**不在基线内**）使其自带 mock 配置 / 覆盖 UNSUPPORTED 处置。 | `OPEN`（5-K 登记，未修复） | `docs/regression_2x/logs/phase3a_run_ingest_test.log`（40 轮、16 SUCCEEDED / 11 active）；`logs/phase5k_ingest_diag.json`（任务停点、最后事件 `conflict_detector` SUCCEEDED）；`logs/phase5k_ingest_diag2.json`（`claims_by_status={'UNSUPPORTED':4,'VERIFIED':30}` 与 4 条 claim 原文） |
| **#63** | **item ③ 的第二项副作用（如实登记）：原「内联 mock 驱动」的离线回归路径在采用新默认配置后改为真实 API** —— 3-A 的 `e2e_mechanical`（`run_all_tests.py --fresh` 的 A/B/C 三组）与 `run_ingest_test` 等项目现在产生**真实模型调用**（`model_used` = `deepseek-flash` / `deepseek-v4-pro`），后果：① 回归**时长与成本**由"秒级/零成本"变为"分钟级/真实计费"（2026-09-21 单日回归项目合计 **$0.23852**：`testA` $0.06743、`testB` $0.06679、`testC` $0.03347、`testD` $0.04003 等）；② 结果**非确定性**（同输入不同轮次可能不同结论）；③ 断言口径隐含依赖 mock 的固定条数（见 #62）；④ **`e2e_mechanical` 实质性退化**：冻结时代结果为 A/B/C 三组 **SETTLED**，2026-09-21 实测为 `A=p_147b37e8c658|MAXROUNDS`、`B=p_5825c2f2b568|MAXROUNDS`、`C=p_c30056d9bb2f|BLOCKED`（rc 仍为 0，**断言只看 rc 故未报红**——"rc 通过 ≠ 结果达标"）。**这是授权 item ③ 的直接结果，不是代码缺陷**；处置（需人工授权）：离线回归注入自有 mock 配置（docs 侧脚本自带），或在 config 保留仅供离线使用的 `llm.mock`。 | `OPEN`（5-K 登记，未修复） | `logs/phase5k_cost_probe.json`（48 个项目、合计 $0.23852、`model_used` 实证）；`docs/regression_2x/logs/phase3a_e2e_mechanical.log`（`RESULT: {...MAXROUNDS...}`） |
| **#64** | **采用新默认配置后 3 个基线内测试套件转红（同一根因：`config.json` 不再含 `llm.mock`）**：`tests/cost_accounting_test.py`（L140 `mock_cfg["llm"]["mock"]` → `KeyError: 'mock'`；此前全绿）、`tests/pipeline_mock.py`（L53 `config["llm"]["mock"]["responses"]` → `KeyError: 'mock'`）、`tests/metrics_test.py` M5d（钉定 `baseline_manifest_3.x-final-baseline.json` 的 config sha：现 `7b03424846f1…` vs 旧 `b264644539b2…`；**该钉定目标本身早已过期**，本次 config 变更使其首次转红；该套件 17/18）。**5-K 未修改**：改 config 或改这些测试均超出十项授权（处置需人工决定：#63 的两条选项，外加把 M5d 重钉到新基线 tag）。**→ 已在 5-L 处置**：新增独立离线 mock 配置 + M5d 改钉当前有效基线（见 #52–#64 之后的 5-L/5-M 记录）。 | `RESOLVED (5-L)` | `logs/suite_cost_accounting_test.log`、`logs/suite_pipeline_mock.log`、`logs/suite_metrics_test.log`、`logs/suites_summary.json`；`PHASE5L_REPORT.md` §4 |
| **#65** | **旁白时长与时间轴不匹配（既有，非 5-M 引入）**：`p_96efdc03e1aa` 旁白实际 **961.656 s**（21 段 TTS 真实时长合计）而时间轴 **1532.0 s**，`voice_output.duration_contract = {within_tolerance: false, shortfall_s: 570.344}`（容差 10%）。后果：成片约 **37% 的画面期间没有旁白**；字幕（5-M 改为按阅读速度、镜头窗口内铺开）因此全片覆盖率 **64.5%**、最大静默间隔 4.6 s。**5-M 未改动该口径**（属内容/时间轴问题，不是字幕呈现问题）；处置（需人工授权）：重写脚本使段落时长贴合旁白、或按旁白时长重排时间轴、或对留白段补充画面/音乐。 | `OPEN`（5-M 登记，未修复） | `projects/p_96efdc03e1aa/artifacts/a_e99273b936c0.json`（voice_output 逐段真实时长 + duration_contract）；`logs/phase5m_render_verify.json`（字幕覆盖率统计） |
| **#66** | **成片"字幕"实为整段文案铺满画面（既有渲染缺陷，已在 5-M 修复）**：`agents/editing/agent.py::_narration_args` 旧实现对**每个脚本段落**生成一条 `drawtext`，按文本长度自适应字号（28/34/42）与硬折行（26/20/16 字/行），**`x=(w-text_w)/2:y=(h-text_h)/2` 居中**、`enable` 覆盖整段时长 → 画面中部被整段旁白占满（用户实测 t=20s 抽帧可见 7 行文字块）。5-M 改为 `core/captions` 切分（≤36 字/条、≤2 行、优先标点断行）+ libass `ass=` 底部居中逐条烧录（字号=高度×4.2%、Outline=3）。**旧行为证据留档**（`output/_5m_frames/v8_t20.png`），新行为见 `logs/phase5m_frames/v9_t*.png`。 | `RESOLVED (5-M)` | `PHASE5M_REPORT.md` §0/§1；`tests/captions_test.py`（21/21）；`logs/phase5m_caption_probe/{report.json,frame_*.png}`；`logs/phase5m_render_verify.json` |
| **#67** | **人工验片判定 v9 成片 FAIL（不得作为发布候选）**，且与工程门禁结论**并存不矛盾**：5-M 的 DoD 只覆盖"字幕呈现改造 + 回归不退化"（**保持 PASS**），**"能否发布"属导演/内容质量维度，5.x 至今没有可度量的发布门**。6-A 只读审计逐条核实 6 项发现（**全部 VERIFIED**，字幕项 PARTIAL）：① **16:01 音频断裂**=静音 961.14→1532.01 s（570.87 s，占 37.26%）；② **素材重复**=21 镜仅 **4 素材**（7/6/5/3 镜）、平均静态保持 73 s、**17/21 镜 >60 s**；③ **Hook 视觉错位**（hook 用"学生举旗合影"，与"AI 证明"无关）；④ **无视觉高潮**（20/21 镜命中核心论点词但仅 4 素材、画面无升级）；⑤ **缺片尾**（无 outro，末镜为限制声明，尾部 570.3 s 静音）；⑥ **字幕残留问题**（73 条=33.8% cue 落在静音区，首条 967.4 s）。 | `OPEN`（6-A 登记；**不修复**） | `docs/regression_2x/PHASE6A_AUDIT.md`；`logs/phase6a_audit.json`（silence/freeze/视觉/漂移/字幕/高潮/片尾）；`logs/phase6a_frames/v9_t*.png` |
| **#68** | **旁白覆盖率无下界门（`apad` 掩盖机制，6-A 追因结论）**：`core/narration.py::duration_contract` 明确把"旁白较短"定义为**允许**（`audio_padded_to_timeline`、注释"较短→静音补齐"），渲染前闸门 `agents/editing/agent.py:560-568` **只拦"旁白过长超容差"**；`voice_output.duration_ok=False`、`render.duration_contract.within_tolerance=False`（shortfall 570.344 s）**被记录但无人消费**；成片闸门仅查整体响度（−16.1 LUFS 达标）→ 570.87 s 静音合法通过。**建议拦截层**：渲染前 PI-1/PI-2（覆盖率下界 + 双侧时长契约）与渲染后 PI-3/PI-5（成片静音/字幕 orphan 实测）。 | `OPEN`（6-A 登记；6-B/6-C 待授权实施） | `PHASE6A_AUDIT.md` §1.4/§4；`PHASE6A_PLAN_DOD.md` §2/§3（PI-1…PI-6） |
| **#69** | **报告/审批口径与交付物脱节（6-A 发现）**：① `compliance_output.summary` 称"视觉为**纯色底字幕卡**、未使用第三方图像/视频素材、署名台账条目 0"，而 v6–v9 实际使用 **4 张 Wikimedia/local_ingest 素材**且 attribution 21 镜 1:1 —— 报告与事实不符（合规结论的**输入快照**疑似停留在早期占位卡版本）；② `editing_plan_APPROVED` 人工裁决 rationale 描述"**25 镜单主轨计划、0 素材下占位卡**"，与最终 4 素材/21 镜成片不一致（审批对象已非交付对象）。 | `OPEN`（6-A 登记；不修复） | `logs/phase6a_extra.json`（agent_reports / quality_related_decisions）；`PHASE6A_AUDIT.md` §4 注 |
| **#70** | **多模态评估层对 v9 有实质结论但无阻断力（6-A 复核）**：逐镜只读复核 4-B `MATCH2/MISMATCH0/UNKNOWN19`、5-A `1/3/17`、5-D `1/2/18`、**Judge 最终 `MATCH1(S03)/MISMATCH2(S05,S11)/UNKNOWN18`**（18 UNKNOWN 中 14 为 `JUDGE_UNKNOWN_DOMAIN`，属 #23/#43 词典覆盖限制）。这些结论**未接入生产判定链**（#49 `BY DESIGN`）→ 即便存在 MISMATCH 2，成片仍可作为 DRAFT/发布候选产出。与 #67 共同指向 6-C（把可度量红线接线为硬门）。 | `OPEN`（6-A 登记，与 #49 相关） | `logs/audit_p96efdc_mm.json`；`PHASE6A_AUDIT.md` §2.5/§4 |

## 71. 两代选材通道在**人工入口层面**尚未统一（4-C `asset_*` 旧命名空间 vs P7-2 `ast-*` 索引宇宙）—— `OPEN`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#71** | 4-C `select-candidate` 只接受**该场景 4-C 候选池内**的 `asset_*` id；P7-6 绑定提案与 P7-2 AssetIndex 使用 `ast-*` id ⇒ **人工无法用 4-C 入口选定 `ast-*` 素材**（Phase 13-C 实测尝试失败）。6-B 提案审批链（`core/execution.py`）可用 `ast-*`（经 `proposal_sha256` 绑定），两条通道**并行且互不可达** | `src/video_studio/core/selection_review.py:129`（`validate_choice(scene["candidates"], asset_id, …)`）；`docs/regression_2x/logs/phase13c_approvals.jsonl`（6-B 链登记 `bp-6320bf486a082901`，绑定 `ast-92ca33138ffe64f4`）；`docs/regression_2x/logs/phase13c_stop_decision.json`（§0 登记；其中"解除路径 ①"正是 4-C 入口，实测不可达 ⇒ 改走 ② 6-B 链转录） |

- **性质**：真实 **integration debt**（两代通道的 id 命名空间与校验来源不同），**非**本阶段引入。
- **为何本阶段不修**：Phase 13-C 边界明确禁止改动选材通道语义（"不碰门禁阈值/不做 promotion"），
  且修它需要统一两个命名空间的原点（4-A 素材池快照 vs P7-2 索引），属**跨阶段集成工作**。
- **影响**：人工在 4-C 入口看不到 `ast-*` 候选 ⇒ 只能走 6-B 链；反之 6-B 链也不产出 4-C 可选项。
  对"人工最终决定"这一契约**不构成放权风险**（两条通道都要求人工归属），但**增加操作摩擦与误用风险**。
- **建议处置**（择一，需新授权）：① 让 `select-candidate` 接受 P7-2 索引宇宙（把 `ast-*` 映射进候选视图）；
  ② 或声明 **6-B 链为唯一选材入口**并把 4-C 入口标注为 legacy（保留只读）。

---

---

## 73. VLM 视觉相关性判定：**判据与人工不同源**（DQ/P7-4 需求语义 vs 人工叙事切题性）— `OPEN`

> **与 #74 的关系**：#73 是**语义相关性**判定（配不配）的任务定义问题；#74 是**视觉存在性**核验（在不在）的度量盲区。二者**不同任务**，Phase 18 的 VLM 仲裁层**不解决 #73**（#73 仍 OPEN）。

| 编号 | 内容 | 证据 |
|---|---|---|
| **#73** | P14-2 冻结真值集（27 对，RELEVANT 24 / IRRELEVANT 3）上，`qwen3-vl-plus` 的
`overall agreement = 4/27 = 14.81%`（阈值 90%；首次独立运行 11.11%）⇒ **门禁 FAIL、P14-3 未集成**。 | `logs/phase14_eval_report.json`；
`tests/fixtures/vlm_relevance_truth_v1.json`（sha256 `6104cfc202113510…`） |

- **性质**：**判据定义层面的失配**，不是模型故障、也不是提示词措辞问题。
  `visual_goal` 派生自脚本/分镜的**生成式画面描述**（`visual_requirements.json#builder_rules R-GOAL`：
  `visual_goal ← shot_description`），而人工 operator 的选材理由是**叙事/主题切题性**。
  模型据字面逐元素比对，故大量判 `IRRELEVANT`/`PARTIAL`，属**按给定任务正确执行**。
- **不是措辞问题（已证）**：把口径改为「话题同一性、可作视觉锚点」的诊断变体（**不参与门禁**）
  首测到 **25.93%**、末测 14.81%（`logs/phase14_eval_diag_anchor.json`）。
- **关键不对称（正面发现）**：两个变体下「人工 IRRELEVANT → 机器 RELEVANT」**均为 0**，且机器仅 1–5 次判 RELEVANT
  ⇒ 该 VLM 在此设定下是**可靠的「拒绝器」**、但**不是可靠的「确认器」**。
- **为何本阶段不修**：授权书明令「评测门禁前置、未达标只报告不集成」；修它需要改 **P7-4 需求语义**
  或另立「主题切题性」判定规范，属**跨阶段口径决策**，须人工授权。
- **影响**：143 对 `NOT_ASSESSABLE` **仍未被解析**（P14-3 未执行）；HITL 面未缩小。
  附带遗留：`visual_relevance.json` 中 RELEVANT 依 `human_*` 证据、其余落 NA，
  **机器判定不得充当人工真值**（本阶段未越界）。
- **建议处置（择一，需新授权）**：① 把 `visual_goal` 与人工判据的统一写成**显式判定规范**（改 P7-4 语义）后重跑门禁；
  ② 把该 VLM 改为**负例过滤/降 HITL 面**用途（仅拒收 IRRELEVANT），并**另立只含负例的评测集**验证；
  ③ 人工补足 **≥30 对**真值（含更多负例）后重跑（当前 27 对、负例仅 3，置信度不足）。

- **端点非确定性（实测）**：设计假定 `temperature=0` ⇒ 同输入同判定，实测**不成立** —— 清空缓存后两次独立运行有 2 对标签改变（S04 `PARTIAL→RELEVANT`、S07 `IRRELEVANT→PARTIAL`），一致率 11.11%→14.81%。**文件缓存内一致**（同键同字节，已验证），**跨键/跨版本不保证复现**；该不确定性不改变门禁结论（两次均远低于 90%）。

### 真值集规模不足（连带登记）
- P14-2 授权要求 **≥30 对**人工真值；全仓实测仅 **27 对**带显式人工正/负证据 ⇒ **未达标**，
  已在运行前登记并保留缺口，**未用机器判定充数**（经用户确认按 27 对执行）。
- 缺口原因：`visual_relevance.json` 的 RELEVANT 依 `human_*` 证据、其余 143 对为 NA（无人工标签）；
  `selection_override` 的 541 条中约 516 条为鉴权测试，其余 `before_asset_id` 混杂**许可/镜次身份**替换，
  与同对正例标签自相矛盾，**不可**作相关性负例。

---

## 74. 渲染后核验度量：**三类盲区已定位并已由 VLM 仲裁层兜底**（非放宽阈值）— `MITIGATED`

| 编号 | 内容 | 证据 |
|---|---|---|
| **#74** | 冻结的渲染后核验度量 `corr_48 = frame_corr(gray48(asset), gray48(frame))`（阈值 0.30）存在**三类结构性盲区**，会把**素材确实在屏**的场景误判为失败。**处置：不改阈值、不改门禁，改由「VLM 存在性核验」仲裁层兜底。** | `PHASE17_REPORT.md`、`PHASE18_REPORT.md`、`logs/phase17_attribution.json`、`logs/phase18_p18_3_vlm_presence.json` |

### 三类盲区（Phase 17 逐景归因定位）
| # | 盲区 | 机理 | 实证 |
|---|---|---|---|
| ① | **稀疏线稿在 48×48 下塌陷** | 白底 + 细黑线 + 细小标记的线稿，重采样到 48×48 后有效信息几乎只落在极少数像素上；轻微缩放/位移即让线条换格 | S07 0.0783 / S08 0.0581 / S13 0.0062（**人工目视均证实同图在屏**） |
| ② | **16:9 中心裁切 / 局部化呈现** | 模板 `scale=1920:1080:force_original_aspect_ratio=increase, crop=1920:1080` 只保留中段；画面是素材的**局部**，与"全图"比较必然低分 | S02（1200×1560 竖多面板，0.1219）、S08（885×1033，0.0581）；S08 人工看图仅缺 D/F 标记 |
| ③ | **运动缩放（画面=素材子窗口）** | 启用运动的场景，画面是运动裁切窗口 = 素材某个**子窗口**，与全图相关性天然低于静态 | S06/S07/S13（SLOW_ZOOM/PAN）；`render/motion_evidence.json` |

### 已执行的修复与裁定（Phase 18）
1. **`present_test` 真 bug 已修（P18-1）**：比较基准由「画面 vs 素材**全图**」改为
   **多尺度 16:9 子窗口 bank** ⇒ S08 rank **4→1**、S13 rank **5→1**（证实"全图口径"是 bug）。
   **但在屏数 3/5 → 4/5，未达 5/5**：**S07 退化为 rank 4**（bank 0.2766 < 误导素材 `301ff850be9c` 0.352）。
   **未调参补救**。
2. **确定性 corr v3 未采纳（P18-2）**：阈值 0.30 不变、双门运行前写死。
   `bank192` 正门 3/5·反门 0/55；**边缘图口径正门 5/5 但反门 35/55 ⇒ 无区分力，否决**；
   最佳 `max(bank48,bank192)` 正门 4/5·反门 2/55 ⇒ **双门未全过 ⇒ 未落地、未改门禁**。
3. **VLM 存在性核验层达标并落地为仲裁层（P18-3）**：任务 = **"帧里在不在该素材"**
   （允许裁切/缩放/局部），**不判**"配不配"（与 **#73 无关**，两者是不同任务）。
   实测 **一致 25/25 = 100%、false-present 0、uncertain 0**，成本 **$0.0180**。
   仲裁：`corr<0.30` ⇒ VLM 核验 ⇒ **present 放行**（附证据）；**absent/uncertain/失败 ⇒ 维持阻断**（fail-closed）。
   五景 **5/5 放行**（4 确定性 + S07 经 VLM）。

### LIMITATION（如实登记，未被当作门通过的理由）
- **反门语料不全**：仅含**构造错配**（帧 vs 池内无关素材）。旧 S05 鲨鱼照等**真实历史错配素材在本仓不存在**
  （全盘检索无该文件，仅存文件名/哈希）⇒ 反门强度受限。
- **VLM 端点非确定性**（P14-2 已实测：`temperature=0` 下独立运行仍有标签变化）⇒ 仲裁层结论
  **以缓存键为复现单位**（同键同字节），跨键/跨版本不保证复现；因此仲裁证据**逐景留痕**并附 `prompt_version` + 模型名。
- **`301ff850be9c` 为已知误导素材**：在 48×48 / bank 口径下对 S02 与 S07 均达 ~0.35（超过阈值），
  是 v3 反门仅有的 2 条误通过来源；**建议后续素材入库时按 P17-3 的 `crop_safety` 同法增加"误匹配倾向"标记**。

### 为何不改阈值
授权与先例（Phase 11 / Phase 17 / Phase 18）均要求**修误报、不松真门**：降低 0.30 会同时放过
真实错配（反门），故采用"**确定性度量 + VLM 存在性仲裁**"而非阈值宽松。

---

## 75. 拆镜「句中切点」设计债 + 40 段时基与 pause 预算的**结构性冲突** — `OPEN`（设计债）

### 75.1 句中拆分（P19-3 第 2/3 轮）登记为 **NOT_EXECUTED**
Phase 20 §0（监理裁定）：**只执行句界拆分**（P19-3 第 1 轮 19 条提案，21→40 景，切点全在旁白句边界）。
第 2/3 轮的**句中切点**提案登记为 `NOT_EXECUTED`，理由：
句中切点的段文本**无法整句切分** ⇒ 字幕对齐风险 > DQ-3 边际收益（38.1% vs 45.0%）。
台账：`logs/phase19_split_execution_ledger.json`（第 2/3 轮记录保留，标注未执行）。

### 75.2 ⚠️ 40 段时基与冻结 pause 预算**结构性冲突**（Phase 20 实测，**阻塞 DQ-3 收口**）
- `core/narration.py::PAUSE_BUDGET_S = 0.75` 为**冻结常量**，`audio_time_base_s` 语义为
  `Σ段实测时长 + pause×(段数−1) + trailing(2.0)`。
- 21 段：`961.656 + 0.75×20 + 2.0 = 978.656s` ✔（与目标 978.7±1s 相符）
- **40 段**：`961.634 + 0.75×39 + 2.0 = 992.884s` ⇒ **超目标 +14.2s**（实测成片 **992.88s**）✘
- 要回到 978.7±1s，需 `pause ≈ 0.3852s/边界`（即把父级 15.0s 的 pause 总量摊到 39 个边界）。
- **但 pause 是冻结常量**（改它 = 动 PI 时基语义，超出授权）⇒ **授权书预期的
  "句界切片后总时长仍 978.7±1s" 在 40 段结构下不可能同时成立**。
- 数学不变量：`内容时长 = 976.656 − 0.75×(段数−1)`；40 段要求旁白内容仅 **946.4s**，
  而实际语音内容为 **961.634s**（4927 字，不可压缩、不可改写）⇒ 差额 15.2s 无解。
- **候选解法（需授权，本阶段未做）**：① 让 `pause_budget_s` 可从 voice 产物/policy 传入
  （改 PI 时基语义，最小改动）；② 或接受 992.88s 时长并同步放宽时长契约；③ 或回到 21 段。

### 75.3 逐景核验的段 ID 绑定缺口（Phase 20 实测）
40 段派生后，`MATERIAL_TIMELINE` decisions **仅覆盖 21 个父景 ID**（P20-2 的
`_phase20_binding` 提供了映射，但 decisions 仍按父景落库）⇒ 派生段
（`S01p1`/`S01p2`…）在核验时 `expected_asset_id` 为空，落入"占位镜头"分支 ⇒
**`checked_scenes` 仅 2/40**，核验近乎空转。
**处置**：拆镜要到 40 段时基**必须同步把素材绑定展开到每个派生段 ID**（否则闸门形同虚设）。
本阶段未做（授权范围未含），登记为设计债。

## 变更纪律

- 本台账只增不删；已解决项标注 `RESOLVED (阶段)` 并保留原文与证据链接；
- **不得**把 `LIMITATION`/`OPEN` 改写成 PASS；判定只用 `PASS/PENDING/BLOCKED/FAILED` 四态（阶段报告口径）。

### 75.4 处置更新（Phase 21 验证）
| 项 | 状态 | 证据 |
|---|---|---|
| **75.2** 40 段 × 冻结 pause 幻影膨胀 | **已修复（RESOLVED）** | `time_base_policy=v2.1`：`core/narration.py::pause_attribution`（归因表驱动，**常量零改动**）；40 段 base **992.884 → 977.884s ∈ 978.7±1**；21 段无表路径 **978.656s 逐字节兼容**。证据 `logs/phase21_p21_1_2_build.json`、`PHASE21_REPORT.md` §1。 |
| **75.3** 派生段未绑定素材 | **已修复（RESOLVED）** | `material_timeline` 展开 40 条（两侧素材继承，`parent_scene_id` + 子窗口）；DQ-2 由 FAIL(share 0.9369/unique 3) 恢复 **PASS(0.1778/10)**；逐景核验覆盖 **2/40 → 40/40**。证据 `logs/phase21_p21_3_verification.json`。 |
| **75.1** 句中切点设计债 | **维持 OPEN** | 依 Phase 20 §0 裁定 NOT_EXECUTED；DQ-3 仍 42.5%（>20%），若需 ≤20% 须解此债或上移 `max_hold_s`（需授权）。 |
| **新：派生段核验误报 33 处** | **OPEN（P21 发现）** | 派生段窗口只含父素材**局部裁切**，核验以 48×48 与**素材全图**比较 ⇒ 33/40 误判失败（即 #74 的"中心裁切/局部化"盲区在同一度量上重现）；门内仲裁需 33 次 VLM（21 段版仅 4 次）。**建议**：派生段改用 P18-1 `bank_score` 子窗口口径（零 VLM 成本、确定性）。 |

### 75.5 LIMITATION：P19-2「素材-素材」指标盲区（一并登记）
P19-2 的 `discriminative_score`（素材间 48×48 最大 corr）**不能**捕获
「**素材 vs 任意成片帧**」的误吸引机制。实证：Phase 18 反门仅有的 2 条误通过来源
`301ff850be9c` 在本指标下仅 **0.0574**（远低于 0.35 阈值），却对 S02/S07 的**成片帧**达 ~0.35。
⇒ 该标记**有用但不充分**；覆盖后一现象需另立「素材 vs 历史帧包」吸引度指标（**未做**）。

---

## 76. 文案风格重写（Phase 23）：盲测**已达标**、q3 清单已处置、v4.1 定稿 + AI 味信号**盲区登记** — `MITIGATED`

### 76.1 盲测待办（**阻塞项**，真值 = 项目所有者）
Phase 23 P23-4 盲测包已就位：`logs/phase23_blind_pack.json`（A/B 已打乱；明文对照封存于
`logs/phase23_blind_answer_key.json`，**验收前请勿查看**）。
**待回答**：q1 哪版更像目标机制？／q2 哪版人味更重？／q3 圈出仍有 AI 味的句子。
**达标线（运行前写死）**：q1 与 q2 **都判 v4 或持平** + 机器信号同向（v4 < v3，**已满足**）
+ 圈出句子**逐条处置**。**未达标** ⇒ 迭代一轮；仍不达标 ⇒ STOP 并转「人工执笔兜底路线」提案。


### 76.1-update 盲测结果与 q3 处置（**已达标，2026-10-01**）
**盲测结果**：**q1 = B（更像目标机制）、q2 = B（人味更重）** ⇒ 两问均判 v4，
机器信号同向（v4 `ai_flavor` 0.0000 < v3 4.5298）⇒ **判定达标**。
**q3 清单 4 条逐条处置**（见 `logs/phase23_q3_disposition.json`，**零额外 LLM 调用**）：
| # | 问题 | 处置 |
|---|---|---|
| ① | 路线图报幕段 | **删除** seg1 的时间线报幕句与"承诺说清"句，保留反方立场句 |
| ② | 「钉死/交代清楚/标清楚」元叙述过多 | **保留 2 处**（≤2 上限）、其余 4 处**折入正文** |
| ③ | 「不满足这个框架」书面腔 | 改口语「套不进这个二选一」 |
| ④ | 「问题有两层」枚举式 | 改口语句式并折入正文（"两件事都躲不开"） |
**处置后复跑**：六项机械校验**全过**；信号**无回退**（`ai_flavor` 0.0000 保持；推进词 0.2997→0.2995；
句长 CV 0.5608→0.5590；字数 3337→3339）。**v4.1 定稿**：`logs/phase23_v4_1_script.json`
（sha256 `228d3f541a7d0522dc7073ced42b715420b54cde800e07f8f45e05a2cacc9ba1`）。
**口径提示**：q3 的 4 条**全部落在信号可覆盖范围**（元叙述/报幕/书面腔/枚举），
故**本轮未新增信号盲区实例**；§76.2 列出的五类盲区（语义空转／伪具体化／立场虚化／
听觉节奏／视角跳变）仍为**待观察**状态。

### 76.2 AI 味信号覆盖不了的句子 ⇒ 登记为**信号盲区**
`core/ai_flavor.py` 的 8 项信号只能覆盖**可机械计数**的 AI 味（推进词／对称构式／设问自答／
句长节奏／冒号展开／破折号／限定语堆叠／段落对称）。以下类型**故意未做信号**（盲区）：
- **语义空转**（说了很多但不推进信息）；
- **伪具体化**（类比贴切度差、类比与概念错配）；
- **立场虚化**（表面上"有态度"，实则无可检验判断）；
- **节奏的"听觉"层面**（朗读顺口度、气口），文本信号无法覆盖；
- **视角跳变**（叙事人称/焦点突然切换）。
⇒ 盲测 q3 若圈出上述类型的句子，**属信号盲区**，按授权书口径**登记而非硬修**。

### 76.3 已知口径限制
- **风格目标文档冻结状态**：`config/style_target_wangxiao_v1.md` 已产出（sha256 见下），
  **待所有者确认后正式冻结**（授权书要求）。
- **v4 内容结论继承 v3 谱系**：**未重跑 claim/事实核查链**（授权明令）⇒ v4 事实层未获新的独立核查。
- **prompt 不含参照例句**：为控体积与防诱导抄袭，system prompt 只投**机制名 + 规则句**；
  防抄依赖**机械 n-gram 守卫**（v4 与参照文本最长公共 **0**）。


> 风格目标 sha256：`31cc7f14d2ef270ba0638e705717da4ddee64152b83d4f7a1d49827f8f8a998f`

---

## 77. Phase 24 P24-1 → **Phase 25 已解除**：幅度上修 1.25 后三指标实测全过 （原「幅度 × 冻结占比」约束冲突）— `RESOLVED`

### 77.1 结论（数学，不是实现问题）
授权同时要求：**zoom ≤1.08 / pan ≤画面宽高 3%**（幅度上限）
与 **冻结占比 <50%、最长连续静止 <25s**（观感指标）。
在**低细节静态图片**素材上，两者**不可兼得**：

| 项 | 推导 |
|---|---|
| zoom ≤1.08 ⇒ 1920px 画布总推进 | **142px**（1920 − 1778） |
| 探针尺度 160px 宽 ⇒ 每 1px 探针变化需全分辨率 | **12px** 推进 |
| 整景只有 142px ⇒ 探针上总变化 | **≈11.8px** |
| 摊满 20s ⇒ 每秒可见变化 | **0.59 px/秒 << 1px/s** |
| 要 20s 内每秒 ≥1px（探针）变化 ⇒ 需累计放大 | **≈112%**，远超 1.08 上限 |

⇒ 冻结占比由「每秒可见内容变化」决定，而该变化的**上界被幅度上限锁定**。

### 77.2 实测（逐秒差分法，`core/motion_metrics.py`）
20s 探针短片：冻结占比 **73.7%** ✘｜最长静止 **9.0s** ✔｜开场变化 **5 次** ✔
（MAD 中位数 **0.0** ⇒ 绝大多数相邻秒逐像素完全相同）。

### 77.3 度量口径的重要更正（如实登记）
**`freezedetect` 不适用于本度量**：实测在 H.264 CRF20 下，它对**真实冻结画面也报 0%**
（6 组 noise/scale 配置全部 0.00s，见 `logs/phase24_p24_1_probe.json`）——
编码噪声抖动持续超过噪声阈值。故它是「**噪声阈值**」度量而非「**内容运动**」度量；
监理的 94.8% 基线**并非由该方法得出**。本阶段改用授权书原本指定的**逐秒差分法**
（1fps 抽帧 → 160×90 灰度 → 相邻 MAD；`MAD<0.05` 判冻结）。

### 77.4 待裁定选项（阻塞 P24-2/3/4/5）
① **放宽幅度上限**（如 zoom ≤1.25，或允许**整幅平移**动画）；
② **换素材策略**（改用含运动的视频素材 / 多图快切）；
③ **图内元素动画**（图注/箭头/高亮的逐段揭示，而非整体缓推）；
④ **重定义指标**（如按 5s 窗口计冻结；注：不改变观众实际观感）。
**本阶段未自行放宽任何阈值、未改口径。**

### 77.5 附：`cap=2` 的池缺口
P24-3 要求的 `per-asset cap = 2 景`，对 21 景需 **≥11 张**不同素材；
当前池 **unique = 10** ⇒ **缺 1 张**。本阶段**未触发受治理获取**（依授权书，缺口应如实报告）。

### 77.6 处置更新（**Phase 25 已解除，2026-10-01**）
| 项 | 结果 |
|---|---|
| **幅度上修** | `MAX_ZOOM_END: 1.08 → **1.25**`（授权 P25-1）；保留 `MAX_ZOOM_END_V1=1.08` 作**守卫降级目标** |
| **总推进** | **142px → 384px**（1920 基准，2.7×）；探针尺度每秒可见变化跨过可测阈值 |
| **三指标实测** | 冻结占比 **73.7% → 0.0%** ✔｜最长静止 **9.0s → 0.0s** ✔｜开场 90s 变化 **5 → 23 次** ✔ |
| **MAD 中位数** | **0.0 → 10.23**（内容运动从"逐像素完全相同"变为显著可测） |
| **每景 corr 守卫** | 新增 `core/motion_guard.py`：`corr<0.30 ⇒ 该景幅度降回 1.08 重渲 + 登记 MOTION_DOWNGRADED`；**只调运动参数**，不改 corr 判定与仲裁语义 |
| **测试** | `motion_guard_test` **27/27**、`motion_metrics_test` **28/28**、`motion_test` **22/22**（共 **77** 项） |

**⚠️ 对 §77.3 的归因更正（如实登记）**：P24 曾把失败归因于"**探针分辨率** + 幅度上限的双重约束"，
并写下"分辨率决定成败"。**P25 实测更正**：1.25 幅度下 **160×90 / 320×180 / 480×270 三种探针全部通过**
（冻结均 0.0%）⇒ **主因是幅度**（1.08 的 142px 太小），分辨率只是**敏感度系数**。
P24 的"分辨率决定成败"表述**过强，特此更正**。（`freezedetect` 不可用作内容运动度量的更正**仍然成立**。）

**⚠️ 与授权书推导的差异（如实登记）**：授权书写"1.25 幅度 ⇒ 480px 推进"；
本实现 `w_end = out_w/zoom_end = 1536` ⇒ 总推进 **384px**（480 对应 `w_end=1440`/1.333 倍）。
倍数关系一致（×1.25），仅"幅度"基准不同；**384px 已足够**（三指标全过），故**未改语义**。

---

## 78. Phase 26 §0：派生段核验「**产物在位但未接入**」已修复 + bank 口径**判别裕度为负** — `MITIGATED`

### 78.1 发现与修复
Phase 22/18 的 bank 口径修复**产物一直在位**（`core/corr_diagnostics.py::bank_score`、
`tests/corr_metric_diagnostics_test.py`、双门证据），但**从未接入编辑链**
—— `agents/editing/agent.py::_verify_scene_frames` 仍走「帧 vs 素材**全图**」，
这正是 Phase 20 在 40 段上产生 **33 处误报**的直接原因。
**Phase 26 §0 已补**：新增 `bank_derived` 门控（`config.tools.frame_match.bank_derived`，**默认 false**
⇒ 关闭时与既有逐字节一致）；开启时期望素材改用子窗口 bank 最大 corr，对照上限取池内**其它**素材。

### 78.2 双门验证（修正期望素材后）
| 门 | 要求 | 实测 |
|---|---|---|
| 正门（帧 vs **实际在屏**素材） | 100% PASS | **52/52 = 100%**（bank min 0.5151 / 中位 0.8804） |
| 反门（帧 vs 其它素材） | 0 误通过 | **0 / 572**（bank min 0.0683 / 中位 0.2029 / p95 0.5277 / max 0.5833） |

**⇒ 双门全过，口径可接入（受门控）。**

### 78.3 ⚠️ LIMITATION：**判别裕度为负**
在屏素材 bank 的**最低值 0.5151** < 无关素材的 **p95 0.5277**（判别间隔 **−0.0126**）⇒
bank 口径在两个分布上有**重叠区**。因判据阈值 0.30 远低于两者分布，双门仍全过；
但**若后续上调阈值、或用于更严的存在性判定，该重叠会先失效**。
**建议**（未做）：加**最小方差门**（丢弃近常量子窗口）或改用 bank/全图混合判据。

### 78.4 ⚠️ 测试方法学更正（如实登记）
首版双门测试用 `fixture.binding` 当期望素材，得出「正门 42.5%、反门 100/440 误通过」的失败结论；
复查发现 **Phase 20 渲染时的实际素材 ≠ fixture 记录的绑定**
（实测 `_frame_S10p1.png` 与 Postal 全图 corr **0.9304**，即该帧**就是** Postal）
⇒ 首版把**真正的在屏素材**当成了"无关素材"，**结论无效**。修正方法：
期望素材 = 该帧的**全图 argmax**（≥0.50 才计入）。**首版证据留档以备案。**

---

## 79. Phase 27 → **Phase 28 已修复**：派生段绑定回退已落到生产路径（失败 17→4）；`//` 滤镜缺陷已修 — `RESOLVED`

### 79.1 派生段绑定未落到渲染（**唯一剩余阻塞**）
**现象**：40 段成片渲染成功，但逐景核验 `checked = 2/40` —— 只有 `S01`/`S20`（父景 id）
有 `expected_asset_id`；其余 **38 个派生段**（`S02p1`…）为 `None` ⇒ 落入"占位镜头"分支
⇒ **17 景失败**；连带 **DQ-2 FAIL**（`max_asset_share 0.9369`、`unique_assets 3`，政策 ≤0.35 / ≥6）。

**根因**：`MATERIAL_TIMELINE` 的 decisions **按父景 ID 落库**；40 段派生脚本的 scene_id 是
**派生 ID**，闸门按派生 ID 查绑定 ⇒ 查不到。
**这是与 Phase 26 §0「产物在位但未接入」同一模式的第二次出现**：
Phase 21 的"绑定展开"只做在**离线复验脚本**里，**未进入渲染链**。

**修复路径（推荐第 1 项）**：
1. **闸门按 `parent_scene_id` 回退查绑定**（改动最小、不动 DB 写入路径）；
2. 或把父景绑定**展开**成 40 条 decisions 写进 `MATERIAL_TIMELINE`；
3. `bank_derived` 已在位并按派生段取子窗口 corr（Phase 26 §0 双门：正门 100% / 反门 0），
   绑定修好后 40/40 可核验；
4. 一并做 **DQ-2 的 `cap=2` 新口径**与**受治理获取 ≤6 张**（本轮未执行，网络用量 0/6）。

### 79.2 v2 运动滤镜使用 `//`，**ffmpeg 表达式解析器不支持**（已修复）
`crop_filter` 的 v2 平移/缩放闭式原用 `//` 做整数除。**ffmpeg 不支持 `//`**
（报 `Undefined constant or missing '(' in '/519)'`）⇒ 首轮渲染 **19/40 景 crop 配置失败**、
**-22 Invalid argument**、成片 **0 B**。已改为 `floor(a/b)`，重测 **40/40 滤镜全部通过**。
**为何 Phase 24/25 未发现**：那两阶段只渲染**单段探针**（S01 走 zoom 分支，
且 24s 场景未触发平移分支的 `//` 路径）⇒ **只有 40 景全片渲染才暴露**。

### 79.3 ✅ 已达成：三指标在**真实 40 景成片**上首次全过
| 指标 | 阈值 | 实测 |
|---|---|---|
| 冻结占比 | <50% | **15.2%** ✔ |
| 最长连续静止 | <25s | **6.0s** ✔ |
| 开场 90s 变化 | ≥3 次 | **69 次** ✔ |

（Phase 24 提出的观感目标至此达成；对比 P24 的 73.7% / 9.0s / 5 次。）
其余门禁全过：时长 **977.88s** ✔｜响度 **−16.1 LUFS / −2.5 dBTP** ✔｜
PI 前/后全 PASS、`promote_blocked=False` ✔｜字幕 `SUBTITLE_ALIGNED`（171 cue、语音内 1.0、越界 0s）✔｜
MOTION_VERIFIED **40/40、0 fallback** ✔。**仅剩 §79.1 一项。**

### 79.4 处置更新（**Phase 28 已修复**，2026-10-01）
**根因比原判断更深**：`_build_material_timeline` **丢弃了脚本自带的 `scene_id`**，
改用序号合成 `S{i+1}` ⇒ 40 段派生脚本的 `S02p1…` 变成 `S01…S40`
⇒ **决策按合成 id 落库、闸门按派生 id 查**，两边 id 空间不一致。
（Phase 27 的 `checked 2/40` 即来源：只有 id 形式恰好相同的 `S01`/`S20` 蒙对。）

**修复（最小改动，不动 DB 写入路径）**：① **保留真实 id**
（`script_scene_id`/`parent_scene_id`/`bind_scene_id`；**裁决仍用合成 id** ⇒ 既有选材/分类语义逐字不变）；
② **父景绑定回退**（内存表 `parent_asset`，不写 DB）：派生段解析不到素材时按 `parent_scene_id`
回退到父景绑定并标记 `binding_source="parent_fallback"`；**无父景绑定 ⇒ 保持原状（fail-closed）**。

**实测效果**：逐景 `checked` **2/40 → 40/40**｜失败 **17 → 4**｜
DQ-2 `max_asset_share` **0.9369 → 0.3638**（阈值 0.35，仅差 **+0.0138**）、`unique_assets` **3 → 11**；
三指标 **15.2%/6.0s/69 → 11.9%/6.0s/82**（保持全过且更好）。

**v2 运动滤镜 `//` 缺陷**：已改 `floor(a/b)`，40/40 滤镜通过；另修正一处**Python 侧误用 `floor()`**
（`//` 在 Python 合法、只在发给 ffmpeg 的字符串里不合法）。

### 79.5 §0 教训入制（流程守卫，Phase 28 新增）
**规则**：任何"修复类"交付**必须在生产路径上加探针测试**；仅"模块 + 离线脚本验证"**不算落地**。
本会话已两次踩坑（Phase 22 bank 修复未接入调用点；Phase 21 绑定展开只做在离线脚本）
⇒ 均表现为"产物在位但未接入"。
**落地**：修复类测试必须**穿过生产调用点**并覆盖 **fail-closed 分支**；
修复类报告必须写明"生产路径探针测试"的位置。

---

## 80. 末段深色画面：**Phase 31 核查结论 = 非缺陷**（素材已持住、暗度系素材固有）；旧「近黑」指标口径废弃 — `NOT_A_DEFECT`（待监理确认）

**发现（Phase 28，仲裁层 VLM 逐景核验直接读出）**：
| 景 | corr | VLM | 理由（原文节选） |
|---|---|---|---|
| **S18p1** | 0.055 | absent | 「**成片帧仅为深色背景加一行字幕**，无任何代码、图表或界面元素」 |
| **S21p2** | 0.000 | absent | 「**成片帧为纯深蓝色画面**，无任何文字、图案或结构特征」 |
| **S21p1** | None | （未调用） | — |
| S14p1 | 0.209 | absent | 「成片帧为数学分支结构图，素材为邮票标签，二者无任何重合」 |

**性质**：这是**真实渲染内容缺陷**（画面不含素材、几近纯色），**不是绑定/度量口径问题**
（绑定回退已修，`checked` 达 40/40）。**S21p1/S21p2 为全片末段**，
**疑与 40 段时基下最后几段的素材窗口/时长边界有关**（末段 `end_s` 被延长到 `cursor+2.0`）。
**建议**：下一阶段专项定位（抽查末段抽帧 + 检查时间轴末段窗口与素材可用性）。

**同阶段澄清**：另有 4 景（S04p1/S10p2/S11p1/S11p2，corr 0.250–0.299 略低于 0.30）
被 VLM 判 **present** 并**放行** —— 属**度量阈值下的正常边缘**（bank 口径 + 仲裁兜底按设计工作），
**不是缺陷**。

### 80.5 根因定位（**Phase 29 P29-1，2026-10-01**）
**根因（授权书未列的第 4 类）**：**时基比内容长 16.25 s ⇒ 视频轨内容耗尽后被补黑**。

| 项 | 值 |
|---|---|
| voice 40 段**内容实测** Σ | **961.634 s** |
| pause 归因表合计（39 边界） | **14.250 s** |
| trailing pad | **2.000 s** |
| 声明 `audio_time_base_s` | **977.884 s** |
| **内容耗尽点**（Σ内容 + trailing） | **963.634 s** |
| **黑板尾长** | **14.250 s**（+结尾 2s，合计 ≈16.25s 无内容） |

**实测印证**：尾段亮度扫描 —— 940–956s `mean≈136.3`（有内容）｜**958–974s `mean≈18.6`（近黑）**｜
976s 回落 136.75。首个近黑时刻 **958.0s** 落在 `S21p1` 声明窗口 `[942.47, 961.35]`；
`S21p2` 窗口中点 969.99s ⇒ `mean 18.60` —— **与仲裁层 VLM 读出的「纯深蓝色画面」「深色背景加一行字幕」完全吻合**。

**假设裁定（逐条）**：a) 窗口映射越界 **不成立**（映射 40/40、文本守恒 3468==3468、
`assert_lineage` 通过、末段窗口连续无缝）；b) 绑定链断裂 **不成立**（Phase 28 已修，`checked` 40/40）；
c) 旁白无素材可配 **不成立**（末段有绑定，`corr=0.000` 是"近黑画面 vs 素材"的比较结果）；
**d) 时基>内容 ⇒ 补黑：成立**。

**附带发现**：`S21p1` 在 Phase 28「未调用仲裁」的原因 = 其 `corr` 为 `None` ⇒
仲裁层按 `SKIPPED_MISSING_INPUT` 处理（**不是仲裁逻辑缺陷**，而是该景本身落在近黑区）。
另：`t=976s` 亮度回落 136.75 ⇒ **片尾最后 ~1–2s 有一段非黑画面**，
与「在 `S21p2` 之后追加 H7 片尾卡」的意图恰好一致。

**修复建议（待裁定）**：① **把 pause 落成真实静音**（推荐：重切/重拼旁白音频，**零文本改动**）；
② 让 pause 不进时间轴（需改 `PAUSE_BUDGET_S` 时基语义 ⇒ **超授权**）；
③ 缩短时基到内容长度（**破 978.7±1 时长契约**）；
④ 仅追加片尾卡（**只能覆盖 ~2–4s，无法覆盖 14.25s 黑板** ⇒ 不能根治）。

### 80.6 **Phase 30 再更正**（重要，2026-10-01）
**修正 ①：Phase 29 的因果归因不完整。** Phase 29 判「时基比内容长 16.25s ⇒ 视频轨补黑」，
并据此采纳了选项①（pause 真实化）。**P30 实测：pause 真实化后黑板逐点未变**
（958/961/964/967/970/973/975s 的 mean 与旧版**完全相同**：18.63/18.19/18.79/18.79/18.60/18.61/18.61）
⇒ **根因在视频侧**（末段素材窗口未覆盖其时间窗），**不是**音频/时基缺口。
Phase 29 的**量化**（时基 977.884 vs 内容 961.634）**仍然正确**，但把它当黑板**根因**是**不完整的**。

**修正 ②：多数「深色画面」是素材固有暗色，不是技术性黑板。**
全片 1 fps 灰度扫描 + 逐景对照：
| 景 | 中点 mean | 判定 |
|---|---|---|
| S16p2 | 246.63 | 亮 |
| **S17p1 / S17p2 / S18p1** | **18.00 / 18.87 / 18.41** | **暗（素材固有）** |
| S18p2 / S19p1 / S19p2 / S20 / S21p1 | 136.28 / 136.16 / 134.03 / 136.57 / 136.40 | 有内容 |
| **S21p2** | **18.60** | **暗（唯一真缺陷所在）** |

**池内素材固有亮度**：`Close-packed spheres.jpg` = **mean 42.54**（全片最暗素材）
⇒ 经 1.25 推近后在探针尺度约 **18**，**与 S17p1/S17p2/S18p1 观测值一致**
⇒ 这三景是**正常的暗色素材内容**（"密堆球"示意），**不是缺陷**。
**Phase 28/29 把它们与"纯蓝/黑板"混为一谈是错的。**

**真正的缺陷收窄为**：**S21p2 的尾部区间** —— 该段窗口 `[961.35, 978.63]`，
**视频内容在 ~961.4s 即结束**，其后为补齐的深色 ⇒ **黑板尾长约 16–17s，仅此一处**。
**授权书要求的「H7 片尾卡追加于 S21p2 之后」正是覆盖该区间的正解。**

**验收指标口径问题（需裁定）**：授权书要求「全片无 ≥3s 连续近黑」。
**实测 978 张抽帧中近黑 204 秒（20.9%）、最长连续近黑 41s** ⇒ 按现口径**不通过**；
但该 41s **包含正常的暗色素材内容**（密堆球示意段 S17p1–S18p1 连续约 41s）
⇒ **该指标把"内容性暗场"与"技术性黑板"混为一谈**，按现口径**不应通过**。
**建议**改为「尾部区间（最后一段窗口）无 ≥3s 补齐黑板」或
「逐景暗度与素材固有暗度一致（而非纯黑 mean<5）」。

### 80.7 P30-1 pause 真实化（选项①）**已完成**（音频侧正确且必要）
按归因表插入真实静音：**19 个原始边界 × 0.75s = 14.250s**、20 个派生边界 × 0；
**trailing 2.0s 亦真实化**（仅拼段+停顿为 975.936s，比声明时基少 2.0s ⇒ 用 `apad` 补齐）。
**运行前写死断言：977.884 ± 0.1s ⇒ 实测 977.952s 通过 ✔**。
零重合成/零文本改动/零变速；逐段 `sha256` + 规则版本入 provenance。
**结论：该修复对黑板无效，但它本身是正确的（时基内容现已真实存在），不撤销。**

### 80.8 **Phase 31 核查结论（终）**：末段"深色"**不是技术性黑板** ⇒ `NOT_A_DEFECT`
**构造侧（代码事实）**：`agents/editing/agent.py` L1565–1577 —— 每个有素材的景，视频输入为
`-loop 1 -framerate 1 -t {ceil(d)+2.0} -i <asset>` + 滤镜 `trim=duration=d`
⇒ **素材以 `-loop` 循环输入、输入时长 ≥ 窗口时长、随后精确裁到窗口**
⇒ **设计上素材必然持住整个窗口**，"窗口 > 视频内容"的景**在当前实现里不会出现**
（Phase 31 §0(b) 假设的那类景不存在，故"延长素材窗口"的改动**不改变任何像素**）。

**像素侧（S21p2 窗口内逐秒抽帧；判据 = std/uniq，而非平均亮度）**
| t (s) | mean | **std** | **uniq** | 判定 |
|---|---|---|---|---|
| 963.0 | 17.85 | **0.36** | **4** | 纯色（**素材内平坦区**，非补齐） |
| 965.0 / 967.0 / 969.0 | 18.79 | **14.92** | **256** | **有完整图像内容** |
| 971.0 / 973.0 / 975.0 | 18.61 | **13.37** | **256** | **有完整图像内容** |
| 977.0 | **113.44** | 38.46 | 171 | **亮**（片尾收束画面） |

**关键判据**：真正"技术性黑板"应为 **std≈0、uniq≈1**；实测 965–975s 为 **std 13–15、uniq 256**
⇒ **是完整图像内容、只是整体偏暗**（沿用池内最暗素材 `Close-packed spheres.jpg`，固有 **mean 42.54**；
经 1.25 推近聚焦暗区后探针 mean≈18）。**⇒ 末段深色 = 素材固有暗色，不是缺陷。**

### 80.9 **指标口径更正（Phase 31 §0(a) 落地）**
**旧指标「全片无 ≥3s 连续近黑」废弃**：它把"**内容性暗场**"与"**技术性黑板**"混为一谈
（实测 978 抽帧中近黑 204s / 最长连续 41s，**其中含正常暗色素材段 S17p1–S18p1**）。
**混淆原因（登记）**：以**平均亮度**作唯一判据，未区分"**低亮度但有内容**"（std/uniq 高）
与"**无内容补齐**"（std≈0、uniq≈1）。
**替代构造断言（运行前写死，建议纳入 tests）**：
| # | 断言 | 判据 |
|---|---|---|
| **A1** | 逐景视频窗口覆盖其声明时间窗（素材持住） | 有素材景：输入 `-t ≥ 窗口 d` **且** `trim=duration=d` ⇒ 视频轨长度 == 窗口长度（**当前实现恒成立**） |
| **A2** | 视频轨无补齐段 | `Σ视频轨时长 == Σ声明窗口时长`（容差 0.1s）；实测 **977.867 vs 977.880** ✔ |
| **A3** | 像素暗度仅作 scene-relative **辅助证据** | 每景中位亮度与其**素材固有亮度**同量级（差异 >30% 才报警），**不作门禁** |

### 80.10 **Phase 31 执行轮（2026-10-01）：A1/A2/A3 已纳入 tests；§1 改动确认 no-op；DQ-2 实测更正**

**A1/A2/A3 已落地为可执行测试**：`tests/no_completion_blackboard_test.py`（**12/12 PASS**）。
其中 **A2 在 P31 真实成片上实测：Σ视频轨 977.884s == 声明时基 977.884s（Δ 0.000s）✔**；
**A3 仅记录、不作门禁**。测试含**源码契约断言**（防"延长素材窗口"类改动回潮）与
**无素材景=显式纯色卡 `color=c=0x0b1226`** 的区分断言（该色**不是**补齐黑板，是设计占位）。

**§1「延长素材窗口」确认 no-op（复核）**：`-loop 1` + `trim=duration=d` 已保证素材持住整个窗口；
本轮重渲（`p_aafdd21cbb9d`，136.1s，977.880s）再次证实**无补齐段**（A2 Δ0.000s）。

**DQ-2 实测更正（文档旧值不准）**：按**渲染实际时间轴**复算 ——
`max_asset_share` **0.3638 → 0.3341**、`unique_assets` **11 → 13**、主导素材复用 **15 景/353.17s → 14 景/326.75s**，
**state = PASS**。旧值溯源为 `logs/phase27_p27_3_verification.json` 的**历史绑定**（含 E1 片尾卡窗口口径）。
**注意**：`retrieval_candidates` artifact 内的 `_p30_binding` 是**选材前的绑定提案**
（与渲染实际决策 **31/40 不一致**），**不得**用于 DQ-2 结论。

### 80.11 **新登记：逐景核验门在 40 段末两景的度量边界（`S11p2`/`S13p2`）**

**现象**：P31 终渲染 `ASSET_INSUFFICIENT` fail-closed —— `S11p2` `corr_expected 0.270`、
`S13p2` `0.285` < 冻结阈值 **0.30**（`tools.frame_match`/`materials.DEFAULT_POLICY.frame_match_min_corr`）。

**已查明：不是素材错配，也不是绑定缺陷**（三项证据）
1. **目视**：成片帧确为期望素材 `301ff850be9c` 的推近裁切（可见其分支结构与文字）。
2. **全池穷举**：期望素材在两景均为**全池最高分**（`bank 0.270 / 0.285`），
   其余 11 张最高仅 **0.197 / 0.196** ⇒ **池内重选无法改善**。
3. **手工细网格**：在同一成片帧上以 16:9 窗口（比例 40%–100% × 9×9 位置）搜索，
   真实呈现窗口（素材宽度 **≈72%**、居中 x≈246/y≈96）得 corr **0.688 / 0.728**。

**根因（可复算）**：冻结 `core.corr_diagnostics.bank_score` 的
`BANK_SCALES=(1.0,0.8,0.6,0.45,0.35)` + `BANK_GRID=5`：
① 该素材 **1404×696（2.02:1）**，16:9 子窗口**可行比例被真实宽高比限制**
（`w=1123` 时 `h=632`，实际为 **0.8 宽 × 0.745 高**，偏离所需 ≈0.72）；
② `5×5` 网格 x 步距 **≈281px**，取不到 `x0≈246`。
⇒ 属 **Phase 17 已登记的度量伪影**（「稀疏线稿在 48×48 塌陷」+「运动缩放致画面=子窗口」；
该素材 `crop_safety 0.0906`）在「**该素材 + 1.25 推近 + 40 景（拆镜后派生段）**」下的**残留**。

**未采取的处置（授权禁改）**：未改阈值、未改 corr 口径、未改 motion POLICY、未改 PI/DQ 语义。
**建议**：按 Phase 17 既有建议 —— **提高分辨率（48 → ≥192）重验同一 bank 形式**（**不放宽阈值**）。

### 80.12 **Phase 32 处置完成 ⇒ `#80` 关闭为 `NOT_A_DEFECT`（2026-10-01）**

**§80.11 的建议已落地：`bank-derived-v2`（探针 192 + 网格自适应步进 ≤170px，阈值 0.30 不变）。**
- **生产实测（40 景）**：`corr_bank` 覆盖 **0/40 → 32/40**（其余 8 为纯色卡景）、`bank_error` **0**；
  **S11p2 0.0914 → 0.3199 ✔**、**S13p2 0.0834 → 0.3332 ✔**（均过 0.30）；逐景 `failed` **0**；
  需 VLM 仲裁的景 **12 → 2**。
- **同时修复了一处静默降级**：生产链以 `gray48`（48×48）取帧而 v2 需 192 ⇒ `_corr` 形状不匹配
  抛错被**裸 `except` 吞掉**、回退到全图口径（**P28 §0 禁止的"静默回落"**）。
  已改为：①`bank_score_of` 自动规整探针分辨率；②v2 下**以 192 重载画面**；③该分支记录 `bank_error`。
- **如实限定**：P17 历史手工语料上 v2 正门 **14/17**、**冻结 v1 亦仅 13/17**
  （`S07 frame_50` 0.2766 在 v1/v2/SSIM 三口径下均 <0.30）⇒ **采纳依据是生产实测**，
  该手工语料的边界**已登记**（材料包 `known_limitations`）；**阈值与口径未改**。

**末段像素证据（最终成片复测，闭合 P29/P30 口径疑点）**：
末段 **976.0s mean 134.56**、**977.0s mean 117.31（亮）**；S21p2 窗口内 961.5 / 965–975 均
**`uniq=256`（有完整图像内容）**、963.0 为**素材内平坦区**（`std 0.36 / uniq 4`，非补齐）；
**全片技术性黑板 = 0**（构造断言 A1/A2 成立：视频轨满覆盖、`Σ视频轨 == 声明时基` Δ 0.000s）。

⇒ **「末段深色」的完整结论**：**素材固有暗色 + 内容性暗场 + 片尾收束亮画面**，
**不是技术性黑板**；旧「全片无 ≥3s 连续近黑」指标**已废弃**并被 **A1/A2/A3 构造断言**取代
（`tests/no_completion_blackboard_test.py`）。**`#80` 关闭 = `NOT_A_DEFECT`。**


