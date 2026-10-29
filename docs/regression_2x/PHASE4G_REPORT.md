# 4.x Phase 4-G 报告：只读节奏分析与人工建议（2026-09-16）

**授权**：进入 4-G；以 `4.x-phase4f-baseline.zip` 为基线；不使用 Git；**不自动修改时间轴、镜头时长、旁白、
素材或 BGM**；**不自动执行 redo**；**不自动语义改选材**；保持 3.x 时间轴权威时长、旁白完整性、响度契约、
4-A～4-F 逻辑不变；建议器**只输出建议/依据/置信或 UNKNOWN**，不写入生产产物；默认关闭或只读；
不改数据库结构；不接第二 Provider；不做 UI/自动发布/5.x。完成后 STOP。

**前置校验（基线）**：`docs/regression_2x/baseline/4.x-phase4f-baseline.zip`
sha256 `214374a1d14a6daf2729c7a8df63056bb8562dcaa4fa5e27e4e5d7cd59f45a23`（实测一致，5,966,731 字节）。

**结论：PASS**（只读、确定性、可复算；10 条规则 + 6 类 UNKNOWN；五项显式证明全部成立；未改任何生产数据）。

---

## 1. 变更文件与影响面

| # | 文件 | 类型 | 影响面 |
|---|---|---|---|
| 1 | `src/video_studio/core/rhythm.py` | **新增**（纯函数，仅依赖 `__future__`/`hashlib`/`json`） | `rhythm-advisor-v1`：阈值读取、旁白时间窗、10 条规则 + 6 类 UNKNOWN、建议与证据组装 |
| 2 | `src/video_studio/ops/rhythm.py` | **新增**（只读） | `readonly_connection`（`mode=ro`）+ 读取既有 `render_output`/`voice_output` + 输入指纹 + 文本格式化 |
| 3 | `tests/rhythm_advisor_test.py` | **新增** | 4-G 单测 **34/34**（A–K 十一组） |
| 4 | `docs/regression_2x/phase4g_evidence.py` | **新增**（docs，不入基线） | 场景矩阵 + 真实项目只读报告 + 只读/确定性证明 |
| 5 | `src/video_studio/cli.py` | 修改（**加法**） | 新增只读子命令 `rhythm`（与 `report`/`metrics`/`semantic-check` 同列：**不经过** `build_engine()`） |
| — | `CHANGELOG.md` / `STATUS.md` | 修改（文档登记） | 版本条目与断点状态 |

**未改动**：`config/config.json`（sha256 `b264644539b2adbb…`）、`db/schema.py`（**无表/列变更**）、
`core/materials.py`、`core/narration.py`、`core/audio.py`、`core/supply.py`、`core/retrieval_quality.py`、
`core/bgm.py`、`agents/**`（**未触碰任何生产 agent**）。

## 2. 分析项与规则（授权要求 1–7）

| 授权分析项 | 规则 | 触发条件（默认阈值） |
|---|---|---|
| 1/5 镜头时长、过短/过长 | `R_SCENE_TOO_SHORT` / `R_SCENE_TOO_LONG` | `< 3.0s` / `> 20.0s` |
| 2 旁白段落时长 | `R_NARRATION_SEGMENT_TOO_SHORT` / `R_NARRATION_SEGMENT_TOO_LONG` | `< 4.0s` / `> 30.0s` |
| 3 镜头与旁白的时间覆盖 | `R_CUT_MID_NARRATION`（`speech_continues_after_cut` / `speech_started_before_cut`） | 旁白段落边界与镜头边界错位 `> 0.5s` |
| 3 旁白超时轴 | `R_NARRATION_TRIMMED` | 旁白总时长 > 成片时长（被契约裁剪） |
| 4 镜头切换密度 | `R_CUT_DENSITY_HIGH` / `R_CUT_DENSITY_LOW` | `> 12` / `< 2` cuts per minute |
| 6 BGM 开启时的节奏提示 | `R_BGM_DUCK_FRAGMENTED` | 单镜头内 duck 切换 `> 2` 次（仅在 BGM **已生效**时） |
| 7 可疑静态画面 | `R_STATIC_HOLD` | 单张静态素材持续 `> 15.0s`（素材类型可判定时） |

**UNKNOWN（不给建议）**：`R_UNKNOWN_DURATION`（镜头时长缺失/非正）、`R_UNKNOWN_NARRATION`（旁白段落缺失/失败/0 时长）、
`R_UNKNOWN_ASSET_TYPE`（素材类型未知 → 不做静态判断）、`R_UNKNOWN_FILM_DURATION`（成片时长缺失 → 不做密度判断）、
`R_UNKNOWN_NARRATION_TOTAL`（旁白总时长缺失）、`R_UNKNOWN_BGM`（BGM 已配置但未生效）。

阈值可由 `tools.rhythm` 覆盖（非法值回退默认，不放松）；`rhythm_settings()` 记录来源（`default(readonly)` 或 `tools.rhythm`）。

**每条建议的字段**（全部实测存在，单测 B2 断言）：`suggestion_id`、`scene_id`、`current_duration_s`、`threshold_s`、
`rule`、`area`、`evidence`（实测值/阈值/差值 或 时间窗/交叉方向）、`action`、`risk`、`confidence`（HIGH/MEDIUM）、
`status="SUGGESTION"`、`applied=false`、`executed=false`、`requires_human_decision=true`。

## 3. 真实项目只读实测（`p_f4b466a4a024`）

```
python run.py rhythm p_f4b466a4a024            # 或 --json
```
| 项 | 实测 |
|---|---|
| 概览 | 成片 **104.0s** / 镜头 **6** / 切换 **5**（**2.885 cuts/min**）/ 旁白 **112.728s**（6 段）/ BGM 关闭 |
| 建议 / UNKNOWN | **11 条 / 0 条** |
| 分布 | `R_CUT_MID_NARRATION` ×6（tail 2.8–8.7s）、`R_STATIC_HOLD` ×3（20/20/25s）、`R_SCENE_TOO_LONG` ×1（S04 25s > 20s）、`R_NARRATION_TRIMMED` ×1（超 8.728s） |
| 输入指纹 | `render_output a_e369526c2f47 sha256 a68b7378…`、`voice_output a_894c229c0055 sha256 a4a60429…` |
| 结论 | 该片是**静态图 + 长镜头**型：3 个镜头单图持续 20/20/25s；切换点落在旁白句中（旁白段落比镜头窗口长）；末段旁白被时间轴契约裁掉 8.7s —— 均为**建议**，未执行任何改动 |

## 4. 验收覆盖（逐条对应）

| 验收项 | 结果 |
|---|---|
| 正常节奏 | 合成用例（旁白与镜头边界对齐、全部 ≤15s）→ **0 建议 / 0 UNKNOWN**（A1/A2） |
| 过短镜头 | 1.5s 镜头 → `R_SCENE_TOO_SHORT`（含 measured/threshold/delta + 动作/风险）（B1–B3） |
| 过长镜头 | 30s 镜头 → `R_SCENE_TOO_LONG`（HIGH 置信，超额 10s）（C1/C2） |
| 旁白与镜头边界异常 | `speech_continues_after_cut`（tail 4.0s）与 `speech_started_before_cut`（lead<0）两个方向；容差内（0.2s）不报警（D1–D3） |
| BGM 关闭 | 不产生任何 BGM 建议；概览 `bgm.enabled=false`（E1） |
| BGM 开启 | 单镜头 3 次 duck 切换 → `R_BGM_DUCK_FRAGMENTED`（含窗口与 bed/duck 参数）；BGM 未生效 → UNKNOWN（F1/F2） |
| 空旁白 / 异常时长 | 无旁白产物 / 段落全失败 / 0 时长 / 镜头时长缺失 / 成片时长缺失 → 全部 UNKNOWN，**不强行给建议**（G1–G3） |
| 无法判断 | 素材类型未知 → `R_UNKNOWN_ASSET_TYPE` 且**不**给静态建议；静态判定依据可解释（`ext_field` 优先于 `name_suffix`）（H1/H2） |
| 输出确定性与重复运行一致 | 纯函数三次调用逐字节一致；真实项目 API 两次运行一致；**CLI 三次运行 stdout 逐字节一致**（I1/I2、J4） |
| 只读验证 | 真实 DB **字节一致** + `tasks/artifacts/events/decisions/changelog` **行数一致**；项目 **74 个文件**（含 5 个成片）逐字节未变；只读连接 `INSERT` 被 SQLite 拒绝（J1–J3） |
| 3-A / 3-B 回归 | 3-A **16/16 PASS**；3-B **32/32** + 失败路径 **12/12** |
| 4-A…4-F 回归 | 4-A **18/18**、4-B **29/29**、4-C **18/18**、4-D **55/55**、4-E **35/35**、4-F **48/48**；套件 **41/41 rc=0（FAILED: []）** |
| `provider=none` 回归 | `config/config.json` sha256 与基线 manifest 一致；BGM/检索/缓存开关默认值未变；`provider_from_config(none)` 仍纯 no-op |
| 网络 PENDING 原样保留 | `phase2e_failure_paths` / `phase2e_real_provider`（及 `phase3a_run1_verify`）**状态与期望值未改写**，仍记 `PENDING（环境）`；本轮实测通过仅作记录 |
| 新 baseline | §7 |

## 5. 五项显式证明

| 证明 | 证据 |
|---|---|
| **不会自动改时长** | 报告 `applied_changes=0`；全部建议 `applied=false`/`executed=false`；`policy.changes_scene_duration=false`；运行前后 `render_output` 产物与成片文件哈希**未变**（K1/K3） |
| **不会绕过 HITL** | `decisions`/`changelog` 行数零新增；`policy.bypasses_hitl=false`、`requires_human_decision=true`；每条建议 `requires_human_decision=true`（K2） |
| **不会改变现有渲染结果** | 项目内 74 个文件（含 5 个成片 `t_ec83e67de429 / t_539c107ab85e / t_b7a62ec8e29a / t_1dbf3c1bc6f7 / t_b8f866ddc062`）逐字节未变；DB 字节未变（J2/K3） |
| **同输入同配置 → 相同建议** | 纯函数三次调用逐字节一致；CLI 三次运行 stdout 逐字节一致；报告内含输入指纹（产物 id+sha256）可核对（I1/J4/K7） |
| **建议不被误报为已执行** | 每条 `status="SUGGESTION"`、`applied=false`；文本输出标注『建议·未执行』与『未执行任何改动』、`applied_changes=0`，且**不含**"已执行/已应用/已修改/已生效"字样（K4） |
| （附加）**静态证明** | `core/rhythm.py` 只依赖 `__future__/hashlib/json`；`ops/rhythm.py` 无写库 SQL；两文件均无 `write_artifact`/`set_task_status`/`run_cycle`/`build_engine`/`subprocess`/redo 调用路径（K5） |

## 6. 只读机制

- 数据库以 `file:<path>?mode=ro` URI 打开（SQLite 层面禁止写入；`INSERT` 实测抛 `OperationalError`）；
- 只读取**既有产物**（`render_output` / `voice_output`），不调用调度器、不建任务、不写文件、不访问网络；
- `run.py rhythm` **不经过** `build_engine()`（避免建库/建目录/派发任务等副作用），与 `report`/`metrics`/`semantic-check` 同列；
- 管线（plan/run/redo）**从不调用**建议器：它只能被人工显式执行。

## 7. 新 baseline（ZIP + manifest + SHA256）与回归批次

| 项 | 值 |
|---|---|
| 标签 | `4.x-phase4g-baseline` |
| ZIP | `docs/regression_2x/baseline/4.x-phase4g-baseline.zip`（5,986,380 字节） |
| **zip sha256** | **`1daf93a1a3971ae5b0c22b57b1fe81a23a878d763c543ea801aabd02adf013c3`** |
| 文件数 / 源码字节 | **360 文件 / 7,819,574 字节**（`src/ config/ tests/ scripts/` + 根文件，**排除 `docs/`**） |
| manifest | `baseline/baseline_manifest_4.x-phase4g-baseline.json`（逐文件 sha256 由 ZIP 内字节重算） |
| 零漂移校验 | `verify_baseline.py 4.x-phase4g-baseline` → **MATCH**（zip 哈希一致、清单 == ZIP 条目、0 缺失、0 漂移） |
| 断点快照 | `snapshots/4.x-phase4g-20260916.{zip,db,json}`（DB sha256 `c030950486ef66d9…`，15,802,368 字节） |
| 相对上一基线 | 代码 **修改 1 / 新增 3 / 删除 0**（改 `cli.py`；增 `core/rhythm.py`、`ops/rhythm.py`、`tests/rhythm_advisor_test.py`；另 `CHANGELOG.md`/`STATUS.md` 文档登记） |
| 回归批次 | `phase3a_regression_batch.py` → **24 项全部 rc=0，非预期结果 = 0** |

## 8. 未做与已知限制（如实登记）

1. **不做任何自动变更**：不自动改时长/时间轴/旁白/素材/BGM、不自动 redo、不自动语义改选材。
2. **每镜头归属**：片级问题（切换密度、旁白超时轴、BGM 未生效 UNKNOWN）以 `scope="film"` 标注，并挂在
   最相关镜头（最短镜头 / 末镜头）上，避免伪造"某镜头的问题"。
3. **旁白时间窗口径**：由 voice 产物**逐段真实时长**顺序累加（与 4-F ducking 同口径）；成片末段若被时间轴契约裁剪，
   窗口仍按未裁剪值计算 —— 因此 `R_CUT_MID_NARRATION` 与 `R_NARRATION_TRIMMED` 可能同时出现（本片即如此，如实记录）。
4. **静态判定只看素材类型**：图片类素材即视为静态；**不做画面内容分析**（没有运动检测/视觉模型），
   类型未知时按 UNKNOWN 处理而不猜。
5. **阈值是工程默认值**（3/20/15s、2/12 cuts/min 等），未按内容类型自适应；可用 `tools.rhythm` 覆盖，改动会改变建议集合。
6. **未做 LLM 语义判断**：规则全部是机械阈值 + 时间窗比较；建议质量取决于输入产物（`render_output`/`voice_output`）是否齐全。
7. 3.x/4-A…4-F 的既有限制**不变**（`KNOWN_ISSUES.md` 与各阶段报告）。

**停止点**：按授权**完成 4-G 即 STOP**，不进入 5.x 或其它阶段。
