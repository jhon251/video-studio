# JOINT 正式生产渲染报告（β-3′ + F-α + F-γ + F-δ）

- 日期: 2026-09-11 · 授权: JOINT 正式重渲染（含 S02-B01 卡版面最小修复）
- exec: `output/run05/exec/RUN05_PROD_JOINT` · 状态 **`ORCHESTRATED_PRODUCTION_OK`** · `render_mode = PRODUCTION_READY`
- **母片**: `output/run05/exec/RUN05_PROD_JOINT/final_long_RUN05_PROD_JOINT.mp4`
  **SHA256[:16] = `47177bf96bb3bc5e`** · 30,778,407 B · **526.12s** · 101/101 拍
- 数据: `joint_render_preflight.json` · `joint_render_result.json` · `joint_render_verify.json` · `viz_relayout_check.json`

---

## 1. 渲染前预检（12/12 PASS）

```
[PASS] manifest 差异 = 仅授权三键 + 卡 A 指针哈希（无规则/白名单/输入改动）
[PASS] authorization interlock（flag + 签核记录完整）· VIZ rollout = NOT AUTHORIZED
[PASS] 注册表 5/5 哈希（plan / index-joint / cv2-joint / tts / font）
[PASS] G10 三件锚定（signals 753 · ECT 101）· ECT 仅 S20-B02/S26-B02 变更（逐 beat 断言）
[PASS] β-3′ 映射表未变 = {ultrasound: [超声]} · VIZ 白名单恰为两拍 · 验收阈值未变
[PASS] **字幕碰撞预检 PASS**：S02-B01 净空 87px · S33B-B01 净空 30px（卡 B 未触碰）
[PASS] 卡 A 哈希与 manifest 指针一致 · exec id 空闲
```

**S02-B01 卡最小修复**（严格按授权参数）：行起点 250→**205** · 行距 160→**145** · 行高 130→**118**；
卡 A sha256 `a026816f…` → **`4753538ef6c31c9d`**；标题/副标题/字号/颜色/语义/落点/白名单/manifest 规则项/策略/阈值**全部未变**；**S33B-B01 卡未修改**（哈希不变）。

## 2. 核心指标与 QA

| 指标 | 值 |
|---|---|
| **domain-consistent CORRESPONDING** | **78**（门槛 ≥60 ✓，余量 +18） |
| CORRESPONDING（cls） | **86** |
| NO_EXPECTATION | **8** |
| **VIZ 结构卡（独立桶）** | **2** |
| HN/FALLBACK | **13（12.9%，较基线 −3.9pp）** |
| ns leakage / policy violations / prerender blocks / crop demotes | **0 / 0 / 0 / 0** |
| patterns：adjacent · gap2 · ABA · ABAB | **0 · 0 · 0 · 0** |
| gate | eligible 325 / ineligible 426 · G10 候选级拒绝 149（带理由） |
| 角标 | HN/FALLBACK **13 处全部带角标** |
| A/V delta · 黑帧 · 字幕 | **0.15s / 0 / 105 采样** · **100%（101/101）** |
| G10 验收 | `domain-consistent=78 >= 60: True` |
| canonical order / order invariant | **PASS / PASS**（101 拍，render==canonical） |
| 阶段 | `family_guard skips=1` · `borrow_prefer_wide penalized=186` · `viz_cards authorized=2` |

## 3. 四项专项核验（成片抽帧，非账面）

### ① S12-B02 超声相邻 → **已消除** ✅
| 检查 | 结果 |
|---|---|
| S12-B01 @3:03 帧 vs `r3_S12-B01_3`（超声） | hamming **5**（仍是超声） |
| S12-B02 @3:09 帧 vs 超声图 | hamming **37**（**已不是超声**） |
| S12-B02 帧 vs 其新借用 `r3_S04B-B02_1` | hamming **6** ✓ |
| 全片超声图展示位置 | `[S12-B01(3:03), S20-B02(5:05)]`（原先 `[S12-B01, S12-B02]`）→ **相邻重复消除** |

### ② 7:34 / 8:35 眼部测试重复 → **已消除** ✅
| 检查 | 结果 |
|---|---|
| S30-B02 素材 | `ss3_S30-B02_13`（眼部测试） |
| S33B-B02 素材 | `ss2_S26-B01_7`（**不同素材**） |
| 7:34 帧 vs 眼部测试图 | hamming **6**（保留一次） |
| 8:35 帧 vs 眼部测试图 | hamming **33**（**重复已消除**） |

### ③ 两张 VIZ 结构卡（实际母片）→ **正确、清晰、无字幕碰撞** ✅
| 拍 | 帧 vs 卡 | 卡内容底边 | 字幕带顶 | **净空** | 字幕带白像素 | 角标 |
|---|---|---|---|---|---|---|
| **S02-B01 @0:17** | hamming **5** | y=903 | y=990 | **87px** | 2141（字幕在位） | 无（自有结构卡） |
| **S33B-B01 @8:31** | hamming **4** | y=960 | y=990 | **30px** | 1830（字幕在位） | 无 |

- cls = `VIZ_STRUCTURAL`（独立 QA 桶 = 2，不计入 domain-consistent）· gate 记录 `viz_narrow_authorized` · 白名单外零使用 · `production_viz_rollout` 仍 **NOT AUTHORIZED**。

### ④ S20-B02 @5:05 honest-neutral 借用（语义评估）⚠️ 合规但拟合较弱
| 检查 | 结果 |
|---|---|
| 记录 | `FALLBACK / BORROW`，素材 `r3_S12-B01_3`，borrow_from=S12-B01，**带角标** |
| 帧验证 | 5:05 帧 vs 超声图 hamming **5**（确为借用该图） |
| 旁白 | "而你随便看一眼画面,信息量是它的百万倍量级。"（人眼带宽） |
| 语义拟合 | **较弱**：画面是临床超声仪控制台，与"人眼信息带宽"无直接证据关系 |
| 规则合规 | ✅ 该拍为 HN 借用（设计上豁免域校验，诚实角标）；同图与 3:03 的 S12-B01 间隔 **122s ≥60**、单内容 ≤2、借用 ≤1 方 |
| 结论 | **不是缺陷、不是指标下降**，但为审片可见的弱拟合借用 → 若需改进需另立授权（F-α 窗口调参或借用偏好规则，均属变更，本次未做） |

## 4. 与上一版母片（FIX-1 `0dcf132387748a91`）的差异

| 项 | FIX-1 | **JOINT** |
|---|---|---|
| CORRESPONDING / domain-consistent | 88 / 78 | **86 / 78** |
| NO_EXPECTATION | 10 | **8** |
| VIZ 结构卡 | 0 | **2** |
| HN/FALLBACK | 13 | 13 |
| 超声相邻 / 眼部测试重复 / Audi 赛车照 | 有 / 有 / 有 | **全部消除** |
| 五层框架图 / 结论图 | 缺失 | **已上屏（两张卡）** |
| 母片 | `0dcf132387748a91` | **`47177bf96bb3bc5e`** |

## 5. 完整性（渲染后复核）

| 对象 | SHA256[:16] |
|---|---|
| **JOINT 母片（本次）** | **`47177bf96bb3bc5e`** |
| FIX-1 母片（原样保留） | `0dcf132387748a91` |
| S7 母片（原样保留） | `7bcaf1093122a3d3` |
| run01 / run02 / run03 | `ff119fcd1c559b52` / `ad52a0c0eb9a4491` / `871489f94b61ed15` |
| run04 前版 / run04 G10 | `074985a527759e1a` / `2f0e66871b76585f` |
| 冻结模块 | **14/14 未变** |

## 6. 判定

```
JOINT 正式生产渲染 = PASS
母片 = output/run05/exec/RUN05_PROD_JOINT/final_long_RUN05_PROD_JOINT.mp4
       SHA256[:16] 47177bf96bb3bc5e · 526.12s · 30,778,407 B · PRODUCTION_READY
指标 = 86 CORRESPONDING / 78 domain-consistent / 8 NO_EXPECTATION / 2 VIZ(_独立桶_) / 13 HN(12.9%)
QA = A/V 0.15s · 黑帧 0/105 · 字幕 100% · 角标 13/13 · provenance 101/101
规则 = 60s 0 · adjacent 0 · >2 次 0 · ABA 0 · ABAB 0 · ns_leakage 0 · violations 0 · prerender 0 · crop demote 0 · canonical order PASS
专项 = ①超声相邻消除 ✓ ②7:34/8:35 眼部重复消除 ✓ ③两张卡正确清晰、净空 87px/30px、无字幕碰撞 ✓ ④S20-B02 弱拟合但为合规诚实借用（已如实记录）
完整性 = FIX-1/S7/run01-04 母片 + 冻结 14/14 全部不变
未再修改 = β-3′ / F-α / F-γ / F-δ 逻辑 · 60s · ≤2 · borrow≤1 · G10 · canonical order · 阈值
STOP——母片已产出，不继续自动修复
```
