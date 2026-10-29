# Stage 3.2b SEAL 报告（FINAL）

- **状态：SEALED / FINAL（条件式：附人工观看确认）**
- 版本：**3.2b**（`src/video_studio/stage32b/__init__.py`：`STAGE32B_VERSION="3.2b"`、`STAGE32B_STATUS="SEALED"`）
- 验收依据：`docs/STAGE32B_FINAL_HUMAN_ACCEPTANCE.md`（A 机器 Gate 全 PASS / B 人工观看清单就绪 / C 已知限制 / D 建议 SEALED）+ P0-7 Remediation Finalization（P0-1…P0-7 全链 Gate PASS）
- 封包时间：2026-08-29

---

## 一、版本信息与修改范围
- 上游冻结基线全部未改：2.x（含 Truth/Evidence、Creator Style v2、`V2_FINAL_SCRIPT_JARVIS.md`）、3.1.4（SEALED，SHA `B33B7310…4754AA`）、Material Package、rights gate / threshold 45 / NO_SAFE_MATCH、F5-TTS / ffmpeg 本体。
- 3.2b 范围（仅此）：`src/video_studio/stage32b/`（vo/alignment/subtitle/blocked/assemble/render/qc + `__init__.py` 状态写入）、`scripts/run_stage32b.py`、测试、docs、`output/stage32b/**`。
- 本 Seal 封包动作：仅写入 `STAGE32B_STATUS="SEALED"` + 本文件 + 验收文档；**无任何功能代码改动**。

## 二、最终产物 SHA256（固化，本次独立复算）
```
output/stage32b/coral/production/final_preview.mp4  3C629B6238B6A167A95BE33A2D208461D7322459451FCD6E1740DE109C8606B8
output/stage32b/coral/subtitles.srt                 B6D82D4B900230BEE2BEC46D555F897548982E9DCE4A3047376F7D8E7CD09C32
output/stage32b/coral/subtitles.ass                 275EFED0F59F98CC80887D13A7BD22919019516BD9F3B13D23CACDCDF070A42E
output/stage32b/coral/voiceover.wav                 24A1AC2A84F5AF041D41772299606CEDDFA675F229A26C1DB0A30B2D25EA3D49
output/stage32b/coral/manifests/vo_manifest.json    2CE0F630A4A7549E9014F4C37A8EAFB32666E9629E7EA324A441D3FE5DCA5D38
output/stage32b/coral/manifests/alignment_manifest.json  33DFDF6BADC76FC252296EC8F2C42BA97CE6E8EB3944FEFB10C26EB7BF2F3515
output/stage32b/coral/manifests/subtitle_manifest.json   AD03D4E703EE173CBBD94D9F7E779FC9E819FFBE8B353DD021C79CF7BC88F8ED
output/stage32b/coral/manifests/blocked_manifest.json    3B7E1ECE1D88A9A73835DDADB216473A15096742A668B379633D36B3AECC5A0B
output/stage32b/coral/manifests/shot_assembly_manifest.json CE446C74C9479AA333F2FF3E3D5F92E101F57C7C809310DBD88C37AF777AE622
output/stage32b/coral/manifests/render_manifest.json 9CEABA76D64D9EEE2A993556F52494AF70292C72A9047A14FD7FF7A75B0D06D6
output/stage32b/coral/qc/qc_report.json              510F3254CA493E14E43B51C752B40F516095711191B2AAD9A7E48C43A000E940
```
> 20 镜逐镜 mp4 SHA 见 `render_manifest.shot_inputs`（render_manifest 本身已固化）；11 个 USE_MATERIAL 素材 SHA 见 `shot_assembly_manifest`。

## 三、冻结资产 SHA 回归（封包前实测，2026-08-29）
- **2.x**：15/19 与 `docs/PRODUCTION_MANIFEST_2X.json` 逐字节一致；4 个 Creator Style v2 裁决升级文件（2026-08-19 基线，此前仅声明差异未留 SHA，本次首次固化）：
```
src/video_studio/production2x/__init__.py       B04E5EB44CF1E1EE56E0746EE74E492F2B1B321A921A1CD5D5220D6D041C09F6
src/video_studio/tools/content_planning.py      3390D6F8378CEEE6EA45CAA84131F4203D1307E303BD4CF34D6FAAC6E167AF78
src/video_studio/tools/narrative_generation.py  69305F6E3813234F373049B7583C58935558FF74DB39AF17D8C9D175307A3E12
src/video_studio/tools/creator_style.py         2C852A13107D2580D8ECAC6364EE0FDE5E529162214DFEC6C3CBE82002D7C1E4
```
- **3.1.4**：12/12 一致（9 模块 + `run_stage31.py` + 2 fetch 脚本；`__init__.py` = `B33B7310991A5E30AD108EEEC4949DB4F51C26DB0F6F6D464E5A32E4204754AA`，与 STAGE31_4_SEAL 记录一致）。
- **冻结口播稿**（coral）：内容 SHA（`read_text` 归一化口径）= `fd60866de1cc2f83342f605fc7afdf1ebb5c4bdc7a7aca18bc272541ad5355e2`，与全链 manifest 一致（文件为 CRLF 行尾；字节级 SHA = `254ACD5987994964DC072A787F9C11CB295B563E096A393B2CDC7216FCAEA4B4`，两者等价，已 Python 复算验证）。
- **参考文本**：`output/stage32b/assets/ref_voice.txt` 归一化 SHA = `4b6ffe0ae33dfa03751a59be432b17c71658a1620078fb9e27c113d79c8d95e8` = vo_manifest.ref_text_sha。
- **素材文件**：11 个 USE_MATERIAL 本地文件 SHA 与 shot_assembly_manifest 11/11 一致。
- **本模块状态文件**：`stage32b/__init__.py`（SEALED 写入后）= `8A5439C3C67FF3CA4A256D6F6069BDA6E72E1FFFEAC0B404BE9F9CA43A9B45AF`。

## 四、封包前回归（本次实测）
- 冻结测试套件 **18/18 全绿、0 失败**：2.x 13 套件 229 项 + stage31 5 套件 147 项（脚本式 `python tests/*_test.py` 执行）。
- P0-7 QC 13 项 Gate 全 PASS（`qc/qc_report.json`）：decode/容器、20 镜完整、VO 20/20、映射、字幕同步 ±0.1s、逐字 Truth、无 overlap/越界、无黑/冻结帧、48kHz+TP-2.2dB+无异常静音、I=-17.7 LUFS、无弱匹配素材、provenance 链、output SHA 一致。
- 逐镜像素级画面分析 20/20 OK（文字卡渲染、素材内容、无黑屏、切换真实；见 `output/stage32b/coral/qc/_frame_analysis.py`）。
- 成片参数：102.04s / 1920×1080 / 25fps / h264 yuv420p / aac 48kHz / VO 259.7 字/分（裁决带内）。

## 五、已知限制（验收文档 C 节全量引用，不隐藏）
素材覆盖不足致 9/20 镜为文字卡；静态图+Ken Burns、无转场/片头片尾/BGM/音效；单克隆 TTS 音色；字幕样式极简；S06/S08 亮图未调色；`qc.py` timeline_gap_note 为旧口径注释残留（未修）；CPU 产能（VO 52min/102s）；人工替换缺 workbench；无剪辑工程导出（3.2a 未实现）；发布链路不在范围。

## 六、封包条件与回滚
- 本 Seal 附条件：**人工观看确认**（`docs/STAGE32B_FINAL_HUMAN_ACCEPTANCE.md` B 节清单 + `qc/human_review.md` 最终版 + `qc/frames/` 抽帧图）。
- 若人工观看发现问题：按既有纪律**重开 remediation**（不修改阈值、不放松标准、不自动改上游），Seal 回滚为 DEV 并记录。

## 七、范围声明
- 未修改 2.x / Truth/Evidence / Creator Style v2 / 冻结稿 / 3.1.4 / Material Package / rights gate / 阈值 / F5-TTS / ffmpeg。
- **不进入 Stage 3.3**；本轮仅封包。STOP，等待下一步授权。
