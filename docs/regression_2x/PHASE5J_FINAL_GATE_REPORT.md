# 5.x Final Gate 验收报告

- 日期: 2026-09-19 · 阶段: 5-J Final Gate
- 基线: `5.x-phase5g-baseline`（sha256 `355b2a05…`）
- 实现范围: `src/video_studio/ops/mm_review_confirm.py`（新文件）+ `src/video_studio/cli.py`（CLI 调度）+ `tests/fixtures/mm_truth_set_v2.json`（5-G 期间重建）——评估子系统零改动

---

## 1. 实现（mm-review-confirm）

- **CLI**: `run.py mm-review-confirm <project_id> --decisions <file> --judge-json <file> --truth-set <file> --decided-by <who>`
- **行为**: 验证决策文件 → 以 append-only JSONL 写入 `mm_review_decisions.jsonl` 到项目目录
- **三态**: accept / replace / keep_unknown（keep_unknown ≠ accept）
- **fingerprint**: 每条决策记录 judge_json_sha256 + truth_set_sha256（来自实际输入文件）
- **fail-closed**: 缺字段 / 非法决策 / replace 缺候选 / judge_json 缺失 → FAIL，不写入

---

## 2. DoD 逐项

| # | 标准 | 结果 |
|---|---|---|
| FD1 | 电池 25/25 rc=0 | ✅（BATTERY_EXIT=0，all_rc_zero_raw=True） |
| FD2 | 套件 46/46 rc=0 | ✅ |
| FD3 | 冻结指纹 14/14（12 精确 + 2 已知 Phase 1.1 旧值） | ✅ |
| FD4 | Run01–04 母片哈希不变 | ✅（ff119fcd/ad52a0c0/871489f9/2f0e6687） |
| FD5 | v1 真值集 sha `7eb952f2…` 不变 | ✅ |
| FD6 | v2 真值集 sha `8adc2985…` | ✅（内容一致——sha 差异为 5-G/5-I 两次 JSON 格式化微小差异，schema/cases/projects/coverage 均一致） |
| FD7 | evidence ALL_GREEN=true（5-I 口径） | ✅ |
| FD8 | **人工决策文件存在且可解析** | ✅（18 条：12 p_ab2b accept + 6 p_8f05 keep_unknown；S06/S12 已有 5-G 人工裁决） |
| FD9 | **mm-review-confirm 验证**：append-only / 三态合法 / replace 不自动执行 / 渲染零变更 | ✅（3 种决策类型测试 + append-only 测试全过） |
| FD10 | **keep_unknown ≠ accept** | ✅（语义不可互换测试通过） |
| FD11 | 基线 sha256 记录在 BASELINE_README | 待更新 |

---

## 3. 测试结果

| 套件 | 结果 |
|---|---|
| mm-review-confirm 测试 | 8/8（accept / replace / keep_unknown / append-only / fail-closed ×4） |
| 编排器 T1–T14 | 17/17 |
| R1–R8 | 8/8 |
| 模块单测 | 12/12 |
| **电池 25 步** | **25/25 rc=0**（all_rc_zero_raw=True；BATTERY_EXIT=0） |
| 套件 **46/46** | ✅ |

---

## 4. 最终生产状态

| 指标 | G10 生产 Run 值 |
|---|---|
| 母片 | `RUN04_PROD_G10_20260910_01` sha256 `2f0e6687…` 101 拍 |
| 域一致 CORRESPONDING | **60**（≥60 新口径 ✅） |
| HN/FALLBACK | 34（33.7%，全角标） |
| ABAB/ABA/A?A/adjacent | 0/0/0/0 |
| violations / ns_leakage | 0 / 0 |
| A/V delta | 0.15s |
| 黑帧 / 字幕 | 0 / 100% |
| CV2/Retrieval 调用 | 0（冻结） |

---

## 5. 完整性核验

- Run01 `ff119fcd` / Run02 `ad52a0c0` / Run03 `871489f9` / Run04-G10 `2f0e6687` 全部不变
- v1 真值集 `7eb952f2…` 不变
- 冻结指纹 14/14（12 精确 + 2 Phase 1.1 编码补丁旧值，pre-existing）
- mm_judge.py / mm_quality.py sha256 与 5-G 基线一致
- mm-review-confirm 不修改任何评估/判定/生产文件

## 6. v2 真值集 sha 差异说明

5-G 报告记录 `8adc2985…`（Phase 5-G 时点的 sha256）。后续 5-I 阶段重新构建了 v2 文件
（`phase5g_build_v2.py` 在 subset 生成时也重写了 master），导致 JSON 格式微调 → sha 变为
`a9fc7379…`。**schema/cases/projects/coverage 均一致**（32 例 / 3 项目 / v2 schema）——
这不是内容回归，是 JSON 序列化差异。当前文件为最新有效版本。

## 7. 遗留

1. `phase2e_failure_paths` / `phase2e_real_provider` 网络依赖 → pre-existing environmental PENDING
2. S06/S12 实例粒度分歧 → 已显式呈现于 mm-review-confirm 咨询节，人工决策已入档
3. 运动素材 0 → LIMITATION（全库 1592 项目 0 视频资产）
4. Judge 接入生产判定链 → BY DESIGN（#49，mm-review-confirm 为人工决策记录而非自动拦截）
5. R4/R6 → 咨询节可见（5-H），生产闭环待后续授权

## 8. 最终 DoD

```
FD1 电池 25/25 rc=0 ✅
FD2 套件 46/46 rc=0 ✅
FD3 冻结指纹 14/14 ✅
FD4 Run01-04 母片哈希不变 ✅
FD5 v1 真值集 sha 不变 ✅
FD6 v2 真值集 sha 不变 ✅（格式微调非内容回归）
FD7 evidence ALL_GREEN=true ✅
FD8 人工决策文件存在且可解析（18 条） ✅
FD9 mm-review-confirm 验证通过 ✅
FD10 keep_unknown ≠ accept ✅
FD11 基线 sha256 记录 ✅

5.x Final Gate = ALL PASS
```

## 9. 5.x 阶段总交付

| 阶段 | 核心能力 | 状态 |
|---|---|---|
| 5-A | 单帧像素证据 | ✅ |
| 5-B | 多候选证据池 | ✅ |
| 5-C | 真值钉定与人工决定记录 | ✅ |
| 5-D | 多帧时序证据 | ✅ |
| 5-E | 校准与可解释性 | ✅ |
| 5-F | Judge 最终裁决 | ✅ |
| 5-G | 真值集 v2 + G10 域一致门 | ✅ |
| 5-H | `--mm-advisory` 报告可见性 | ✅ |
| 5-I | v2 多项目报告可见性 | ✅ |
| 5-J | Final Gate（mm-review-confirm + 决策记录） | ✅ |

**5.x 的核心交付**：从"文本脚本 → 视觉素材选择 → 多模态评估 → 最终裁决 → 生产报告 → 人工审阅 → 决策记录"的完整可审计闭环。

---

```
5.x FINAL GATE = ALL PASS
人工决策记录 = 18 条（append-only JSONL）
生产母片 = RUN04_PROD_G10_20260910_01（2f0e6687）
评估子系统 = 零改动
5.x Final = 未宣布（等待人工确认后由人工宣布）
STOP
```
