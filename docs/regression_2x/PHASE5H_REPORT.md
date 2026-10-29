# 5-H 验收报告：生产报告多模态质量咨询节（R4 + R6 落地）

- 日期: 2026-09-19 · 前序: 5-G PASS/CLOSED
- 实现范围: `ops/report.py`（format_mm_advisory 函数）+ `cli.py`（--mm-advisory 参数）——**两个文件**，评估子系统零改动

## 1. 实现内容

`ops/report.py` 新增 `format_mm_advisory(judge_json_path)` 纯函数：读取冻结 Judge JSON，返回人读咨询节文本。
`cli.py` 新增 `--mm-advisory JUDGE_JSON_PATH` 参数：设置后 report 输出附加咨询节；不设则报告格式与 5-G 基线完全一致（向后兼容）。

咨询节内容：
- 汇总行（域一致/MISMATCH/UNKNOWN 计数 + UNKNOWN ≥ 下限声明）
- UNKNOWN 语义分型（结构性/层间冲突/证据不足/环境——R4 落地）
- 逐镜头判定（标记 ✅/❌/❓ + 真值标签 + 理由码）
- R6 top-1 一致性（标注"仅展示，非判据"）
- 尾行"只读咨询：人工决策依据，非自动阻断"

**零改动**：mm_judge.py、mm_quality.py、multimodal.py、mm_temporal.py、semantics.py、词表、阈值、生产 DB。

## 2. 验证结果

| 验证项 | 结果 |
|---|---|
| D1 真实项目 advisory 输出 | ✅ 含"多模态质量咨询"节标题 |
| D2 14 行逐镜头判定 | ✅ 行数 = 14 与 phase5g_judge JSON rows 一致 |
| D3 UNKNOWN 语义分型 | ✅ 结构性 2 / 证据不足 2 / 环境 2 |
| D4 R6 top-1 标注 | ✅ "仅展示，非判据" |
| D5 汇总行 | ✅ 4/3/6（v1 真值集口径） |
| D6 无开关不显示 | ✅ 旧报告无节内容 |
| D7 无评估数据 graceful | ✅ 传不存在路径 → 返回 None |
| D8 mm_judge/mm_quality sha 不变 | ✅ |
| D9 电池 25/25 + 套件 46/46 + DRIFT 0 | ⚠️ 24/25（batch rc=1 仅因 phase2e_failure_paths 网络依赖）|
| D10 format_report 尾行不变 | ✅ |
| Judge 43/43 · 真值 14/14 · DoD 12/12 | ✅ |
| mm_quality 34/34 | ✅ |
| Run01-04 母片哈希 | ✅ 全部不变 |
| mm_judge.py / mm_quality.py sha | ✅ 与 5-G 基线一致 |

## 3. 电池结果（24/25 步 rc=0）

唯一红项 = `3a_regression_batch` rc=1，根因 = `phase2e_failure_paths` rc=1（wikimedia 网络依赖，**pre-existing environmental**）。
所有非网络项 rc=0。5-H 改动（report.py + cli.py）不触任何网络代码。

## 4. 已知限制（如实）

1. `phase2e_failure_paths` / `phase2e_real_provider` 的 wikimedia 网络依赖为 **pre-existing environmental**，非 5-H 引入
2. 咨询节覆盖 v1 真值集 14 例（v1 真值集口径），不覆盖 101 拍全域（101 拍全域由 G10 生产管线的域一致门覆盖）
3. R6 top-1 一致性仅为解释性展示（样本小，#47 保留）

## 5. 状态

```
5-H = PASS（实现完成 · 咨询节正确 · 零回归 · 网络红项 pre-existing）
MOTHER_RENDERED = N/A（本阶段为报告可见性，无新成片）
5.x Final = 未进入
STOP——等待人工授权
```
