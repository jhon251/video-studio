# 5-F 最终收尾报告（代理环境验证 · 结项）

- 日期: 2026-09-18 · 前序: PRE-PRODUCTION FINAL AUDIT (G10) 之外独立线——5.x Phase 5-F 断点续作与结项
- **注意: 本轮全部成功结果为"代理环境验证"**（HTTP_PROXY/HTTPS_PROXY/ALL_PROXY = http://127.0.0.1:7890；wikimedia 直连 TLS 超时期间经代理完成电池），不得表述为"原直连环境恢复"
- 探测记录: `logs/ss3_proxy_probe.json`（2026-09-18T16:46:39 · HTTP 200 · 1.9s · 项目 UA · 经代理 · 3 页 JSON）

## 1. 授权要求逐项完成

| # | 要求 | 结果 |
|---|---|---|
| 1 | 代理探测单独记录 | ✅ `logs/ss3_proxy_probe.json`（时间/代理/状态码/耗时/UA 全录）|
| 2 | 不覆盖直连超时/24/25 失败轮/PENDING 历史 | ✅ 直连超时记录保留于续作档 §网络窗口探测记录；24/25 轮与调度失误完整留痕（续作档 §过程事件 + `logs/phase5f_rerun_stale_20260918_dir/` 203 文件移位存档）|
| 3 | 同一代理环境独占 GBK 电池 | ✅ 独占单进程（启动前进程核查仅无关项目），去 PYTHONUTF8（GBK 口径）+ 注入代理变量 |
| 4 | 禁并发/禁压测/禁中途插入 | ✅ 无并发电池；无中途恢复脚本插入；全程未压测 |
| 5 | 目标 25/25 rc=0 | ✅ **25/25**（all_rc_zero_raw=True；run.txt 50 处 rc=0、0 处 rc≥1）|
| 6 | evidence ALL_GREEN=true | ✅ **ALL_GREEN=True**（suites 46/46 rc0、failed=[]、restored True）|
| 7 | 恢复冻结日志 + 独立复验 DRIFT 0 | ✅ 电池自带恢复 True + 独立复验脚本再验：504 文件回拷后 **DRIFT 0** |
| 8 | Judge 43/43 · 真值 14/14 · DoD 12/12 · 套件 46/46 | ✅ 四项全过（suite_mm_judge_test 43/43；judge 14 例 0 违例 0 未解决；dod_all_pass=true；46/46）|
| 9 | 冻结 5.x-phase5f-baseline + manifest/SHA256/verify MATCH/delta/快照/报告/归档 | ✅ 全部完成（见 §2）|
| 10 | 代理环境验证标注 | ✅ 本报告与 BASELINE_README 5-F 行均已显式标注 |
| 11 | STOP 不进 5.x Final | ✅ |

## 2. 5.x-phase5f-baseline（当前基准）

- 路径: `docs/regression_2x/baseline/5.x-phase5f-baseline.zip`
- SHA256: **`e4dd33ad427020250ae83fc3e53cabca6baf27fd1d5606e375264ca37c39dc4d`**
- 378 文件 / 8,213,757 B 源 / 6,121,278 B zip；manifest: `baseline_manifest_5.x-phase5f-baseline.json`
- `verify_baseline.py` → **MATCH**（missing 0 / drifted 0）
- 相对 5-E delta: **修改 3 / 新增 4 / 删除 0**（与授权预期一致）：
  - MODIFIED: CHANGELOG.md · STATUS.md · src/video_studio/cli.py
  - ADDED: core/mm_judge.py · ops/mm_judge.py · tests/fixtures/mm_judge_truth_v1.json · tests/mm_judge_test.py
- 快照: `snapshots/5.x-phase5f-20260917`

## 3. 质量确认

- Judge: **43/43** 单元 · 冻结 14 例 **14/14 满足真值**（0 违例/0 未解决）
- 最终判定: MATCH=4 / MISMATCH=3 / UNKNOWN=6（UNKNOWN ≥ 下限 5，合法保留；未放宽任何条件）
- DoD: **12/12 PASS**（dod_all_pass=true）
- 套件: **46/46 rc=0**（含 subprocess_encoding_test 6/6——GBK 口径下通过）
- 阈值: thresholds_touched=False；只读四项 True；三层未覆盖 True
- 处置: R3/R4/R6 进最终产品 · R1/R2 未来研究 · R5 产品决策

## 4. 诚实记录（未删除/未伪装）

1. **直连不可达历史**: 今晨起 wikimedia 对本线路 TLS 握手超时（三次直连探测 20–23s 全超时），记录于续作档 §网络窗口探测记录
2. **24/25 失败轮**: 早期 GBK 电池因 wikimedia 不可达致 `phase2e_failure_paths` 4 项网络注入失败（后两轮为 25/29→24/29 漂移），失败明细全录
3. **调度失误**: GBK#1 未结束即启动 GBK#2 的并发写日志事故 + 一次恢复脚本跑在电池中途——已披露（续作档 §过程事件），三层原始证据零触碰（每轮后 DRIFT 复验 0）
4. **陈旧失败件移位**: `logs/phase5f_rerun/`（首轮中间失败件 203 文件）→ `logs/phase5f_rerun_stale_20260918_dir/` 移位存档，未删除

## 5. 状态

```
5-F = 已结项（CLOSED）· 基线 5.x-phase5f-baseline（e4dd33ad）= 当前基准
代理环境验证 = 是（非直连恢复）
5.x Final = 未进入（等待人工授权）
STOP
```
