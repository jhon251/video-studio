# RUN05 最小增量接入 · S0–S6 执行报告（S7 未执行）

- 日期: 2026-09-11 · 授权: S0–S6（**S7 正式 Run 明确禁止**）
- 命名空间: `output/run05/`（全部动作仅写入此目录；run03/run04/冻结件/生产代码/历史母片零改动）
- 机器可读判定: `output/run05/s6_verdict.json` · 影子 QA: `output/run05/exec/RUN05_SHADOW_SS2SS3/qa_summary.json`

---

## 1. S0–S4 构建（全部完成）

| 步 | 产物 | 关键数字 |
|---|---|---|
| **S0 素材迁移** | `run05/asset_cache/files/` + `asset_manifest.json` | **316 文件 / 28,624,892 B**；**排除 12 个 `_note` 垃圾**；逐文件 sha256 校验全部一致（复制后 == 源） |
| **S1 版本化索引** | `run05/retrieval_index_ext.json` | run03 原文 **438** 条 + 追加 **316** = 754；sha256 `3ed7d77a5c712d81…`；**run03 索引哈希不变** `aff83cbd…` |
| **S2 版本化 CV2** | `run05/cv2_results_ext.json` | run03 CV2 原文 + **316** 条冻结 CV2 判定（同模型 `deepseek-v4-flash-vision-exp`、focus='' 约定，未重判）；sha256 `83026a8052fa44c8…`；**run03 CV2 哈希不变** `d7cc5fba…` |
| **S3 版本化信号** | `run05/g10/pool_signals.json` | 锚定 **439**（含 `_meta`）+ 新增 **314** = **753**；sha256 `d1cac773ae1d8fd8…`；**ontology / ECT 字节复制、哈希与 run04 完全相同**（`cf7cb98b…` / `fdcfc642…`）；**run04 信号文件哈希不变** `cc426611…` |
| **S4 新 manifest** | `run05/run05_manifest.json` | sha256 `0eee4d2bbd2adaa4c…` |

S3 说明：新增 316 个候选中 **2 个无解析信号**（fail-closed → R2 REVIEW，不可作对应），故入库 314 —— 符合设计，非缺陷。

**S4 关键配置（未改动项逐条核对）**：

| 项 | 值 | 状态 |
|---|---|---|
| `allowed_asset_namespaces` | run03/asset_cache + prod01/tts + **run05/asset_cache** | 仅追加 |
| `blocked_markers` | 原样（stage22/exp225/experimental/audit/pilot/viz_pilot） | 不变 |
| `g10.review_signoffs` | S09-B02/S12-B02/S13-B01/S17-B02/S29-B02 | **不变** |
| `g10.signal_overrides` | `r3_S20-B03_2 → generic_stock_concept` | **不变**（S5 逐字校验通过） |
| `g10.new_acceptance` | **≥60（次数口径）· 错配上屏 0** | **不变** |
| `hard_gates` / plan / TTS / font | 原样 | 不变 |
| `production_run_authorized` | **false**（S6 影子；S7 需新签核） | 按授权 |
| `production_viz_rollout` | NOT AUTHORIZED | 不变 |

---

## 2. S5 fail-closed 预检扩展（14/14 全通过）

```
[PASS] 1a 信号总数 753（锚定 439 + 新增 314）
[PASS] 1b ontology 哈希 == run04        [PASS] 1c ECT 哈希 == run04
[PASS] 1d 锚定前缀逐条相同（438/438）
[PASS] 2  S20-B03 override 逐字保留
[PASS] 3a 316 文件全部存在   [PASS] 3b sha256 全匹配   [PASS] 3c 全部在允许命名空间内
[PASS] 3d _note 垃圾已排除（staged=316）
[PASS] 4  4 个缺口拍各 ≥1 合格候选：S23-B01=15 · S27-B04=1 · S29-B04=1 · S30-B02=12
[PASS] 6  8 个自指拍合格候选 = 0（保持 HN）
[PASS] 6b S20-B03 合格 = 0（override → R4 LOW，保持 HN）
[PASS] 5  内容分区等价：实验命名空间 295 簇 == run05 命名空间 295 簇（逐簇相同）
```

---

## 3. S6 影子回放（跑通且干净，但**与预期不一致**）

**运行结果**：`ORCHESTRATED_SHADOW_OK` · `render_mode = DEFERRED_PRODUCTION_NOT_AUTHORIZED` · **母片 = null（未渲染）**

| 指标 | run04 现役 | **run05 影子（实测）** | 预期（接入方案） | 判定 |
|---|---|---|---|---|
| cls CORRESPONDING | 67 | **88** | 92 | ✗ 差 4 |
| **域一致 CORRESPONDING** | 60 | **78** | **80** | ✗ 差 2 |
| NO_EXPECTATION 展示 | 7 | 10 | 12 | ✗ 差 2 |
| HN/FALLBACK | 34（33.7%） | **13（12.9%）** | 9 | ✗ 差 4 |
| 独立成片时长 | — | 7.64 min | 7.99 min | ✗ |
| ns_leakage | 0 | **0** | 0 | ✅ |
| policy violations | 0 | **0** | 0 | ✅ |
| prerender blocks | 0 | **0** | 0 | ✅ |
| ABAB/ABA/A?A/adjacent | 0 | **0/0/0/0** | 0 | ✅ |
| G10 门槛 ≥60 | 60（贴线） | **78（余量 +18）** | 80 | ✅ |
| 母片 | 2f0e6687 | **无（DEFERRED）** | 无 | ✅ |

**必需校验项逐条**：

| 校验 | 结果 |
|---|---|
| 4 个缺口拍各 ≥1 冻结CV2+G10 合格 | ✅ 15 / 1 / 1 / 12 |
| 4 个缺口拍实际上屏各自素材 | ✅ S23-B01←`ss3_S23-B01_0` · S27-B04←`ss3_S27-B04_12` · S29-B04←`ss3_S29-B04_11` · S30-B02←`ss3_S30-B02_13`（全部 CORRESPONDING） |
| S20-B03 override 完整保留 | ✅ 逐字一致，该拍 FALLBACK/HN、合格候选 0 |
| 8 个自指拍仍 HN | ✅ 全部 FALLBACK、合格候选 0 |
| S27-B04 / S29-B04 单点候选未被复用策略误伤 | ✅ 两者均获得各自单点素材且 CORRESPONDING |
| namespace leakage = 0 | ✅ |
| G10 ≥ 60 | ✅ 78 |
| Run01–04 母片 / 14 冻结项哈希不变 | ✅ `ff119fcd` / `ad52a0c0` / `871489f9` / `074985a5` / `2f0e6687`；冻结 **14/14** |
| 既有生产件哈希不变 | ✅ run03 索引 `aff83cbd` · run03 CV2 `d7cc5fba` · run04 信号 `cc426611` · run04 manifest `e3d0be12` |
| run05 之外的写入 | ✅ 无 |
| **影子与预期 80/9/0/7.99min 对齐** | ❌ **未对齐（78/13/0/7.64）** |

---

## 4. 与现役母片的**完整差异**（beat 级）

- **CORRESPONDING：67 → 88（+21 净）**
- **净增 23 拍**：S03-B02 · S06-B03 · S08-B01 · S09B-B01 · S09B-B02 · S11-B01 · S16-B02 · S16-B03 · S18-B02 · S19-B02 · S21B-B01 · S23-B01 · S23-B02 · S24-B01 · S25-B01 · S25-B02 · S26-B01 · S26-B02 · S27-B04 · S29-B01 · S29-B03 · S29-B04 · S30-B02
- **失去 2 拍**：**S22-B02** · **S27-B03**（现役母片中为 CORRESPONDING，本次影子退为 HN/BORROW）
- 域一致 60 → 78（+18）· HN 34 → 13（−21）

---

## 5. 偏差根因（两条，均**非规则违规**）

**D-1｜实验影子模型的缺陷（幻影 +1）**：EXP-SS2/SS3 的贪心影子只对**新候选**做了分辨率检查，未对 run03 旧候选复检；而生产完整性门会拦。**S33-B02** 的唯一合格候选被 **G2:BLOCK** 拦下（该拍在现役母片中同样是 FALLBACK）→ 预测多算了 1 拍。这是**我的投影模型缺陷**，不是接入问题。

**D-2｜拍内选材分歧 + 跨源内容合并（−3）**：生产政策在拍内的选择与贪心影子不同，且新素材与下游拍依赖的内容发生了 dHash≤6 合并（每内容全片 1 次）：

| 拍 | 贪心影子选 | 生产政策选 | 后果 |
|---|---|---|---|
| S18-B02 | `ss2_S18-B02_1`（C736） | `ss2_S18-B02_8`（**C880**） | C880 与 S22-B02 依赖内容同簇 → 早拍先占 → **S22-B02 退 HN** |
| S16-B03 | `ss2_S16-B03_0`（C723） | `ss2_S16-B03_11`（**C953**） | C953 与 S27-B03 唯一合格内容同簇 → **S27-B03 退 HN** |
| S30-B01 | `r3_S30-B01_0` | `r3_S30-B01_1`（C983） | 与 S32-B03 唯一合格内容同簇 → S32-B03 未获独立供给（现役亦为 FALLBACK，非新增损失） |

即：**接入确实带来 +23，但政策的全局分配把 2 个原本对应的拍的素材"让渡"给了更早的拍**；两者都是合法政策语义。

---

## 6. 判定

```
RUN05 INTEGRATION S0-S6 = FAIL（仅"与预期对齐"一项不达标；其余全部 PASS）
S0-S4 = 完成（316 文件 / 28.6MB 迁移、索引 754 条、CV2 +316、信号 753、manifest 锚定；ontology/ECT/签核/override/验收阈值全不变）
S5 = 14/14 PASS（fail-closed）
S6 = 影子跑通且干净：ORCHESTRATED_SHADOW_OK · 无母片 · ns_leakage 0 · violations 0 · prerender 0 · patterns 全 0
     实测 88 / 78 / 13 / 7.64min  vs  预期 92 / 80 / 9 / 7.99min  → 未对齐（fail-closed 判 FAIL）
必需校验 = 全部 PASS（4 缺口拍全对应且各获自有素材 · override 保留 · 8 自指拍 HN · 单点素材未被误伤 · leakage 0 · G10 78≥60）
完整性 = run01-04 母片 + 14 冻结项 + run03 索引/CV2 + run04 信号/manifest 哈希全部不变；run05 之外零写入
相对现役收益 = CORRESPONDING 67→88（+23 得 / −2 失）· 域一致 60→78 · HN 34→13
偏差根因 = D-1 影子模型未对旧候选做完整性门（幻影 1 拍）+ D-2 拍内选择分歧与跨源内容合并（3 拍）——均非规则违规
未执行 = S7 正式 Run · 未渲染 · 未改生产代码 · 未改冻结件 · 未改验收口径 · 未推进 VIZ · 未继续扩池

待决策选项（均未执行）：
 O-A 接受 78/13 为真实接入结果（投影本身有缺陷，规则不动）
 O-B 修正实验影子模型（对旧候选同样跑完整性门 + 复刻政策拍内选择）后重新给出投影
 O-C 复用政策引入"临界性感知"tie-break（避免早拍吃掉后拍的唯一选项）—— 预计可挽回 ≤3 拍，需授权（政策语义变更）
 O-D 对级联失守的 2-3 拍做定向补检索 —— 需授权（扩池已被叫停）
STOP——等待授权（不启动 S7、不渲染、不改规则）
```

产物：`output/run05/`（build_report.json · asset_manifest.json · retrieval_index_ext.json · cv2_results_ext.json · g10/ · run05_manifest.json · preflight_ext.json · exec/RUN05_SHADOW_SS2SS3/ · s6_verdict.json · 全部脚本）
