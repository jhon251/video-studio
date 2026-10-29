# FIX-1 实施报告：Canonical Render Order（单一顺序源 + fail-closed 不变量）

- 日期: 2026-09-11 · 授权: **立即实施 FIX-1，除此之外不改规则**
- 执行范围: 仅消除"政策顺序 ≠ 成片渲染顺序"导致的 reuse 检查错位
- 未做: 未正式重渲染（母片 `7bcaf109…` 原样保留）· 未改 60s/≤2 次/借用≤1 方等任何规则 · 未改 G10/ECT/CV2/验收阈值 · 未扩池 · 未推进 VIZ

---

## 1. 代码改动（唯一改动文件）

| 项 | 值 |
|---|---|
| 文件 | `output/run04/orchestrator_core.py` |
| 改动前 SHA256 | `09204D625D1A3BFC53EBB84D2012341ED441CCA1C593D7C5C868F6B7479CDD8D` |
| 改动后 SHA256 | `B9BCE964D4DB27D74A39A456B6FBC59CB56D9BA1D767064328BF7032103C94D3` |
| 回滚备份 | `output/run05/fix1_backup_orchestrator_core.py.bak`（= 改动前哈希） |
| 补丁存档 | `output/run05/fix1_diff.patch`（5 个 hunk，+46 / −9 行） |

**5 处改动**：

1. **`run()`：定义唯一 canonical order** `canon = sorted(beats, key=beat_id)`，时间轴（start/end）**在 canonical order 上赋值**；`reuse policy`、`beats_by_id`、`matmap` 全部改为消费 `canon`。
2. **`run()`：新增 fail-closed 不变量**——`render_order == canon_ids` 否则 `RuntimeError` → STOP、不产母片；并在 timing 记录 `canonical_order` / `order_invariant`。
3. **`render_plan_stage(..., canon_order=...)`**：按传入的 canonical order 输出 clip_specs（不再自行 `sorted`），并把 `canonical_order` 写入 `render_plan.json`。
4. **`qa_stage()`：顺序守卫**——adjacent/ABA/ABAB/60s 指标在 canonical order 上计算，且校验 `decision order == canonical timeline order`，不一致即 `RuntimeError`。
5. 上述新阶段的 timing/审计字段（`canonical_order`、`order_invariant`）入 `qa_summary.json`。

**规则零改动**（逐项核对）：`min_display_gap_s=60.0` · 同内容 ≤2 次 · 禁相邻同内容 · `max_borrowers_per_content=1` · `same_chapter_borrow_penalty=100.0` · G10 全部规则 · ECT · CV2 约定 · 验收阈值（≥60 次数 / 错配 0）· manifest 与冻结件。

---

## 2. 离线生产函数回归（改动后，先跑）

用**生产函数原样**（`candidate_gate_stage` → canonical 时间轴 → `run_reuse_policy` → `prerender_stage` → `crop_stage` → `render_plan_stage`）重算：

| 指标 | 改动前（已发布） | **改动后（FIX-1）** |
|---|---|---|
| canonical order == sorted(beat_id) | 时间轴用 plan 顺序 ✗ | **True ✓** |
| order invariant（render == canonical） | 不存在 | **True ✓** |
| **CORRESPONDING** | 88 | **88（不变）** |
| 域一致 CORRESPONDING | 78 | **78** |
| NO_EXPECTATION / HN | 10 / 13 | **10 / 13** |
| **成片级 60s 违规** | **1**（C991：41.5s） | **0 ✓** |
| 成片级 adjacent 同内容 / >2 次 | 0 / 0 | **0 / 0** |
| 分配变化 | — | **15 拍**（12 例借用源 + 3 例本拍候选换选：S25-B01/S18B-B01/S18B-B02，均保持 CORRESPONDING） |

数据：`output/run05/fix1_regression.json`

## 3. fail-closed 负向测试（证明不变量真的会拦）

| 测试 | 结果 |
|---|---|
| A 正向：canonical 顺序通过不变量 | PASS |
| **B 负向：打乱顺序 → 被不变量检出（run() 将 RuntimeError → STOP，无母片）** | PASS |
| **C 负向：决策集与 canonical 时间轴不一致 → QA 守卫抛 `QA order invariant violated`** | PASS |
| D 正向：真实 canonical 拍集被 QA 接受 | PASS |

数据：`output/run05/fix1_negative_tests.json`

## 4. 回归套件

| 套件 | 结果 |
|---|---|
| 编排器测试（含 T14 G10 接线） | **17/17 PASS** |
| R1–R8 回归夹具 | **8/8 PASS** |
| G10 预生产静态审计（AST/文本链路检查） | **40/40 PASS** |
| 冻结模块 | 14/14（未触碰） |
| 历史母片 | run01–04 全部哈希不变 |

## 5. Shadow Run（改动后，未渲染）

`exec_id = RUN05_SHADOW_FIX1` · exec 目录 `output/run05/exec/RUN05_SHADOW_FIX1`

| 项 | 值 |
|---|---|
| 状态 / 渲染模式 | `ORCHESTRATED_SHADOW_OK` / `DEFERRED_PRODUCTION_NOT_AUTHORIZED` |
| 母片 | **None（未渲染，符合授权）** |
| CORRESPONDING / 域一致 / NO_EXP / HN | **88 / 78 / 10 / 13（12.9%）** |
| ns_leakage / patterns / violations / prerender blocks | 0 / 全 0 / 0 / 0 |
| **新增阶段** | `canonical_order: 101 beats, order=sorted(beat_id)` · `order_invariant: 101 beats, render==canonical` |
| G10 验收 | `domain-consistent=78 >= 60: True` |
| **成片级顺序审计（独立重算）** | **60s 违规 0 · adjacent 0 · >2 次 0** |

**审片相关项在 FIX-1 下的变化**：

| 审片项 | 改动前 | FIX-1 |
|---|---|---|
| C991（S30B-B01 7:47 ↔ S33-B02 8:29，41.5s） | **违规** | ✅ 消除（S33-B02 改借 `ss2_S29-B01_11`） |
| 3:54 / 5:10 同图重复（S16-B03 ↔ S20-B03） | 存在（合法借用） | ✅ 消除（S20-B03 改借 `r3_S17-B02_4`） |
| **3:03–3:13 超声同主体相邻（S12-B01/B02）** | 存在 | ❌ **未变**——不属 FIX-1 范围（需 FIX-3 规则扩展或 FIX-4 定向检索，均需授权） |

## 6. 判定

```
FIX-1 = IMPLEMENTED & VERIFIED（未正式重渲染）
唯一改动 = output/run04/orchestrator_core.py（09204D62… -> B9BCE964…，备份+补丁已存档）
机制 = canonical render order = sorted(beat_id) 统一驱动 时间轴 / reuse policy / render_plan / QA 指标
      + fail-closed 不变量（run(): render==canonical；qa_stage(): decision==canonical）
离线回归 = CORRESPONDING 88（不变）· 域一致 78 · 成片级 60s 违规 1 -> 0 · 15 拍分配变化
负向测试 = B/C 均被拦（打乱顺序 / 决策集不一致 -> STOP）· A/D 正向通过
套件 = 编排器 17/17 · R1–R8 8/8 · 静态审计 40/40 · 冻结 14/14 · 历史母片哈希不变
Shadow = ORCHESTRATED_SHADOW_OK · 88/78/10/13 · leakage 0 · patterns 全 0 · 无母片
规则零改动 = 60s / ≤2 次 / 借用≤1 方 / 同章节惩罚 / G10 / ECT / CV2 / 验收阈值 全部原样
未解决 = 超声同主体相邻（S12）仍为规则盲区（FIX-3/FIX-4 未执行，待授权）
STOP——等待授权（是否正式重渲染 / 是否推进 FIX-3/FIX-4）
```
