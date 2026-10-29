# 5.x Phase 5-C 断点续做卡（CHECKPOINT）— 2026-09-16 **已结项**

> 本卡先作为"收工断点"写入（2026-09-16 晚），随后在**同一天**按 §4 的 6 步续做并**全部完成**。
> 结论：**5-C PASS（含 1 项如实登记的退化 #32）**；未进入 5-D。纪律不变：只做 5-C，**禁止进入 5-D**；
> 不得把任何未完成项写成 PASS；不得放宽任何冻结规则；每一项 PASS 必须有证据路径。

## 0. 状态

| 项 | 结果 |
|---|---|
| 阶段判定 | **PASS（含 1 项如实登记的退化 #32）** |
| 报告 | `docs/regression_2x/PHASE5C_REPORT.md` |
| 基线（当前基准） | `baseline/5.x-phase5c-baseline.zip` sha256 **`227c3a2d2be5675a69a3a0bf321d9575eea64a0138d0e2d0930e47f9e0268525`**（367 文件 / 7,955,906 B 源码 / 6,035,577 B zip）；`verify_baseline.py` → **MATCH**；相对 5-B delta = **修改 3 / 新增 0 / 删除 0** |
| 阶段快照 | `snapshots/5.x-phase5c-20260916.{zip,db,json}`（DB sha256 `a46ec08c644bc295c4818e0c59736ceb8a206d897a766fb13e345a9c6585a9af`） |
| 证据汇编 | `logs/phase5c_evidence.json`（**ALL_GREEN=true**，含 211 个证据文件哈希；原始 `all_rc_zero=False` 与唯一网络偏差项也如实保留） |
| 测试归档（收工版） | `snapshots/phase5c-tests-archive-20260916.zip` sha256 `1135ad4b898c17033c339bd4ba52afa074e86f72dcbcc13bd780fc3bd2f5fc4d`（200 文件，含首轮 42/43 失败留档） |
| 测试归档（结项版） | `snapshots/phase5c-tests-archive-20260916-final.zip`（哈希见其同名 manifest 的 `zip_sha256`；含最终报告/本卡/证据汇编） |
| 5-D | **未进入**（等待人工授权） |

## 1. 十项授权要求 → 落地位置

| 授权项 | 落地 |
|---|---|
| ① 人工明确选择（禁止自动选材） | decision `d_5ffb9971d5a3` / changelog `#902`／`--by human:project-owner` + 必填理由；5-B 全流程 `select_candidate_called=0` |
| ② 复用 4-C 闭环、不新增写入口 | 只用 `select-candidate`（写既有 `decisions`+`changelog`）+ 人工 `redo`；`src/` 零改动、无新表/列 |
| ③ 真实 S06 完成多模态候选替换 | S06 `front` → `side`（5-B 排序第一，CLIP 0.2886，`FREE_ATTRIBUTION`） |
| ④ 替换后复验 4-B/5-A/3-A/3-B/attribution/许可门禁/版本链 | 本卡 §2 与报告 §5/§8/§10（4-B `MATCH=6`；5-A 见 #32；3-A 16/16；3-B ×2 rc=0；attribution 1:1；门禁 6/6；v1–v6） |
| ⑤ 旧版本保留 / append-only / 人工可追溯 | `phase5c_db_append_only.json`（库级：删除 0 / 改写 0，仅 6 条白名单依赖重指）+ `phase5c_append_only.json` A/B 段 |
| ⑥ fail-closed（禁止自动回退） | `phase5c_failclosed.json` N1–N5 全 PASS、**零写入** |
| ⑦ 未修改未授权镜头 | 仅 S06 变化；S01–S05 素材与全部时间窗完全一致（C 段 ok=true） |
| ⑧ 全量回归 3-A～5-B | 报告 §10（3-A 16/16、批次 23/24、套件 43/43、各证据脚本 rc=0；冻结日志 drift 0） |
| ⑨ 输出前后证据/决定/版本链/语义/渲染响度抽帧/新基线+SHA256 | 本卡 §0/§2、`PHASE5C_REPORT.md` §1–§6、§13 |
| ⑩ 完成后 STOP，不进 5-D | 已停 |

## 2. 关键结果（复算入口）

| 项 | 值 |
|---|---|
| 人工决定 | `d_5ffb9971d5a3`（`human:project-owner`）+ changelog **#902** |
| 版本链 | v1 `t_ec83e67de429` → v5 `t_b8f866ddc062` → **v6 `t_6d692b93e342`**（全 SUCCEEDED，旧版全留） |
| v6 成片 | `t_6d692b93e342_draft.mp4`，6,027,761 B，sha256 `1c5759229cab328e985c10f1efd480e4ddc0d0409640c655092f14bfcfd1beef`，h264 High 1920×1080（3114 帧）+ aac LC 24 kHz，104.0 s |
| 响度（独立 ebur128） | **−16.1 LUFS / TP −2.7 dBTP**（契约 −16±1 / ≤−1.5） |
| 抽帧 | 6/6 corr_ok；S06 side **0.354118** > front 0.214879 > Visitor −0.065783 |
| 4-B / 5-A / 5-B | 4-B `MATCH=6`；5-A v5→v6 `MATCH 5→4 / UNKNOWN 1→2`（S06 退化 #32）；5-B S05/S06 `CANDIDATES_READY`（只读） |
| 复算脚本 | `python docs/regression_2x/phase5c_snapshot_after.py`、`phase5c_verify_film.py a_fa4716cffb26`、`phase5c_append_only.py`、`phase5c_db_append_only.py`、`phase5c_failclosed.py`、`phase5c_checkpoint_check.py`、`phase5c_evidence.py` |

## 3. 唯一代码改动（如实登记）

`tests/multimodal_test.py` F2 断言：`len(after["films"]) == 5` → 「成片字典逐字节未变 **且** 成片条数 == DB 中成功
渲染版本数（新增 `successful_render_versions()`）」。原因：5-C 授权替换使项目由 5 个成片变为 6 个（**过期校准**）；
首轮回归 **42/43**（`multimodal_test` 33/34），失败证据原样留档
`logs/phase5c_rerun/PRESERVED_suite_multimodal_test_failed_20260916.log`、`PRESERVED_suites_summary_42of43.json`；
修正后 **43/43**。**未放宽任何规则、未改任何产品逻辑与阈值**；登记 `KNOWN_ISSUES.md` **#37**。

## 4. 续做六步的执行记录（全部完成）

| 步 | 内容 | 结果 |
|---|---|---|
| ① | 单跑网络项 `phase2e_real_provider.py` | 仍 `PROVIDER_TIMEOUT`（TLS 握手超时）→ **环境问题**，与冻结 `PENDING（环境）` 一致；冻结日志 `phase2e_real_provider.json` **未被改写**（哈希与备份一致，无需恢复） |
| ② | 回归后库级 append-only 复验 | `phase5c_db_append_only.json` → **ALL_PASS=true**（删除 0 / 改写 0；新增 71 项目 / 332 任务 / 299 产物 / 33 决定 / 13 changelog / 2312 事件全部来自回归夹具；5-C 应有新行齐备） |
| ③ | 冻结 5-C 基线 + manifest + 校验 + 快照 | `make_baseline.py 5.x-phase5c-baseline --no-docs` → 367 文件 / 6,035,577 B；`make_manifest_one.py`；`verify_baseline.py` → **MATCH**；`make_snapshot.py 5.x-phase5c-20260916` |
| ④ | 报告 §10/§13/§14 | 已补（回归结果表 / 基线 SHA256 与 delta / 结论 + 待人工决策项） |
| ⑤ | 文档收尾 | `CHANGELOG.md` V2.5.3-Phase5C、`STATUS.md` 顶部与章节、`KNOWN_ISSUES.md` #32–#37、`BASELINE_README.md` 5-C 行与 §1 说明、`RUNBOOK.md` §4i、本卡 |
| ⑥ | 证据汇编 + 归档 + STOP | `phase5c_evidence.py` → **ALL_GREEN=true**；`phase5c-tests-archive-20260916-final.zip`；**未进入 5-D** |

## 5. 断点处的环境事实（复核过）

- 冻结证据日志：`logs/` 下 473 个非 `phase5c_*` 文件 vs `logs_5b_frozen/` → **drift 0**（`phase5c_checkpoint_check.py`）；
- 版本链 v1–v6 全 `SUCCEEDED`，v6 成片存在；
- 回归电池会创建夹具项目（如 `p_5efb23e5694f` = `test_phase2e_real_provider`），这是既有回归的常规副作用；
- 后台作业：全部结束；`5.x-phase5b-baseline.zip` 自身 zip 哈希与 manifest 仍相符（冻结 ZIP 未变），
  工作树相对其 delta = 修改 3（`CHANGELOG.md`/`STATUS.md`/`tests/multimodal_test.py`）。

## 6. 绝不可忘的纪律

- 5-A 的 `min_sim=0.20`/`margin=0.02`、5-B 的 `0.22`/`max_candidates=3`、4-B 词表与真值钉定
  （`a_2ed5f41d6b58`、词表 sha 前缀 `083e8d55c9899706`）、响度契约、素材验证阈值、许可门禁、
  append-only/version+1、HITL —— **一个字都不许改**（S06 的 5-A 退化只能登记，不能调阈值消除）；
- 不得自动改选材：任何素材变更只能由**人工** `select-candidate` + 人工 `redo`；
- 不得新增写入口；不得删除/覆盖 5-A/5-B 冻结证据（已用 `logs_5b_frozen/` + drift 校验证明未动）；
- 2 项 Wikimedia 真实网络项仍记 `PENDING（环境）`，即使某轮跑过也不得改写其状态；
- **未进入 5-D**。
