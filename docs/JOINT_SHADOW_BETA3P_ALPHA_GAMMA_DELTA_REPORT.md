# 联合 Shadow 报告：β-3′ + F-α + F-γ + F-δ（未正式渲染）

- 日期: 2026-09-11 · 授权: 四项联合 Shadow，**禁止正式渲染**
- exec: `output/run05/exec/RUN05_SHADOW_JOINT` · 状态 **`ORCHESTRATED_SHADOW_OK`** · `render_mode = DEFERRED_PRODUCTION_NOT_AUTHORIZED` · **master = None**
- manifest: `output/run05/run05_manifest_shadow_joint.json`（sha256 `675c5f7789a71b85`）
- 数据: `joint_build.json` · `joint_sim.json` · `joint_real_diff.json` · `joint_verify.json` · `joint_shadow_result.json`

---

## 1. 实施内容（保持 β-3′ 现状不变）

| 项 | 实现 | 关键约束 |
|---|---|---|
| **β-3′**（不变） | manifest 驱动守卫：同域 + 共享映射词 ∩ 锚定词；映射表 **仅 `{ultrasound: [超声]}`** | 未扩词表、未调阈值 ✓ |
| **F-α** | 借用择源新增惩罚项：源内容在 **≥120s 窗口内已被 EVIDENCE 展示** → score += 1000（**仅偏好**，合法性判定不动） | ≤2 次 / 借用≤1 方 / ≥60s **全部未改** |
| **F-γ** | 新 ECT（`evidence_core_table_v1_1_fg.json`）**仅改 S20-B02 与 S26-B02** 两拍：expectation→DOMAIN_BOUND（S20-B02 primary=[human_perception_science, neuroscience]；S26-B02 primary=[vr_ar]） | 其他 META/CONCEPT 逻辑未动；本体未扩；逐 beat 断言 diff = 这两拍 |
| **F-δ** | 两张 1920×1080 结构卡：`viz_card_five_layer_framework.png`（149KB）/ `viz_card_five_layer_timeline.png`（114KB）；仅注入 S02-B01 / S33B-B01；`cls=VIZ_STRUCTURAL`、**独立 QA 桶**、gate 记录 `viz_narrow_authorized`、**fail-closed 断言**（卡出现在非授权拍或 gate 失败即 STOP） | `production_viz_rollout` **仍为 NOT AUTHORIZED**；未生成第三张、未授权其他拍 |

改动文件（3 个源文件 + 新增 run05 工件）：
`global_reuse_policy.py` `11d461af61fc19e6` · `orchestrator_core.py` `8ec54572257e3e49` · `schemas.py` `672671094c3b1f3b`；
新工件：`run05/g10/evidence_core_table_v1_1_fg.json`（`88b11b52…`）· `run05/retrieval_index_joint.json`（`27be3a77…`）· `run05/cv2_results_joint.json`（`c02d71b8…`）· 两张卡 PNG。

## 2. 逐项指标（A = FIX-1 基线 → B = JOINT）

| 指标 | A（FIX-1） | **B（JOINT）** | 说明 |
|---|---|---|---|
| **domain-consistent** | 78 | **78** | **未下降**（优于预估 76：F-γ 的 S26-B02 找到替代合格候选；β-3′ −1 被抵消） |
| CORRESPONDING | 88 | **86** | −2 = β-3′ S12-B02 + F-γ S20-B02 |
| HN/FALLBACK | 13 | **13** | +2（S12-B02/S20-B02 降级）−2（S02-B01/S33B-B01 转 VIZ） |
| **NO_EXPECTATION** | 10 | **8** | F-γ −2 |
| **VIZ 结构卡** | 0 | **2** | 独立桶，不计入 domain-consistent |
| <60s / adjacent / >2 次 / ABA / ABAB | 0/0/0/0/0 | **0/0/0/0/0** | ✓ |
| G10 验收 | 78≥60 | **78≥60 ✓** | `g10_acceptance_ok: true` |
| ns leakage / violations / prerender blocks / crop demotes | 0 | **0 / 0 / 0 / 0** | ✓ |
| FIX-1 canonical order / order invariant | PASS | **PASS**（101 拍，render==canonical） | ✓ |
| 渲染模式 / 母片 | DEFERRED / None | **DEFERRED / None** | 未正式渲染 ✓ |

## 3. 各修复的实测行为

**β-3′（命中/误伤）**：触发 **1 次**，`S12-B02 ↔ S12-B01`（domain=medicine_clinical，共享锚定词 `ultrasound`）→ **零误伤**（S17→S18、S06、S04B 等均未触发）。
- S12-B01 保留（CORRESPONDING，`r3_S12-B01_3`）；S12-B02 → FALLBACK/BORROW（`r3_S04B-B02_1`）→ **3:03–3:13 超声相邻重复消除**。

**F-α（重选数量）**：惩罚事件 **186 次**（覆盖 13 个借用拍的候选源评估）→ **15 个借用拍中有 12 个改源**（其余为级联）。

| 借用拍 | A 源 | B 源 |
|---|---|---|
| S01-B03 | S08B-B01 | **S09B-B01** |
| S02-B03 / S02-B04 | S09B-B01 / S09B-B02 | **S09B-B02 / S10-B01** |
| S12-B02 | （新增借用） | S04B-B02 |
| S20-B02 | （新增借用） | S12-B01 |
| S20-B03 | S17-B02 | **S11-B03** |
| S22-B02 | S18B-B02 | **S15-B01** |
| S27-B01 / S27-B03 | S30-B04 / S30B-B02 | **S19-B01 / S19-B02** |
| S32-B03 / S33-B02 | S29-B02 / S29-B01 | **S25-B02 / S25-B01** |
| **S33B-B02** | **S30-B02（眼部测试同图 61.2s）** | **S26-B01** → **眼部测试重复消除** ✓ |
| S33B-B03 | S30-B03 | **S26-B02** |

**F-γ（两拍结果）**：
- **S20-B02 @5:05**：Audi E-Prix 赛车照（transport）→ **REJECT → FALLBACK/BORROW**（借用 `r3_S12-B01_3`，带角标）✓ 目标达成；
- **S26-B02 @6:36**：原 `ss2_S26-B02_1`（transport 未来隧道）→ REJECT，但该拍**存在另一合格候选** `ss2_S26-B02_5`（vr_ar）→ **仍为 CORRESPONDING**（未降级）✓。

**F-δ（两张卡）**：

| 拍 | 时间 | cls | 素材 | gate 记录 | render_plan | 角标 | prerender |
|---|---|---|---|---|---|---|---|
| **S02-B01** | 0:17 | `VIZ_STRUCTURAL` | `viz_five_layer_framework` | `viz_narrow_authorized` | `viz_card_five_layer_framework.img.png` | 无 | final=PASS |
| **S33B-B01** | 8:31 | `VIZ_STRUCTURAL` | `viz_five_layer_timeline` | `viz_narrow_authorized` | `viz_card_five_layer_timeline.img.png` | 无 | final=PASS |

- 生成 ✓（1920×1080，落盘允许命名空间）· 渲染计划引用 ✓（**实际 mp4 渲染未执行**：DEFERRED）· QA 独立桶 = **2** ✓
- **无越权**：卡只出现在这两个授权拍；`production_viz_rollout` 仍 NOT AUTHORIZED；未生成第三张 ✓

## 4. 真实分配差异（16 拍；已排除 `content_id` 重编号噪声）

`joint_real_diff.json`：**15 个借用源变化 + 1 个本拍候选换选（S26-B02）**，其中：
- β-3′ 造成 **1 拍**（S12-B02）、F-γ 造成 **1 拍降级 + 1 拍换选**（S20-B02 / S26-B02）、F-δ 造成 **2 拍**（S02-B01 / S33B-B01 转结构卡）、F-α 及其级联造成其余借用源变化。
- 核对：S30-B02 与 S33B-B02 **不再是同图**（眼部测试重复消除）；S12-B01/B02 **不再同时出现超声**；Audi 照片 **已下屏**。

## 5. 回归

| 套件 | 结果 |
|---|---|
| 编排器测试（含 T14 G10 接线） | **17/17 PASS** |
| R1–R8 回归夹具 | **8/8 PASS** |
| G10 预生产静态审计 | **40/40 PASS** |
| FIX-1 正式母片哈希 | `0DCF132387748A91…` **未变**（未重渲染） |
| 冻结件 / Run01–04 母片 | 未触碰 |

## 6. 判定

```
JOINT（β-3′ + F-α + F-γ + F-δ）Shadow = PASS（未正式渲染）
domain-consistent 78（未降，优于预估 76）· CORRESPONDING 88→86 · HN/FB 13→13 · NO_EXPECTATION 10→8 · VIZ 卡 2
β-3′ = 命中 1（S12-B02）· 误伤 0 · F-α = 186 惩罚事件 / 12 个借用改源（含眼部测试重复消除）
F-γ = Audi 下屏（S20-B02→HN）· S26-B02 换用合格替代候选（未降级）
F-δ = 2 张卡、独立 QA 桶、零越权、VIZ 全局权限仍关闭
规则 = 60s / ≤2 次 / 借用≤1 方 / canonical order / G10 阈值 / 本体 / 词表 全部未改
检查 = <60s 0 · adjacent 0 · >2 次 0 · ABA 0 · ABAB 0 · ns_leakage 0 · violations 0 · prerender 0
回归 = 编排器 17/17 · R1–R8 8/8 · 静态审计 40/40 · FIX-1 母片未变
观察（非指标下降）= S20-B02 改借 `r3_S12-B01_3`（5:05 出现一张 HONEST_NEUTRAL 借用超声图，与 3:03 的 S12-B01 同内容、间隔 122s ≥60、cap 2、带角标，合规）
未执行 = 正式渲染 · F-γ 之外的其他 META/CONCEPT 改动 · 词表扩展 · 阈值/规则变更
STOP——等待授权：是否以本联合结果正式重渲染；是否处理上述 S20-B02 借用观察
```
