# β-3′（主体锚定词相邻守卫）离线仿真 + Shadow 报告

- 日期: 2026-09-11 · 授权: **仅 β-3′**，离线仿真 → Shadow，**禁止正式渲染**（严格遵守：未重渲染、母片未动）
- 判据（按授权实现）：**同 content_domain + 共享显著词中至少一个"主体锚定词"**；锚定词必须出现在该拍对的 evidence_core 或旁白语义中；映射表**仅** `ultrasound ↔ 超声`
- 未做: F-α / F-γ / F-δ（按要求等 β-3′ 结果后再联合实施）· 未扩关键词表 · 未调阈值 · 未扩规则范围 · 未改 60s/≤2 次/canonical order/G10 阈值

---

## 1. 代码改动（2 个文件，均为"manifest 驱动、默认关闭"）

| 文件 | SHA256[:16] | 改动 |
|---|---|---|
| `src/video_studio/orchestration/global_reuse_policy.py` | `8f1a527f85053d23` | `ReusePolicyConfig.family_ctx` 新增；PASS 1 在选定候选前增加守卫：同域 且 共享映射词 ∩ 锚定词集合 非空 → 跳过该候选并写审计条目 `FAMILY_GUARD_SKIP` |
| `output/run04/orchestrator_core.py` | `8e91e024b937e25d` | 新增 `family_ctx_from_manifest()`：**只从 manifest 读取** `fixes.family_guard` 与 `fixes.family_anchor_map`（空表=关闭，fail-closed）；把触发次数写入 `stages.family_guard` |

**默认行为不变**：`run05_manifest.json` / `run05_manifest_prod_fix1.json` 无 `fixes` 字段 → 守卫关闭，FIX-1 母片行为与结果不受影响。

## 2. 判据的可审计实现（无隐式扩展）

```
同域判定        : G10 信号域（经本体同义词归一）相等
映射词          : 仅 manifest.fixes.family_anchor_map 提供的键（本次 = {ultrasound: [超声]}）
标题侧          : 候选素材标题中出现的映射键（本片 = C793 / C797，均含 ultrasound）
锚定侧          : 该拍（或其已决策的相邻拍）的 narration + ECT.evidence_core 中出现映射值（超声）
触发条件        : 同域 ∧ 两候选的映射词交集 ∩ 锚定集 ≠ ∅
```

## 3. 离线仿真（生产函数，A/B 对照）

| 指标 | A：守卫关闭（FIX-1） | **B：守卫开启（β-3′）** |
|---|---|---|
| CORRESPONDING | 88 | **87**（S12-B02 → FALLBACK） |
| **域一致 CORRESPONDING** | **78** | **77** ✅ 与授权预期一致 |
| HN/FALLBACK | 13 | **14** |
| 触发清单 | — | **仅 1 条**：`S12-B02 ↔ S12-B01`，domain=medicine_clinical，共享锚定词 `ultrasound` |
| 误伤（S17→S18 / S06 等） | — | **0 条** ✅ |
| 代价 | — | **1 拍** ✅ |
| 成片级 <60s / adjacent / >2 次 / ABA / ABAB | 0/0/0/0/0 | **0/0/0/0/0** |
| canonical order | 101 拍 | 101 拍（不变） |

**仿真验收 = PASS**（`output/run05/beta3_sim.json`）

## 4. Shadow（未渲染）

`exec_id = RUN05_SHADOW_BETA3` · `render_mode = DEFERRED_PRODUCTION_NOT_AUTHORIZED` · **master = None**

| 项 | 值 |
|---|---|
| 状态 | `ORCHESTRATED_SHADOW_OK` |
| CORRESPONDING / **域一致** | **87 / 77** |
| NO_EXPECTATION / HN-Fallback | 10 / **13.9%（14 拍）** |
| ns_leakage / patterns / violations / prerender blocks | **0 / 全 0 / 0 / 0** |
| G10 验收 | `domain-consistent=77 >= 60: True` |
| **新阶段** | `family_guard: guard=True map=['ultrasound'] skips=1` · `canonical_order: 101 beats` · `order_invariant: 101 beats, render==canonical` |
| 成片级审计（独立重算） | **<60s=0 · adjacent=0 · >2 次=0 · ABA=0 · ABAB=0** |
| S12-B01 | CORRESPONDING / EVIDENCE / `r3_S12-B01_3`（保留） |
| **S12-B02** | **FALLBACK / BORROW**（源 `r3_S08-B02_2`，第 14 拍邻位，合法：≥60s、cap≤2、借用 ≤1 方、带角标）→ **超声相邻重复消除** |
| S17-B03 / S18-B01（防误伤核对） | 均 **未变**（CORRESPONDING，`r3_S17-B03_0` / `r3_S18-B01_0`） |

**Shadow 验收 = PASS**（`output/run05/beta3_shadow_verify.json`）

## 5. 回归

| 套件 | 结果 |
|---|---|
| 编排器测试（含 T14 G10 接线） | **17/17 PASS** |
| R1–R8 回归夹具 | **8/8 PASS** |
| G10 预生产静态审计 | **40/40 PASS** |
| 冻结件 / 历史母片 | 未触碰（本次未重渲染） |

## 6. 判定

```
β-3′（主体锚定词相邻守卫）= 离线仿真 PASS + Shadow PASS（未正式渲染）
判据 = 同域 + 共享映射词 ∩ 锚定词；映射表仅 ultrasound ↔ 超声（manifest 驱动、默认关闭）
命中 = 仅 S12-B01→S12-B02（1 条）· 误伤 = 0 · 代价 = 1 拍
指标 = 域一致 78 → 77 · CORRESPONDING 88 → 87 · HN 13 → 14（13.9%）· NO_EXPECTATION 10（不变）
规则 = 60s / ≤2 次 / 借用≤1 方 / canonical order / G10 阈值 全部未改；审计条目 FAMILY_GUARD_SKIP 入档
回归 = 编排器 17/17 · R1–R8 8/8 · 静态审计 40/40
未实施 = F-α / F-γ / F-δ（等待联合实施授权）· 未正式重渲染
STOP——等待裁决：是否以本 β-3′ 结果联合实施 F-α + F-γ + F-δ
```
