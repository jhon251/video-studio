# Run05 生产验收报告：旁白 v1.6.1 全链重制（RUN05_PROD_GSV161）

> 本报告全部数字直接取自产物 JSON（preflight/result/qa_summary/subtitle_audio_match/asr_qc/index_build/pick/verify），未手工抄写。

## 0. 结论

- 文案真源：`output/run05/narration_final_v16.json`（v1.6.1，sha256 前16位 `bc2624f9a251f4b4`）
- 新 master：`C:\mp4agent\video-studio\output\run05\exec\RUN05_PROD_GSV161\final_long_RUN05_PROD_GSV161.mp4`
- 时长：**593.600 s**（9.89 分钟）｜ 大小 **34.6 MB** ｜ **sha256 `03bf8cb44b1209eb5a540683d9957435831b3628e89a88f432331c04790d7d23`**
- 字幕/配音/真源同源：**101/101**（`subtitle_audio_match`）｜ ASR 平均 CER **4.2%**
- 综合判定：**PASS**

## 1. 文案真源与变更范围

| 项 | 值 |
|---|---|
| 真源文件 | `output/run05/narration_final_v16.json` |
| sha256 前16位 | `bc2624f9a251f4b4` |
| 拍数 | 101（不增不减不合并） |
| 相对 v1.3 改动拍 | 11 拍（5 处 v1.4 内容修正 + 6 处 v1.5 语言润色，S30B-B02 重叠） |
| 冻结拍 | S16-B02 / S17-B02 与 v1.3 逐字节相同 |

## 2. 重建 plan / 时间轴

- 由 `output/prod01/prod01_plan.json` 仅替换 `shots[].narration` → `prod01_plan_v16.json`
- shots 数 **101**；未匹配 shot **0**；v1.6.1 未被覆盖拍 **0**；重复 key 无
- 与 `prod01_plan_v13.json` 的 narration 差异：**11 拍**（S11-B02, S12-B01, S14-B02, S19-B03, S20-B02, S20-B03, S22-B01, S25B-B01, S29-B01, S30B-B02, S33B-B02）
- family anchor 不变量：anchored_of 差异 = 无（完全一致）

时间轴不是独立文件：orchestrator 由 `tts[beat]['dur']` 累加出每拍 start/end、字幕 cue 窗口与画面片长，故「重建时间轴」= 换索引 + 同一套冻结决策重跑。

| 索引指标 | 值 |
|---|---|
| 拍数 | 101/101 |
| 采样率 / 声道 | [32000] / [1] |
| 单拍时长 | 1.78–14.34s（中位 5.70s） |
| 新总时长 | **593.500 s** |
| 相对 v1.3 音频 | +6.760 s |
| 相对 run03 Edge 音频 | +67.530 s |

## 3. TTS 重配音（11 拍重合成 / 90 拍复用）

复用判据（可审计）：**文本与 v1.3 逐字节相同** 的 90 拍沿用既有 QC 通过音频；文本变化的 11 拍一律重新合成，绝不复用旧音频。索引构建脚本对两侧都做哈希断言（复用件哈希一致 / 改文件哈希不同）。

| 拍 | 采用 take | 时长 | ASR CER | 最长内部停顿 | 文案 |
|---|---|---|---|---|---|
| S11-B02 | C | 4.90s | 0.0% | 0.42s | 抓住虚拟物体的时候,你能感到手套施加的阻力。 |
| S12-B01 | B | 6.54s | 0.0% | 0.62s | 实验室里还有一条路:空中超声触觉,不碰皮肤,也能给你触感。 |
| S14-B02 | A | 5.06s | 0.0% | 0.00s | 让人沉浸进去,还得保证身体安全——到今天没有标准答案。 |
| S19-B03 | C | 7.26s | 12.0% | 0.00s | 往大脑写光、声、触、平衡——这要同时和数量庞大的神经通路对话。 |
| S20-B02 | B | 8.10s | 3.3% | 0.90s | 而你随便看一眼画面,感官在另一层面上接收的信息量,是它的百万倍以上。 |
| S20-B03 | C | 7.70s | 0.0% | 0.54s | 要把完整的感官体验写进大脑,量级上的差距就摆在那里——没有已知的捷径。 |
| S22-B01 | C | 5.98s | 0.0% | 0.46s | 植入电极要穿过颅骨,长期安全这件事,到现在都还没有数据。 |
| S25B-B01 | A | 8.78s | 6.7% | 0.64s | 对话只是第一步。难的是让它们保持一致:NPC 不能今天救人,明天屠城。 |
| S29-B01 | C | 7.62s | 0.0% | 0.54s | 按现有路线推,第二层里更完整的身体追踪和局部触觉,十年内会先进家庭。 |
| S30B-B02 | C | 5.94s | 0.0% | 0.70s | 无线 VR 也一样,真正难的是把这种延迟稳定压下去。 |
| S33B-B02 | A | 4.14s | 5.9% | 0.00s | 它开始变成伦理和监管问题:谁有权决定。 |

择优评分：`100*CER + max_gap + n_gap80 + |dur-expect|`；硬否决：`CER>0.35 / max_gap>=1.2 / dur>2.2*expect / dur<0.45*expect`。全部 11 拍均有可用 take，0 拍被全部否决。

> 评分口径在首轮择优后做过一次修正：最初用 `20×CER + 3×停顿`，会把逗号处的自然停顿罚得比真实错读还重（曾让 CER 0% 的 take 输给 CER 3–4% 的 take）。改为 `100×CER + 1×停顿` 后，9/11 拍选中 CER ≤6.7%（7 拍为 0%）。修正过程与两次结果都留在 `v161_logs/pick_report.json`。

- 合成调用：6 次（3 个 take × [9 拍 all_zh + 2 拍中英混合]），总耗时 8.6 分钟
- 参数与 v1.3 全片一致：GPT-SoVITS **v2**（s1bert25hz-5kh / s2G2333k）、sample_steps=32、top_k=20、top_p=0.6、temperature=0.6、speed=1.0、参考音 `ref_win3.wav`、响度 match run03

## 4. 渲染与 preflight（24 项）

- `0_delta_keys_expected_only`：PASS — ['authorization', 'run_id', 'shared_input_registry', 'status', 'type']
- `1_authorization_interlock`：PASS — flag=True + sign-off 完整（by/at/ref）
- `2_viz_rollout_not_authorized`：PASS — NOT AUTHORIZED
- `3_registry_plan`：PASS — output/run05/prod01_plan_v16.json
- `3_registry_retrieval_index`：PASS — output/run05/retrieval_index_joint.json
- `3_registry_cv2_results`：PASS — output/run05/cv2_results_joint.json
- `3_registry_tts_index`：PASS — output/run05/tts_gsv_v161/tts_index_gsv.json
- `3_registry_font`：PASS — output/production_002/build_v2/msyh.ttc
- `3_registry_narration_source`：PASS — output/run05/narration_final_v16.json
- `4_exec_id_free`：PASS — RUN05_PROD_GSV161
- `5_g10_anchored`：PASS — signals=753 ect=101
- `6_family_map_unchanged`：PASS — {'ultrasound': ['超声']}
- `7_viz_whitelist_exactly_two`：PASS — {'S02-B01': 'viz_five_layer_framework', 'S33B-B01': 'viz_five_layer_timeline'}
- `8_acceptance_threshold_unchanged`：PASS 
- `9_expected_beats_101`：PASS — 101
- `10_tts_beat_set_identical`：PASS — new=101 old=101
- `11_all_wavs_exist`：PASS — missing=[]
- `12_dur_matches_audio`：PASS — mismatch=[]
- `13_uniform_format`：PASS — sr=[32000] ch=[1]
- `14_total_s_consistent`：PASS — sum=593.5 total_s=593.5
- `15_plan_subtitle_text_equals_v161`：PASS — 101 shots, mismatch=[]
- `16_tts_index_text_equals_v161`：PASS — mismatch=[]
- `17_frozen_beats_byte_identical`：PASS — S16-B02/S17-B02 与 v1.3 逐字节相同
- `18_narration_source_pinned`：PASS — narration_final_v16.json sha256=bc2624f9a251f4b4

manifest delta（相对 prod_joint）：['authorization', 'run_id', 'shared_input_registry', 'status', 'type']

## 5. 工程 QA（production_qa）


## 6. 文案 / 字幕 / 配音对齐 QA

- SRT cue 数 **101** ｜ canonical 拍数 **101**
- 字幕文本 vs v1.6.1 真源逐条一致：**101/101**
- cue 时长/起始 vs 音频实测一致：**101/101**（SRT 每个 part 时间轴各自从 0 起，脚本按 part 重置游标后逐拍校验）
- 全局音频合计 **593.500s**（= 渲染时间轴 593.500s）；示例末段 part 内累计 22.620s
- 判定：**PASS**

成片音轨 ASR 客观复检（master 按时间轴切窗后转写）：

- 覆盖 **101** 拍 ｜ 平均 CER **4.2%** ｜ CER>15% 的拍 **5**
- 数字读数错误 **0** 处
- **同一口径对比上一版成片**：GSV13（v1.3）平均 CER **4.3%** / CER>15% 的拍 7 → GSV161（v1.6.1）平均 CER **4.2%** / CER>15% 的拍 5
- 11 个改文拍（确认成片说的是新文案）：

| 拍 | CER | 真源 | 转写 |
|---|---|---|---|
| S11-B02 | 0.0% | 抓住虚拟物体的时候,你能感到手套施加的阻力。 | 抓住虚拟物体的时候，你能感到手套施加的阻力。 |
| S12-B01 | 0.0% | 实验室里还有一条路:空中超声触觉,不碰皮肤,也能给你触感。 | 实验室里还有一条路，空中超声触觉不碰，皮肤也能给你触感。 |
| S14-B02 | 0.0% | 让人沉浸进去,还得保证身体安全——到今天没有标准答案。 | 让人沉浸进去，还得保证身体安全。到今天没有标准答案。 |
| S19-B03 | 12.0% | 往大脑写光、声、触、平衡——这要同时和数量庞大的神经通路对话。 | 往大脑血光牲畜平衡，这要同时和数量庞大的神经通路对话。 |
| S20-B02 | 3.3% | 而你随便看一眼画面,感官在另一层面上接收的信息量,是它的百万倍以上。 | 而你随便看一眼画面，感官在另一层面上，接收的信息量是他的百万倍以上。 |
| S20-B03 | 0.0% | 要把完整的感官体验写进大脑,量级上的差距就摆在那里——没有已知的捷径。 | 要把完整的感官体验写进大脑量级上的差距就摆在那里，没有已知的捷径。 |
| S22-B01 | 4.0% | 植入电极要穿过颅骨,长期安全这件事,到现在都还没有数据。 | 直入电极要穿过颅骨，长期安全这件事到现在都还没有数据。 |
| S25B-B01 | 6.7% | 对话只是第一步。难的是让它们保持一致:NPC 不能今天救人,明天屠城。 | 对话只是第一步，难的是让他们保持一致。 Pc不能今天救人，明天屠城。 |
| S29-B01 | 0.0% | 按现有路线推,第二层里更完整的身体追踪和局部触觉,十年内会先进家庭。 | 按现有路线推第二层里更完整的身体追踪和局部触觉，十年内会先进家庭。 |
| S30B-B02 | 0.0% | 无线 VR 也一样,真正难的是把这种延迟稳定压下去。 | 无线VR也一样，真正难的是把这种延迟稳定压下去。 |
| S33B-B02 | 5.9% | 它开始变成伦理和监管问题:谁有权决定。 | 他开始变成伦理和监管问题，谁有权决定？ |

## 7. 复用 / 顺序 / G10 硬约束回归

| 指标 | 本次 | RUN05_PROD_JOINT |
|---|---|---|
| corresponding | 86 | 86 |
| domain_consistent_corresponding | 78 | 78 |
| no_expectation_displays | 8 | 8 |
| viz_structural_displays | 2 | 2 |
| hn_fb_rate_pct | 12.9 | 12.9 |
| ns_leakage | 0 | 0 |
| g10_acceptance_ok | True | True |
| render_mode | PRODUCTION_READY | PRODUCTION_READY |
| canonical_order | True | True（JOINT 同） |
| order_invariant（render==canonical） | True | True（JOINT 同） |

- 决策产物与 RUN05_PROD_GSV13 逐字节相同：3 个（gate_decisions.json, ledger.json, namespace_decisions.json）
- 存在差异：9 个（assignment_policy.json, crop_recheck.json, ledger_rows.json, preflight_v2.json, prerender_gate.json, qa_summary.json, render_log.json, render_plan.json, shot_provenance.json）——含路径/文案/时间轴字段；差异性质见第 10 节证据链
- 与上一版 v1.3 生产（GSV13）对比：

| 指标 | GSV13 | GSV161 |
|---|---|---|
| corresponding | 86 | 86 |
| domain_consistent_corresponding | 78 | 78 |
| hn_fb_rate_pct | 12.9 | 12.9 |
| ns_leakage | 0 | 0 |
| g10_acceptance_ok | True | True |
| master_sha16 | 4f8e28db45b6399a | 03bf8cb44b1209eb |
| master_duration_s | 586.85 | 593.6 |

### 7.1 成品 master 登记表（全部保留，互不覆盖）

| master | 类型 | 时长 | sha16 |
|---|---|---|---|
| RUN05_PROD_JOINT | 旧音频 + 旧字幕 | 526.12s | `47177bf96bb3bc5e` |
| RUN05_PROD_GSV | 新音频 + 旧字幕 | 613.89s | `fa834f883ef9694c` |
| RUN05_PROD_GSVL | 语言修正音频 + 旧字幕 | 586.85s | `eac47eec7e60265a` |
| RUN05_PROD_GSV13 | v1.3 音频 + v1.3 字幕 | 586.85s | `4f8e28db45b6399a` |
| **RUN05_PROD_GSV161（本次）** | **v1.6.1 音频 + v1.6.1 字幕** | **593.60s** | **`03bf8cb44b1209eb`** |
| RUN05_PROD_GSV161SHADOW | 影子（无 master，仅决策链） | — | — |
| RUN05_PROD_GSVCTRL | 控制实验（v1.3 输入，验证可复现） | — | — |

## 8. 画面帧证据

改动拍中点抽帧（新版 vs 上一版对照），已核对字幕文本确为 v1.6.1：

- `S11-B02` @ 197.99s → `exec/RUN05_PROD_GSV161/v161_frames/S11-B02_v161.png`（对照 `S11-B02_gsv13.png`）
- `S12-B01` @ 208.21s → `exec/RUN05_PROD_GSV161/v161_frames/S12-B01_v161.png`（对照 `S12-B01_gsv13.png`）
- `S14-B02` @ 234.85s → `exec/RUN05_PROD_GSV161/v161_frames/S14-B02_v161.png`（对照 `S14-B02_gsv13.png`）
- `S19-B03` @ 332.49s → `exec/RUN05_PROD_GSV161/v161_frames/S19-B03_v161.png`（对照 `S19-B03_gsv13.png`）
- `S20-B02` @ 346.07s → `exec/RUN05_PROD_GSV161/v161_frames/S20-B02_v161.png`（对照 `S20-B02_gsv13.png`）
- `S20-B03` @ 353.97s → `exec/RUN05_PROD_GSV161/v161_frames/S20-B03_v161.png`（对照 `S20-B03_gsv13.png`）
- `S22-B01` @ 378.19s → `exec/RUN05_PROD_GSV161/v161_frames/S22-B01_v161.png`（对照 `S22-B01_gsv13.png`）
- `S25B-B01` @ 428.49s → `exec/RUN05_PROD_GSV161/v161_frames/S25B-B01_v161.png`（对照 `S25B-B01_gsv13.png`）
- `S29-B01` @ 482.63s → `exec/RUN05_PROD_GSV161/v161_frames/S29-B01_v161.png`（对照 `S29-B01_gsv13.png`）
- `S30B-B02` @ 542.77s → `exec/RUN05_PROD_GSV161/v161_frames/S30B-B02_v161.png`（对照 `S30B-B02_gsv13.png`）
- `S33B-B02` @ 585.05s → `exec/RUN05_PROD_GSV161/v161_frames/S33B-B02_v161.png`（对照 `S33B-B02_gsv13.png`）

## 9. 音频工程质检（101 拍）

- 拍数 **101** ｜ 采样率 32000 ｜ 削波拍数 **0** ｜ 峰值最大 **0.461**
- 响度 RMS 0.0427–0.0725 ｜ 标准差 **0.0060**（与 v1.3 同值，无逐拍响度跳变）
- 内部停顿合计 **136** 个 ｜ ≥0.80s 的 **13** 个 ｜ 中位字速 **4.49 字/秒**

### 9.1 11 个改文拍：旧音频 vs 新音频 同栈 ASR 对照（防退化）

- 平均 CER：**旧 2.9% → 新 2.5%**（Δ-0.4%）｜明显变差(>+2pp)的拍：['S20-B02', 'S25B-B01']

| 拍 | 旧 CER | 新 CER | Δ | 采用 take |
|---|---|---|---|---|
| S11-B02 | 0.0% | 0.0% | +0.0% | C |
| S12-B01 | 0.0% | 0.0% | +0.0% | B |
| S14-B02 | 0.0% | 0.0% | +0.0% | A |
| S19-B03 | 13.0% | 12.0% | -1.0% | C |
| S20-B02 | 0.0% | 3.3% | +3.3% | B |
| S20-B03 | 0.0% | 0.0% | +0.0% | C |
| S22-B01 | 0.0% | 0.0% | +0.0% | C |
| S25B-B01 | 3.6% | 6.7% | +3.1% | A |
| S29-B01 | 0.0% | 0.0% | +0.0% | C |
| S30B-B02 | 10.5% | 0.0% | -10.5% | C |
| S33B-B02 | 5.0% | 5.9% | +0.9% | A |

> 说明：两处 +3pp 级差异均为 ASR 同音字（它/他 tā、它们/他们）与拉丁词（NPC→Pc），非发音缺陷；S19-B03 的「写光、声、触、平衡」在旧新两侧转写同样为「血光牲畜平衡」（13%→12%），属既有念法特性而非本次引入。

## 10. 复用/顺序/G10 硬约束回归的证据链

### 10.1 控制实验（关键）

用**完全未变的 v1.3 plan + v1.3 索引**跑影子（不编码），检查决策引擎是否复现上一版生产：

- 逐字节复现的文件（7/7）：gate_decisions.json, namespace_decisions.json, prerender_gate.json, crop_recheck.json, assignment_policy.json, ledger.json, ledger_rows.json
- 仅 exec 路径承载文件不同：render_plan.json, shot_provenance.json（exec 目录名不同所致）
⇒ 引擎与规则具确定性，影子口径与正式生产可比。

### 10.2 规则未改

- `fixes` / `g10` / `hard_gates` / `baseline_run03` / `expected_beats` / `allowed_asset_namespaces` / `blocked_markers` / `cv2_convention` 与 prod_joint **逐字节相同**
- manifest delta 仅：['authorization', 'run_id', 'shared_input_registry', 'status', 'type']

### 10.3 显示位差异的真实性质（必须如实说明）

- 101 个显示位中 **94 个逐位相同**，**7 个换了素材**：其中 5 位（下标 75/77/95/97/99）是**同一素材集合的轮换**，2 位（下标 63/100）替换了 2 个素材（新增 `['ss2_S16-B03_11', 'ss3_S27-B04_12']`，移除 `['ss2_S16-B02_2', 'r3_S25B-B02_3']`）
- 这些显示位的时间位移仅 +0.04s … +7.04s
- 原因：复用策略的 `min_display_gap_s=60` 与「近期证据惩罚」都以**累计时间轴为输入**；时间轴重建后边界处的合格集合发生变化。**这不是规则放宽、也不是视觉策略重设计。**
- 复用间隔不变量（同素材相邻两次上屏 ≥60s）：三次运行（GSV13 / 控制 / v1.6.1）**均 0 违规**，最小间隔 121.52s

### 10.4 聚合指标三版一致

| 指标 | JOINT | GSV13 | v1.6.1 |
|---|---|---|---|
| corresponding | 86 | 86 | 86 |
| domain_consistent_corresponding | 78 | 78 | 78 |
| no_expectation_displays | 8 | 8 | 8 |
| viz_structural_displays | 2 | 2 | 2 |
| hn_fb_rate_pct | 12.9 | 12.9 | 12.9 |
| ns_leakage | 0 | 0 | 0 |

## 11. 完整性与边界

- 验证失败项：无
- 未改动：素材池、检索索引、CV2 判决、G10 本体/ECT/signals 与阈值、VIZ 授权范围（仍为 `NOT AUTHORIZED`，白名单仍为 S02-B01 / S33B-B01 两张卡）、编排与复用规则。
- 未重新设计视觉策略、未重新优化画面；画面差异仅来自时间轴变化引起的片长/切点变化。
- 既有 master 未覆盖：RUN05_PROD_JOINT / RUN05_PROD_GSV / RUN05_PROD_GSVL / RUN05_PROD_GSV13 全部保留。
