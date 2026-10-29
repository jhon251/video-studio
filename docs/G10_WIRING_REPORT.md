# G10 Domain Consistency Gate — 生产接线报告

- 日期: 2026-09-10 · 授权阶段: G10 接线（shadow/replay + 回归；不启动新正式生产 Run）
- 接线对象: `output/run04/`（orchestrator_core.py + run04_manifest.json g10 配置 + g10/ 资产三件）
- 链序落位: `候选级 G10（Gate→CV2→G10→Policy 合格池）→ … → Pre-render G10 复核（仅 CORRESPONDING 主张）→ Render 计划 → QA`

## 1. 接线内容（全部位于 run04 编排层；冻结模块/历史母片零触碰）

| 组件 | 实现 |
|---|---|
| 资产装载 | `load_g10_assets`：本体 v1.1 + ECT + 池信号三件 **SHA256 锚定**，任一错配 raise（fail-closed） |
| 候选级判定 | `g10_candidate_verdict`：R1 自指外来→REJECT · R2 缺信号/低置信/非法域→REVIEW · R4 拼词+泛化库存→LOW · R5 primary→PASS · R6 近域→REVIEW（**签核放行→PASS**）· R7 异域→REJECT · R8 无期望。规则序修正：R4 先于 R8（堵 META 拍拼词图绕行，审计发现于接线自测） |
| 合格池 | Policy 输入 = 确定性 Gate + 冻结 CV2 + **G10 PASS** 三者交集；REJECT/LOW/REVIEW 候选不进 CORRESPONDING |
| Pre-render 复核 | 对每个 CORRESPONDING 主张展示重算 G10；非 PASS/NO_EXPECTATION = policy/gate 不一致 → STOP。BORROW 豁免（已角标） |
| 人工机制 | `review_signoffs`（5 拍近域签核，记录 authorized_by/at/ref；S19-B02 明确排除）· `signal_overrides`（S20-B03 抽象渲染人工覆盖→HN） |
| 硬门槛 | 域一致 CORRESPONDING ≥60 · 域错配上屏=0（结构性：仅 PASS 可为 CORRESPONDING）· 未达 → `G10_ACCEPTANCE_FAIL` 不产母片 |

## 2. 池信号覆盖（本轮新增）

- 全池 438/438 唯一素材完成 rubric v2 信号（deepseek-flash；pro 禁用；402 熔断；增量落盘）——Policy 重选时每个候选都有域信号，不存在"无信号盲区"

## 3. Shadow Replay 结果（exec/RUN04_G10_SHADOW_20260910）

| 指标 | Run04 现状母片 | G10 接线 shadow | 新口径 |
|---|---|---|---|
| **域一致 CORRESPONDING** | 81（含域错配 27） | **60（59.4%）** | **≥60 ✅** |
| 域错配上屏 | 27 | **0** | =0 ✅ |
| HN/FALLBACK（全角标） | 19.8% | **33.7%**（34 拍） | 诚实标识 ✅ |
| NO_EXPECTATION（META 拍，单列不冒充） | — | 7 | ✅ |
| ABAB/ABA/A?A/adjacent | 0 | **0** | ✅ |
| policy violations / ns_leakage / prerender G10 阻断 | — | 0 / 0 / 0 | ✅ |
| CV2/Retrieval 调用 | — | **0**（池信号已冻结） | ✅ |
| render_mode | — | DEFERRED_PRODUCTION_NOT_AUTHORIZED | ✅ |

签核与降级落点验证：5 个签核拍（S09-B02/S12-B02/S13-B01/S17-B02/S29-B02）全部上屏本拍素材为域一致 CORRESPONDING；S20-B03 降级 HN（借用 BCI 图解+角标）；S19-B02 未签→HN；S02-B01/S33B-B01/S33B-B02/S29-B04 等已知错配家族全部 HN 角标。

## 4. 回归结果

编排器 T1–T14（含 T14 G10 接线测试：域错配候选不得 CORRESPONDING + 本体哈希篡改 preflight FAIL）**17/17 PASS** · R1–R8 **8/8** · 模块单测 **12/12** · 冻结指纹 **14/14** · Run01–04 母片哈希不变（ff119fcd/ad52a0c0/871489f9/074985a5）· run03 assignment 不变

## 5. 接线中发现并修复

1. **规则序漏洞**（接线自测发现）：R8（无期望）原在最高优先 → META 拍的拼词图（S31-B01 "POLICY"）可绕过 R4 上屏。已按设计序修正（R4 先于 R8），S31-B01 三个拼词候选全部被拒、换显示池内正常素材（NO_EXPECTATION 桶）。
2. **BORROW 豁免语义**：prerender G10 复核仅约束 CORRESPONDING 主张；BORROW 已诚实角标，不再阻断（避免"借用必须同域"的过度约束）。

## 6. 成本变化（G10 开启后的正式口径）

| 指标 | 值 |
|---|---|
| 域一致 CORRESPONDING | **60/101（59.4%）**（Run04 母片 81 中 27 拍域错配/低证据全部移除） |
| HN/FALLBACK | **34/101（33.7%）**（全角标，含 5 签核拍释放的借用回退） |
| 信号成本 | 每版一次性全池信号 ~438 视觉调用（flash 档）；增量更新按新候选计 |
| 已知信号误差 | 1/101（S20-B03 抽象渲染过自信，已人工覆盖；rubric v2.1 修订项：抽象渲染→generic_stock_concept 指引） |

## 7. 生产运行条件判定

| 条件 | 状态 |
|---|---|
| G10 接线（双判定点+fail-closed） | ✅ |
| 新验收口径达成（域一致 60≥60、错配 0、诚实角标） | ✅（shadow 实测） |
| 回归全绿 + 冻结/母片完整性 | ✅ |
| 签核记录完整（REVIEW 5 拍 + S20-B03 覆盖） | ✅（manifest 内） |
| 生产执行器 | ✅（RUN04_PROD_20260910_01 已验证） |

**具备正式生产运行条件。** 启动下一次正式 Run（G10 口径首个生产母片）仅需：用户明示"启动 RUN04 G10 生产 Run"（现有生产授权与执行器已就绪，将产出替换母片候选 `final_long_<exec>` 供人工 QA）。

```
G10 WIRING = PASS
SHADOW ACCEPTANCE = PASS（域一致 60≥60 · 错配上屏 0 · 诚实角标 34 · 模式/违规/泄漏全 0）
回归 = 17/17 + 8/8 + 12/12 + 冻结 14/14 + 母片哈希不变
生产条件 = 具备（等待"启动正式 Run"指令；不自行启动）
零冻结件触碰 · 零历史母片修改 · Retrieval/CV2 零调用（池信号冻结复用）
STOP——等待授权
```
