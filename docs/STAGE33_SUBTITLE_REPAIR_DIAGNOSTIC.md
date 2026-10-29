# Stage 33 — SUBTITLE REPAIR DIAGNOSTIC(只读根因诊断)

> **性质**:只读修复方案诊断(已授权)。未修改 `subtitle_pipeline.py` / 任何冻结模块 / SRT / renderer;未重渲染;未生成生产视频;未动 Production Entry / Final Quality Gate / APPROVED / Pre-flight 状态。
> 对象:5 处已确认字幕缺失(`master_subtitle_timing_qa = FAIL`)。
> 机器可读:`output/subtitle_repair/subtitle_repair_diagnostic.json`

## 1. 字幕链路(实际代码路径)

```text
storyboard.build_beat_cues(冻结)          → 逐拍 cue(全局时间,旁白逐行等比切分)
run_162_final.py(非冻结)                 → 减去 part_start 得分部本地时间,写 part{1,2,3}.srt
subtitle_pipeline.burn_in(冻结)          → 解析 SRT → 每条 cue 一个 drawtext(textfile + enable=between(t,t0,t1)) → 重编码
concat(part1..3_burned)                  → final_long.mp4
```

注:本 ffmpeg 构建无 libass,drawtext 是唯一烧录路径;drawtext 文本默认经 expansion 处理。

## 2. 缺陷表(6 条缺陷 / 5 处报告点位)

| ID | 拍 | 时间 | 源 SRT cue | 成片烧录 | 类型 | 根因 |
|---|---|---|---|---|---|---|
| D1 | S09-B01 | 2:06.0–2:08.3(报 2:04–2:11) | 有("全球GDP或激增20%，") | **无** | 烧录层静默丢弃 | RC-A |
| D2 | S09-B01→B02 | 2:08.3–2:11.2 | 有("但白领岗位自动化率超60%，") | **无** | 同上 | RC-A |
| D3 | S23-B01 | 5:19.8–5:21.8(报 5:20) | 有("全球GDP或增7%，") | **无** | 同上 | RC-A |
| D4 | S23-B02 | 5:23.6–5:26.1(报 5:23) | 有("白领岗位自动化率超50%，") | **无** | 同上 | RC-A |
| D5 | S30-B01 | 7:04.8–7:08.4(报 7:04–7:08) | 有("全球约20%的岗位可能被自动化取代，") | **无** | 同上 | RC-A |
| D6 | S25-B01 | 5:42.9–5:44.4(part3 开头,报 ~5:43) | 有("到2035年，") | **无** | 负时间戳解析跳过 | RC-B |

关键对照:夹在 D3 与 D4 之间、**不含 %** 的 cue("但就业结构将剧变，" 5:21.8–5:23.6)**正常显示**(帧 322.5s)→ 证明是逐 cue 条件丢弃,不是时间轴整体漂移。

## 3. 根因(均为 confirmed,非推测)

### RC-A:drawtext expansion 对含 `%` 文本静默清空(5 条 cue)

- 机制:`burn_in` 把每条 cue 文本写入 textfile;drawtext `expansion=normal` 会解释 `%` 序列;**孤立 `%`** 触发警告 `Stray % near '，'` 并**整条文本渲染为空**;ffmpeg 退出码仍为 0,`burn_in` 的成功检查(returncode==0)**完全无法感知**;
- 实证(受控实验,同一生产 ffmpeg 二进制 + 同字体):
  - 含 `%` textfile → 黑帧 + stderr `[Parsed_drawtext_0] Stray % near '，'`(`one_pct.png` / `e1.txt`);
  - 不含 `%` → 正常渲染、零警告(`one_ok.png`);
  - **`%%` 转义在该构建下同样失败**(`Stray % near '%，...'` + 空白帧)——转义方案不可行;
  - **`expansion=none` 完美渲染含 `%` 文本**(rc=0、零警告,`one_expnone.png`)→ 已验证的唯一有效修复;
- 范围:全片 189 条 cue 中**恰有 5 条含 `%`**(part1:2 / part2:2 / part3:1)——与人工 QA 的 5 处缺陷**精确一一对应**;其余 184 条(含被检测脚本低估的极短 cue,如"教育、"116.0s 抽帧已证实显示)全部正常。

### RC-B:part 边界浮点漂移 → 负 cue 时间戳 → 解析跳过(1 条 cue)

- 机制:`c.start - part_start` 中 part_start 按**实测 wav 时长**累加、storyboard g_start 按**拍时长**累加,两套累加在 part2→part3 边界产生 −10ms 漂移 → 本地 start = −0.010s → `ts()` 把负数格式化为 `-1:59:59,990`(part3.srt 第 2 行原文)→ `burn_in` 时间戳正则 `(\d+):(\d+):(\d+),(\d+)` 匹配不了前导负号 → **整条 cue 在解析阶段被跳过**(part3 实际只建了 60 个 drawtext,61 条 cue);
- 范围:仅 S25-B01 首行;part1/part2 开头从 0.000 开始,不受影响;其余漂移 ≤~10ms,不可感知。

## 4. 五问回答

- **Q1**:不能归并为一个根因——**两个独立根因**(RC-A × 5 条,RC-B × 1 条)。
- **Q2**:最少 **2 个独立修复点**:(1) drawtext `expansion=none`(RC-A,冻结内);(2) 负 start 钳位(RC-B,脚本侧或冻结内均可)。
- **Q3**:**是**。两条修复都只动 cue 文本/时间戳;修复路径复用既有 `part{i}_va.mp4`(未烧录视频+音频),视觉素材、beat 时序、CV2、correspondence、motion、composition、音频全部不动。60.86% 与 B1/B2/B3/W08 不受影响。
- **Q4**:**部分**。RC-B 可不动冻结模块(脚本侧钳位);**RC-A 不能**——本构建下 `%%` 转义实证无效,唯一验证有效的修复(`expansion=none`)位于冻结的 `subtitle_pipeline.py` 内;脚本侧唯一替代是改用全角 `％`(字幕文本不再逐字一致,属编辑决策)。因此**完整修复必须触碰冻结边界**。
- **Q5 最小安全路径(仅方案,未执行)**:
  1. **授权的冻结修改**:`subtitle_pipeline.py` 的 drawtext 模板增加 `expansion=none`(单参数改动;全片 cue 均为纯文本旁白,流水线任何环节未使用 `%{...}` 函数,无其他行为变化);
  2. 重算 SHA256 并更新 `stage19_8_frozen_fingerprints.json`(指纹修订程序);
  3. 修复脚本:复制 part{i}.srt → 钳位负 start 至 0.000;
  4. 以**既有** `part{i}_va.mp4` 调用修复后的 `burn_in` → `part{i}_burned_repair.mp4`(新文件);
  5. concat → `render_163_subtitle_repair/final_long_subtitle_repair.mp4`(**不覆盖 render_162**);
  6. 自动验证:像素差扫描 0 缺失 + D1–D6 点位抽帧 + A/V delta + 时长核对;
  7. 人工 QA 复核 5 处点位;
  8. 基线切换(Production Entry / Gate)为**另一次显式授权**的独立决策。
  回归风险:`expansion=none` 无 `%{...}` 使用点(已核)→ 行为面仅恢复 %-cue 显示;重编码代际损失(crf20,与原生产路径相同);D6 钳位恢复的是设计意图(字幕应从拍首显示)。

## 5. 冻结边界处理

- 本诊断**零冻结修改**;`subtitle_pipeline.py` SHA256 未动;
- **重要结论**:RC-A 的唯一已验证修复(`expansion=none`)位于冻结模块内 → **完整修复必须触碰冻结边界**;`%%` 转义与脚本侧绕过均被实证不可行;若不接受冻结修改,唯一替代是全角 `％` 替换(内容偏离,编辑决策);
- 若你授权冻结修改,程序为:修改 → 重算 SHA256 → 更新 `stage19_8_frozen_fingerprints.json` → 定向回归(burn_in 单测 + 单分部渲染)→ 修复母片构建 → QA;
- Production Baseline 保护:render_162/final_long.mp4、生产 ledger、60.86%、Residual Register 均未动;修复产物将写入全新目录。

## 6. 证据索引

- 受控实验:`tmp_scan/one_pct.png`(含 % → 空白)、`e1.txt`(`Stray % near '，'`)、`one_ok.png`(无 % → 正常)、`tmp_scan/one_esc.png`(`%%` 转义 → 仍失败 + `Stray %` 警告)、**`tmp_scan/one_expnone.png`(`expansion=none` → 完美渲染含 % 文本)**、`e4.txt`(零警告);
- 抽帧:`_qa_frames/f_126.jpg`(D1/D2 区)、`f_320.5.jpg`(D3)、`f_343.5.jpg`(D6)、`f_425.jpg`(D5)、`tmp_scan/v_p1_116.0.jpg`(对照:短 cue 正常)、`chk_bu_1485.jpg`(对照:cue 正常);
- 全量逐 cue 像素差扫描:`tmp_scan/scan_v2.json`(含极短 cue 的检测伪影说明)。

```
SUBTITLE REPAIR DIAGNOSTIC = COMPLETE · STOP
6 缺陷 / 2 独立根因(RC-A: drawtext % 静默清空 ×5 · RC-B: 负时间戳解析跳过 ×1) ·
%% 转义实证不可行 · expansion=none 实证有效但位于冻结模块 → 完整修复必须触碰冻结边界(授权+指纹更新) ·
修复仅影响字幕层(va.mp4 复用) · render_162 与生产账本零触碰 · 修复执行等待显式授权
STOP——不进入修复执行
```
