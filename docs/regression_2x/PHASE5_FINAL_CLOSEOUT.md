# 5.x Final Closeout 报告

- 日期: 2026-09-19
- 基线: **`5.x-final-baseline`** sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e`
- 前序: 5-A～5-J 全部 PASS/CLOSED
- 纪律: 本报告为 5.x 阶段最终收口，不进入 5-K、不新增能力

---

## 1. 5-A～5-J 全部 PASS/CLOSED

| 阶段 | 核心能力 | 状态 | 报告 |
|---|---|---|---|
| 5-A | 单帧像素证据（CLIP 3 帧，域一致性/相似度/边际/top-k） | ✅ PASS | `PHASE5A_REPORT.md` |
| 5-B | 多候选证据池（候选聚合、层间独立性） | ✅ PASS | `PHASE5B_REPORT.md` |
| 5-C | 真值钉定与人工决定记录（append-only 台账 38/38） | ✅ PASS | `PHASE5C_REPORT.md` |
| 5-D | 多帧时序证据（CLIP 7 帧 + 帧间一致性 + 逐帧投票 + 结构性 UNKNOWN） | ✅ PASS | `PHASE5D_REPORT.md` |
| 5-E | 校准与可解释性（真值集 14 例冻结、边界距离/证据分级/四段式可解释链/敏感性披露） | ✅ PASS | `PHASE5E_REPORT.md` |
| 5-F | Judge 最终裁决（J0–J6 + 5 级优先级 + 冲突不选边 + 10 理由码 + DoD 12/12；零阈值） | ✅ PASS/CLOSED | `PHASE5F_FINAL_CLOSEOUT.md` |
| 5-G | 真值集 v2（32 例 / 3 项目 / 多镜头 12 / 纯色 6 / 边界 4）+ 校验器 v2 分支 + G10 域一致门 | ✅ PASS/CLOSED | `PHASE5G_REPORT.md` |
| 5-H | 生产报告 `--mm-advisory` 只读咨询节（v1 14 例 + UNKNOWN 分型 + R6 展示） | ✅ PASS/CLOSED | `PHASE5H_CLOSEOUT.md` |
| 5-I | v2 多项目报告可见性（32 例 / 3 项目分组；层间冲突显式呈现；纯色 fail-closed 显式呈现） | ✅ PASS/CLOSED | `PHASE5I_REPORT.md` |
| 5-J | Final Gate（mm-review-confirm + append-only 决策记录 + 全量验证） | ✅ PASS/CLOSED | `PHASE5J_FINAL_GATE_REPORT.md` |

## 2. 最终 baseline

- **`5.x-final-baseline.zip`**
- SHA256: `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e`
- 384 文件 / 6,146,189 B zip
- `verify_baseline.py` → **MATCH**（missing 0 / drifted 0）
- delta vs `5.x-phase5g-baseline`: 修改 2（cli.py + ops/report.py）/ 新增 2（mm_review_confirm.py + test_review_confirm.py）/ 删除 0
- 快照: `snapshots/5.x-final-20260919`

## 3. 生产母片

| 母片 | SHA256[:16] | 拍数 | 域一致 | HN | 状态 |
|---|---|---|---|---|---|
| Run01 | `ff119fcd` | 101 | 81 (80.2%) | 19.8% | 已冻结 |
| Run02 | `ad52a0c0` | 101 | 51 | 38.6% | 已冻结 |
| Run03 | `871489f9` | 101 | 60 | 19.8% | 已冻结 |
| **Run04-G10** | **`2f0e6687`** | **101** | **67 (66.3%)** | **33.7%** | **当前最新** |

## 4. 决策记录

- `projects/p_f4b466a4a024/mm_review_decisions.jsonl`: **19 条** append-only JSONL
- 分布: 13 accept + 6 keep_unknown
- 每条含: decision_id / project_id / scene_id / case_id / decision / rationale / decided_by / decided_at / input_fingerprint（judge_json_sha256 + truth_set_sha256）/ baseline_sha256

## 5. 评估子系统零改动证明

| 模块 | SHA256[:16] | 状态 |
|---|---|---|
| `core/mm_judge.py` | `bb882fb7…` | 未修改 |
| `core/mm_quality.py` | `d7a78587…` | 仅校验器 v2 分支（5-G 授权） |
| `core/multimodal.py` | `0081b4dd…` | 未修改 |
| `core/mm_temporal.py` | `a38194b1…` | 未修改 |
| `core/semantics.py` | `2374d51f…` | 未修改 |
| 冻结指纹 14/14 | 12 精确 + 2 已知 Phase 1.1 编码补丁旧值 | ✅ |

## 6. 如实披露

| 项 | 状态 |
|---|---|
| 运动素材 = 0 | 全库 1592 项目 0 视频资产——LIMITATION 保留 |
| Wikimedia 网络 PENDING | pre-existing environmental；不因网络改写 PASS |
| S06/S12 实例粒度分歧 | 人工已裁决（accept），决策记录 append-only 留痕 |
| `phase5h_regression_run.txt` / `phase5j_regression_run3.txt` 恢复 DRIFT 1 | 电池自身输出日志，非评估证据 |
| 指纹 json 2 条旧值 | Phase 1.1 编码补丁旧值（pre-existing），非 5.x 回归 |
| v2 master SHA 序列化差异 | `8adc2985…` → `a9fc7379…`：5-I 阶段 subset 生成时 `phase5g_build_v2.py` 重写了 master 文件，JSON 序列化微调导致 sha 变化；schema/cases/projects/coverage 均一致，非内容回归 |
| 5-J 修复的 pre-existing CLI fall-through bug | mm-judge 块末尾缺 return，fall-through 到 select-candidate（pre-existing） |

## 7. 最终回归

- 电池 **25/25 步 rc=0**（BATTERY_EXIT=0）
- 套件 **46/46 rc=0**（含 subprocess_encoding_test 6/6 GBK 口径）
- R1–R8 回归 **8/8 PASS**
- mm_quality **34/34** · mm_judge **43/43** · 编排器 **17/17**
- 冻结证据 DRIFT **0**（三层 5c/5d/5e 原始证据逐字节一致）

## 8. 5.x 核心交付

**从"文本脚本 → 视觉素材选择 → 多模态评估 → 最终裁决 → 生产报告 → 人工审阅 → 决策记录"的完整可审计闭环。**

```
文本脚本 (4-B 语义)
    ↓
素材检索 + G10 域一致门 (60 域一致 / 34 HN 角标 / 0 域错配)
    ↓
多模态评估 (5-A 单帧 + 5-D 时序 + 5-F Judge)
    ↓
生产报告 (--mm-advisory 32 例 / 3 项目咨询节)
    ↓
人工审阅 (mm-review-confirm append-only 决策记录 19 条)
    ↓
5.x FINAL = COMPLETE / FROZEN
```

---

```
5.x FINAL = COMPLETE / FROZEN
当前基准 = 5.x-final-baseline（be1717b9）
5-A～5-J = 全部 PASS/CLOSED
评估子系统 = 零改动
人工决策记录 = 19 条 append-only JSONL
生产母片 Run01-04 = 哈希不变
LIMITATION = 运动素材 0 + Wikimedia 网络 PENDING + 实例粒度分歧 2 例（已裁决）
不进入 5-K、不新增能力、不修改任何冻结件
STOP
```
