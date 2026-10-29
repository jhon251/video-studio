# Run05 GSV 重配音：时间轴重建 + 正式重渲染报告

- 性质：**换配音 + 重建时间轴 + 重渲染**。素材池、检索、CV2、G10 判定、VIZ 白名单、复用策略、验收阈值**全部沿用**，未做任何放宽。
- 授权：用户（项目负责人）「接受新时长，进入时间轴重建」（2026-09-13），已写入新 manifest 的 `authorization` 并计入 `auth_ok` 联锁。
- 结论：**ORCHESTRATED_PRODUCTION_OK**；冻结决策逐项复现、与旧渲染零差异；A/V 一致性 +0.108s。

---

## 1. 关键机制发现（决定了"时间轴重建"怎么做）

1. **时间轴不是独立文件**：`orchestrator_core.run()` 里
   `b.start = t; b.end = t + tts[beat]['dur']; t += dur`（845–851 行），
   字幕 cue 窗口（643–647 行）与画面片长（`ffmpeg -t {dur}`，618 行）都由同一个 `dur` 派生。
   ⇒ **重建时间轴 = 换掉 `tts_index` 的 `dur/wav`，用同一套冻结决策重跑**。
2. **`tts_index` 在整条渲染链里只被一个地方消费**（`orchestrator_core.py:814`），
   并作为 `shared_input_registry` 的一员被 **sha256 钉死**（`preflight_v2` 逐项校验）。
   `run(inputs_override=...)` 会同时替换路径与哈希，`manifest_override` 可直接注入新清单。
3. **索引里的 `wav` 是绝对路径**（run03 即如此），且会被直接写入 ffmpeg concat 清单（634–638 行）
   ⇒ 必须与音频实际时长一致，否则每拍累积 A/V 漂移。
4. **同一 concat 链内格式必须统一**：101 个 wav 全为 32 kHz / 单声道，故 5 个 part 的音频拼接安全。
5. 授权联锁：`auth_ok()` 要求 `production_run_authorized is True` **且** authorization 记录三项（by/at/ref）非空 —— 只改 flag 不能绕过。

## 2. 索引转换（run03 同构）

`output/run05/build_gsv_index.py` → `output/run05/tts_gsv_v2_full/tts_index_gsv.json`

| 项 | 值 |
|---|---|
| 拍数 | 101（与 run03 beat 集合**完全一致**，diff=∅） |
| 采样率 / 声道 | 32000 Hz / 1ch（统一） |
| 总时长 | **613.780 s**（run03 525.97 s → **+87.81 s / +16.7%**） |
| 单拍时长 | 1.78–14.34 s（中位 5.90 s） |
| `dur` 精度 | **3 位小数**（run03 为 2 位；提高精度以压低逐拍舍入导致的 A/V 漂移） |
| `wav` | 绝对路径（例：`C:\mp4agent\video-studio\output\run05\tts_gsv_v2_full\S01-B01.wav`） |
| VERDICT | PASS |

## 3. 前置校验（`output/run05/gsv_render.py`，14 项全 PASS）

清单相对 `run05_manifest_prod_joint.json` 的**变更键仅 5 个**：`run_id / type / status / authorization / shared_input_registry`（校验项 `0_delta_keys_expected_only`）。
其余：授权联锁、VIZ rollout 仍 NOT AUTHORIZED、5 项 registry 哈希（plan / retrieval_index / cv2_results / **tts_index** / font）、G10 锚定（signals=753 / ect=101）、family map 不变、VIZ 白名单恰为两张、验收阈值不变（≥60 / mismatch 0）、expected_beats=101、exec_id 未占用。
TTS 专项：beat 集合一致、101 个 wav 全部存在、**时长与音频实测一致（0 处不符）**、格式统一、`total_s` 自洽。

## 4. 渲染结果

| 项 | 新（GSV） | 旧（JOINT） | 差异 |
|---|---|---|---|
| master | `exec/RUN05_PROD_GSV/final_long_RUN05_PROD_GSV.mp4` | `exec/RUN05_PROD_JOINT/final_long_RUN05_PROD_JOINT.mp4` | — |
| 时长 | **613.89 s（10:13.9）** | 526.12 s（8:46.1） | **+87.76 s / +16.7%** |
| 大小 | 35.34 MB | 30.78 MB | +4.6 MB |
| sha16 | **`fa834f883ef9694c`** | `47177bf96bb3bc5e` | — |
| 视频 | h264 1920×1080 30fps，18402 帧 | 同规格，15775 帧 | 帧数与时长相符 |
| 音频 | AAC **32000 Hz** 单声道 | AAC 24000 Hz 单声道 | 音质提升 |
| master − 索引音频合计 | **+0.108 s** | +0.15 s | A/V 一致性略优 |

**冻结决策逐项复现（与旧渲染零差异）**：corresponding **86**、域一致 CORRESPONDING **78（≥60 通过）**、NO_EXPECTATION 8、VIZ 结构卡 **2**、HN/FB **12.9%**、命名空间泄漏 **0**、patterns（adjacent / gap2_AxA / ABA / ABAB）全 0、`g10_acceptance_ok=True`、`render_mode=PRODUCTION_READY`、canonical_order PASS、family_guard skips=1、borrow_prefer_wide penalized=161。

## 5. 产出

| 文件 | 说明 |
|---|---|
| `output/run05/run05_manifest_prod_gsv.json` | 新清单（授权记录 + 新 tts_index 钉） |
| `output/run05/tts_gsv_v2_full/tts_index_gsv.json` | run03 同构索引（渲染链输入） |
| `output/run05/tts_gsv_v2_full/index_build_report.json` | 索引构建校验 |
| `output/run05/gsv_render_preflight.json` | 14 项前置校验 |
| `output/run05/gsv_render_result.json` | 渲染完整结果 |
| `output/run05/gsv_render_verify.json` | 独立验证（时长/A-V/决策复现） |
| `output/run05/exec/RUN05_PROD_GSV/` | clips 101 / parts 35 / master + 全套 QA 产物 |
| `output/run05/build_gsv_index.py`、`gsv_render.py`、`gsv_render_verify.py` | 可复现脚本 |

## 6. 未决 / 风险

1. **拉丁词读法未验证**：`NerveGear / Neuralink / Telepathy / FullDive / Blindsight` 等由英文前端处理（日志显示为 `N E R V E G E A R` 形式）。需抽听 S01-B01、S16-B02、S17-B01、S18B-B02、S27-B03；若按字母念错，重生成这几拍（每拍 ~10 s）+ 重渲染（~5 min）即可。
2. **剩余 13 拍**仍有 0.8–2.0 s 内部停顿（最长 S16-B01 2.02 s），可能属正常句读。
3. **画面未变**：仍为素材池 + 冻结判定，每拍静帧按新时长延长；若要利用变长后的时间轴做更多运镜/切分，属新的编排改动，需另行授权。
4. **旧 master 未被覆盖**，两条线并存可对比。
5. VIZ rollout 仍 **NOT AUTHORIZED**；未做任何规则/阈值/白名单/映射改动。
