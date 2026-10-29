# 5-M 断点卡（成片字幕化）—— 已结项

- 阶段: **5-M 成片字幕化**（触发：用户指出成片"在画面中直接显示了整段文案"，要求改成字幕）
- 周期: 实现/验证 2026-09-21；电池重跑与冻结 2026-09-23
- **阶段判定: PASS（必要电池全部达 DoD）** —— 电池 **25/25 步 rc=0**、批次 **24/24 符合预期**、
  套件 **49/49 rc=0**、E2E **3/3 SETTLED**、冻结证据日志 **drift 0**、代码/测试指纹电池前后一致
- 授权基线: `5.x-post-final-maintenance-baseline-r2`（sha256 `2adc09c4092352f3c13af7b000db04b11e5ae34c96eb8389549ad7e3bcfb64e7`）
- 新基线: **`5.x-post-final-maintenance-baseline-r3`**（389 文件，sha256 `e02cdaa7309dfbd7d5244a90661d65d40eeaf648f97c5f783f5656a4b10f9a16`，`verify_baseline` → **MATCH**）
- 旧终稿: `5.x-final-baseline` sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e` —— **未变**（门禁 G6 复核）
- 快照: `snapshots/5.x-post-final-maintenance-20260921-r3.{zip,db,json}`（DB 39,600,128 B / sha256 `25d45d9f…`）
- 详细报告: `docs/regression_2x/PHASE5M_REPORT.md`

---

## 1. 判定（授权范围：只改字幕呈现）

| 项 | 结果 | 证据 |
|---|---|---|
| 字幕呈现改造 | 画面内整段文案（居中、最多 7 行）→ **底部逐条字幕**（≤2 行、带描边） | `PHASE5M_REPORT.md` §0/§1；`core/captions.py`（新）；`agents/{subtitle,editing}/agent.py` |
| 单元套件（新） | `tests/captions_test.py` **21/21** | `logs/phase5m_evidence.json` |
| 受影响套件 | `scene_assembly_test` **15/15**、`narration_contract_test` **40/40**、5-K `maintenance_fixes_test` **28/28**、5-L `offline_mock_test` **23/23**、`attribution_compliance_test` **24/24**、`pipeline_mock` rc=0 | `logs/phase5m_affected_suites.txt` |
| 视觉探针 | 真实素材 + 真实脚本 + 同款 `ass=` 滤镜：单行/两行字幕底部居中、无溢出、CJK 正常 | `logs/phase5m_caption_probe/` |
| 真实成片（render **v9** `t_d0a54bdf1810`） | 容器 1532.0 s / **视频轨 1531.96 s** / 38,300 帧 / 1920×1080 h264+aac；**−16.1 LUFS、TP −2.5 dBFS**；字幕产物 21 段 → **216 条 cue**；内容与 claims/decisions 未变；v1–v8 保留 | `logs/phase5m_render_verify.json` |
| 字幕节奏 | 覆盖率 **64.5%**、静默间隔均值 2.51 s / 最大 **4.64 s**、单条 1–8 s | `logs/phase5m_evidence.json` → `coverage` |
| 电池（25 步） | **25/25 rc=0**（`all_rc_zero_raw=True`，4,397.0 s）；批次 **24/24**；套件 **49/49 rc=0**；`e2e_mechanical` **3/3 SETTLED**；`run_ingest_test` **PASS**；`phase2e_real_provider` **13/13**；冻结日志恢复（163 改写回拷 / 0 新增 / 0 删除） | `logs/phase5m_regression_summary.json`、`logs/phase5m_rerun/**` |
| 门禁 | G1–G7 **全通过**（含 G6 旧 Final sha 未变、G7 指纹一致） | `logs/phase5m_freeze_gate.json` |

## 2. 过程如实披露（均已修正并在最终电池中复跑全绿）

1. **首轮电池中断**（2026-09-21）：第 1–24 步完成，第 25 步 `unit_suites` 未跑完 → 无 summary、
   未执行电池自带收尾。2026-09-23 用 `phase5m_preserve_and_restore.py` 补做（162 回拷 / 82 留档 / **drift 0**），
   随后**完整重跑**电池得 25/25。
2. **首轮中间红项**（作为历史留档，非最终结论）：批次 23/24（唯一红 = `phase2e_real_provider` 环境网络 TLS）、
   `suite_all` 48/49（唯一红 = `strip_v2_test` 过期契约）。
3. **两处自身缺陷**（已修）：① ASS 命名依赖 `task["task_id"]` → 以"最小 task 字典"调用 `_narration_args` 的两个套件
   `KeyError`（改为 `task.get("task_id") or "adhoc"`；不影响已渲染成片，v9 无需重渲）；
   ② `strip_v2_test` 的"烧录字幕源"断言 glob 旧 `_seg*.txt` → 按测试契约改为 `_captions_*.ass`（断言意图不变）。
   代码指纹 `before` `ba4978e7c585…` → `after` `c495dd64913c…`，差异**仅** `tests/strip_v2_test.py`。

## 3. 后续可选项（不阻塞本阶段结论）

1. **#65（OPEN）**：旁白 961.7 s vs 时间轴 1532.0 s（短差 570.3 s，`within_tolerance=false`）→ 约 37% 画面无旁白，
   也是字幕覆盖率 64.5% 的根因；可选处置：重写脚本贴合旁白 / 按旁白重排时间轴 / 留白段补画面或音乐。
2. **字幕与真实语音对轴**：当前 cue 时间基 = 脚本/时间轴；语音侧已有逐段真实 TTS 时长
   （`voice_output.segment_details[].duration_s`），可进一步按语音排布。
3. **样式微调**：只改 `core/captions.py::style_for()`（字号 4.2%×高、MarginV 5%×高、Outline 3）与
   `MAX_CUE_S/CHARS_PER_SEC/MAX_LINE_CHARS`；改后须重跑 `tests/captions_test.py` 与电池。
4. **#57 产品决策**：v7（视频轨短 21 s）与 v8（时长已修正、整段文案）与 v9（时长修正 + 逐条字幕）三者保留；
   以哪个作为发布候选由人工决定。
5. 陈旧分支（render v3 BLOCKED / v5）的清理需运维授权；`KNOWN_ISSUES` **#52–#55、#58–#61** 仍未处理（按授权不处理）。

## 4. 复现命令（幂等）

```powershell
cd C:\mp4agent\video-studio
python tests\captions_test.py                      # 21/21
python docs\regression_2x\phase5m_battery.py       # 25 步电池（~73 min）
python docs\regression_2x\phase5m_code_fingerprint.py now
python docs\regression_2x\phase5m_evidence.py      # 证据包
python docs\regression_2x\phase5m_freeze_r3.py     # 门禁 + 冻结（已冻结 r3；重跑会覆盖同名 tag）
```

**禁忌**：不得覆盖 r1/r2 与 `5.x-final-baseline`；不要单独重跑 `phase3a_real_chain.py`（会改写 5 份冻结证据日志）；
若再改任何基线内文件（`src/ config/ tests/ scripts/` 或根 `CHANGELOG.md`/`STATUS.md`）必须重跑电池并重新冻结。

## 5. 关键文件索引

- 报告/本卡：`docs/regression_2x/PHASE5M_REPORT.md`、`docs/regression_2x/PHASE5M_CHECKPOINT.md`
- 证据包：`docs/regression_2x/logs/phase5m_evidence.json`；电池 summary：`logs/phase5m_regression_summary.json`；门禁：`logs/phase5m_freeze_gate.json`
- 成片：`projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`（v9）；旧/新画面对照
  `output/_5m_frames/v8_t20.png` ↔ `logs/phase5m_frames/v9_t*.png`
- 基线：`baseline/5.x-post-final-maintenance-baseline-r3.zip` + manifest + `baseline_status_…-r3.json`；
  快照 `snapshots/5.x-post-final-maintenance-20260921-r3.*`；`BASELINE_README.md` r3 行
- 代码/测试：`src/video_studio/core/captions.py`（新）、`agents/subtitle/agent.py`、`agents/editing/agent.py`、
  `tests/captions_test.py`（新）、`tests/strip_v2_test.py`（契约修正）
- 脚本：`docs/regression_2x/phase5m_{caption_probe,verify_render,battery,evidence,code_fingerprint,freeze_r3,preserve_and_restore}.py`

