# Run05 配音引擎对比：GPT-SoVITS v2/v3 vs F5-TTS（本机 CPU 实测）

- 目的：验证"换用 MIT 授权的 GPT-SoVITS 能否同时解决**商用授权**与**F5 的吞字/吃尾音/喷麦/口吃/金属感**"。
- 结论：**能解决授权与部分瑕疵，速度取决于版本**；v2 极快（全片约 22 分钟）但相似度基准较低，v3 质量更高但本机 CPU 上极慢（32 步 ≈ 7.1 小时）。
- 状态：三拍试听包已生成，等人工听判后决定是否全片。

---

## 1. 结论速览（本机实测，非外推）

| 引擎 / 配置 | 授权 | 单拍均值 | 全片 98 拍外推 | 官方 zero-shot SIM 基准 | 客观瑕疵 |
|---|---|---|---|---|---|
| **GPT-SoVITS v2**（包内 90M s2） | MIT | **13.5 s** | **≈ 22 分钟** | 0.549 | 无 1.5s 空洞；高频占比 0.01 |
| F5-TTS nfe16（现用） | 权重 CC-BY-NC | 71 s | 1.9 小时 | 未公布（同档） | S12 有 **1.50s 异常空洞**；高频占比 0.04–0.08 |
| GPT-SoVITS v3 @8 步 | MIT | 90 s | 2.5 小时 | 0.702 | 无 1.5s 空洞；高频占比 0.01 |
| F5-TTS nfe32 | 权重 CC-BY-NC | ~156 s | 4.2 小时 | 同上 | 同上 |
| GPT-SoVITS v3 @32 步（官方"音质最佳"） | MIT | 262 s | 7.1 小时 | 0.702 | 同上；官方称步数低会"电" |

> SIM 为官方 wiki 在字节 SeedTTS 中文测试集上的 zero-shot 音色相似度，真人 GT = 0.750。

## 2. 安装与授权（已核实）

- 整合包：`C:\mp4agent\gpt-sovits\GPT-SoVITS-v3lora-20250228\`（**11.71 GB**，6.75 GB 压缩包下载 405 s @16.7 MB/s，7-Zip 解压）
- 自带环境：**Python 3.9.13 + torch 2.0.0+cu118**（`torch.cuda.is_available() = False` → 自动走 CPU，`is_half=False`），**不依赖系统 Python 3.13，也不动 `.venv_tts`**
- 捆绑模型：**v1 / v2 / v3**（`s1bert25hz-2kh`、`gsv-v2final-pretrained/`、`s1v3.ckpt`+`s2Gv3.pth`+BigVGAN 24k），**G2PW 中文前端已就位**（`g2pW.onnx`）
- **不含 v2Pro / v4**：需另下（`v2Pro/s2Gv2ProPlus.pth` 190.9 MB、`sv/pretrained_eres2netv2w24s4ep4.ckpt` 102.5 MB、`gsv-v4-pretrained/s2Gv4.pth` 733.4 MB）；且本包 `process_ckpt.py` 只识别 v1/v2/v3（**无 v2Pro 分支**），官方 README 也称 v2Pro 需"clone the latest codes"
- 许可：仓库 LICENSE = **MIT**（Copyright 2024 RVC-Boss）；HF 权重卡 `License: mit`；BigVGAN 为 NVIDIA，模型卡 `license: mit`；**待自查**：G2PW 许可、v4 自训声码器

## 3. 关键工程发现（踩坑记录，复现必读）

1. **包内 `api_v2.py` 跑不了 v3**：本包的 `GPT_SoVITS/TTS_infer_pack/TTS.py` **只有 v1/v2 分支**（无 v3/v4/v2Pro、无 `sample_steps`）——那是 v2 时代管线；我最初读到的带 `sample_steps` 的 `api_v2.py` 是 GitHub main 分支的新版。
2. **v3 的官方入口是 `GPT_SoVITS/inference_webui.py`**（WebUI 与 `inference_cli.py` 都走它）→ 因此本轮驱动改为**直接 import 它**、不起 HTTP 服务。
3. `change_sovits_weights()` **是生成器函数**，必须 `next(...)` 才会真正执行加载（官方在模块 import 时也是这么调用的）；只调用不迭代 = 什么也没发生。
4. **`sys.path` 必须补两个目录**：`<包根>/GPT_SoVITS`（`from text... / from AR...`）与 `<包根>/GPT_SoVITS/BigVGAN`（`bigvgan.py` 内部 `import activations` 是扁平导入）。官方 `go-webui.bat` 未设 `PYTHONPATH`，整合包内也没有对应启动脚本。
5. **`sample_steps` 是"电音"旋钮**：官方 UI 标签原文「采样步数，如果觉得电，提高试试，如果觉得慢，降低试试」，可选 4/8/16/32，UI 默认 32，而代码默认 8。
6. 耗时结构（v3）：`参考预处理 / T2S(GPT) / 文本前端 / S2(CFM+BigVGAN)` = `1.4 / 2.2 / 6.2 / 232.2`（S12 拍）→ **S2 占 95%+**，这是 v3 慢的根因；v2 的 S2 只有 `1.8 / 3.3 / 0.6 s`。
7. 进度条 `0/1500` 是 **AR 解码的 token 预算**（`max_sec×50`），遇 EOS 即停，与 S2 无关。

## 4. 客观指标（本机实测，3 拍）

**S12-B02（31 字）**——F5 最明显的缺陷在这里消失：

| 配置 | 时长 | 字/秒 | 内部停顿（≥0.25s） | 谱重心 | 4–8k/0.5–4k |
|---|---|---|---|---|---|
| F5 nfe16 | 6.68 | 4.64 | **1 个：2.70s×1.50s** | 957 | 0.08 |
| GSV v2 | 6.86 | 4.52 | 1 个：4.50s×0.52s | 588 | 0.01 |
| GSV v3@8 | 6.76 | 4.59 | 2 个：3.02s×0.26 + 4.04s×0.62 | 576 | 0.01 |
| GSV v3@32 | 6.76 | 4.59 | 2 个：3.02s×0.26 + 4.06s×0.60 | 580 | 0.01 |

**S17-B02（64 字）**：F5 13.23s / 4 停顿共 1.84s；GSV v2 16.14s / 5 停顿 2.54s；GSV v3 14.44s / 4 停顿 1.82s。
**S27-B01（7 字）**：F5 1.39s；GSV v2 1.62s；GSV v3 1.75s。三者均无内部停顿。

读法：**F5 的谱重心与 4–8k 占比明显高于 GPT-SoVITS（0.04–0.08 vs 0.01）**，与其"金属感"主观评价一致；GPT-SoVITS 更暗、更闷一些（v3@32 与 v3@8 指标几乎相同，差别要到听感层面找）。另外 GPT-SoVITS 会正确朗读数字（"32 例"→"三十二例"）。

## 5. 产出与复现命令

目录：`output/run05/`
| 目录 | 内容 |
|---|---|
| `tts_gsv_v2` | GPT-SoVITS v2 三拍（13.5s/拍） |
| `tts_gsv_v3_s8` | v3 @8 步三拍（90s/拍） |
| `tts_gsv_v3_s32` | v3 @32 步三拍（262s/拍） |
| `tts_gsv_v3_smoke` | 单拍冒烟（链路验证） |
| `AB_bundle_4engines.wav` | **交错试听包**（100.8s，每拍依次 F5 → v2 → v3@8 → v3@32）+ 同名 `.txt` 清单 |

命令模板（用包内 Python 运行）：
```powershell
& "C:\mp4agent\gpt-sovits\GPT-SoVITS-v3lora-20250228\runtime\python.exe" `
  scripts\gsv_run.py --beats "S17-B02,S12-B02,S27-B01" `
  --ref "C:\mp4agent\voice_ref\ref_win3.wav" --ref-text "C:\mp4agent\voice_ref\ref_win3.txt" `
  --out "output/run05/tts_gsv_v2" `
  --gpt "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt" `
  --sovits "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth"
```
（v3 用默认 `s1v3.ckpt` + `s2Gv3.pth`；`--sample-steps 8|32`；`--expect-version v3` 可加断言）

## 6. 待决

1. **听判**：`AB_bundle_4engines.wav` —— v2 是否够像？v3 是否明显更像我？v3@8 有没有"电"？
2. **配置选择**：v2（22 分钟）/ v3@8（2.5 小时）/ v3@32（7.1 小时）三选一，或继续用 F5（但**商用授权不通过**）。
3. 若选 v3 且嫌慢：可尝试①把文本前端（g2pw+BERT，单拍 1.5–20s）缓存化；②降低 S2 chunk 的 prompt 帧数；③`if_sr` 关闭（已关）。
4. `--speed`（GPT-SoVITS 自带语速调节）可用于对齐现有时间轴。

## 8. 全片实测（GPT-SoVITS v2，101 拍，择优后）

**配置**：`s2G2333k.pth` + `s1bert25hz-5kh…ckpt`，`how_to_cut=不切`，`top_k=20 / top_p=0.6 / temperature=0.6`，`speed=1.0`，响度对齐 run03 同拍 RMS。
**耗时**：全片 101 拍 **约 17 分钟**（均值 9.7 s/拍），输出 **32 kHz**。

| 指标 | 数值 |
|---|---|
| 总时长 | **613.8 s（10:14）** vs 现片 526.0 s → **+87.8 s（+16.7%）** |
| 响度 | RMS 0.0427–0.0725（−27.4…−22.8 dBFS）| 标准差 **0.0060**（与 run03 同档）| 峰值最大 0.494 |
| 削波 | **0 拍** |
| 内部停顿 | 148 个（其中 ≥0.8 s 的 15 拍）| 停顿总时长 79.4 s |
| 字速 | 中位 **4.42 字/秒**，范围 2.42–5.64 |

### 8.1 发现的两个失败模式（都已处理）

1. **重复循环**：偶发生成到 token 预算上限 → 单拍 55–60 s（take A 的 S01-B01 55.54 s、take B 的 S02-B01 60.26 s）。这类 take 的"最长空洞 + 时长偏差"评分极差，自动被淘汰。
2. **异常长内部空洞**：初版 S16-B03 有 **5.60 s** 空洞（21.94 s / 34 字）。

处理方式：对 18 个可疑拍各生成 2 组不同种子的 take（`retake_A` seed 55500000 / `retake_B` seed 66600000），用 `pick_best_take.py` 按
`score = 3×最长停顿(≥0.4s) + (≥0.8s 停顿个数) + |时长 − 字数/4.27|` 择优，**替换 16 拍**，原版存档于 `_replaced/` 并记录在 `replace_log.json`。

效果：总长 681.0 s → **613.8 s**（+29.5% → +16.7%）；字速下限 1.37 → **2.42**；≥0.8 s 停顿由 22 拍降至 15 拍；最长停顿 5.60 s → **2.02 s**（S16-B03 变为 7.82 s / 0.82 s）。

### 8.2 仍需人工确认

- **拉丁词读法**：v2 前端把 `NerveGear / Neuralink / Telepathy / NEO / SAO / FullDive / NPC / BCI / ACE / Blindsight` 交给英文前端（日志显示 `N E R V E G E A R` 形式）。`VR / AI / NPC / BCI` 按字母念在中文里正常，但 `NerveGear / Neuralink / FullDive / Blindsight` 若按字母念就是错的 —— 需抽听 S01-B01、S16-B02、S17-B01、S18B-B02、S27-B03 等。
- **剩余 13 拍**仍有 0.8–2.0 s 停顿（可能属正常句读，也可能需要再重生成）。
- 数字朗读正常（`32 例`→`三十二例`、`1500 美元`→`一千五百美元`）。

### 8.3 产出（`output/run05/tts_gsv_v2_full/`）

| 文件 | 内容 |
|---|---|
| `_audition_all.wav` | **全片试听文件**（101 拍按 canonical 顺序，段间 0.6 s，674.4 s） |
| `_audition_all.txt` | 逐拍文本与时长清单 |
| `tts_index.json` | run03 同构索引（narration/text/wav/dur/target_dur/delta/rms/gaps） |
| `qc_report.json` | 全片质检（时长/响度/停顿/可疑拍清单） |
| `gsv_report.json` | 合成报告（含每拍耗时与分组计时） |
| `replace_log.json` + `_replaced/` | 择优替换记录与原版存档 |

## 7. 边界

未触碰任何冻结产物（run01–04、14 个模块、run03/prod01 TTS、run05 各 master）；旁白仍为 **v1.3**（101 拍）；F5 产出仍仅限非商用试听；GPT-SoVITS 产出（MIT）可在商用链路中使用，但**声音权与 AI 标识义务不变**。
