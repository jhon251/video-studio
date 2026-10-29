# RUN04 PRODUCTION REPORT（首次正式生产执行）

- 日期: 2026-09-10 · exec_id: **RUN04_PROD_20260910_01**
- 变更集（一次授权）: Production Executor + Authorization Interlock + Manifest Sign-off
- 报告: `docs/RUN04_ORCHESTRATED_SHADOW_REPORT.md`（前序）→ 本报告（生产执行）

## 1. 授权与互锁

- manifest `production_run_authorized: true` + 签核记录 `authorization: {authorized_by, authorized_at, authorization_ref}`（Run04 Production Execution 授权；VIZ 保持 NOT AUTHORIZED）
- 互锁 `auth_ok()`：**flag 严格 True 且签核三字段非空**——只改 flag 不带签核 = preflight FAIL（fail-closed，T13 实证）
- 字体入注册表（sha256 锚定）；prod01/tts 音频目录入 allowed 名单（frozen tts）

## 2. 执行前门（全绿）

| 门 | 结果 |
|---|---|
| Preflight-v2 | ALL PASS（注册表哈希 / 母片全哈希 / 14/14 冻结指纹 / 授权记录 / VIZ 状态） |
| 模块单测 | 12/12 |
| R1–R8 回归 | 8/8 |
| T1–T13 编排器套件 | 13/13（含 T11 迷你生产端到端、T12 失败停机、T13 互锁） |

## 3. 生产执行结果（101/101 拍）

| 项 | 值 |
|---|---|
| 母片 | `output/run04/exec/RUN04_PROD_20260910_01/final_long_RUN04_PROD_20260910_01.mp4` |
| 母片 SHA256[:16] | **`074985a527759e1a`**（35,295,948 B，526.12s） |
| A/V delta | **0.15s**（audio 525.97s）✅ ≤0.5s |
| 黑帧 | **0 / 105 采样** ✅ |
| 字幕 presence | **101/101 = 100%** ✅ ≥95% |
| correspondence | **81/101（80.2%）**（≥51 ✅；对 run03 84：-3 为 Gate 诚实重排） |
| HN/Fallback | **20 拍（19.8%，+3.0pp）** ✅ ≤+5pp（借用全部带"中性画面"角标） |
| 全片模式 | ABAB/ABA/A?A/adjacent = **0/0/0/0** ✅ |
| policy violations | **0**（60s 间隔/借用者上限/内容上限全合规） |
| namespace leakage | **0**（433 候选路径逐一定责；audit/pilot/experimental 零读取） |
| prerender BLOCK | 0 |
| CV2/Retrieval 调用 | **0**（全冻结种子） |
| 布局 | 90 cover / 11 contain（10 G3 强制 + 1 语义风险降级）/ 0 blank |
| 渲染日志 | 122 条 ffmpeg 调用，**exit-code 全 0**，逐条输入/输出 sha16 |
| 产物 | 101 clips + 5 分部（burned）+ 母片 + 11 件审计 JSON，全部在 exec 目录 |

## 4. 完整性审计（执行后）

- 冻结 14 件指纹 **14/14 一致**
- Run01 `ff119fcd` / Run02 `ad52a0c0` / Run03 `871489f9` / baseline `7e148585` 全部不变
- run03 assignment `b220eeb8` 不变；render_v3/retrieval_run3/cv2_run 未触碰
- 本轮新写入仅 `output/run04/exec/RUN04_PROD_20260910_01/` 与 `output/run04/qa/latest.json`

## 5. 逐段链路执行记录

Preflight-v2 ALL PASS → 注册表输入加载（零 Retrieval/CV2）→ plan_viz_guard（无 VIZ）→ Candidate Gate（433 候选：247 合格 / 186 不合格含原因）→ Reuse Policy（101 决策）→ Pre-render Gate（0 BLOCK）→ Crop/Layout+Recheck（90 cover / 11 contain）→ **Render Executor**（101 clips → 5 分部 concat/mux/burn → 母片 concat；122 调用全 rc=0）→ Production QA（本报告 §3）→ 持久化完成。

## 6. 判定

```
RUN04 PRODUCTION = PASS
MOTHER_RENDERED = YES
HUMAN_QA = PENDING
```

- 母片为**候选成片**：必须通过人工母片 QA（BLK-4 清单：字幕抽检/观感/黑帧复核/逐段抽验）后方可对外
- 本报告不宣布 2.x 完成；VIZ Production Rollout 仍未授权（本片无 VIZ 拍，20 拍借用全部诚实角标）
- 任何人工 QA 缺陷 → 按 RUN01 先例出缺陷报告并定责修复线

STOP——等待人工母片 QA
