# 生产接入前整合审计 + 最小接入方案（DESIGN ONLY）

- 日期: 2026-09-11 · 性质: **只读审计 + 方案设计**（未执行任何接入动作）
- 授权边界遵守: 无正式 Run · 无生产代码修改 · 无冻结件修改 · 无验收口径修改 · 无 VIZ 推进 · 无既有产物覆盖
- 机器可读方案: `output/audit_20260911_ss3/integration_plan.json`
- 审计证据: `output/audit_20260911_ss3/ss3_integration_audit.json` · 代码依据 `output/run04/orchestrator_core.py`、`src/video_studio/orchestration/*`

---

## 0. 状态确认：92/101 是**实验态**，不是生产态

| 维度 | 生产现状（真实母片） | 实验结果（影子） |
|---|---|---|
| 母片 | `RUN04_PROD_G10_20260910_01/final_long_...mp4`，SHA16 `2f0e66871b76585f`，526.12s | **无母片**（shadow 不产母片） |
| 域一致 CORRESPONDING | **60**（门槛 ≥60，贴线） | 80 |
| HN/FALLBACK | 34（33.7%，全角标） | 9 |
| 独立素材 | —（34 拍借用） | **92/101**（69 run03 + 19 ss2 + 4 ss3） |
| 新素材位置 | 不在生产池 | `output/audit_20260910_ds1/ss2_pool/`、`output/audit_20260911_ss3/ss3_pool/` |

**关键事实（本次审计发现）**：316 个新素材**当前无法进入生产池**——生产门 `G8` 以路径标记硬拦：

```
check_namespace('.../output/audit_20260910_ds1/ss2_pool/files/...')
  -> BLOCK  reasons: ["experimental_marker:audit"]
allowed_path(...) -> False  reason: marker:experimental_marker:audit
```

且 QA 会把"allowed 但路径含 blocked marker"的素材计入 `ns_leakage`（硬门槛 = 0）。因此 **SS3 的 92 不能直接当作生产状态**；它也**不能靠放宽规则入池**，只能靠"迁入干净命名空间 + 版本化输入 + 新 manifest 锚定"。

---

## 1. 生产接入链路（代码依据）

`orchestrator_core.run()` 的固定链序与输入来源：

```
preflight_v2(注册表哈希锚定 + 授权互锁 + VIZ guard + 冻结/母片校验)
 → 载入 plan / retrieval_index / cv2_results / tts（全部 SHA256 锚定）
 → load_g10_assets(ontology + ECT + pool_signals，任一哈希不符 raise)
 → candidate_gate_stage:  namespace(allowed_path) → 完整性门 evaluate_asset → 冻结 CV2 → G10
 → run_reuse_policy（内容身份全局复用，min_gap 60s）
 → prerender_stage（G4 台账一致性 + G10 复核，不一致 = STOP）
 → crop/layout → render_plan → （授权时）render + production_qa + G10 验收门(≥60)
```

三条硬事实决定接入方案形态：

1. **`allowed_asset_namespaces` 仅** `output/run03/asset_cache` + `output/prod01/tts`；`blocked_markers` = `stage22/exp225/experimental/audit/pilot/viz_pilot`；
2. **所有输入都是哈希锚定的注册表项**——新增素材必须进"新路径 + 新哈希"，不能改既有文件；
3. **内容身份是内容派生**（MD5 + dHash 并查集聚类，路径只作键）→ **字节级复制不改变分区**，因此"迁移"不改变复用语义。

---

## 2. 316 个新素材的生产门画像（只读实测）

| 门 | 结果 | 说明 |
|---|---|---|
| G0 存在 / G1 MIME | 316 PASS | 文件与格式均正常 |
| **G2 分辨率** | **PASS 7 · DEMOTE 307 · BLOCK 2** | 短边 480–719 → 放大至 720（DEMOTE，不拦）；2 个 940×470 被拦 |
| G3 画幅 | PASS 314 · DEMOTE 2 | 越界仅强制 contain（表现层） |
| G4 内容重复 | 316 PASS | 候选级 displayed_contents 为空，由政策统一管 |
| G5/G6/G7 | 23 / 1 / 3 条 ADVISORY | **仅建议，永不单独 BLOCK** |
| **G8 命名空间** | **316 BLOCK（当前路径）** | 全部因 `audit` 标记；迁入 `run05` 后按代码判定为 PASS |
| G9 provenance | 316 PASS | 全部素材有 beat + title |

**"迁移后可用性"（忽略 G8 重算）**：**314 可用**（309 DEMOTE + 5 PASS）· 2 BLOCK · **0 缺失 provenance**。

**分辨率画像对比（重要）**：

| 池 | n | 短边中位数 | 短边≥720 | 480–719(DEMOTE) | <480 |
|---|---|---|---|---|---|
| 现役 run03 池 | 438 | 627 | 187（43%） | 240 | 11 |
| 新池 ss2+ss3 | 316 | 627 | **7（2%）** | **307** | 2 |

新素材**分辨率画像弱于现役池**（靠放大路径），但 **DEMOTE 放大正是现役生产已在用的机制**（现役 240/438 属同一档），故属"既有实践内、需人工 QA 关注"，不是规则问题。

**4 个关键补口素材的门画像**：

| 拍 | 素材 | 非 G8 门 |
|---|---|---|
| S23-B01 | `ss3_S23-B01_0` | G2 DEMOTE，其余 PASS（含 G9） |
| S27-B04 | `ss3_S27-B04_12` | **G2 PASS**，G3 DEMOTE |
| S29-B04 | `ss3_S29-B04_11` | G2 DEMOTE，G7 ADVISORY |
| S30-B02 | `ss3_S30-B02_8` | G2 DEMOTE |

→ **四个关键素材在迁移后均可用**（唯一阻断项是路径标记，已由迁移消除）。

---

## 3. 最小接入方案（S0–S7，全部为新增/版本化，零改动既有件）

| 步 | 动作 | 关键约束 |
|---|---|---|
| **S0** | 把 316 个新素材**复制**到干净命名空间 `output/run05/asset_cache/files/`，生成逐文件 sha256 清单 | **排除** `ss2` 的 12 个 `_note` bug 垃圾文件；字节复制 → 内容分区不变 |
| **S1** | 新 `run05/retrieval_index_ext.json` = run03 索引原文 + 每拍追加新条目（路径改写为 run05） | **绝不修改** `output/run03/retrieval/retrieval_index.json` |
| **S2** | 新 `run05/cv2_results_ext.json` = run03 CV2 原文 + 316 条冻结 CV2 判定（复用 `ss2v_cv2_new.json`/`ss3_cv2.json`） | 同一模型/同一 focus='' 约定；**不重判** |
| **S3** | 新 `run05/pool_signals_ext.json` = 438 锚定 + 262 ss2 + 64 ss3 域信号 | ontology/ECT **不改**（哈希与 run04 相同，SS2V 已验） |
| **S4** | 新 `run05_manifest.json`：registry 三项换新路径+新哈希；`allowed_asset_namespaces` **追加** `output/run05/asset_cache`；`blocked_markers`/`review_signoffs`/`signal_overrides`/`new_acceptance`/`hard_gates` **全部不变**；`production_viz_rollout` 保持 NOT AUTHORIZED；**新增授权签核记录**（flag 单独不足以授权，`auth_ok` 互锁） | 验收口径 **不动**（仍 ≥60 次数、错配 0） |
| **S5** | 预检增补（写在 run05 侧，不动 run04）：信号总数 438+262+64 且 ontology/ECT 哈希等于 run04；override 条目在位并锚定；每个新路径在允许命名空间内且 sha256 匹配；**4 个补口拍各 ≥1 合格候选（否则 STOP）**；内容分区等价性校验 | 全部 fail-closed |
| **S6** | 用新 manifest 跑**影子回放**（render DEFERRED），与 EXP-SS3 影子逐项对比（92 / 80 / 0 / 0） | 任何偏差（除 2 个 G2-BLOCK 文件）→ STOP 报告 |
| **S7** | **另需单独授权**的正式 Run（产新 exec 母片；历史母片不动） | 需 G10 验收 ≥60（预计 80）+ 制作 QA + 人工 QA |

**回滚**：run05 命名空间与新 manifest **纯增量**；删除/回退即可恢复原状态（原状态哈希已存档：`aff83cbd`/`d7cc5fbae`/`cc426611`/`e3d0be12`/`2f0e6687`）。

---

## 4. 8 个自指拍 + S20-B03 的 HN 保持（无需改规则）

| 对象 | 机制 | 接入动作 |
|---|---|---|
| **8 个自指拍**（S01-B03/S02-B01/S02-B03/S02-B04/S27-B01/S33B-B01/B02/B03） | ECT `self=True` + primary=`['self_structure']` → **R1 拒绝一切外来域**；且本方案**不为这 8 拍暂存任何候选** → 政策走 BORROW + 角标 = HN | 无（规则不变） |
| **S20-B03** | manifest `signal_overrides['r3_S20-B03_2'] = generic_stock_concept` → **R4 LOW** → 不合格 → HN | 必须**逐字保留**该 override 条目并在 S5 校验；若丢失，Flash 信号 `bci_neuro 0.92` 会让它变成 CORRESPONDING（静默语义回退） |

两处都不需要、也不允许改 G10/ECT/签核规则。

---

## 5. 单点余量风险（S27-B04 / S29-B04）与保护策略

**系统级安全（不需要新动作）**：若单点候选在 prerender 复核（G4 台账 + G10 复算 + G6/G9）被拒，政策级联自动降级为 BORROW/HN（角标），**不 STOP、不改规则**；指标由 80 降为 78/79，**仍 ≥60**。即"风险是分数波动，不是系统失效"。

**可选加固（需授权，本方案不执行）**：

- **O1（无新检索，推荐）**：预检"单点声明 + 人工 QA 签核"——把 S27-B04/S29-B04 各只依赖 1 个候选写入 exec 台账，要求人工在母片 QA 时逐帧确认这两处。
- **O2（需新授权）**：仅对这 2 拍做一小轮定向检索，使每拍 ≥2 个合格候选（估 6 查询 / ~32 下载 / ~64 判定）。注意：这属于"继续扩池"，与上一轮"停止扩池"指令冲突，**必须显式授权**。
- **O3（不推荐）**：用签核把 near 域备选升为 PASS——需要改冻结规则，超出本方案范围。

---

## 6. 接入后生产指标预测（影子推导，需 S6 复核确认）

| 指标 | 现生产 | 接入后（预测） | 门槛 |
|---|---|---|---|
| 域一致 CORRESPONDING（次数） | 60 | **80** | ≥60 ✅（余量 +20） |
| cls CORRESPONDING 总数 | 67 | 92（80 PASS + 12 NO_EXPECTATION） | — |
| 域错配上屏 | 0 | 0（结构性：仅 PASS 可 CORRESPONDING） | =0 ✅ |
| HN/FALLBACK | 34（33.7%） | **9（8.9%）** | 全角标 ✅（基线 16.8%，为下降） |
| ns_leakage | 0 | 0（**前提**：迁入干净命名空间） | =0 ✅ |
| ABAB/ABA/A?A/adjacent | 0/0/0/0 | 待 S6 影子确认 | 全零 |
| 独立成片时长 | — | 7.99 min（92 × 5.208s） | — |

---

## 7. 风险登记

| ID | 风险 | 证据 | 缓解 | 级别 |
|---|---|---|---|---|
| R-1 | 新素材靠放大（307/316 DEMOTE） | 新池短边≥720 仅 2%，现役 43%（现役亦有 240 文件同档） | 沿用既有放大机制；S23-B01/S29-B04/S30-B02 三处列入人工 QA 关注 | MEDIUM |
| R-2 | 2 个新文件 G2 BLOCK | 940×470 | 门自动排除，且不在 92 选择内 | LOW |
| R-3 | 10 个内容碰撞簇涉及 ss3 | 影子中 0 上屏 | 政策一次性约束 | LOW |
| R-4 | 新增 wikimedia 来源（ss3 池 7 个，含 1 个关键补口） | `ss3_downloads.json` source 字段 | 索引条目保留来源；现役池同样混源 | LOW |
| R-5 | 单点候选被 prerender 拒 | 余量 = 1 | O1 / O2 | MEDIUM |
| R-6 | S20-B03 override 丢失导致静默升级 | Flash 信号 0.92 | S5 强制校验 override 在位 + 哈希锚定 | MEDIUM |

---

## 8. 结论

```
PRE-PRODUCTION INTEGRATION AUDIT = COMPLETE（只读）
状态确认 = 92/101 为实验影子态；生产真实态 = 60 域一致 / 34 HN（母片 2f0e6687）
接入可行性 = 可行，但必须经"干净命名空间迁移 + 版本化输入 + 新 manifest 锚定 + 授权签核"
           当前实验路径被 G8 硬拦（experimental_marker:audit）且会触发 ns_leakage——不得直接接入，也不得放宽规则
门画像 = 316 新素材：G0/G1/G4/G9 全通过；G2 7 PASS / 307 DEMOTE / 2 BLOCK；G3 2 DEMOTE；G5-G7 仅建议
         迁移后可用 314/316；4 个关键补口素材迁移后全部可用
HN 保持 = 8 自指拍（R1 结构性）+ S20-B03（override → R4）零规则改动；override 必须逐字保留并校验
单点风险 = S27-B04/S29-B04 余量 1；系统安全（级联降级为 HN，不 STOP），加固选项 O1（推荐）/O2（需授权）
预测 = 域一致 60→80（≥60 ✅，余量 +20）· HN 34→9 · 独立 7.99 min
方案 = S0–S7（全部新增/版本化，零改动既有件，可回滚）
未执行项 = 素材复制、索引/信号/CV2 合并、manifest 生成、影子回放、正式 Run —— 全部等待授权
STOP——等待授权（不复制素材、不建 run05、不改 run04、不跑影子/正式 Run、不推进 VIZ）
```
