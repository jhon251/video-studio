# 5.x Phase 5-D 断点卡（CHECKPOINT）— 2026-09-17 **已结项**

> 授权（逐字遵守）：只做 5-D，**完成后 STOP，不进入 5-E/Final**；不得把未完成项写成 PASS；
> 不得放宽任何冻结规则；每一项 PASS 必须有证据路径。本卡记录：做了什么、证据在哪、还剩什么不可做。

## 0. 状态

| 项 | 结果 |
|---|---|
| 阶段判定 | **PASS**（含 §11 如实登记的限制 #38–#42） |
| 报告 | `docs/regression_2x/PHASE5D_REPORT.md` |
| 授权基线（起点） | `5.x-phase5c-baseline.zip` sha256 `227c3a2d2be5675a…`（与授权书逐字节一致、ZIP 自洽） |
| **新基线（当前基准）** | `baseline/5.x-phase5d-baseline.zip` sha256 **`cab3324bad69bb56252cce7344372dff5fa90e6d980c030843e072019e2d73d8`**（370 文件 / 8,042,659 B / 6,063,180 B zip）；`verify_baseline.py` → **MATCH** |
| 相对 5-C 的 delta | **修改 4 / 新增 3 / 删除 0**（修改：`CHANGELOG.md`、`STATUS.md`、`cli.py`、`mm_worker_clip.py`；新增：`core/mm_temporal.py`、`ops/mm_temporal.py`、`tests/mm_temporal_test.py`） |
| 阶段快照 | `snapshots/5.x-phase5d-20260917.{zip,db,json}`（DB sha256 `2c6ad9561b138823…`） |
| 证据汇编 | `logs/phase5d_evidence.json`（**ALL_GREEN=true**） |
| 测试/回归归档 | `snapshots/phase5d-tests-archive-20260917.zip`（+ 同名 manifest） |
| 5-E/Final | **未进入**（等待人工授权） |

## 1. 十项授权要求 → 落地位置

| 授权项 | 落地 |
|---|---|
| ① 多帧采样验证同一 scene 视觉语义一致性 | 每镜头 **7 帧**（12.5%–87.5%，与 5-A 同 `frame_plan`）+ 相邻帧余弦（mean/min）+ 散布 + 一致性分类 `STABLE/MODERATE/SPLIT` |
| ② 每帧证据 / 聚合规则 / 三态 / confidence | 报告 `frames[]`（id/time_s/sha256/期望相似度/argmax/边际/top-3）、`aggregate{}`、`stability{}`、`rule_id`、`confidence`、`reason` |
| ③ 保留 4-B 文本语义不覆盖 | 4-B 模块与词表 sha256 与 5-C 基线一致；重跑 `semantic-check` 与 5-C 冻结证据一致（`four_b_preserved`） |
| ④ 不自动换材/选材/redo/改时间轴 | 只读层；报告 `policy` 显式声明 + 静态扫描无写调用 + DB/项目文件零变更 |
| ⑤ 默认关闭 + fail-closed | `tools.multimodal_temporal` 缺省不存在；模型/解释器/无帧/worker 失败/超时/非法 JSON/帧数不足/期望域推不出 → UNKNOWN + 明确错误码 |
| ⑥ 不改 5-A 原始结果 | `core/multimodal.py` 哈希未变、5-A 输出与冻结证据一致、报告只放 `five_a_reference` 引用副本 |
| ⑦ 覆盖 S04/S05/S06 + 解释 S06 | §4/§5（v5/v6/真值三版对照；结论：**不是**时序/视角抖动，而是视角导致的稳定域区分度不足） |
| ⑧ DB 零写 / 生产数据不被污染 | 证据脚本前后 DB 字节+五张表行数一致；项目 78 文件逐字节未变；测试夹具只写临时目录 |
| ⑨ 全量回归 3-A～5-C + 网络 PENDING 原状 | 套件 **44/44**、批次 **24/24**、3-A **16/16**、5-C 只读脚本全 rc=0、冻结证据 drift 0；历史 `PENDING（环境）` 记录未改写 |
| ⑩ 报告/限制/证据汇编/新基线+SHA256 | `PHASE5D_REPORT.md`、`KNOWN_ISSUES.md` #38–#42、`logs/phase5d_evidence.json`、`5.x-phase5d-baseline` + `cab3324b…` |

## 2. 关键结果（复算入口）

| 项 | 值 |
|---|---|
| 真实运行（v6 成片） | `MATCH=4 / MISMATCH=0 / UNKNOWN=2`（S01–S04 `T3`；S05/S06 `T7_AMBIGUOUS` MEDIUM） |
| 真实运行（v5 成片） | `MATCH=5 / MISMATCH=0 / UNKNOWN=1`（S06 `T3 MATCH` HIGH） |
| 冻结 4-B 真值产物 | `MATCH=4 / MISMATCH=2 / UNKNOWN=0`（S04/S06 `T4`，最像域 `wildlife`，与 4-B 方向一致） |
| S06 视角解释 | v5 中位边际 **0.0745** → v6 **0.0061**；两版逐帧投票 **1.0**、一致性 0.975/0.969、无 split |
| 受控夹具（真实模型） | 镜头内切图：相邻余弦 min **0.452 < 0.50** → `UNKNOWN / MMT_TEMPORAL_SPLIT`（`T1`）；静态对照 0.99999 → `STABLE` |
| fail-closed（CLI） | 模型缺失 → 6/6 `UNKNOWN` + `MM_MODEL_MISSING`，无 MATCH/MISMATCH |
| 阈值敏感性 | **S06 在任何扰动下都不翻转**；S04 仅在 `margin+0.01` 时 MATCH→UNKNOWN；S05 在 `margin−0.005/−0.01`（放宽）时 UNKNOWN→MATCH |
| 复算命令 | `python tests/mm_temporal_test.py`（53/53）、`python run.py mm-temporal p_f4b466a4a024 [--artifact a_e369526c2f47\|a_fa4716cffb26\|a_2ed5f41d6b58] --json`、`python docs/regression_2x/phase5d_evidence.py`、`phase5d_frozen_check.py` |

## 3. 本阶段改了什么（最小面）

| 文件 | 类型 | 影响面 |
|---|---|---|
| `src/video_studio/core/mm_temporal.py` | 新增 | 5-D 全部纯函数 + worker 调用 + 报告组装 |
| `src/video_studio/ops/mm_temporal.py` | 新增 | 只读编排（`mode=ro`）+ 5-A 引用副本 |
| `tests/mm_temporal_test.py` | 新增 | 53/53 |
| `src/video_studio/cli.py` | 加法式 | 新增只读子命令 `mm-temporal`（加入只读白名单，**不经过** `build_engine()`） |
| `src/video_studio/core/mm_worker_clip.py` | 加法式 | 新增 `return_embeddings`（**默认 false**）；5-A 默认路径输出逐字节不变（H4/H5/I1 断言） |
| `CHANGELOG.md` / `STATUS.md` | 文档 | V2.5.4-Phase5D 段 / 顶部与章节 |
| `docs/**`（不入基线） | 文档/证据 | 报告、断点卡、证据脚本、RUNBOOK §4j、KNOWN_ISSUES #38–#42 |

## 4. 还剩什么（明确不可做）

- **不可**进入 5-E/Final（本轮授权到 5-D 为止）。
- **不可**为了把 S06 变成 MATCH 而调阈值：敏感性分析已证明 `margin` 放宽 0.01 即会把 S05 这类边际镜头翻成
  MATCH（属放宽规则）；换素材同样需要新的 5-B 报告 + 新的人工决定 + redo（属 4-C 闭环，本阶段不做）。
- **不可**把 5-D 接进生产管线（默认关闭是设计要求）；如需启用，需新授权 + 影响面评估。

## 5. 绝不可忘的纪律

- 冻结规则：4-B 词表与真值钉定（`a_2ed5f41d6b58`、词表 sha 前缀 `083e8d55c9899706`）、5-A 阈值（0.20/0.02）、
  5-B 阈值（0.22/3/许可必清）、响度契约、素材验证阈值、许可门禁、append-only/version+1、HITL —— **一个字都不许改**；
- 不得自动改选材：任何素材变更只能由**人工** `select-candidate` + 人工 `redo`；
- 不得新增写入口；不得删除/覆盖 4-B / 5-A / 5-B / 5-C 的冻结证据（本轮已用 `logs_5c_frozen/` + drift 校验证明未动）；
- 2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`，即使某轮跑过也不得改写其状态；
- **未进入 5-E/Final**。
