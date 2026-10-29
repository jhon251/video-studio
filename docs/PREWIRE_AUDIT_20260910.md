# 生产 render 接线前审计（Pre-wiring Audit）

- 日期: 2026-09-10 · 性质: 只读审计（零代码修改、零生产 Run、零 Retrieval/CV2 调用）
- 审计对象: 当前生产 render/assignment 链（run03 现行线 + prod02 对照）与 Visual Orchestration Layer 的接线缺口
- 结论先行: **链路无法严格串成目标形态——四个新模块（namespace_guard / visual_integrity_gate / global_reuse_policy / crop_recheck）在全部生产脚本中零接线**；VIZ 在 run03 生产路由中不可能产生（prod02 历史泄露已封存）；存在 3 项高风险历史机制需在接线时消除。**具备"授权后接线"条件**。

## 1. 当前链路（as-built，run03 现行生产线）

```
p0_p1_build.py      P0/P1：manifest/claims/narrative/viz_plan（viz_plan 明示本 run 无 VIZ）
preflight_gate.py   P0 治理门：冻结件哈希/母片哈希/P2 claims/B2-Tempi 禁令/viz_rollout=NOT AUTHORIZED
retrieval_run3.py   检索下载：过滤仅 mime∈{jpeg,png} + width≥640；写入 run03/asset_cache ✓
cv2_run.py          冻结 vision_call 全候选判定（focus 恒为空，见 F7）
render_v3.py        ★内联完成 Assignment（CV2 择优+借用+全局兜底）+ Crop(FULL_BLEED) + Render + 母片
QA                  临时执行，产物在 docs；run03/qa/ 目录为空（未持久化）
```

与目标链 `Retrieval → Gate → CV2 → Assignment → Reuse Policy → Integrity Gate → Crop/Layout → Crop Recheck → Render → QA` 逐段对照：

| 目标段 | as-built | 判定 |
|---|---|---|
| Retrieval | retrieval_run3.py | ✅（但无质量 Gate 前置） |
| **Gate** | **不存在**（preflight 是治理门，非资产质量门） | ❌ |
| CV2 | cv2_run.py（冻结 rubric） | ✅ |
| Assignment | render_v3.py 内联（非独立阶段产物之外的校验） | ⚠️ |
| **Global Reuse Policy** | **不存在**（内联借用 d≥2 + 全局兜底） | ❌ |
| **Integrity Gate** | **不存在**（无 G0–G9 任何调用） | ❌ |
| **Crop/Layout** | **隐式**：`decide_composition('IMAGE','','')` 恒 FULL_BLEED 中心裁切 | ❌ |
| **Crop Recheck** | **不存在** | ❌ |
| Render | render_v3.py | ✅ |
| QA | 临时脚本+docs 记录；qa/ 目录空 | ⚠️ |

`grep -rln orchestration output/{prod01,prod02,run03}/*.py` = **零命中**——正式模块与生产脚本之间没有任何接线。

## 2. 绕过盘点（四模块逐一）

| 模块 | 绕过现状 | 具体泄漏路径 |
|---|---|---|
| namespace_guard | **完全绕过** | render_v3 直接信任 retrieval_index 的 local_path，无 G8；跨 Run 读：render_v3/cv2_run 读 prod01_plan（文档化共享输入，但与 manifest "no cross-run read/write" 声明矛盾）；viz_pilot01.py 读 prod02 artifact 且**写 run03 命名空间之外**（`output/viz_pilot_01`） |
| visual_integrity_gate | **完全绕过** | 候选阶段仅 mime+宽≥640；无 G0/G2/G3/G9；pre-render 无任何检查；出处链从未校验 |
| global_reuse_policy | **完全绕过** | render_v3 内联借用：无内容身份（路径级）、无账本、无 60s 间隔、无借用者上限；d≥2 最近借用 = A?A 制造机制（Run02 P0 同款）；**第 69–74 行"ultimate fallback"：无素材拍统一填充首个 CORRESPONDING 素材**——静默大规模复用的现成机制（本次 101/101 有素材未触发，属潜伏） |
| crop_recheck | **完全绕过** | 全部剪辑恒 FULL_BLEED 中心裁切（focus 恒空串），S10-B02 类"原图 PASS/裁切后异常"无任何防线；MOTION 正则再次为死代码（v3:99） |

## 3. 风险等级（按接线前现状）

| # | 风险 | 等级 | 证据 |
|---|---|---|---|
| R-H1 | 未来 Run 复用 render_v3 模板 = 原样复现 Run02 P0（无账本借用 + 全局兜底填充） | **高** | render_v3:52–74 |
| R-H2 | 四模块零接线：新 Run 默认绕过 namespace/integrity/policy/crop 全部防线 | **高** | grep 零命中 |
| R-M1 | clip 缓存跨 exec 复用：`if not clip.exists()` 不校验来源 exec/输入哈希——已实证发生（15:31 exec 的 clip 被 16:22 exec 复用，本次因确定性输入侥幸字节一致；若 CV2/assignment 变更则静默用旧画面） | **中** | render_v3:128–131；两 exec 同哈希事实 |
| R-M2 | 失败路径缺陷：单拍 clip 失败时 clip+wav 同时缺席但全局时间轴不变 → 母片变短而 srt 仍按原时间轴烧录（字幕漂移）；且 ok_all=False 时**母片仍被写出** | **中** | render_v3:129–131,167–170 |
| R-M3 | 三代 render 脚本（render.py/render_v2.py/render_v3.py）共存于 run03 命名空间，均可原地覆写 `final_long.mp4`，无 exec 隔离目录 | **中** | 三脚本同写 R/'final_long.mp4' |
| R-L1 | preflight_gate.py:21 `run02_master_unchanged ... or True` **恒真**（无效检查）；:65 用 16 位前缀弱比对 | 低 | preflight_gate.py:21,65 |
| R-L2 | cv2_run.py `rec_focus()` 死函数（`_focus` 永未填充，调用即 KeyError）；实际判定 focus 恒空——冻结结果即此口径，未来 run 若"顺手修好"会与冻结口径不一致 | 低 | cv2_run.py:33–46 |
| R-L3 | prod01_plan 跨 Run 读与 manifest 隔离声明矛盾；共享输入无正式注册表 | 低 | render_v3:21；manifest:17 |
| R-L4 | QA 产物未持久化在 run 命名空间（run03/qa/ 空）；final_status.json 由旧 exec 写就未随 v3 更新 | 低 | 目录清单 |
| R-L5 | 死代码：MOTION 正则（v3:99）、EXEC_ID 假分支（render_run2:15） | 低 | 已列 |

## 4. VIZ 是否可能进入生产路由

- **run03：不可能。** render_v3 无 VIZ 分支（cls 仅 CORRESPONDING/FALLBACK）；viz_plan 明示"VIZ 拍仍使用 text/card 或 HN fallback"；run03 全部脚本无 stage22/exp225 引用；preflight 显式检查 `production_viz_rollout == 'NOT AUTHORIZED'`。
- **prod02：历史已发生**（exp_run02_route.py:16–113 硬编码 exp225 图表入生产渲染），该泄露通道随 run02 封存关闭。
- **结构性结论**：防线当前依赖"每个 Run 的脚本纪律"，不存在共享层强制。未来任何 Run 的路由表/计划文件仍可像 prod02 一样硬编码实验资产——**必须由 orchestration 层（gate G8 + namespace_guard + policy VIZ 预算）强制**，这正是接线的核心动机之一。

## 5. 最小修改方案（供"授权后接线"执行；本轮不动手）

原则：**不改 render_v3.py / retrieval_run3.py / cv2_run.py / 任何冻结件**；新增一个编排入口 + 配置，旧脚本全部保留为历史。

1. **新增 `run04_render_orchestrated.py`**（置于新 Run 命名空间），按目标链序调用 orchestration：
   - 候选阶段：`build_content_index` → 逐候选 `evaluate_asset(stage=candidate)`（G0-G3,G8,G9 确定性门）→ CV2 冻结判定 → 合格池
   - `run_reuse_policy`（60s/借用账本/VIZ 预算/callback 注册表）→ 产出独立 `assignment_policy.json`
   - pre-render：`evaluate_asset(stage=pre-render, displayed_contents=ledger)` + `check_namespace`
   - `evaluate_crop`（cover 布局全覆盖；DEMOTE→contain 重排后复检）
   - 复用 render_v3 的 ffmpeg 段落逻辑（作为库函数复制进编排脚本，或以子进程调用其渲染段），**母片仅在 ok_all 且 gate 清洁时写出**
2. **exec 隔离**：所有中间产物写 `render/<exec_id>/` 子目录；母片写 `render/final_long_<exec_id>.mp4` + 哈希登记；消灭跨 exec clip 复用。
3. **失败路径**：任一 clip 失败 → 停止该分部、不写母片（或写出 `.unusable` 后缀）；时间轴/srt 从实际成功的拍重建。
4. **共享输入注册表**：run manifest 增加 `frozen_shared_inputs: [prod01_plan]`，namespace_guard 对注册表内路径放行（消除 R-L3 矛盾）。
5. **VIZ 禁令硬编码化**：编排脚本读取 manifest 的 `production_viz_rollout`；非 AUTHORIZED 时路由校验直接拒绝 VIZ 动作（替代"脚本纪律"）。
6. **QA 持久化**：gate manifest + policy ledger + pre/crop 报告写入 `<run>/qa/`。
7. **preflight 修补**（可并入接线授权）：删除 `or True` 恒真检查、母片比对改全哈希——此项触碰 run03 现有脚本，需单独授权或在新编排脚本内重做等价检查。

## 6. 接线后需新增的回归测试

| # | 测试 | 断言 |
|---|---|---|
| T1 | 链序强制 | 未过候选门的候选进入 policy → 必须 ineligible（policy 输入构造即拒绝） |
| T2 | namespace 拒绝 | retrieval_index 含命名空间外条目 → 候选门 BLOCK，渲染决策 0 泄漏 |
| T3 | 全局兜底废除 | 无素材拍 → BLANK_CARD（绝不出现"首个素材填充 N 拍"） |
| T4 | clip 缓存隔离 | 同名 clip 不同 exec/不同 assignment → 必须重建（按 exec 目录或内容哈希命名） |
| T5 | 失败路径 | 单拍 clip 失败 → 母片不写出（或标记 unusable）；srt 与实际时间轴一致 |
| T6 | VIZ 禁令 | manifest viz_rollout=NOT AUTHORIZED + 路由含 VIZ → 路由校验失败 |
| T7 | focus 口径 | CV2 调用 focus 与冻结口径一致（空则为显式空，非遗漏） |
| T8 | 字幕-时间轴完整性 | 任拍缺席 → 后续拍时间轴整体重建，无漂移 |
| T9 | R1–R8 回归套件 | 对编排入口（而非旧脚本）全量重跑通过 |
| T10 | 60s/ABAB 全片性质测试 | 编排后全片决策序列 patterns=0、violations=0（等价 Config A 验收） |

## 7. 是否具备"授权后接线"条件

**具备。** 依据：
1. 四个正式模块 + schema + 单测（12/12）+ 回归（R1–R8 8/8）已就绪且经全片影子重放验证（Config A 与封存 VG1 逐项一致、Config B 严格治理行为计量入账）；
2. 接线缺口全部位于"新增编排入口"层，最小方案（§5）不需要触碰 render_v3/retrieval_run3/cv2_run/冻结 14 件/Retrieval/CV2；
3. 风险清单（§3）的每一项在 §5 中有对应消除动作，无"必须改历史生产代码才能接线"的阻塞项；
4. 前提条件（执行面）：接线需新授权，且应在一个**新 Run 命名空间**中做（或对既有数据只读影子接线），并满足§5-7 的 preflight 修补授权。

```
PRE-WIRE AUDIT = COMPLETE
链路 = 不可严格串成（四模块零接线；Gate/Crop 段缺失；QA 未持久化）
绕过 = 四模块全部被绕过（现状即"无防线"），VIZ 在 run03 不可能、在共享层无强制
最高风险 = 复用 render_v3 模板即复现 Run02 P0（借用无账本 + 全局兜底填充）
最小修改 = 新编排入口 + exec 隔离 + 失败路径 + 共享输入注册表 + VIZ 禁令硬编码化 + QA 持久化
新增回归 = T1–T10
接线条件 = 具备（待授权；新 Run 命名空间执行）
本轮零修改 · 零生产 Run · 零 Retrieval/CV2 调用
STOP
```
