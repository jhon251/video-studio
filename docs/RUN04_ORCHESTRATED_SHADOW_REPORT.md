# RUN04 Orchestration 接线实现 + 影子重放报告

- 日期: 2026-09-10 · 授权: 接线前审计（PREWIRE_AUDIT_20260910）后的下一阶段——仅创建新编排入口
- 交付物: `output/run04/`（独立命名空间）
  - `run04_render_orchestrated.py`（入口）· `orchestrator_core.py`（链序核心库）· `run04_manifest.json`（共享输入注册表+硬门槛）· `tests/test_orchestrator.py`（B+C 套件）· `exec/<exec_id>/`（完全隔离的执行目录）· `qa/latest.json`（持久 QA）
- 执行顺序: A 实现 → B 单测 → C T1–T10 → D 影子重放 → E 审计 → F 本报告 → G STOP

## 1. 已建立的严格生产链（每段一个显式函数，任何失败即 STOP）

```
P0/P1(冻结种子) → Preflight-v2 → Retrieval(冻结) → [Candidate Gate] → CV2(冻结)
→ Assignment = Global Reuse Policy → Pre-render Integrity Gate → Crop/Layout(+Crop Recheck)
→ Render(计划；生产模式被门控) → Persistent QA
```

先质量 Gate 后 Policy 已由构造固化：候选先过确定性 Gate + 冻结 CV2 才进入 `run_reuse_policy` 的合格池；渲染计划只从 policy 决策构建——不存在未过 Policy 的素材进入 Render 的路径。

## 2. PREWIRE 审计八项"彻底消除"逐条对账

| 要求 | 实现 |
|---|---|
| 废除 ultimate fallback 首素材填充 | 编排层无该机制；无合法来源 → BLANK_CARD（T3 专项证明：1 素材 + 多拍 → 1 展示 + 诚实空位） |
| 未过 Integrity Gate 的素材进入 Policy | 候选级确定性门先于 CV2/policy（T1 证明：gate-block 与 cv2-reject 双路径都不可达决策） |
| 未过 Policy 的素材进入 Render | render_plan 仅由 policy decisions+ledger 构建（结构上无旁路） |
| 跨 Run cache 复用 | 每 exec 唯一目录，重复 exec_id 直接拒绝（T4） |
| 任意 local_path 直接信任 | 注册表哈希锚定 + namespace 决策 + 逐候选 Gate 三重验证（T2） |
| VIZ 未授权进入生产路由 | plan_viz_guard + manifest 授权位；未授权时任何 VIZ 意图 → STOP（T6） |
| 失败后继续写母片 | 影子模式不写母片；生产模式需 manifest 显式翻转 + 全段清洁；失败路径只持久化 STOPPED QA（T5） |
| QA 只存在内存/临时输出 | qa_summary/ledger/gate/namespace/crop/prerender/shot_provenance/assignment_policy 全部落盘 exec 目录 + run04/qa/latest.json |

另：**preflight `or True` 恒真检查已在新层修复**（preflight_v2 全哈希母片比对 + 注册表哈希锚定 + 14/14 指纹），历史 preflight_gate.py 未触碰。

## 3. 测试结果

| 套件 | 结果 |
|---|---|
| B 单测（preflight 修正/执行隔离/G5-G7 advisory 结构） | 3/3 PASS |
| C T1 链序强制 / T2 namespace 拒绝 / T3 兜底禁止 / T4 cache 隔离 / T5 failure-stop / T6 VIZ 禁令 / T7 CV2 focus 口径（0 调用+冻结口径声明）/ T8 字幕完整性 / T9 R1–R8 迁移 / T10 全片模式 | **10/10 PASS** |
| T9 内嵌 R1–R8 回归 | 8/8 PASS |
| orchestration 模块单测（既有） | 12/12 PASS |

## 4. D：Run04 正式影子重放（exec: `RUN04_SHADOW_OFFICIAL_20260910`）

输入 = 冻结注册表（prod01_plan + run03 retrieval/CV2/TTS，SHA256 锚定，Retrieval/CV2 零调用）：

| 硬门槛 | 结果 |
|---|---|
| correspondence ≥ 51 | **81** ✅（对 run03 的 84：-3 为 Gate 诚实重排——低清/重复候选按规换池或转借用） |
| HN/Fallback 增幅 ≤ +5pp（对 run03 基线 16.8%） | **19.8%（+3.0pp）** ✅ |
| 全片 ABAB / ABA / A?A / adjacent | **0 / 0 / 0 / 0** ✅ |
| policy violations | **0**（无 60s 违规、无借用者超限、无内容 >2 展示） |
| namespace leakage | **0**（438 候选逐一路径判定；实验标记路径 0 进入决策） |
| G5/G7 单独 BLOCK | **0**（结构禁止 + prerender_blocks=0） |
| R1–R8 捕获 | R1 裁切（fixture DEMOTE vis=0.387/shift=25 + 重放 11 拍 contain 降级）、R2/R7（T9 端到端 exp225 阻断）、R3（G3 强制 contain 10 拍）、R4（内容合并）、R5/R6（模式归零）、R8（回调注册机制）✅ |
| CV2 重跑 | **0 次调用**（冻结口径：focus=empty 如实声明） |
| render 模式 | **DEFERRED_PRODUCTION_NOT_AUTHORIZED**（未授权不产母片） |

重放产物（exec 目录 11 件）：preflight_v2 / gate_decisions（433 判定：247 合格/186 不合格含原因）/ namespace_decisions / assignment_policy / prerender_gate / crop_recheck / render_plan / ledger+rows / shot_provenance（101 行全链） / qa_summary。

**逐 shot 溯源链示例**：beat → policy(action/cls/borrow_from/reason) → content_id → material_id → cv2 判定分 → 候选门判定 → namespace 决策 → prerender 判定 → crop 布局 → render 计划态。

**接线一致性修正（实现中发现）**：Integrity Gate 的 G3 DEMOTE（竖构图强制 contain）必须被 Crop/Layout 消费——已接线（10 拍 gate-forced contain + 1 拍语义风险 contain，90 拍 cover）。

## 5. E：完整性审计（实现后）

- 冻结 14 件指纹 **14/14 一致**
- 母片：run01 `ff119fcd` / run02 `ad52a0c0` / run03 `871489f9` / baseline `7e148585` 全部不变；run03 assignment `b220eeb8` 不变
- render_v3 / retrieval_run3 / cv2_run / 历史脚本：零修改；Retrieval/CV2：零调用
- 生产读取范围：仅注册表内冻结输入 + run03/asset_cache（生产种子资产）；audit/pilot/experimental 命名空间零读取

## 6. 遗留与边界

1. 影子模式未执行 ffmpeg 渲染（按授权：Production Run = NOT AUTHORIZED）；生产模式下 render 段按 render_plan 执行的逻辑需在授权时补足并附带 T4/T5 的执行级测试
2. CV2 裁切带实判与人工盲测仍待 API 额度/评分者（与前两轮相同的外部阻塞）
3. G5/G7 保持 advisory，独立校准未做（结构上已无法单独 BLOCK）

```
ORCHESTRATED SHADOW = PASS
Production Run = NOT AUTHORIZED
状态 = Visual Orchestration Layer 已接线于 Run04 编排入口（影子优先）· 冻结件与历史 Run 零触碰
未自动启动任何正式 Run04/Run03
STOP——等待授权
```
