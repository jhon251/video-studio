# 4.x Phase 4-A + 4-B 完成与交接点（2026-09-15）

> **状态：4-A（只读质量/成本指标）+ 4-B（离线三态语义核验）已完成，授权范围内判定 PASS；
> 完整回归因 2 项真实网络用例被环境阻断记为 PENDING（见 §4）。**
> 基线：`4.x-phase4ab-baseline`（345 文件 / 7,490,170 字节 / sha256 `3a7eb41a…191f`，MATCH）。
> **已按授权 STOP，未进入 4-C/4-D/4-E/4-F。**

---

## 1. 交付物清单

| 交付物 | 位置 | 说明 |
|---|---|---|
| 只读指标命令 | `src/video_studio/ops/metrics.py` + `cli.py` | `python run.py metrics <pid> [--json]` / `--all [--limit N]` |
| 离线三态验证器 | `src/video_studio/core/semantics.py` | `MATCH`/`MISMATCH`/`UNKNOWN` + 规则 ID + 信号（纯函数、离线、无阈值） |
| 语义知识库 v1 | `src/video_studio/core/lexicons/semantics_v1.json` | 12 域 + 12 同形词条；带 `version` 与 `sha256` |
| 语义命令 | `src/video_studio/cli.py` | `python run.py semantic-check <pid> [--json]` |
| 测试 | `tests/semantic_check_test.py`（**28/28**）、`tests/metrics_test.py`（**18/18**） | 含确定性/离线/只读/可解释性断言 |
| 证据 | `docs/regression_2x/logs/phase4ab_*` | 真值表+混淆计数、两次一致性、全库扫描、provider=none、变更清单、网络诊断 |
| 报告 | `docs/regression_2x/PHASE4A_4B_REPORT.md` | 8 项要求逐一对应 |

## 2. 关键结论（可直接引用）

- **真值表验收（3-A 项目）**：S04/S06 → `MISMATCH`（TP=2）；S01/S02/S03/S05 → `MATCH`（FP=0）；FN=0；
  本样本 `UNKNOWN=0`。命中规则分别是 `R3_DOMAIN_DISJOINT`（S04）与 `R2_SENSE_CONFLICT`（S06）。
- **判据无阈值**：规则为**类别式**（域交集 / 域不相交且无词级桥 / 同形词义冲突），**没有**相似度或概率阈值。
- **根因**：3-A 的 S04/S06 误选来自匹配器 `kw_tokens` 的**2 字符字面碎片**（`es` 落在 *Azores* 内）——
  S04 的检索文本根本不含 `PICO`。因此"碎片桥不算语义支持"是必要判据。
- **只读/离线/确定性**：`mode=ro` 连接（写被拒）、禁 socket 仍可运行、两次运行 JSON **逐字节一致**。
- **`provider=none` 未变**：`config/config.json` sha256 与冻结基线 manifest 一致；默认配置项目仍 `mode=none`、
  请求/下载为 0 且照常出片。

## 3. 变更全貌（相对 3.x 冻结基线）

修改 **1** 个（`src/video_studio/cli.py`，接线两个只读子命令）；
新增 **5** 个（`core/semantics.py`、`core/lexicons/semantics_v1.json`、`ops/metrics.py`、
`tests/semantic_check_test.py`、`tests/metrics_test.py`）。
**未**改数据库结构、**未**改冻结契约、**未**接第二 Provider、**未**动默认配置。
完整清单：`logs/phase4ab_change_list.json`。

## 4. 未完成 / PENDING（不得改写为完成）

| 项 | 状态 | 说明 |
|---|---|---|
| `phase2e_failure_paths.py` | **PENDING（环境）** | 本次 26/29：用例 6/7/8 停在 `PROVIDER_TIMEOUT`（均需真实搜索）；`commons/upload.wikimedia.org` **TLS 握手超时**（`logs/phase4ab_net_probe.txt`）；一小时前同一脚本 29/29 |
| `phase2e_real_provider.py` | **PENDING（环境）** | `TransportError: [PROVIDER_TIMEOUT]`；同上环境；一小时前 13/13 |
| 真值样本规模 | 已知限制 | n=6（正例 2 / 反例 4）属**冒烟级**，**不构成准确率结论** |
| 知识库覆盖 | 已知限制 | 全库 294 镜头 `UNKNOWN=168`（57%）；13 个历史镜头被标记 `MISMATCH` 但**无标注**，仅待人工复核 |
| `keyboard` 等其它同形词 | 已知限制 | v1 未收录，实测该类样本会被域交集**误支持为 MATCH**（已用测试固定观察行为，**未**临时扩表凑绿） |
| LLM 语义判定 | 未实现 | 本次选择离线确定性方案；如需 LLM 判定须缓存+记账+版本化并标注非确定性 |
| 判定结果落库 | 未做 | 新增 artifact 类型需先报告并获授权 |
| 成片质量改善 | **未做（越界）** | 4-A/4-B **只检测不改片**：S04/S06 错配素材**仍在 3-A 成片内**，替换属 4-C |

## 5. 工具层已知限制（本次实测发现，未修改脚本——超出授权）

- `docs/regression_2x/phase3b_audit.py` 的**默认路径是 3-B 早期的旧文件**（`t_539c10785…`、`run03/render/final_long.mp4`），
  不带参数运行会测到"旧的不合规成片"；本阶段按 3-B 的做法**显式传入当前交付成片**复测：
  正式链 **-16.1 LUFS / TP -2.7**、`stage32b` **-16.8 / -1.9**、E2E **-16.1 / -2.9**（全部达标）。
  建议后续阶段把该脚本改为"自动发现最新成片"（本阶段未改）。

## 6. 下一阶段入口（需单独授权）

- **4-C（人审候选替换）**：以 `semantic-check --json` 的 `MISMATCH` 列表为输入，列出候选池（含许可类别），
  **人工选定**后走既有 `redo`（append-only、版本+1）；不得自动替换、不得自动生成候选。
- 复现/巡检命令见 `PHASE4A_4B_REPORT.md` §2 与 `docs/RUNBOOK.md` §7–§8。

## 7. 停止点

按授权：**未**接入第二 Provider、**未**修改默认配置、**未**改数据库结构、**未**自动改选材或生成替换候选、
**未**修改成片、**未**做 BGM/UI/节奏自动改时长/Git tag，**未**改动 Claim/HITL·append-only·redo·
时间轴权威时长·旁白完整性·响度契约·素材验证·许可台账。**STOP。**
