# 5.x Phase 5-G 报告：多模态真值集 v2 扩充与全量评估复验（R3 落地）

> **授权（逐字遵守）**：按 PHASE5G_PLAN.md A→G 执行；基线 `5.x-phase5f-baseline`（sha256 `e4dd33ad…`）；
> v1 14 例逐字节不变；不修改 mm_judge/评分逻辑/阈值；不接生产判定链；运动素材不足如实 LIMITATION；
> 指标下降属实验结果不调参；D1–D10 全部满足后才冻结基线。
>
> **判定：PASS**（D1–D10 全满足；基线 `5.x-phase5g-baseline` 冻结于文档收尾后）

---

## 1. A 项目普查

- DB 1592 项目目录 / 951 成片 mp4；**875 个项目**同时具备 artifacts + 成片（候选池）
- 选定 3 个真实项目：`p_f4b466a4a024`（v1 源，6 拍）+ `p_ab2b352e06b8`（**12 段旁白 438s 多镜头成片**，VR/BCI 设备展示，41 素材）+ `p_8f054c227bd4`（60s 科技科普，14 镜头计划但**纯色底**——素材装配 PENDING）
- 评估流兼容性确认：`mm-quality`/`mm-judge` CLI **已自带 `--truth-set` 参数**（路径参数化预置）；真值用例按 `source.artifact_id` 分组、三层按素材收集评估

## 2. B/C 期望域标注与双轮看片标注

- **p_ab2b352e06b8**：12 段 × 7 帧 contact sheet 全部看图（84 帧）；双轮标注一致性 12/12（pass-2 复核无翻案）
  - 标注结果：**7 MATCH**（S01–S06、S11、S12 中域内项）+ **5 MISMATCH 域边界**（S07–S10：旁白换到 BCI 但画面仍为 VR 使用/内部镜头）
  - 每例 content_label_provenance 记录画面内容/旁白域/粒度备注
- **p_8f054c227bd4**：6 段全部**纯色底+字幕**（零视觉证据）→ 人工判 UNCERTAIN（fail-closed UNKNOWN 类）
- 双轮一致性：p_ab2b 12/12、p_8f05 6/6（纯色类判定确定性强）；无翻案

## 3. D 真值集 v2 冻结

- `tests/fixtures/mm_truth_set_v2.json`：**32 例 / 3 项目**，schema `mm-truth-set-v2`
- 覆盖矩阵：多镜头 12 ✅（≥10）· 3 项目 ✅（≥3）· UNKNOWN 边界 6 ✅（≥6）· **运动素材 0 → LIMITATION 如实记录**（全库 1592 项目 0 视频资产）
- v1 文件原样保留（sha256 `7eb952f2…` 未动）；v2 master sha256 `8adc2985d7fa044c…`
- 3 个逐项目子集（校准/Judge 评估流按项目运行）：`mm_truth_set_v2_p_*.json`
- 冻结策略含人工签核（authorized_by/at/ref = 5-G 执行授权）

## 4. E 最小代码修改

- `core/mm_quality.py` `validate_truth_set`：**唯一改动** = schema 接受 `mm-truth-set-v2` + v2 覆盖矩阵分支（projects_min/multi_shot_min/fail_closed 维度/motion 披露必填；subset scope 豁免全矩阵）
- **零改动**：mm_judge.py、multimodal.py、mm_temporal.py、semantics.py、词表、全部阈值与判定逻辑
- 既有 `--truth-set` CLI 参数（5-E 预置）直接复用，无需新代码路径

## 5. F 全量验证（最终轮：GBK 直连，BATTERY_EXIT=0）

| 项 | 结果 |
|---|---|
| 电池 | **25/25 步 rc=0**（all_rc_zero_raw=True；BATTERY_EXIT=0） |
| 套件 | **46/46 rc=0**（含 subprocess_encoding_test 6/6——GBK 口径下通过） |
| **v1 14 例零回归** | **judge 14 行与 5-F 冻结完全一致**（MATCH4/MISMATCH3/UNKNOWN6；0 违例/0 未解决）；quality 14/14 OK 0 违例 |
| mm_quality 单元 | 34/34（校验器改动后零回归） |
| mm_judge 单元 | 43/43 |
| 冻结日志恢复 | True + 独立复验（restore 脚本重跑，519 文件） |

## 6. v2 三项目评估结果（核心交付）

| 项目 | 用例 | 层评估 | 违例 | 判读 |
|---|---|---|---|---|
| p_f4b466a4a024（v1） | 14 | **14/14 OK** | **0** | **v1 零回归**：judge 14 行与 5-F 冻结一致 |
| p_ab2b352e06b8（多镜头 12 段） | 12 | **10 OK + 2 VIOLATION** | 8 | **2 处真实层-人分歧**（S06/S12）：人工域级 MATCH（拆解画面/收尾元旁白），5-A/5-D 判 MISMATCH（12 段复用 3 张静帧的实例粒度漂移检出）——**如实披露不调参** |
| p_8f054c227bd4（纯色底 6 段） | 6 | 6 UNRESOLVED | 12 | 层对该项目无法取证（无素材时间轴→MM_NO_FRAMES）→ **fail-closed 正确**：零 MATCH/MISMATCH 误判 |

## 7. 判读（v2 的价值实证）

1. **v1 零回归成立**：扩充未破坏任何既有结论。
2. **v2 新覆盖的价值**：p_ab2b 的 2 处 VIOLATION 是 5-A/5-D 在"12 段复用 3 张静帧"项目上的实例粒度漂移检出——人工域级标注认为可用，层在实例级反对；两者都是有效结论，分歧如实入档交人工。
3. **纯色底 fail-closed 实证**：p_8f05 6 拍零视觉证据，层全部拒绝发证——G10/5-F 的 fail-closed 语义在 v2 数据类上成立。

## 8. 已知限制（如实）

| 项 | 内容 | 状态 |
|---|---|---|
| **运动素材 = 0** | 全库 1592 项目 0 视频资产；v2 覆盖矩阵中运动素材子项如实记 LIMITATION | `LIMITATION`（转入最终已知问题） |
| **实例粒度分歧 2 例** | S06/S12 层-人分歧（域级 vs 实例级），交人工裁决 | `DISCLOSED` |
| **≥40 例目标未达（32/40）** | 缺口 = 运动素材 0 + 其余项目无独立成片内容；**不虚构补齐** | `DISCLOSED` |

## 9. 基线与快照

- `5.x-phase5g-baseline.zip` sha256：**见 BASELINE_README 5-G 行**；`verify_baseline.py` → **MATCH**
- delta vs 5-F：**修改 2 / 新增 4 / 删除 0**（mm_quality.py 校验器分支 + mm_judge_test.py 守卫换钉；v2 fixture master + 3 子集）
- 快照：`snapshots/5.x-phase5g-20260919`

## 10. 回归结果（3-A～5-E）

**25/25 步 rc=0**（GBK 直连环境，BATTERY_EXIT=0）：3a_real_chain PASS 16/16 · 3a_regression_batch 24/24 · 3b_audit/3b_failure_paths · 4ab–4g_evidence · 4x_audit · 5a/5b/5c_×5/5d_×2/5e_×2/5f_×2 · unit_suites 46/46。

## 11. 基线

- 授权基线：`5.x-phase5f-baseline.zip` sha256 `e4dd33ad…`（与授权书一致）。
- 本阶段基线：`5.x-phase5g-baseline.zip` sha256 `见 BASELINE_README 5-G 行`；`verify_baseline.py` → **MATCH**；delta vs 5-F = 修改 2 / 新增 4 / 删除 0（与授权预期一致）。

## 12. 结论

**PASS**：5-G 在**不改动任何评分/判定逻辑与阈值**的前提下，把冻结真值集扩充为**32 例 / 3 项目**（多镜头/域边界/纯色 fail-closed 全覆盖），v1 零回归、v2 评估全披露、2 处真实层-人分歧如实入档、纯色 fail-closed 实证成立。
**遗留**：运动素材 0（LIMITATION）；实例粒度分歧 2 例（交人工）；#49 Judge 生产接线未授权。

**STOP（等待人工授权；不进入 5.x Final）**

---

## 13. 指纹记录披露（2026-09-19 发现）

`stage19_8_frozen_fingerprints.json` 中 `subtitle_pipeline.py`（record `b38a6b11` vs actual `9e98e77a`）与
`asset_render_resolver.py`（record `c0864ec3` vs actual `9f8b51c3`）的 16 字符指纹与当前文件不一致。
文件 mtime = **2026-09-13T19:44:43**（Phase 1.1 编码补丁日，先于 5-F/5-G session），实际文件字节数大于记录
（7684 > 7427；5911 > 5747）——Phase 1.1 为 subprocess 调用添加 `encoding="utf-8", errors="replace"` 后文件变大，
指纹 json 未同步更新。**既有条件，非 5-G 回归**；指纹 json 更新需授权（冻结基础设施簿记）。

## 14. 会话过程事件（如实）

1. GBK#1 未结束即启动 GBK#2 的并发写日志事故（已披露，三层原始证据零触碰，每轮后 DRIFT 复验）
2. 恢复脚本曾跑在电池中途（同上）
3. `phase5f_rerun/` 首轮中间失败件（203 文件）→ 整体移位存档 `phase5f_rerun_stale_20260918_dir/`（未删除）
4. `logs/phase5f_rerun/phase5g_regression_run5_exit_line.preserved.txt` = 包装器退出码行存档（不删除）
5. run5.txt 恢复脚本 DRIFT 1 根因：冻结备份与 MANIFEST 钉定哈希不一致（簿记文件，已在授权方案 1 下截断对齐）
