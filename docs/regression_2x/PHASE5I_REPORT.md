# 5-I 验收报告：v2 多模态评估结果生产报告可见性

- 日期: 2026-09-19 · 前序: 5-H PASS/CLOSED
- 实现范围: `ops/report.py`（format_mm_advisory 重写为多文件聚合）——**一个文件**

## 1. 实现内容

`format_mm_advisory` 重写：从单文件（v1 judge JSON 仅 14 例）改为**多文件聚合**（逗号分隔多路径，逐项目读取冻结 Quality JSON），覆盖 v2 全量 **32 例 / 3 项目**。

- 数据来源 = 冻结 Quality JSON（`phase5g_quality_p_*.json` ×3），**零实时计算**
- 按项目分组展示：p_f4b466a4a024 (14) + p_ab2b352e06b8 (12) + p_8f054c227bd4 (6)
- 每例：状态（OK/VIOLATION/UNRESOLVED）+ content_label + 4B/5A/5D 层判定值
- 层间冲突显式呈现（4-B MATCH vs 5A/5D MISMATCH → "需人工确认"）
- 纯色底 fail-closed 显式呈现（"零视觉证据，层拒绝发证"）
- R4 UNKNOWN 语义分型（结构性/证据不足/层间冲突/环境）
- R6 top-1 一致性（"仅展示，非判据"）

## 2. 咨询节实际输出

```
=== 多模态质量咨询（只读；人工决策依据，非自动阻断） ===
  覆盖: 32 例 / 3 项目
  层判定汇总: MATCH=35 | MISMATCH=19 | UNKNOWN=13 | 无证据(UNRESOLVED)=6
  状态: OK=24 | VIOLATION=2 | UNRESOLVED=6
  阈值: 未触碰 | UNKNOWN 为合法最终结果
  ── p_f4b466a4a024 (14 例) ──
    ❌ T01_S04_truth_artifact_mismatch [MISMATCH] ...
    ✅ T03_S01_v6_clear_match [MATCH] ...
    ...
  ── p_ab2b352e06b8 (12 例) ──
    ⚠️ 层间冲突（需人工裁决）:
      G01_pab2b_S06_match: 4B=MATCH / 5A=MISMATCH / 5D=MISMATCH → 需人工确认
      ...
    ✅ G01_pab2b_S01_match [MATCH] status=OK
    ...
  ── p_8f054c227bd4 (6 例) ──
    ⚠️ 零视觉证据（层拒绝发证）:
      G02_p8f05_S1_unknown
      ...
  R6 top-1 一致性: 仅展示，非判据（样本小，见 #47）
  （只读咨询：人工决策依据，非自动阻断；不触发任何生产动作）
```

## 3. DoD 逐项

| # | 标准 | 结果 |
|---|---|---|
| D1 | 咨询节覆盖 32 例 / 3 项目分组 | ✅ |
| D2 | 14 行 v1 判定与 phase5g Judge JSON 一致 | ✅（32 例 case markers） |
| D3 | S06/S12 实例粒度分歧显式呈现 | ✅（"需人工确认"标注） |
| D4 | 6 处纯色底 fail-closed 显式呈现 | ✅（"零视觉证据"标注） |
| D5 | G10 域一致状态 | ✅（汇总行 MATCH/MISMATCH/UNKNOWN 计数） |
| D6 | `--mm-advisory` 默认关闭 | ✅（不加开关无节内容） |
| D7 | 无评估数据不崩溃 | ✅（返回 None） |
| D8 | mm_judge/mm_quality sha 不变 | ✅（bb882fb7/d7a78587） |
| D9 | 电池 25/25 rc=0 + 套件 46/46 | ✅ |
| D10 | format_report 尾行不变 | ✅ |
| D11 | v1 14 例判定逐行一致 | ✅ |
| D12 | v2 全量 32 例对账 | ✅（14+12+6=32） |

## 4. 完整性

- Run01 `ff119fcd` / Run02 `ad52a0c0` / Run03 `871489f9` / Run04-G10 `2f0e6687` 全部不变
- v1 真值集 sha256 `7eb952f2…` 不变
- 冻结 14/14（12 精确 + 2 Phase 1.1 编码补丁旧值）
- mm_judge.py / mm_quality.py sha256 与 5-G 基线一致
- 5-I 唯一改动：`ops/report.py` format_mm_advisory 函数（咨询节格式重写，不改任何评估/判定逻辑）

## 5. 32 例对账

| 项目 | v1 用例 | 新增用例 | 合计 |
|---|---|---|---|
| p_f4b466a4a024 | 14 | 0 | 14 |
| p_ab2b352e06b8 | 0 | 12 | 12 |
| p_8f054c227bd4 | 0 | 6 | 6 |
| **合计** | **14** | **18** | **32** |

## 6. 遗留

1. `phase2e_failure_paths` / `phase2e_real_provider` 网络依赖 → pre-existing environmental PENDING
2. S06/S12 实例粒度分歧 → 已显式呈现于咨询节，待人工裁决
3. 运动素材 0 → LIMITATION（全库如实记录）
4. Judge 接入生产判定链 → BY DESIGN（#49，未授权）
5. R4/R6 生产接线 → 5-H 已完成咨询节展示，自动化待人工授权

## 7. 状态

```
5-I = PASS（v2 全量 32 例/3 项目报告可见性完成；v1 零回归；评估子系统零改动）
5.x Final = 未进入
STOP——等待人工授权
```
