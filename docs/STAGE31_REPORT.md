# Stage 3.1 封包报告 —— AI 素材研究员（Material Researcher）

- 版本：3.1.0 ｜ 状态：**SEALED / FINAL**（人工裁决通过，2026-08-27；SEAL 报告见 `docs/STAGE31_SEAL.md`）
- 定位（§一）：不是"自动做视频"。3.1 = AI 素材研究员/采购员：Storyboard → 视觉意图解析 → 素材需求 → 合法素材检索 → 版权硬门槛 → 语义匹配评分 → 最终推荐 → 来源/许可证/下载/署名记录 → Material Package。
- 3.1 未实现且不实现：自动剪辑、自动配音、自动发布、导演 Agent、复杂视频生成（G13 检查通过）。

---

## 一、架构（6 个新文件，全部在 `src/video_studio/stage31/`，未触碰任何 2.x 文件）

| 模块 | 职责 |
|---|---|
| `visual_intent.py` | 读 shotlist.json + v2 稿映射 → 每镜 VISUAL_INTENT（subject/action/environment/mood/visual_metaphor/camera_style/preferred_duration/avoid_list）+ match_type（DIRECT/CONCEPTUAL/EMOTIONAL/RHYTHM/EVIDENCE/SELF_MADE） |
| `sources.py` | 检索层：Wikimedia Commons API（无 key、自带许可证元数据）；Openverse/Pexels/Pixabay 状态诚实登记 |
| `rights.py` | 版权硬门槛：领域黑名单（影视/新闻/社交/图库平台）→ 许可证分类 → SAFE/CONDITIONAL/UNSAFE/UNKNOWN |
| `ranking.py` | 七维评分（semantic_match/visual_quality/license_safety/source_reliability/resolution/duration_fit/style_fit）；UNSAFE/UNKNOWN 在评分前直接淘汰（HARD GATE，非权重） |
| `package.py` | Material Package 组装：materials/metadata/rights/shot_mapping/search_log/README + 人工状态（APPROVED/REJECTED/NEEDS_REVIEW） |
| `run_stage31.py`（scripts/） | 执行入口 |

## 二、数据模型（§六 provenance 全字段）

每个候选素材记录：material_id / shot_id / source_url / original_url / source_name / creator / license / license_url / rights_status / commercial_use / attribution_required / attribution_text / download_url / retrieved_at / content_type / duration / resolution / visual_description / match_type / match_score / score_detail / copyright_notes / review_status。**测试逐字段断言完整。**

## 三、JARVIS 实跑结果（output/production_002/material_package_31/）

- 44 镜全部生成 VISUAL_INTENT；类型分布：RHYTHM 19 / EMOTIONAL 11 / EVIDENCE 5 / CONCEPTUAL 4 / DIRECT 3 / SELF_MADE 2（四类关系齐全，G4）
- 37 个 B-roll 镜 × 4 查询（2 关键词 × 图片+视频）真实检索
- 候选记录 **449 条**；入池 **438 条**（SAFE 115 / CONDITIONAL 323）；**UNKNOWN 23 条全部淘汰**（如无版本"Attribution"、GPL）；UNSAFE 0 条入池
- **27 镜有 Primary 推荐**；**9 镜 NO_SAFE_MATCH**（S06/S07/S11/S16/S21/S25/S30/S35/S36/S40 中部分因查询无结果或限流，均记录搜索词/来源/淘汰原因/自制建议）
- Evidence 与 B-roll 分离（§十一）：S12/S20/S28/S32/S41 只登记证据截图需求，不搜 B-roll
- 预览图已下载至 materials/；视频只给下载地址；README 含完整使用说明与诚实声明

## 四、版权安全（§三/§四/§十五）

- 领域黑名单：youtube/youtu.be/bilibili/小红书/抖音/tiktok/腾讯视频/爱奇艺/优酷/netflix/disney/marvel/imdb/微博/instagram/x.com/图库站等 → 一律 UNSAFE（先于许可证判断）
- 许可证映射：CC0/Public Domain → SAFE；CC BY/CC BY-SA/GFDL → CONDITIONAL（必须署名，BY-SA 注明相同方式共享）；BY-NC/BY-ND/ARR/FairUse → UNSAFE；无许可证/无法识别 → UNKNOWN
- **诚实声明（写进 README）**：本系统不声称"绝对不会侵权"；只基于可验证的许可证与来源信息做风险筛选；无法确认授权 → UNKNOWN 排除。

## 五、测试与验收（G1–G15）

| 门 | 结果 |
|---|---|
| G1 读取 2.x 包 | PASS（shotlist.json 44 镜 + v2 稿） |
| G2 全量镜头需求 | PASS（44/44） |
| G3 自动检索 | PASS（真实检索 Wikimedia Commons；来源状态如实登记） |
| G4 四类关系 | PASS（DIRECT 3/CONCEPTUAL 4/EMOTIONAL 11/RHYTHM 19） |
| G5 原始来源追溯 | PASS（每条含 source_url/original_url） |
| G6 许可证记录 | PASS（逐条 license/rights_status） |
| G7 UNSAFE/UNKNOWN 不进池 | PASS（池内仅 SAFE+CONDITIONAL；23 条 UNKNOWN 淘汰） |
| G8 NO_SAFE_MATCH | PASS（fixture 测试 + 实跑 9 镜记录） |
| G9 Shot→Material 映射 | PASS（44 镜逐镜 JSON + all_shots） |
| G10 Material Package 可执行 | PASS（六目录 + README + 预览图） |
| G11 冻结不变 | PASS（13 冻结套件 0 失败；19 文件 SHA 中 15 与 8R manifest 一致，4 个为 2026-08-19 人工裁决的 Creator Style v2 升级版，本轮零改动——时间戳证明） |
| G12 不破坏 2.x | PASS（13/13 冻结套件）⚠ 见下方"发现" |
| G13 未实现 3.2 | PASS（能力级扫描：无 ffmpeg/moviepy/TTS/发布/导演代码） |
| G14 有测试 | PASS（3 套件） |
| G15 版权安全测试 | PASS（69 项：电影/B站/YouTube/抖音/小红书/新闻/无许可证/CC0/CC BY/CC BY-SA/CC BY-NC/CC BY-ND/PD/GFDL/ARR） |

- 3.1 测试：rights 69/69、intent 106/106、package 22/22。
- 验收机读报告：`docs/STAGE31_ACCEPTANCE.json`（fails=0）。

## 六、已知缺口（诚实记录，不假装完成）

1. **Openverse**：当前环境超时不可达（登记为缺口；代码已就绪，网络可达时即插即用）。
2. **Pexels / Pixabay**：API 可达但需要 API key（未提供），运行时状态如实标记 NEEDS_API_KEY。
3. **Wikimedia Commons 限流**：部分查询 429（每次 4 请求/镜节奏下中段触限），受影响查询在 search_log 中逐条记录；重跑时把 sleep 调大到 2–3s 可缓解。
4. **CONDITIONAL 占比高**：Commons 多数素材为 CC BY/CC BY-SA，默认池以 SAFE 优先、CONDITIONAL 备选并强制署名——符合 §四，但真人采用时须逐条按 rights/ 署名。

## 七、发现（pre-existing）→ 已定位根因并修复测试基线（未动生产逻辑）

**根因（诊断脚本 `scripts/_dbg_claim_cover.py`，逐阶段定位）：**

- 缺失实体：S2/S4 均为 `openworm`。
- 机制：冻结链 8G（claim_structuring）把拉丁词实体**统一小写**存为 `openworm`；正文按自然大小写写成 **"OpenWorm"**（"OpenWorm 模拟302个神经元的线虫跑了十余年（证据…）"）。冻结的 `_subtitle_emphasis` 用**大小写敏感的逐字匹配**统计覆盖 → 小写实体永远匹配不到正文。
- 历史遮蔽：v1 模板 hook（"关于{entity}，有一个你可能没想过的答案"）曾把小写实体原样嵌入镜头文本，恰好提供小写精确匹配；Creator Style v2（2026-08-19 人工裁决冻结）删除实体嵌入模板后，该遮蔽消失，问题暴露。
- **内容判定：实体在成稿中真实被覆盖（OpenWorm 出现在镜头正文），并非真实 claim/entity 覆盖错误。**

**分类：D（其他）** —— v2 验收时"15 套件"未覆盖 scripts/ 下的端到端回归（兼有 A 的遗漏要素）；非 C（无真实覆盖错误）；修复路径采用 B 类授权（"修正测试/基线，使其准确反映已经冻结的合法状态"）。

**修复（仅改回归脚本检查 #3，未触碰任何冻结代码/数据）：**

- `scripts/final_production_regression.py` 的 claim覆盖 检查改为**大小写不敏感覆盖校验**（实体列表仍由冻结 8G 函数生成；数字检查保持严格逐字）；
- 冻结链的逐字指标（14/15、28/29）**并列打印可见**，差异说明写入输出（不隐藏、不删除检查、不降标准）；
- 生产链 19 个冻结文件 SHA256 全部未变（修复后再验）。

## 八、修复后全量验证（7 项，全部 PASS）

| # | 验证项 | 结果 |
|---|---|---|
| 1 | 2.x 全套回归（13 冻结套件 + 端到端 final_production_regression） | **PASS**（端到端 ALL PASS，逐字指标差异以备注可见） |
| 2 | Creator Style v2 acceptance（style_v2_ab + v2_script_acceptance） | **PASS**（exit 0 / exit 0） |
| 3 | Truth/Evidence regression（evidence_regression 等 13 套件内） | **PASS** |
| 4 | Stage 3.1 G1–G15 | **PASS**（fails=0） |
| 5 | Stage 3.1 三套测试（rights 69/69、intent 106/106、package 22/22） | **PASS** |
| 6 | 版权安全测试（G15：电影/B站/YouTube/抖音/小红书/新闻/无证/CC0/CC BY/CC BY-SA/BY-NC/BY-ND/PD/GFDL/ARR） | **PASS** |
| 7 | Provenance 检查（逐素材 18 字段断言 + metadata/materials.json） | **PASS** |

## 九、封包结论

**3.1 READY FOR SEAL。** 3.1 本体（功能/版权安全/Provenance/测试）全部 PASS；pre-existing 2.x 回归问题已定位根因（大小写敏感的冻结检查 × v2 已裁决模板移除，内容无真实覆盖错误），并以"仅修正回归脚本检查口径、生产逻辑零改动"方式修复；7 项验证全绿。**不自行宣布 SEALED，等待人工最终裁决。不进入 3.2。**
