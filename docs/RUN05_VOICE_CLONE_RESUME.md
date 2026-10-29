# Run05 配音克隆：断点恢复文档（关机存档）

- 存档时间：2026-09-12 深夜（用户关机前）
- 一句话状态：**旁白 v1.3 已冻；参考音 4 个候选已备；6 拍试听已判"像但有瑕疵"；A/B 实验 A 组完成、B 组缺 2 拍 → 明天一条命令自动续跑。**
- 失败/异常文件：**0**（全部 wav 可解码、非静音、与索引自洽）

---

## 1. 断点续跑（明天开机先执行这一条）

```powershell
cd C:\mp4agent\video-studio
$env:PYTHONIOENCODING="utf-8"
& ".venv_tts\Scripts\python.exe" scripts\clone_voice_run05.py `
  --ref "C:\mp4agent\voice_ref\ref_win3_lv.wav" `
  --ref-text "C:\mp4agent\voice_ref\ref_win3.txt" `
  --beats "S17-B02,S12-B02,S27-B01" --nfe 32 --threads 8 --loudness match `
  --out "C:\mp4agent\video-studio\output\run05\tts_ab_w3n32"
```

**为什么这就是"从断点续跑"**：脚本默认**跳过已存在的 wav**（除非显式 `--force`）。B 组已完成 S12-B02，因此本条只补 S17-B02 与 S27-B01（约 5–6 分钟）。
> 注意：脚本的索引 `tts_index_clone.json` 与时长报告**只在整轮跑完时写出**，所以 B 组补完后才会生成索引 —— 这是 PARTIAL 标记的原因，不是数据损坏。

---

## 2. 产出目录现状（已逐文件校验）

| 目录（`output/run05/`） | 状态 | 内容 | 参数 |
|---|---|---|---|
| `tts_ab_w1n32` | **COMPLETE** | 3 拍（S17-B02 / S12-B02 / S27-B01） | window1 + **nfe32** + 响度匹配 |
| `tts_ab_w3n32` | **PARTIAL（1/3）** | 仅 S12-B02 | window3 + nfe32 + 响度匹配 |
| `tts_clone_audition_lv` | COMPLETE | 6 拍 + 试听包 | window1 + nfe16 + 响度匹配（**你已听判的那一版**） |
| `tts_clone_audition` | COMPLETE | 同上 6 拍 | window1 + nfe16，**未做响度归一**（更响，对照用） |
| `tts_clone_dryrun` | COMPLETE | 3 拍 | 冷启动演练（用 run03 老配音当参考） |
| `tts_clone` | 空目录 | 正式全片输出位，**尚未启用** | — |

试听包：各目录内 `_audition_all.wav`（段间 0.7s）+ `_audition_all.txt`（逐拍文本）。
> 完整性脚本会把 `_audition_all.wav` 一起计入盘上合计，故显示"与索引不一致"，属正常。

---

## 3. 你的听判与假设验证进展

你的判定（第一版 6 拍试听）：**比较像我的；有吞字、吃尾音、喷麦、口吃；金属感略有点。**

| 症状 | 假设 | 结论 | 证据 |
|---|---|---|---|
| 吃尾音 | F5 自动分块 + 0.15s 交叉淡化吃掉块尾 | **已排除** | 按 F5 真实公式（`chunk_text` 只用中文标点切分，ASCII `,` `;` 不触发），当前参考音每块上限 159 字节，**0/101 拍会被切成多块** |
| 喷麦 / 部分金属感 | 参考音低频隆隆声被学走 | **基本排除** | 你的基频 **120.9 Hz**，`<150Hz` 能量占 34.6%，主要是基音本身；75 Hz 高通后只降到 33.9%（几乎无效果） |
| 口吃 / 吞字 | NFE=16 太低 | **待听判** | A 组（nfe32）已产出，与第一版（nfe16）同文本可直接对比 |
| 口吃 | 参考段含中英切换（`NerveGear`）的犹豫 | **部分排除** | window1 内部**无 ≥0.25s 停顿**；但含中英切换，故并列测试纯中文的 window3 |
| 金属感 | 参考段长度/内容导致条件偏置 | **待听判** | B 组（window3，6.61s 纯中文） |
| 口吃 | 生成随机性（seed） | **未测** | 候选方案：多 take 择优（需先做自动瑕疵评分） |

### 已测到的客观瑕疵证据

| 拍 | 时长 | 内部停顿（≥0.25s） |
|---|---|---|
| S01-B01 | 7.19s | 1 处 1.48s @3.94s（文本含破折号，可能合理） |
| S05-B01 | 5.43s | 1 处 0.38s @3.54s |
| **S12-B02** | 6.68s | **1 处 1.50s @2.70s（异常）** |
| **S17-B02** | 13.23s | **4 处 0.64 / 0.26 / 0.38 / 0.56s** |
| S27-B01 | 1.39s | 0 |
| S33B-B01 | 4.32s | 1 处 0.52s @1.28s |

其它已测事实：
- **nfe 32 与 nfe 16 输出时长完全一致**（13.23 / 6.68 / 1.39s）⇒ 时长由「文本字数 ÷ 参考字速」决定，与 NFE 无关。
- 单拍耗时（8 线程）：window1@nfe32 = 225s(S17) / 152s(S12) / 90s(S27)；window3@nfe32 = 103s(S12) ⇒ **短参考省约 30% 时间**。
- 响度匹配生效：成品逐拍与 run03 同拍 RMS 差值 **+0.0 dB**，峰值 ≤0.518，削波 0。

---

## 4. 参考音候选（均在 `C:\mp4agent\voice_ref\`）

| 文件 | 时长 | 文本 | 字速 | 锚定质量 | 说明 |
|---|---|---|---|---|---|
| `ref_short.wav` | 160.46s | 完整段 1–4（790 字） | 4.92 | — | 你的原始录音（保留；未来 CosyVoice/Chatterbox 可当长参考） |
| `ref_win.wav` / `ref_win_lv.wav` | 9.54s | 47 字（含 NerveGear） | 4.93 | **双端残差 −0.6 字** | window1（第一版试听用的就是它） |
| `ref_win3.wav` / `ref_win3_lv.wav` | **6.61s** | **31 字，纯中文** | 4.69 | **双端残差 −0.6 / +0.9 字** | **window3**：更短（省 30% 时间）、无中英切换 |
| `ref_win_ch0.wav` | 9.54s | 同 window1 | — | — | 左声道备选（原录音是双麦，corr 0.68） |
| `ref_win_hp.wav` | 9.54s | 同 window1 | — | — | 75 Hz 高通版（实测几乎无效，留档） |

- `*_lv.wav` = 已归一化到 F5 标称电平 **RMS 0.0955（−20.4 dBFS）**。F5 源码里只把 **RMS<0.1 的参考音**归一化到 0.1，更响的参考会**原样透传**导致输出过载（实测原始尖峰 >2、写盘削波 0.03%–0.37%）。**务必用 `_lv` 版本。**
- 每份 `ref_win*.wav` 都有同名 `.txt`（逐字对应文本），必须成对使用。

---

## 5. 明天建议流程（按序）

1. **续跑 B 组**（第 1 节命令，约 5–6 分钟，自动跳过已完成）。
2. **出三方客观对比**：
   ```powershell
   & ".venv_tts\Scripts\python.exe" scripts\ab_metrics.py `
     --dirs output\run05\tts_clone_audition_lv output\run05\tts_ab_w1n32 output\run05\tts_ab_w3n32 `
     --labels "第一版 nfe16/window1" "A nfe32/window1" "B nfe32/window3" `
     --beats S17-B02,S12-B02,S27-B01
   ```
   （指标：时长、字速、内部停顿数/时长、谱重心、4–8k/0.5–4k 比值、起停数）
3. **出并排试听包**（同一拍三版连续播放，便于盲听分辨）。
4. **若仍不达标**，下一批杠杆（按性价比排序）：
   - `--nfe 64`（单拍约 2× 时间，通常进一步减少吞字/金属感）；
   - `cfg_strength` 2.5–3.0（需给脚本加参数，默认 2.0）；
   - **多 take 择优**：每拍生成 2–3 个 seed，用"内部停顿 + 时长合理性 + 起停数"自动打分选最优；
   - **尾部处理**：尾部补 0.1–0.2s 静音 / 文本末尾补句号，缓解吃尾音；
   - 换 window1 左声道或另切一个候选窗口。
5. **达标后跑全片**（**需你明确批准**）：
   ```powershell
   & ".venv_tts\Scripts\python.exe" scripts\clone_voice_run05.py `
     --ref "C:\mp4agent\voice_ref\ref_win3_lv.wav" --ref-text "C:\mp4agent\voice_ref\ref_win3.txt" `
     --nfe 32 --threads 8 --loudness match `
     --out "C:\mp4agent\video-studio\output\run05\tts_clone"
   ```
   预计 **2.5–2.9 小时**（window3+nfe32，98 拍，含重试余量）；若用 `--nfe 16` 约 **1.3 小时**。
   产出：`tts_clone/`（逐拍 wav + `tts_index_clone.json` + `clone_duration_report.json`）。脚本支持断点续跑，随时可中断。

---

## 6. 脚本清单（本轮新增，均在 `scripts\`）

| 脚本 | 作用 |
|---|---|
| `clone_voice_run05.py` | **主驱动**：按 `narration_final.json` 逐拍克隆；断点续跑、`--limit/--beats/--force`、防削波、响度匹配（match/fixed/none）、时长对照 |
| `check_voice_ref.py` | 参考录音质检（时长/采样率/电平/削波/静音/文本-时长一致性） |
| `pick_voice_ref_window.py` | 160s 录音 ↔ 朗读稿的**边界匹配对齐**，输出候选窗口 |
| `cut_voice_ref.py` | 切出 ≤12s 窗口并导出逐字文本（`--channel auto/0/1/mix`） |
| `prep_voice_ref.py` | 高通滤波 + 电平归一化；含基频估计（避免削薄嗓音） |
| `check_internal_pauses.py` | 查内部停顿（判断参考段/生成音频是否卡顿） |
| `diagnose_clone_quality.py` | 分块分析 + 生成音频内部停顿 + 参考音喷麦扫描 |
| `ab_metrics.py` | A/B 客观指标对比表 |
| `check_wav_integrity.py` | 全目录 wav 完整性校验 |
| `make_audition_bundle.py` | 逐拍 wav 拼成单文件试听包 |
| `bench_f5_cpu.py` | CPU 性能基准（已跑完：7 次推理实测） |

---

## 7. 边界与合规（务必保持）

- **F5-TTS 权重是 CC-BY-NC**（代码 MIT、权重非商用）⇒ 当前所有克隆产出**只能内部试听，不得进入已发布/变现的成片**。商用需换 Apache/MIT 授权引擎或云声音复刻服务。
- 中国《人工智能生成合成内容标识办法》自 **2025-09-01** 施行（显式＋隐式标识）；平台另有 AI 声明规则。
- 本轮**未触碰任何冻结产物**：run01–04 产物、14 个冻结模块、`run03/tts`、`prod01/tts`、run05 各 master 全部原样。
- 旁白仍为 **v1.3**（101 拍、`final` 空值 0、S17-B03 归属已修正）。
- 版本链：`narration_final_v1.1_backup.json` → `v1.2_backup.json` → 当前 v1.3。

---

## 8. 未决事项（明天需要你决策）

1. **音色是否达标**：第一版 vs A(nfe32) vs B(window3,nfe32) 三者听判。
2. **全片用哪个配置**（决定 1.3h 还是 2.9h）。
3. **时间轴策略**：新文案比现片长约 **+12.2s（+2.3%）**，但 98/101 拍逐拍位移很大（S17-B02 6.74→14.15s）⇒ 重配音**必须重排时间轴并重渲染**，不能只换音轨。
4. **商用路线**：本地换 Chatterbox（MIT，最干净）/ CosyVoice2（Apache-2.0 但 Windows 安装有风险）/ IndexTTS2（B 站自定义协议），或云声音复刻 API。
