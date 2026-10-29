# RUN05 正式生产 Run（S7）执行报告

- 日期: 2026-09-11 · 授权: **S7 正式 Run**（以 run05 集成产物 + 已闭合 projection v2 为唯一输入）
- exec: `output/run05/exec/RUN05_PROD_SS2SS3` · 母片: **`final_long_RUN05_PROD_SS2SS3.mp4`**，SHA16 **`7bcaf1093122a3d3`**，30,764,658 B
- 机器可读: `output/run05/s7_verdict.json` · 核验数据 `s7_verification.json` / `s7_preflight.json` / `s7_result.json`

---

## 1. 运行前 fail-closed preflight（21/21 PASS）

| 组 | 检查 | 结果 |
|---|---|---|
| 授权 | manifest 差异**仅 3 处**（`production_run_authorized` / `authorization` / `status`） | ✅ |
| 授权 | `auth_ok` 互锁（flag=True **且** 签核记录完整） | ✅ |
| 授权 | `production_viz_rollout = NOT AUTHORIZED`（VIZ 未推进） | ✅ |
| 注册表 | plan / retrieval_index / cv2 / tts / font **5/5 哈希匹配** | ✅ |
| G10 | ontology / ECT / signals 三件哈希锚定装载（753 信号 · 101 ECT · 28 域） | ✅ |
| 规则 | ontology、ECT **与 run04 逐字节相同**；signoffs 5 拍不变；override `r3_S20-B03_2` 在位；验收阈值 60/0 不变 | ✅ |
| 素材 | 316 个暂存文件存在、sha256 匹配、全部位于允许命名空间 | ✅ |
| 语义 | **8 自指拍合格候选 = 0**；4 缺口拍合格 15/1/1/12；**S27-B04=1、S29-B04=1 单点候选在位**；S20-B03 合格 = 0 | ✅ |
| 隔离 | run05 生产 exec 目录无冲突 | ✅ |

## 2. 正式执行链（prerender → render → final G10/QA）

```
preflight_v2 ok(failed=[]) → inputs_loaded → viz_guard ok(no VIZ in route)
→ candidate_gate 101/101 beats, eligible=327 → timeline(tts)
→ reuse policy → prerender gate(0 blocks) → crop/recheck(0 demotes)
→ render plan PRODUCTION_READY → render executor → production QA → G10 acceptance
```
渲染执行：**101 clips + 61 parts + master**，`render_log.json` **122 条 ffmpeg 调用全部 returncode=0**。

## 3. 正式结果 vs projection v2（唯一预期）

| 指标 | projection v2 | **正式实测** | 一致 |
|---|---|---|---|
| CORRESPONDING（cls） | 88 | **88** | ✅ |
| 域一致 CORRESPONDING | 78 | **78** | ✅ |
| NO_EXPECTATION 展示 | 10 | **10** | ✅ |
| HN/FALLBACK | 13 | **13**（12.9%） | ✅ |
| 独立素材时长 | 7.64 min | **7.64 min**（全片 8.77 min） | ✅ |
| 逐拍分配（101 拍） | — | **与 S6 影子 0 差异** | ✅ |

**G10 验收**：`domain-consistent=78 >= 60: True` · `g10_acceptance_ok = true`（阈值未改）。

## 4. 制作 QA / 材料审计

| 项 | 值 | 门槛 |
|---|---|---|
| 母片时长 / A/V delta | **526.12s / 0.15s** | ≤0.5s ✅ |
| 黑帧 | **0 / 105 采样** | =0 ✅ |
| 字幕 | **101/101 = 100%** | ≥95% ✅ |
| namespace leakage | **0** | =0 ✅ |
| reuse：ABAB / ABA / A?A / adjacent | **0 / 0 / 0 / 0** | 全零 ✅ |
| policy violations / prerender blocks / crop demotes | **0 / 0 / 0** | ✅ |
| 展示内容 | 101 次展示 / **88 唯一内容**；CORRESPONDING **88/88 唯一** | ✅ |
| 借用 | 13 次 BORROW，**每内容 1 个借用方**（cap=1） | ✅ |
| 角标 | **13** 处 HN/FALLBACK 全部角标 | ✅ |
| provenance | **101/101** 全链（policy+content+material） | ✅ |
| G10 候选级拒绝 | 145 条（含规则+理由入档） | — |
| HN/FB 相对基线 | 12.9% vs 16.8% → **−3.9pp**（硬门槛为最多 +5pp） | ✅ |

**G2 / G10 / 内容身份异常**：无。候选级 G2 拦截 2 个（940×470，未入选）；内容身份分 295 簇、上屏零重复；预渲染 G10 复核 78 PASS + 10 NO_EXPECTATION + 13 借用（无 BLOCK）。

## 5. 与 Run04 母片及冻结件对比

| 对比项 | Run04 G10 母片 `2f0e6687` | **Run05 母片 `7bcaf109`** |
|---|---|---|
| CORRESPONDING | 67 | **88**（+21） |
| 域一致 CORRESPONDING | 60（贴线） | **78**（+18，余量 +18） |
| HN/FALLBACK | 34（33.7%） | **13（12.9%）** |
| 时长 | 526.12s | 526.12s |

**哈希完整性（运行后复核，全部不变）**：run01 `ff119fcd` · run02 `ad52a0c0` · run03 `871489f9` · run04 前版 `074985a5` · **run04 G10 `2f0e6687`** · run03 索引 `aff83cbd` · run03 CV2 `d7cc5fba` · run04 信号 `cc426611` · run04 manifest `e3d0be12` · run05 影子 manifest `0eee4d2b` · run05 扩展索引/CV2/信号 `3ed7d77a`/`83026a80`/`d1cac773` · **冻结模块 14/14** · run05 影子 exec 未触碰。

## 6. 判定

```
S7 FORMAL PRODUCTION RUN = PASS
母片 = output/run05/exec/RUN05_PROD_SS2SS3/final_long_RUN05_PROD_SS2SS3.mp4 (sha16 7bcaf1093122a3d3, 526.12s)
状态 = ORCHESTRATED_PRODUCTION_OK · render_mode = PRODUCTION_READY · G10 验收 = 78 ≥ 60 ✅
结果 = 88 CORRESPONDING / 78 domain-consistent / 10 NO_EXPECTATION / 13 HN / 7.64 min 独立覆盖
     = projection v2 逐项一致，且逐拍分配与 S6 影子 0 差异
QA = A/V 0.15s · 黑帧 0 · 字幕 100% · leakage 0 · ABAB/ABA/A?A/adjacent 全 0 · violations 0 · 借用 cap 合规
规则 = G0–G10 / ECT / CV2 / 复用政策 / tie-break / 验收阈值 / SS3 结果 / 生产代码 全部未改
完整性 = Run01–04 母片 + 14 冻结项 + 全部冻结输入哈希不变；写入仅限 run05
异常 = 无
验收依据 = 生产真实结果（未以 92/101 或 7.99 min 为目标；88/78/13/7.64 与闭合投影一致）
STOP——等待人工母片 QA 或下一步指令
```

产物：母片 + exec 全量审计（`qa_summary.json` · `assignment_policy.json` · `gate_decisions.json` · `namespace_decisions.json` · `prerender_gate.json` · `crop_recheck.json` · `render_plan.json` · `render_log.json` · `shot_provenance.json` · `ledger*.json` · 101 clips + 61 parts）
