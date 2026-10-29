# PHASE 13-D 报告：ctx 构建 + P13-4 执行（真实执行器）/ P13-5 状态

> 阶段：Phase 13-D ｜ 依据：Phase 13-D 授权（ctx 构建 + 两次全片渲染）
> **结论（逐项如实）**：
> **ctx 构建：DONE ✔ ｜ P13-4 执行：SUCCEEDED（候选已产出、零 promotion）但 **PI 强制复核 BLOCKED（5/6 FAIL）⇒ 未通过** ｜
> P13-5 全片合成候选：**PENDING（未执行）** ｜ DQ：overall FAIL（如实记录，未改口径）**
> 铁律：未通过即未通过，**不得**改写为 PASS；LLM $0、网络 0；母片/既有候选/Phase 7–13C 产物零改动。

## 1. ctx 构建（6-C 同款，权威来源逐项登记）

| 项 | 值（可复算） |
|---|---|
| 项目 / 权威时间线 | `p_96efdc03e1aa` / `render_output`（task `t_d0a54bdf1810`）的 `material_timeline` ⇒ **21 景**；`timeline_duration_s = 1532.0` |
| 母片（沙箱源） | `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`（44 MB），sha256 `22705c7d7ea20b40…`（与 6-C 的 `V9_SHA` 常量一致 ✓） |
| 证据 / cues | `ops_direction.load_evidence("docs/regression_2x/logs/audit_p96efdc_mm.json")` + `core_captions.build_cues(script.segments)` |
| 素材注册表 | timeline 候选与在用素材 **+ 并入 P7-2 权威索引**（`logs/asset_index.json`）并套用 **Phase 12 许可覆盖层**（`license_overlay_v1.json`）⇒ 13 条，含 `ast-92ca33138ffe64f4`（Russell 页，sha256 `65377b888b778226…`，`PUBLIC_DOMAIN`） |
| 沙箱 | `ops_exec.prepare_sandbox(..., label="13d")` ⇒ `output/phase6b_m4_sandbox/p_96efdc03e1aa_13d`（**copy-on-write**；源项目与母版未被触碰 ✓） |

**差异登记（现实优先）**：6-C 可见的 `build_ctx()` **不含** `attach_dcv2_time_base`/母版 caption cues 的显式附着；
本阶段照抄同一构造（不擅自增补），其后果见 §3 的 PI 阻塞分析。

## 2. 设计决定登记：**派生执行提案**（不改 P7-6 内容）

- 6-B 执行器契约要求 `affected_scope.scenes` + `proposed_change.params.asset_id`；
  P7-6 提案 `bp-6320bf486a082901` **不含**这两个字段。
- 其 `proposal_sha256`（`8fc618a0cbe816c837d94bb2…`）已被批准 `ap-0850dfa8c52f` **绑定** ⇒ **不得改动其内容**（否则 tamper guard 失效）。
- 故派生执行提案 `bp-5923b15f5201e666`（= `sha256(P7-6 id|S05|新素材)[:16]`），字段：
  `affected_scope={"scenes":["S05"],"assets":["ast-92ca33138ffe64f4"]}`、
  `proposed_change={"type":"replace_asset","params":{"asset_id":"ast-92ca33138ffe64f4"}}`、
  **`derived_from={"proposal_id":"bp-6320bf486a082901","proposal_sha256":…,"deterministic_hash":…}`**；
  并为其登记派生批准 `ap-b182acf5bfa8`（`approved_by=human:project-owner`，
  `approval_document="Phase 13-C 授权书 §0 + 本消息（human:project-owner 签发）"`，
  `recorded_by=agent:transcription`）——`verify_approval` ⇒ **`{"ok": true, "code": "APPROVED"}`** ✓。
- **两条绑定（P7-6 批准 + 派生执行批准）都可独立校验**；P7-6 提案内容与母片均未被改动。

## 3. P13-4 执行结果（真实执行器；**PI 未通过**）

产物：`logs/phase13d_execution_ledger.jsonl`（hash chain seq=1）、`logs/phase13d_p13_4.json`

| 项 | 结果 |
|---|---|
| 执行状态 | **`SUCCEEDED`**（`executor_invoked=true`、`promoted=false`、`sandbox_only=true`）｜耗时 **80.5 s** |
| 执行动作 | 窗口 `[245.0, 300.0]`（S05，55 s）：真实素材校验（sha256 一致 + 可解码 + 许可不受限）→ 重编码该窗口（**字幕重烧**）→ 母版音轨流复制 → 头/尾 stream copy 拼接 |
| 修订候选 | `output/phase6b_m4_sandbox/p_96efdc03e1aa_13d/output/t_d0a54bdf1810_draft_m5_bp-5923b15f5201e666_replace.mp4`<br>84,996,782 B ｜ sha256 **`b5f8d9850d0f819a80d50e46185d3b829703a6a595071f250e46fb2112a090c0`**（现值复核一致 ✓） |
| 素材证据 | `asset-replacement-evidence-v1`：新素材 `ast-92ca33138ffe64f4`（`65377b888b778226…`）、旧素材 `asset_30dd89a16713`（`…Four color theorem map of Germany 3.png`）、`replaced=true`（抽帧比对见 `asset_verifications`） |
| 源项目/母片 | **未触碰**（沙箱 copy-on-write；母片 sha256 `22705c7d7ea20b40…` 未变）｜**零 promotion** ✓ |
| **PI 复核** | **`BLOCKED`**：PI-1 **FAIL**（旁白覆盖率 0.6277 < 0.9）、PI-2 **FAIL**（时长契约 shortfall **570.344 s**）、PI-3 **FAIL**（尾部静音 570.874 s、占比 0.3726）、PI-5 **FAIL**（字幕 orphan 73、0.338 > 0.02）、PI-6 **FAIL**（段落边界漂移 **552.16 s** > 5.0 s）；仅 **PI-4 PASS**；`[PROMOTE_BLOCKED]` |
| **DQ 复核** | `overall=FAIL`（DQ-2/3/4/5/6/8 FAIL、DQ-1 UNKNOWN）；DQ-3 明细 `mean_hold_s=72.952 / max_hold_s=95.0`（21 景） |

### 3.1 阻塞分析与**未定位项**（不得据此判定替换有问题）
- PI-2 的 **570 s 时长缺口**、PI-3 的 **570 s 尾部静音**、PI-6 的 **552 s 边界漂移** 三者量级一致且
  **远超**本次 55 s 窗口编辑 ⇒ 高度疑似**沙箱 ctx 的时基/字幕基未完整附着**
  （6-C 实际运行与可见 `build_ctx()` 的差异；本阶段照抄可见构造，未擅自增补）。
- **诚实结论**：本次 PI 阻塞**不能**归因于"S05 替换本身"（素材校验、窗口重编码、拼接与音轨复制步骤均有独立证据），
  也**不能**据此宣布替换成功 ⇒ 记为 **`P13D-OPEN-1`（UNRESOLVED）**，下一阶段**优先定位**
  （核对 6-C 运行时的 `_caption_time_base`/`timeline_identity` 附着点，再复跑执行器）。
- **未做**：未放宽/未调整任何 PI/DQ 阈值；未把 BLOCKED 改写为 PASS；未 promote。

## 4. P13-5 状态：**PENDING（未执行）**
- 未产出全片合成候选（S05 替换 + 运动层）。
- **前置阻塞**：`P13D-OPEN-1` 未定位前，运动臂的全片渲染会**同样**触发 PI-1/2/3/5/6 阻塞 ⇒ 先修 ctx 再渲染（否则重复无效渲染）。
- 运动臂开关已就绪（Phase 13：`core/motion.py` + `resolve_config` 三级链；默认 off），无需新代码。
- DQ-3 口径提醒（沿用）：运动使 `freezedetect` 不再触发 **≠** 结构变化 ⇒ 产物报告中**不得**宣称 DQ-3 PASS，
  只能并列原口径复算与语义说明。

## 5. 预算 / 边界 / 回归

| 项 | 结果 |
|---|---|
| LLM / 网络 | **$0 / 0 次** ✓ |
| 渲染耗时 | 执行器窗口拼接 **80.5 s**（**非**全片渲染；P13-5 全片渲染未执行，故无全片耗时数据） |
| 代码改动 | 本阶段**未改 `src/`**（新增阶段脚本 + 登记产物） |
| 回归 | 未改代码 ⇒ 沿用 Phase 13 干净口径 **76 套件 / 76 rc=0 / FAILED: []**（未重跑；如需可复跑） |
| 不可变 | 母片 `22705c7d7ea20b40…`（=`3b61dafd…` 的 6-G 母版谱系）未变；`config.json` `7b03424846f15efc…` 未变；P7-6 提案产物 `3f7fd67737d8e52d…` 未变；Russell 页素材 `65377b888b778226…` 未变 |
| 边界 | 未触碰 promotion、门禁阈值、转场/花字/BGM、字幕/混音/时基**源码**、素材 provider、`config.json`、Phase 7–13C 产物 |

## 6. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `docs/regression_2x/logs/phase13d_execution_ledger.jsonl` | `1c60f88a73a26bd80e3c6bf58aea8b46b6c828f63d5beb008007d46bf1055062` |
| `docs/regression_2x/logs/phase13d_approvals.jsonl` | `c4ce7dfdf8c4aa2373add2e5064945fe93e708adc5204942aadcf9c38943ca26` |
| `docs/regression_2x/logs/phase13d_p13_4.json` | `bb1022898a5711db5c78db8c584ddc6aac3e1a3528f7b306fe37fd86b2852244` |
| `output/phase6b_m4_sandbox/p_96efdc03e1aa_13d/output/t_d0a54bdf1810_draft_m5_bp-5923b15f5201e666_replace.mp4` | `b5f8d9850d0f819a80d50e46185d3b829703a6a595071f250e46fb2112a090c0` |
| `projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4`（母片，**未变**） | `22705c7d7ea20b40…` |

## 7. 下一步（解除阻塞所需）
1. **定位 `P13D-OPEN-1`**：核对 6-C 运行时的时基附着（`attach_dcv2_time_base` / 母版 caption cues）与 PI 检查的输入口径；
   修正 ctx 后**复跑** P13-4 执行器（幂等：ledger 已有记录 ⇒ 需以新 label 沙箱重跑并追加新账）。
2. PI 通过后，再执行 **P13-5**（S05 替换 + 运动层 enabled，全片渲染）→ 全门复验（含逐景 corr，重点 S06 的 0.3244 小裕度，**不调阈值**）+ DQ 双口径报告。
3. 全程零 promotion；候选仅供人工观看。

**Phase 13-D 按上表收尾：ctx DONE；P13-4 执行成功但 **PI 未通过**；P13-5 PENDING。STOP。**
