# Run05 ASR 客观复检 + 英文词读法修复报告

- 目的：不听音也能客观判断配音质量（吞字/错读/数字读法），并核查英文/缩写词的实际读法。
- 结论：**中文朗读质量良好**（平均 CER 6.9%、相似度中位 0.967、数字读数 7/7 全对）；**发现并修复了一个真实缺陷**——含英文词的 25 拍里，非词典英文词被逐字母拼读；修完英文变好、全片还**缩短了 27 秒**。
- 新 master：`exec/RUN05_PROD_GSVL/final_long_RUN05_PROD_GSVL.mp4`，**586.85s（9:46.9）**，sha16 `eac47eec7e60265a`。

---

## 1. 复检方法

- 工具：整合包自带 **FunASR paraformer-large（中文）+ FNDM VAD + 标点模型**（revision v2.0.4，包内已带模型，无需下载）。
- 输入：全片 101 个 beat wav（32 kHz 单声道）。
- 比对（`output/run05/asr_compare.py`）：
  - 词级：去标点空白、只保留汉字与拉丁字母，**数字统一替换为占位符**（避免"32"与"三十二"的形式差异污染结论），用 `difflib` 给出 替换/删除/插入 明细（删除≈吞字，插入≈重复）。
  - 数字专项：把原文数字按「数值读法」（32→三十二、1500→一千五百）与「逐年读法」（2022→二零二二）两种中文写法去转写里找。
  - 拉丁词专项：列出全部含拉丁词的拍与其**原始转写文本**。

## 2. 中文部分：良好（剩余差异主要是 ASR 自身的同音误听）

| 指标 | 数值 |
|---|---|
| 平均 CER | **6.9%** |
| 相似度中位 | **0.967** |
| 数字读数 | **7/7 全部正确**（三十二、一千五百、二零二二、二零二五…） |

典型差异均为 ASR 同音误听（**不是**配音错误）：桐人→同仁堂、硬脑膜外→硬朗膜外、轮椅→文艺、机器狗→机器孔、振动→震动、光→空。

## 3. 发现的缺陷：非词典英文词被逐字母拼读

**根因是我脚本里的配置 bug**：`scripts/gsv_run.py` 里用
`next(k for k,v in dict_language.items() if v=="all_zh")` **写死了「中文 = all_zh（全部按中文识别）」**，
`--text-lang` 参数被忽略。GPT-SoVITS 为"中文夹英文"设计的档位是**「中英混合」**（值 `zh`）。

后果（ASR 证据）：

| 拍 | 原文 | all_zh（旧） | 中英混合（新） |
|---|---|---|---|
| S16-B02 | Neuralink / Telepathy | `younmy, you are AAODPA七a choice` | **`neural link teleathy`** |
| S01-B01 | NerveGear | `NERB` | **`nerva`**（且时长 14.02→9.06s） |
| S29-B03 | FullDive | `HUL` | **`full life`** |
| S19-B01 | Blindsight | `Bio INDSIGAHH` | **`Blinds…`** |
| S27-B02 | AI | `Hey,哎哎`（拼字母） | **`AI`** |
| S30B-B02 | VR | `b耳光` | **`VR光画面`** |

机制：中英混合前端会把 `FullDive` 规范成 **`Full Dive`**（补空格），英文 G2P 才看到两个词典词；all_zh 下未知词退化为逐字母朗读。

## 4. 逐拍择优（不能一刀切）

中英混合并非全面更优——部分拍因英文走英文前端而**时长暴涨**（S24-B03 16.42s vs 预期 6.14s、S25-B02 13.62s、S30B-B02 11.90s、S21B-B01 11.74s、S25B-B02 11.94s），ASR 转写也被截断。

因此按客观分数逐拍择优（`output/run05/pick_best_langfix.py`）：

```
score = CER(ASR, 原文) + 0.5 × max(0, |时长−预期|/预期 − 0.35)
```

- 25 拍中 **10 拍换用中英混合**（S01-B01 / S16-B02 / S17-B01 / S19-B01 / S23-B02 / S24-B02 / S25B-B01 / S26-B02 / S27-B02 / S29-B03）
- **1 拍按证据覆盖**：S27-B04（同一个词 `FullDive`，混合版胜出；旧版仅因 "FULODIE" 与 "fulldive" 编辑距离近而被分数误判）→ 合计 **11 拍**换用
- 其余 14 拍保留 all_zh 版本（多为缩写，本来就按字母念；且混合版会拖长时长）

**连带收益**：全片总长 **613.78s → 586.74s**（+16.7% → **+11.6%**）—— 逐字母拼读本身就在拖长音频。

## 5. 重渲染结果（RUN05_PROD_GSVL）

| 项 | 新（GSVL） | 基准（JOINT，旧配音） |
|---|---|---|
| master | `exec/RUN05_PROD_GSVL/final_long_RUN05_PROD_GSVL.mp4` | `exec/RUN05_PROD_JOINT/…` |
| 时长 | **586.85s（9:46.9）** | 526.12s（8:46.1）→ **+60.72s / +11.5%** |
| 大小 / sha16 | 33.8 MB / **`eac47eec7e60265a`** | 30.8 MB / `47177bf96bb3bc5e` |
| master − 音频合计 | **+0.108s** | +0.15s |
| 字幕 / 黑帧 | 101/101（100%）/ 0 | — |

**前置校验 14/14 PASS**（清单相对 prod_joint 仅 5 个键变化）；**冻结决策逐项复现、与旧渲染零差异**：corresponding 86、域一致 78（≥60）、NO_EXPECTATION 8、VIZ 结构卡 2、HN 12.9%、命名空间泄漏 0、patterns 全 0、`render_mode=PRODUCTION_READY`、`g10_acceptance_ok=true`。

## 6. 仍需人工确认

1. **英文/缩写词听感**：`output/run05/LATIN_check.wav`（25 拍，取最终选定版本，184.3s）。重点听：
   - 真词：S01-B01 NerveGear / S16-B02 Neuralink+Telepathy / S19-B01 Blindsight / S27-B04+S29-B03 FullDive
   - 缩写：AI / VR / SAO / NPC / NEO / BCI / MR / ACE（中文里按字母念属正常，但需确认不是念成怪音）
2. **保留 all_zh 的 14 拍**里，S24-B03（ACE/NPC）、S25-B02（NPC）的 ASR 转写偏乱，建议重点听；若不可接受可单独再试其它前端档位（如多语种混合）或改文本。
3. 中文 ASR 判英文本身不可靠 —— 上表是**相对比较**证据，最终以人耳为准。

## 7. 产出

| 文件 | 说明 |
|---|---|
| `output/run05/LATIN_check.wav` / `.txt` | 英文词专用试听文件（25 拍） |
| `output/run05/asr_qc.json` | 全片 ASR 复检逐拍明细（原文/转写/CER/删除插入/数字/拉丁词） |
| `output/run05/langfix_pick_log.json` | 逐拍择优记录（分数与决定） |
| `output/run05/latin_beats.txt` | 含拉丁字母的 25 拍清单 |
| `output/run05/gsv_render_preflight_gsvL.json` / `_result_gsvL.json` / `_verify_gsvL.json` | 本次渲染的校验、结果与独立验证 |
| `output/run05/run05_manifest_prod_gsvL.json` | 本次清单（授权记录 + 新 tts_index 钉） |
| `scripts/gsv_run.py`（已修） | 新增 `--text-lang-val/--prompt-lang-val`，不再写死 all_zh |
| `output/run05/asr_compare.py`、`pick_best_langfix.py`、`build_gsv_index.py`、`gsv_render.py`、`gsv_render_verify.py` | 可复现脚本链 |

## 8. 补修：字幕源缺陷（用户报告「我和字幕是各说各的」）

### 8.1 症状与根因

用户听 GSVL master 后报告：**配音与字幕内容不一致**。

根因（读 `orchestrator_core.py` 得到）：**字幕文本不是取自 TTS 索引，而是取自渲染计划**：

```
orchestrator_core.py:889  narr_map = {shot_id-beat_id: s['narration'] for s in plan['shots']}
                     :411  clip_specs[].narration = narr_map[beat]
                     :646  字幕 cue 文本 = x['narration']
                     :607  空白卡文字同样来自该 narration
```

`plan` = `output/prod01/prod01_plan.json`（frozen shared narrative beats，run03 时期旧稿）。
上一轮我只换了 TTS 音频（v1.3），**没有换 plan 的文本** → 音频说 v1.3、字幕说旧稿。

**量化证据**（`output/run05/check_subtitle_audio_match.py`，比对渲染实际写出的 `parts/part*.srt` 与 v1.3 文本）：

| master | 字幕文本 == 配音文本 | cue 时长/起始 == 音频 |
|---|---|---|
| RUN05_PROD_GSVL（上一版） | **1 / 101** | 101 / 101 |
| **RUN05_PROD_GSV13（修复后）** | **101 / 101** | **101 / 101** |

### 8.2 修复方式

新造 `output/run05/prod01_plan_v13.json`：**只把 `shots[].narration` 换成 narration_final v1.3**，其余字段逐字不变（`output/run05/build_plan_v13.py`）。

- 101 个 shot，key 全部匹配（`shot_id-beat_id`），无重复、无缺失；
- **100 拍文本被替换**（另 1 拍本就相同）；
- 并把新 plan **钉进新清单** `run05_manifest_prod_gsv13.json`（`shared_input_registry.plan`，含 sha256）。

### 8.3 安全性证明（shadow 先行，未改任何决策）

关键不变量：`family_ctx_from_manifest` 只用 narration 做锚词匹配
（`anchored = {tok for tok, terms in amap.items() if any(t in text for t in terms)}`，
`text = narration + ECT.evidence_core`）。

- **锚点不变量**：旧 plan 与 v1.3 plan 下 `anchored_of` **完全一致**（差异拍 = 空）→ family guard 行为不变；
- **shadow 对照**（exec `RUN05_SHADOW_PLANV13B`，未授权、不写 master）与上一版生产渲染逐文件比对：

| 产物 | 结果 |
|---|---|
| `assignment_policy.json` | **逐字节相同** |
| `gate_decisions.json` | **逐字节相同** |
| `namespace_decisions.json` | **逐字节相同** |
| `crop_recheck.json` | **逐字节相同** |
| `prerender_gate.json` | **逐字节相同** |
| `render_plan.json` | 非 narration 字段全同；**narration 恰好 100 拍不同** |

样例（S01-B01）：shadow=v1.3「2022年,桐人躺进游戏舱,戴上NerveGear,闭上眼——下一秒,他站在艾恩葛朗特。」vs 旧生产「2022年,桐人戴上NerveGear,躺进游戏舱,意识沉入艾恩葛朗特。」

### 8.4 最终 master

| 项 | RUN05_PROD_GSV13（最终） |
|---|---|
| 路径 | `exec/RUN05_PROD_GSV13/final_long_RUN05_PROD_GSV13.mp4` |
| 时长 / 大小 | **586.85s（9:46.9）** / 34.3 MB |
| sha16 | **`4f8e28db45b6399a`** |
| A/V 一致性 | master 586.85s − 音频 586.74s = **+0.108s** |
| 字幕 / 黑帧 | 101/101（100%）/ 0 |
| 前置校验 | **15/15 PASS**（新增第 15 项：plan 覆盖的字幕文本必须等于 v1.3） |
| 冻结决策 | 逐项复现（86 / 78 / 8 / VIZ 2 / HN 12.9% / 泄漏 0 / patterns 全 0 / PRODUCTION_READY） |

**master 谱系**（四版并存，均未被覆盖）：

| 版本 | 时长 | 音频 | 字幕 |
|---|---|---|---|
| RUN05_PROD_JOINT | 526.12s | run03 Edge（旧稿） | 旧稿 |
| RUN05_PROD_GSV | 613.89s | GSV v2（v1.3） | 旧稿 ← 与配音不符 |
| RUN05_PROD_GSVL | 586.85s | GSV v2 + 英文词修复 | 旧稿 ← 与配音不符 |
| **RUN05_PROD_GSV13** | **586.85s** | GSV v2 + 英文词修复 | **v1.3 ✔ 与配音一致** |

## 9. 边界

未改动素材池、检索、CV2、G10、VIZ 白名单、复用策略与验收阈值；`production_viz_rollout` 仍为 NOT AUTHORIZED；旁白文本仍为 **v1.3**（本次只改**读法/前端档位**，未改一个字）；三条 master（JOINT / GSV / GSVL）并存可对比。
