# Stage 33 — SUBTITLE REPAIR EXECUTION(受控冻结模块修复)

> **性质**:受控修复执行(已授权)。唯一修改文件:`src/video_studio/stage33/subtitle_pipeline.py`;唯一行为变更:RC-A `expansion=none` + RC-B 负 start 钳位。
> **修复产物(REPAIR CANDIDATE)**:`output/stage33/stage16_audit/render_163_subtitle_repair/final_long.mp4`(508.290s)
> **Production Baseline 不变**:`render_162/final_long.mp4` 仍是唯一 baseline;render_163 仅候选,未经人工 QA 确认不得切换。
> 机器可读:`output/subtitle_repair/subtitle_repair_execution.json`

## 1. 冻结指纹修订

| | 值 |
|---|---|
| 文件 | `subtitle_pipeline.py` |
| 旧 SHA256 | `a50f96aacc0b8440e1938681a87ea2d92679554e486193eea376b9953c0a46c1`(7283 bytes,指纹 `a50f96aacc0b8440`) |
| 新 SHA256 | `b38a6b11b14286023fa3129e742d08f7e443f5c80dda5c504114c6a11b3e98da`(7427 bytes,指纹 `b38a6b11b1428602`) |
| 指纹文件 | `stage19_8_frozen_fingerprints.json` 已更新该条目;**修订后 14/14 模块复核一致** |
| 修改原因 | 修复人工 QA 确认的 6 条字幕缺失(诊断报告 RC-A/RC-B) |
| 授权依据 | 用户 SUBTITLE REPAIR EXECUTION 授权(本轮) |
| 其他指纹 | 未触碰(13 个模块 hash 原样) |

## 2. 精确代码变更(共 3 处,均在 `burn_in` 内)

1. **RC-B 正则**:`(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+)...` → `(-?\d+):(\d+):(\d+),(\d+)\s*-->\s*(-?\d+)...`(容忍负号,使 `-1:59:59,990` 可解析);
2. **RC-B 钳位**:`t0, t1 = sec(1), sec(5)` 后增加 `if t0 < 0: t0 = 0.0`;
3. **RC-A**:drawtext 模板增加 `expansion=none`(cue 文本按字面量渲染;全片无 `%{...}` 用法,无其他行为影响)。

回滚:`output/subtitle_repair/rollback/` 保存了修复前的模块与指纹文件(字节级校验重建,`a50f96aacc0b8440`),恢复即回到修复前状态;`render_163_subtitle_repair/` 可整体删除。

## 3. Level 1 — 受控验证(8/8 PASS)

15s 合成黑底视频 + 6 类 cue:普通中文 ✓ · 含 `%`("全球GDP或激增20%，")✓ · 连续 `%`("增长20%下降30%")✓ · 数字百分比("超50%，")✓ · 正常正时间 ✓ · **精确 D6 负时间戳模式**("-1:59:59,990 → 00:00:01,513")✓;无 cue 时段无字幕 ✓;stderr **零 `Stray %` 警告**。帧检测数据见 `level1/level1_detection.json`(含目视图 `pos_3.0.png`:`全球GDP或激增20%,` 清晰渲染)。

## 4. Level 2 — 原分部复用

`burn_in` 直接作用于**既有** `part{1,2,3}_va.mp4`(未烧录视频+音频逐字节复用,视觉/音频生成层**未重新运行**);SRT 为原始文件位级拷贝(内容零修改)。3 分部 burn 全部 success、零 Stray 警告。

## 5. Level 3 — 新目录

全部产物写入 `render_163_subtitle_repair/`(burned_repair 分部 ×3、final_long.mp4、SRT 溯源拷贝、build_log);**`render_162/` 逐字节未动**(母片 sha256 前缀 `67627bbe6cb93326` 保持)。

## 6. 自动回归

### A. 原 5 缺陷点 — 全部出现字幕 ✅

| 点位 | band diff frac | 字幕 |
|---|---|---|
| D1 S09-B01(2:06) | 0.028 | ✅ |
| D2 S09-B01→B02(2:08) | 0.049 | ✅(帧检:"但白领岗位自动化率将超60%,") |
| D3 S23-B01(5:20) | 0.030 | ✅ |
| D4 S23-B02(5:23) | 0.048 | ✅ |
| D5 S30-B01(7:05) | 0.061 | ✅ |
| D6 S25-B01(5:43,part3 头) | 0.009 | ✅(帧检:"到2035年,") |

### B. 全片 cue 完整性 — missing = 0 ✅(附诚实标注)

| 项 | 值 |
|---|---|
| source cue count | **190**(65+63+62) |
| expected cue count | 190 |
| 自动检出 burned | 188 |
| 自动标记 missing | 2 → 逐条目视核验**均已显示**(“教育、”“此刻，”,0.7–0.8s 超短 2–3 字 cue,2fps 采样伪影,`fine_edu_bu.jpg`/`fine_ciki_bu.jpg`) |
| **有效 missing** | **0** |
| unexpected/misaligned(窗外字幕段 ≥1s) | **0** |

诚实标注:**NOT FULLY AUTOMATED(严格意义)**——190 条中 188 条机器验证,2 条超短 cue 因采样分辨率需单帧目视确认;人工 QA 仍按要求保留。

### C. A/V — PASS ✅

- 新 final 508.290s = 旧 final 508.290s;分部时长与 va 差 ≤0.04s(容器取整,与原 burned 相同);
- **音频逐样本一致**:新旧 final 解码 PCM correlation = 1.000,rms_diff = 0.0(同一 aac 编码路径、同一源 wav);
- silence(≥1s @ −35dB):new 1 = old 1,无新增;
- concat 正常(copy 流,无重编码)。

### D. 视觉不变性 — PASS ✅

- 结构性保证:pv/pa/clip 层从未重新生成,仅对 va 重跑 burn_in → 素材/拍时序/CV2/correspondence/motion/composition 结构性不变;
- 像素级:12 个跨片采样帧,字幕带外 |diff| 均值 0.12–0.93(p99 ≤ 4,重编码噪声底),带内 3.2–13.4(纯字幕像素)→ **除字幕区域外无任何视觉变化**;
- va 文件与 render_162 母片 untouched(mtime/size/hash 核验)。

## 7. 人工 QA(不代签)

`output/pre_flight_signoff/master_subtitle_timing_qa_DRAFT.md` 已更新为 v2:**仍为 DRAFT**,记录 render_163 修复候选与 5 点位复核清单,**无 APPROVED、无伪造观看结果**。自动验证仅作辅助证据;需项目负责人全片(重点 5 处)人工观看后签核。

## 8. Production Baseline

**不切换。** `render_162/final_long.mp4` 仍是唯一 Production Baseline;`render_163_subtitle_repair/final_long.mp4` 为 REPAIR CANDIDATE。Production Entry、Final Quality Gate、correspondence 60.86%、B1/B2/B3/W08、Pre-flight = BLOCKED 全部维持原状。

```
SUBTITLE REPAIR EXECUTION = PASS · HUMAN QA REQUIRED · STOP
不自动进入 Production Run 01 · 不自动切换 Production Baseline · 不自动写入 APPROVED
```
