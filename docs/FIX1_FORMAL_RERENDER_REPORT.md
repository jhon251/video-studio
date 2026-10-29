# FIX-1 正式重渲染报告（RUN05_PROD_FIX1）

- 日期: 2026-09-11 · 授权: **正式重渲染 FIX-1 版本**（不实施 FIX-3/FIX-4）
- 代码: 已验证的 FIX-1 补丁（`orchestrator_core.py` sha256 `b9bce964d4db27d7…`，原版备份 `09204d62…`）
- 输入/manifest: 与 S7 相同（run05 集成产物）；manifest 仅 3 处授权元数据差异
- **母片**: `output/run05/exec/RUN05_PROD_FIX1/final_long_RUN05_PROD_FIX1.mp4`
  **SHA256[:16] = `0dcf132387748a91`** · 30,879,599 B · 526.12s · 101/101 拍

---

## 1. 渲染前 preflight + order invariant（19/19 PASS，任一失败即 STOP）

```
[PASS] manifest 差异仅授权三键 · auth 互锁 · VIZ NOT AUTHORIZED
[PASS] 注册表 5/5 哈希（plan/retrieval/cv2/tts/font）
[PASS] G10 三件锚定（signals 753 · ECT 101 · 域 28）· ontology/ECT 与 run04 逐字节相同
[PASS] S20-B03 override 在位 · 签核 5 拍不变 · 验收阈值（≥60 / 错配 0）不变
[PASS] FIX-1 代码在位（canonical_order + order invariant 文本均存在）
[PASS] 先验母片存在（run01/02 校验）· exec id 空闲
[PASS] order invariant：canonical == sorted(beat_id)，101 拍，且等于全计划拍集
```
`output/run05/fix1_render_preflight.json`（`all_pass: true`）

## 2. 正式执行与核心指标

| 项 | 值 |
|---|---|
| 状态 / 渲染模式 | **`ORCHESTRATED_PRODUCTION_OK` / `PRODUCTION_READY`** |
| 新增阶段 | `canonical_order: 101 beats, order=sorted(beat_id)` · **`order_invariant: 101 beats, render==canonical`** |
| **CORRESPONDING** | **88** |
| **域一致 CORRESPONDING** | **78**（≥60 ✓，余量 +18） |
| NO_EXPECTATION / HN-FALLBACK | 10 / **13（12.9%，较基线 −3.9pp）** |
| G10 验收 | `domain-consistent=78 >= 60: True` · `g10_acceptance_ok: true` |
| gate | eligible 327 / ineligible 422 · G10 候选级拒绝 145 条（带规则+理由） |
| namespace leakage | **0** |
| policy violations / prerender blocks / crop demotes | **0 / 0 / 0** |
| reuse 模式指标 | adjacent 0 · gap2_AxA 0 · ABA 0 · ABAB 0 |

## 3. 完整 QA

| 项 | 值 | 门槛 |
|---|---|---|
| 母片时长 / 音频总长 / A/V delta | 526.12s / 525.97s / **0.15s** | ≤0.5s ✅ |
| 黑帧 | **0 / 105 采样** | =0 ✅ |
| 字幕 | **101/101 = 100%** | ≥95% ✅ |
| 渲染日志 | 101 clips + 5 parts + master（全部 exit 0） | ✅ |
| 角标 | 13 处 HN/FALLBACK 全部带"中性画面" | ✅ |
| provenance | 101/101 全链 | ✅ |

## 4. 成片真实顺序 + 规则复核（独立重算，非账面对齐）

- **成片顺序**：`render_plan.clip_specs` 顺序 == canonical == `sorted(beat_id)`；`render_plan.canonical_order` 已写入；master 由 5 个 part 顺序拼接（101 clips）。
- **帧级抽帧交叉验证**（从母片取像素，与台账所选素材 dHash 比对；因裁切/缩放/编码，期望 0–10）：

| 时间 | 台账素材 | hamming | 说明 |
|---|---|---|---|
| 3:05 | r3_S12-B01_3 | 5 | 审片项①超声（见 §5） |
| 3:11 | r3_S12-B02_3 | 7 | 审片项①超声 |
| 3:56 | ss2_S16-B03_11 | 1 | 3:54 处素材 |
| **5:11** | **r3_S17-B02_4** | **0** | 3:54/5:10 同图重复**已消除** |
| 5:44 | ss3_S23-B01_0 | 10 | SS3 修复拍 |
| 7:49 | r3_S30B-B01_2 | 8 | C991 主体 |
| **8:31** | **ss2_S29-B01_11** | **8** | C991 <60s 重复**已消除** |

- **成片级规则审计（独立重算）**：**<60s 重复 = 0**（改动前为 1）· adjacent 同内容 0 · >2 次展示 0 · ABA 0 · ABAB 0；13 个素材各展示 2 次（上限 2 ✓），全部近重复对（hamming=0）间隔 ≥60.6s。
- **全片 <60s 重复扫描**：**0 例**（无新增）。

## 5. 审片原问题逐条核对

| 审片项 | 改动前（`7bcaf109`） | **FIX-1 母片（`0dcf1323`）** |
|---|---|---|
| **3:04–3:13 超声 back-to-back** | S12-B01 3:03 / S12-B02 3:09（两张临床超声仪照片相邻） | **仍然存在（未变）** —— FIX-1 只修顺序，不涉及"同主体邻接"规则盲区；FIX-3/FIX-4 按令未实施 |
| **3:54 / 5:10 同图重复** | S16-B03 ↔ S20-B03 同一素材（C953） | ✅ **已消除**：5:10 改为 `r3_S17-B02_4` |
| **全片 <60s 重复** | 1 例（C991：41.5s） | ✅ **0 例**（S33-B02 改借 `ss2_S29-B01_11`） |

## 6. 与 FIX-1 shadow 的差异

| 项 | shadow（`RUN05_SHADOW_FIX1`） | 正式（`RUN05_PROD_FIX1`） |
|---|---|---|
| CORRESPONDING / 域一致 / NO_EXP / HN | 88 / 78 / 10 / 13 | **88 / 78 / 10 / 13（一致）** |
| **逐拍分配差异** | — | **0 拍**（101/101 相同） |
| 成片级 <60s 违规 | 0 | 0 |
| 母片 | 无（DEFERRED） | **`0dcf132387748a91`** |

→ shadow 与正式结果**完全一致**，投影/影子可信。

## 7. 与上一版母片（`7bcaf109`）的差异与历史完整性

- **15 拍分配变化**（12 例借用源变化 + 3 例本拍候选换选：S25-B01 / S18B-B01 / S18B-B02），**CORRESPONDING 88 → 88 不变**，域一致 78 → 78 不变。
- **历史母片与冻结件全部不变**（渲染后复核）：

| 对象 | SHA256[:16] |
|---|---|
| run01 母片 | `ff119fcd1c559b52` |
| run02 母片 | `ad52a0c0eb9a4491` |
| run03 母片 | `871489f94b61ed15` |
| run04 前版母片 | `074985a527759e1a` |
| run04 G10 母片 | `2f0e66871b76585f` |
| **上一版 run05 母片** | `7bcaf1093122a3d3`（原样保留，未覆盖） |
| **本次 FIX-1 母片** | **`0dcf132387748a91`** |
| 冻结模块 | **14/14 未变** |

## 8. 判定

```
FIX-1 FORMAL RE-RENDER = PASS
母片 = output/run05/exec/RUN05_PROD_FIX1/final_long_RUN05_PROD_FIX1.mp4 (sha16 0dcf132387748a91, 526.12s, 30,879,599 B)
preflight = 19/19（含 order invariant）· 状态 = ORCHESTRATED_PRODUCTION_OK · PRODUCTION_READY · G10 验收 78>=60 ✅
指标 = 88 CORRESPONDING / 78 域一致 / 10 NO_EXPECTATION / 13 HN(12.9%) · leakage 0 · violations 0 · blocks 0
QA = A/V 0.15s · 黑帧 0/105 · 字幕 100% · 角标 13/13 · provenance 101/101
顺序 = 成片顺序 == canonical（render_plan + master_cl + 帧级抽帧三重验证）
规则复核 = 成片级 <60s 重复 1 -> 0 · adjacent 0 · ABA/ABAB 0 · >2 次 0 · 全片无新增 <60s 重复
审片 = 3:54/5:10 同图重复已消除 · C991 <60s 已消除 · 3:04-3:13 超声同主体相邻仍存在（FIX-3/FIX-4 未授权实施）
差异 = 与 FIX-1 shadow 逐拍 0 差异 · 与上版母片 15 拍变化（对应性无损）
完整性 = Run01-04 母片 + 冻结 14/14 + 上版 run05 母片 全部不变
非预期指标变化 = 无（未自行修改任何规则）
STOP——等待人工 QA / 下一步指令
```
