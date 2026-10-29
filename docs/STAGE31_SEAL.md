# Stage 3.1 SEAL 报告（Final）

- **状态：SEALED / FINAL**
- 版本：**3.1.0**（`src/video_studio/stage31/__init__.py`：`STAGE31_VERSION = "3.1.0"`、`STAGE31_STATUS = "SEALED"`）
- 封包时间：2026-08-27（人工裁决通过后执行）
- 上游冻结基线：2.0.0 / 2x-final-8q 未变；Truth/Evidence、Creator Style v2、`V2_FINAL_SCRIPT_JARVIS.md` 均未修改。

---

## 一、版本与文件状态

- **无 Git 仓库**（`git rev-parse` 返回 NO_GIT_REPO）。文件状态以 SHA256 基线记录，任何后续改动可对照本报告检测。

### 3.1 封包文件 SHA256 基线

| 文件 | SHA256 |
|---|---|
| src/video_studio/stage31/__init__.py | E8E630D360F105DDB1792CD5A24F1DA91BFCF97288B32AA3C2346EE5CE4AEA79 |
| src/video_studio/stage31/package.py | AABD18407C01B98B4ABAB1882DEC08D84F3BB00D035074FA500721748979353C |
| src/video_studio/stage31/ranking.py | C561158231C9C5DE7D59B1F98C5E6BB561C708FCA1CF2F0C30DD75628CFDA092 |
| src/video_studio/stage31/rights.py | 1BE6894B6774664E4872D7FD794A00C41D607AFF9251DEB0C6B3FA696372E97C |
| src/video_studio/stage31/sources.py | A5E9CC48E18EF58184FD9E5C9B80101D05BF0019BBAE8F3A728698AF66BE8746 |
| src/video_studio/stage31/visual_intent.py | C1B557F932190193672DB599E0E76E115F1CEF75B926D8CC9165E40F22815B53 |
| scripts/run_stage31.py | B0E2B4482DB69F6F817E0A3A0B6B65F01583D9E984BE1B4582AE0DE6173644C2 |
| scripts/run_stage31_acceptance.py | BEBA2E83A3080B87EE2DB06EF091A35E0532A12709C5A9238FC3D8ED3605F4A3 |
| scripts/verify_stage31_package.py | DE818BCE3E6A546254109D29F89F4CA02EBDA73B4A3ED832C3B986604049DA4A |
| tests/stage31_intent_test.py | 7617C8499747844365695645D103E8DA28FCDA822E6CB07AFFE3233521ABD01E |
| tests/stage31_package_test.py | 447EDC51A675B38E644A1EF0DF41B71239581FC203D68AF352A41741B0389196 |
| tests/stage31_rights_test.py | F5F705679CD04520C0807865E14817F48D8E5271F2AE8602E45C655A47F9E3C3 |
| scripts/final_production_regression.py（含 claim覆盖 大小写不敏感修复，人工裁决保留） | EE403177F4892F710AB3E76D53859B8DAD1FEEB688E0E9DD505B78562D4F41FF |

### 2.x 冻结基线（未变）

- 19 个 2.x 冻结核心文件 SHA256 校验通过（15/19 与 8R manifest 一致；4 个为 2026-08-19 人工裁决的 Creator Style v2 升级版，本轮零改动）。
- 13 套 2.x 冻结测试全部 PASS。

---

## 二、3.1 最终能力边界（明确写入封包）

1. Agent 读取 2.x Production Package（shotlist 44 镜 + v2 口播稿映射），为**每个镜头**自动生成 VISUAL_INTENT（subject/action/environment/mood/visual_metaphor/camera_style/preferred_duration/avoid_list）并据此自动检索候选素材；
2. 素材与口播的关系分四类：**DIRECT（直接对应）/ CONCEPTUAL（概念对应）/ EMOTIONAL（情绪对应）/ RHYTHM（节奏型 B-roll）**，另有 EVIDENCE（证据截图，与 B-roll 分离，走 Truth/Evidence 体系）与 SELF_MADE（自制字卡/占位镜）标记；
3. **每个候选素材必须记录**：来源（source_url/original_url）、许可证（license/license_url）、作者、署名要求与文案、下载地址、检索时间、分辨率/时长、视觉描述等 18 项 provenance 字段；
4. **版权硬门槛**：UNKNOWN / 不满足版权安全门槛（UNSAFE：影视/新闻/社交平台/无证素材）的素材**不得进入推荐池**；默认池只放 SAFE（CC0/Public Domain），CONDITIONAL（CC BY/CC BY-SA/GFDL）仅作备选且必须按 rights/ 署名；
5. 找不到安全匹配时输出 **NO_SAFE_MATCH**（含搜索过的来源、用过的关键词、候选被淘汰原因、推荐的自制方案），**绝不编造素材**；
6. 素材源现状（如实记录，不伪装）：**Wikimedia Commons = 当前实际可运行来源**（无 key，自带许可证元数据）；**Pexels/Pixabay 需要 API key**（未提供，运行时标记 NEEDS_API_KEY）；**Openverse 当前环境不可达**（代码就绪，网络可达即可启用）；
7. **3.1 的目标是"辅助人工找安全素材"**：不是自动完成剪辑，不生成最终视频，也不保证每个镜头都有 DIRECT 对应素材（CONCEPTUAL/EMOTIONAL/RHYTHM 同样是合法答案，NO_SAFE_MATCH 同样是被接受的正确结果）。

---

## 三、SEAL 前最终验证结果（全部 PASS）

| # | 验证项 | 结果 |
|---|---|---|
| 1 | 2.x 端到端回归 final_production_regression（4 场景 × 4 平台 × 10 检查） | **ALL PASS**（含大小写不敏感修复口径） |
| 2 | 13 套 2.x 冻结测试 | **PASS（0 失败）** |
| 3 | Creator Style v2 acceptance（style_v2_ab + v2_script_acceptance） | **PASS（exit 0 / 0）** |
| 4 | Truth/Evidence regression | **PASS** |
| 5 | Stage 3.1 G1–G15 | **PASS（fails=0）** |
| 6 | Stage 3.1 三套测试（rights 69/69、intent 106/106、package 22/22） | **PASS** |
| 7 | 版权安全测试（G15 全用例） | **PASS** |
| 8 | provenance 检查（18 字段 + metadata/rights/映射引用一致） | **PASS** |
| 9 | material_package_31 完整性校验（verify_stage31_package.py） | **16/16 PASS** |

Material Package 六件套齐全且内部引用一致：`materials/`（预览图，引用齐备）、`metadata/materials.json`（449 条）、`rights/rights_summary.json`（449 条一一对应）、`shot_mapping/`（44 镜 + NO_SAFE_MATCH 9 镜）、`search_log/search_log.json`（44 镜查询 + 来源状态）、`README.md`。

---

## 四、已知限制（冻结记录，不继续优化）

1. 素材源仅 Wikimedia Commons 实时可用；Openverse 超时、Pexels/Pixabay 无 key——按裁决记录为已知限制，**不因"还有素材源没接入"而继续开发**；
2. Commons 匿名限流（429）导致部分查询无结果/报错，已在 search_log 逐条如实记录；
3. Commons 素材以 CC BY/CC BY-SA 为主 → CONDITIONAL 占比高，真人采用须逐条署名；
4. 语义匹配为确定性词重叠评分（无 LLM），效果以"可追溯、可复核"优先于"更聪明"；
5. 冻结链自身的大小写敏感逐字指标（如 openworm/OpenWorm）与修正后检查口径的差异在回归输出中可见，不隐藏。

## 五、范围声明

- **3.2（自动剪辑、自动配音、自动发布、导演 Agent 等）不属于本版本范围**，本次封包不实现、不预留、不进入。
- 本轮未修改任何 2.x 冻结文件、Truth/Evidence 数据、Creator Style v2、V2_FINAL_SCRIPT_JARVIS.md。
- 本轮对 `scripts/final_production_regression.py` 的大小写不敏感修复及其全部回归结果**予以保留**（人工裁决授权）。

**封包完成。STOP。**
