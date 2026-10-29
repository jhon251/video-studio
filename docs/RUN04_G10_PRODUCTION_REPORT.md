# RUN04 G10 口径首个正式生产报告

- 日期: 2026-09-10 · exec_id: **RUN04_PROD_G10_20260910_01**
- 授权链: PRE-PRODUCTION FINAL AUDIT = PASS（33/33）→ 用户指令"启动正式 Run"
- 链路: Preflight-v2 ALL PASS → 冻结输入（注册表哈希锚定）→ Candidate Gate（含 G10 候选级判定）→ Reuse Policy → Pre-render Integrity Gate + G10 复核 → Crop/Layout/Recheck → Render Executor → Production QA → 持久化

## 母片

- 路径: `output/run04/exec/RUN04_PROD_G10_20260910_01/final_long_RUN04_PROD_G10_20260910_01.mp4`
- SHA256[:16]: **`2f0e66871b76585f`** · 31,896,627 B · 526.12s · 101/101 拍

## 生产 QA（G10 新口径）

| 指标 | 值 | 门槛 |
|---|---|---|
| **域一致 CORRESPONDING（次数口径）** | **60** | **≥60 ✅** |
| 域错配上屏 | **0** | =0 ✅ |
| G10 候选级拒绝 | 62 条（全部含规则+理由入档） | — |
| NO_EXPECTATION（META 拍单列） | 7 | 不冒充域一致 ✅ |
| HN/FALLBACK | 34（33.7%）**全角标** | 诚实标识 ✅ |
| ABAB / ABA / A?A / adjacent | 0 / 0 / 0 / 0 | 全零 ✅ |
| policy violations / ns_leakage | 0 / 0 | ✅ |
| A/V delta | **0.15s**（audio 525.97s） | ≤0.5s ✅ |
| 黑帧 | **0** / 105 采样 | =0 ✅ |
| 字幕 presence | **101/101 = 100%** | ≥95% ✅ |
| provenance | **101/101** 全链（policy→content→cv2→gate→ns→prerender→crop→render） | ✅ |
| Retrieval/CV2 调用 | **0** | ✅ |
| render_log | 122 条 ffmpeg 调用，exit-code 全 0，逐条输入/输出 sha16 | ✅ |
| 产物 | 101 clips + 5 分部 + 母片 + 11 件审计 JSON，全部在 exec 目录 | ✅ |

## 与前版母片对比（G10 门的效果）

| 指标 | RUN04_PROD_20260910_01（无 G10，074985a5） | **RUN04_PROD_G10_20260910_01（2f0e6687）** |
|---|---|---|
| 域一致 CORRESPONDING | 60 拍上屏中含 27 拍域错配/低证据（Hydrogen Ladder、power-line ladder、RECAP/forecast/POLICY 拼词、自指拍外来图） | **60 拍全部域一致，错配上屏 0** |
| 已知 P0（Hydrogen Ladder 0:17） | 上屏 | **HN 角标借用（触觉背心）** |
| CORRESPONDING 总数 | 81（含形式相关但域不符） | 67（60 域一致 + 7 META 单列） |
| HN/FALLBACK | 19.8% | 33.7%（全诚实角标） |

两版母片均保留（各自 exec 目录），无任何历史母片被覆盖：run01 `ff119fcd` / run02 `ad52a0c0` / run03 `871489f9` / 前版 run04 `074985a5` 复验不变；冻结 14/14；render_v3/retrieval_run3/cv2_run 未触碰。

## 人工决策记录（本 Run 依赖，均已入 manifest）

- REVIEW 近域签核 5 拍（S09-B02/S12-B02/S13-B01/S17-B02/S29-B02，S19-B02 排除）
- S20-B03 抽象渲染信号覆盖→HN（人工像素基准判定）

```
RUN04 PRODUCTION (G10) = PASS
MOTHER_RENDERED = YES（2f0e6687，101/101 拍，QA 全过）
HUMAN_QA = PENDING
STOP——等待人工母片 QA（域一致口径首个成片；不自行进入下一阶段）
```
