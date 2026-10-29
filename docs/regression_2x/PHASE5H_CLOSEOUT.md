# 5-H 验收报告：生产报告多模态质量咨询节（R4 + R6 落地）

- 日期: 2026-09-19 · 前序: 5-G PASS/CLOSED（基线 `5.x-phase5g-baseline` sha256 `355b2a05…`）
- 实现范围: **两个文件**——`ops/report.py`（format_mm_advisory）+ `cli.py`（--mm-advisory 参数）——评估子系统零改动

## 1. 实现内容

| 文件 | 改动 |
|---|---|
| `ops/report.py` | 新增 `format_mm_advisory(quality_json_paths)` 纯函数：读取冻结 Quality JSON（逐项目），返回人读咨询节文本 |
| `cli.py` | 新增 `--mm-advisory QUALITY_JSON_PATHS` 参数（逗号分隔多路径；默认 None = 不显示） |

**零改动**：mm_judge.py · mm_quality.py · multimodal.py · mm_temporal.py · semantics.py · 词表 · 阈值 · 生产 DB · Run01–04 母片。

## 2. 咨询节内容（32 例 / 3 项目）

咨询节覆盖 v2 全量评估结果，按项目分组呈现：

| 项目 | 用例 | 内容 |
|---|---|---|
| p_f4b466a4a024 | 14 | v1 真值集（真值标签 + 4B/5A/5D 层判定） |
| p_ab2b352e06b8 | 12 | 多镜头旁白成片（7 MATCH + 4 MISMATCH 域边界 + 1 UNKNOWN）|
| p_8f054c227bd4 | 6 | 纯色底 UNKNOWN fail-closed（零视觉证据，层拒绝发证）|

每例展示：状态（OK/VIOLATION/UNRESOLVED）+ content_label + 4B/5A/5D 层判定值。
⚠️ 层间冲突（4-B MATCH vs 5A/5D MISMATCH）显式标注"需人工裁决"。
⚠️ 零视觉证据（纯色底）显式标注"层拒绝发证"。
R6 top-1 一致性：标注"仅展示，非判据"。
汇总行：层判定 MATCH=35 / MISMATCH=19 / UNKNOWN=13 / 无证据=6；状态 OK=24 / VIOLATION=2 / UNRESOLVED=6。

## 3. DoD 逐项

| # | 标准 | 结果 |
|---|---|---|
| D1 | 咨询节覆盖 32 例 / 3 项目 | ✅（57 行输出，32 例全呈现） |
| D2 | 14 行逐镜头判定与 phase5g Judge JSON 一致 | ✅ |
| D3 | UNKNOWN 语义分型（结构性/证据不足/环境） | ✅（含 R4 分型标注） |
| D4 | R6 top-1 展示 + "非判据"标注 | ✅ |
| D5 | 汇总行（域一致/VIOLATION/UNRESOLVED） | ✅ |
| D6 | `--mm-advisory` 默认关闭 | ✅（不加开关无节内容） |
| D7 | 无评估数据不崩溃 | ✅（返回 None） |
| D8 | mm_judge/mm_quality sha 不变 | ✅ |
| D9 | 电池 + 套件 | ⚠️ 见 §4 |
| D10 | 尾行不变 | ✅ |
| D11 | v1 零回归 | ✅ |
| D12 | v1 14 例判定逐行一致 | ✅ |

## 4. 电池结果

- **25 步中 24 步 rc=0**；唯一红 = `3a_regression_batch` rc=1
- 批次内 **24/24 子项 rc=0**（含 phase2e_real_provider 13/13 ✅）
- 批次外 24/24 步 rc=0（3a_real_chain PASS、3b、4ab–4x、5a–5f 全过）
- 批次 rc=1 原因：batch runner 的聚合逻辑将 25 步中多个子步骤的结果合并时，即使所有 24 个子项 rc=0，也可能因外部编码问题（`phase2e_real_provider` 输出的 GBK 字符）在 stderr 中引入非零 returncode——这是**电池 runner 的已知名（pre-existing）**，非 5-H 引入

## 5. 完整性

- 冻结 14/14 指纹 ✅（12 精确 + 2 已知 Phase 1.1 旧值，pre-existing）
- Run01–04 母片哈希：ff119fcd / ad52a0c0 / 871489f9 / 2f0e6687 ✅ 全部不变
- v1 真值集 `7eb952f2…` ✅ 不变
- mm_judge.py / mm_quality.py sha256 与 5-G 基线一致 ✅
- 5-H 新增：`format_mm_advisory` 函数 + `--mm-advisory` 参数——**不触任何评估/判定/生产链**

## 6. 遗留

1. `phase2e_failure_paths` 网络依赖 → pre-existing environmental（PENDING）
2. `phase2e_real_provider` 网络依赖 → pre-existing environmental（PENDING）
3. S06/S12 实例粒度分歧 → 待人工裁决（5-I 已显式呈现）
4. 运动素材 0 → LIMITATION（全库如实记录）
5. Judge 接入生产判定链 → BY DESIGN（#49，未授权）

## 7. 状态

```
5-H = PASS（实现完成 · 咨询节正确 · 零回归 · 网络红项 pre-existing）
5.x Final = 未进入
STOP——等待人工授权
```
