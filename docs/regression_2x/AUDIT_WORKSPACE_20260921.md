# 工作区状态审计（2026-09-21）：相对 `5.x-final-baseline` 的漂移与断点归属

> **审计范围**：仓库当前状态 vs 冻结基线 `5.x-final-baseline`；以及"5-F 断点"是否仍然存在。
> **方式**：只读（基线 ZIP 取旧版对比现行文件、DB `mode=ro`、脚本只写 `docs/regression_2x/` 下审计日志）。
> **结论摘要**：**5-F 已于 2026-09-18 完成**、**5.x Final 已于 2026-09-19 冻结**；当前工作树相对该冻结基线
> **修改 4 / 新增 1 / 删除 0**，其中 **2 处是产品代码改动**且**未记入 CHANGELOG** —— 需要人工决策，**本文档不实施任何修复**。

## 1. 断点归属（关键）

| 事实 | 证据 |
|---|---|
| 本会话 09-17 的 5-F 断点卡（`PHASE5F_CHECKPOINT.md`）**已被后续会话超越** | 该文件现为 **09-18 18:06** 版本（7817 B），内含"已结项"结论 |
| 5-F **已冻结**：`5.x-phase5f-baseline.zip`（09-18 18:01） | `docs/regression_2x/baseline/`；`PHASE5F_FINAL_CLOSEOUT.md`（09-18 18:07） |
| 其后依次完成 5-G（真值集 v2，32 例）→ 5-H（生产报告 `--mm-advisory`）→ 5-I（v2 多项目可见性）→ 5-J（Final Gate） | `PHASE5G_REPORT.md`、`PHASE5H_CLOSEOUT.md`、`PHASE5I_REPORT.md`、`PHASE5J_FINAL_GATE_REPORT.md` |
| **5.x Final 已冻结**：`5.x-final-baseline.zip` sha256 `be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e`（384 文件 / 6,146,189 B） | `PHASE5_FINAL_CLOSEOUT.md`（09-19 23:15）；本次复核：**ZIP 哈希与 closeout 文档一致**、`manifest==ZIP 条目`、`missing 0` |
| 5.x Final 快照 | `snapshots/5.x-final-20260919.{zip,db,json}` |

**⇒ "在 5-F 断点处继续"已无对象**：5-F 与整条 5.x 线均已完成并冻结。本会话的正确动作是**停止**（已停止误启动的 5-F 回归），
并把审计结果与下述漂移交给人工决策。

## 2. 当前工作树相对 `5.x-final-baseline` 的漂移（修改 4 / 新增 1 / 删除 0）

| 文件 | 变更 | 性质 | 是否记入 CHANGELOG |
|---|---|---|---|
| `src/video_studio/agents/editing/agent.py` | 图片输入增加 `-framerate 1`（+5 行含注释）：避免 N 路 `-loop 1` 图片输入在 25fps 下持续解码导致 filter 队列膨胀（实测 21 路 25min 片：WorkingSet 6.7 GB、输出停滞；解码负载降 ~25 倍）；时长/转场/字幕不变 | **产品代码（行为影响）** | **否** |
| `src/video_studio/tools/ffmpeg_tool.py` | ffmpeg 超时 **1800 → 7200 s**（两处：raw op 与 loudness 重编码）：长图片时间轴渲染会被 1800 s 误杀 | **产品代码（行为影响）** | **否** |
| `config/config.json` | 默认配置重写：`tiers` 改为 `deepseek-v4-pro`/`deepseek-flash`、去掉内联 mock 响应、新增 `max_retries/backoff_base_s` 与 `pricing` 段 | 配置/契约（默认模型与成本口径） | **否** |
| `STATUS.md` | 顶部新增 GLM 会话的真实 LLM 端到端叙述（`p_96efdc03e1aa`：27 任务 SUCCEEDED、20 次真实调用、$0.107、4 闸 approve、100 claim 裁决、首版成片为**占位卡 DRAFT 未发布**） | 文档 | — |
| `config/config.mock.json.bak` | 新增备份文件 | 杂物 | — |

**技术评审（不改动，仅结论）**：
- `-framerate 1` 只在**图片输入**分支（与既有 `-loop 1` 同分支）内生效，输出时长由 `-t` 与后续 `fps=30` 滤镜决定 → 语义等价；
  若未来在图片路径引入插帧/时序滤镜需重新评估。
- 超时 1800→7200 s 是**放宽等待上限**（不放松任何质量契约），代价是真正卡死的 ffmpeg 需 2 h 才被杀 → 建议保留但增加进程级看护（未实施）。
- `config/config.json` 的默认模型/定价变更属**契约变化**：影响成本估算与默认行为，应显式记录。

## 3. 文档一致性缺口（未修复）

| 缺口 | 证据 |
|---|---|
| **CHANGELOG 未覆盖 5-H/5-I/5-J/5.x Final**，也未覆盖上述 2 处产品代码改动与配置变更 | `CHANGELOG.md` 最新条目为 `V2.5.7`（5-G，位于 **1160 行**，排在旧版本之后）→ 顺序错乱且缺 5 条 |
| `STATUS.md` 顶部叙述描述的是 GLM 会话**首版成片**（占位卡、provider=none、未发布），**未反映**其最终的 21 镜真实素材成片（DB render v7） | 本文档 §2 + `AUDIT_P96EFDC03E1AA.md` |
| 审计对象项目 `p_96efdc03e1aa` 的素材编辑（2 张中心裁剪）缺显式的"编辑前/后 sha + operator + decision"字段 | `AUDIT_P96EFDC03E1AA.md` §3 |

## 4. 本会话的误操作与修复（如实登记）

| 项 | 事实 |
|---|---|
| 误操作 | 依据 09-17 断点卡，于 `18:26` 启动了 09-17 版 `phase5f_regression.py`；它先备份 `logs/`（写入 `logs_5e_frozen`，mtime 18:25:59），随后重跑了 `3a_real_chain` 与部分 3-A 批次，**改写了 5 个既有日志**（另有 5 个内容相同） |
| 处置 | 发现仓库已推进到 5.x Final 后**立即停止**该作业；运行 `restore_logs_20260921.py` 从 18:25:59 备份**逐文件回拷** |
| 复核 | `logs/` 与 18:25:59 备份 **drift 0 / missing 0（525 文件）**；`5.x-final-baseline.zip` 哈希未变（`be1717b9…`）；本会话只在 `docs/regression_2x/`（不在基线内）新增审计脚本/日志，未改动 `src/`、`tests/`、`config/`、`CHANGELOG.md` |
| 未受影响 | 项目生产数据：`p_f4b466a4a024`（5-F 对象）在 5-E 快照与当前 DB 之间**删除 0 / 改写 0**；`p_96efdc03e1aa` 仅被只读审计 |

## 5. 需要人工决策的事项（**本会话不实施**）

| # | 事项 | 建议 |
|---|---|---|
| 1 | 5 处 post-final 改动（2 处产品代码 + 配置 + 文档 + 备份文件）是否纳入正式基线 | 若接受，需**新授权阶段**（如 5.x-patch / 6-A）：补 CHANGELOG、跑全量回归、冻结新基线；**不得**就地改写 `5.x-final-baseline` |
| 2 | `-framerate 1` 与 7200 s 超时是否需要回归覆盖（含视频输入路径不受影响的反证） | 新阶段中加 2 条针对性测试 |
| 3 | 审计发现的完整性问题：悬空候选引用（13 条）、陈旧 `external/.index.json`（11 条）、素材原地编辑的一等溯源、邮票 sha 不明变化 | 建议按 `AUDIT_P96EFDC03E1AA.md` §3 优先级排期 |
| 4 | CHANGELOG 顺序修复与缺失条目（5-H/5-I/5-J/Final + 2 处代码改动） | 文档补齐即可，属零行为风险 |

## 6. 审计产物

- 本文档：`docs/regression_2x/AUDIT_WORKSPACE_20260921.md`
- 项目审计：`docs/regression_2x/AUDIT_P96EFDC03E1AA.md`
- 漂移逐行 diff：`docs/regression_2x/logs/audit_final_drift.json`
- 日志回拷记录：`docs/regression_2x/logs/restore_logs_20260921.json`
- 项目逐镜头多模态：`docs/regression_2x/logs/audit_p96efdc_mm.json`（+ `audit_p96efdc_film_check.json`）
- 审计脚本：`docs/regression_2x/audit_p96efdc{,_b,_c,_d,_e,_f,_g,_mm}.py`、`audit_final_drift.py`、`restore_logs_20260921.py`
