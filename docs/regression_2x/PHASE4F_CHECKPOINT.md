# 4.x Phase 4-F 完成与交接（2026-09-16）

> **状态：4-F 可选 BGM + 旁白 ducking 已完成并冻结基线**。结论看 `PHASE4F_REPORT.md`，进度看 `STATUS.md`。
> **BGM 默认关闭；未进入 4-G。**

## 0. 一句话结论

在**不改默认行为、不改数据库结构、不接第二 Provider**的前提下，给成片加了**可选** BGM：
来源/字节/许可/attribution 全量校验（失败即 fail-closed，不静默降级）、**确定性可复算的 ducking 规则**
（旁白期间 -26 dB / 之外 -20 dB / 250 ms 线性过渡，旁白优先），最终母带仍满足既有响度契约
（实测 **-15.9 LUFS / TP -8.0 dBTP**）。

## 1. 冻结产物（可直接引用）

| 项 | 值 |
|---|---|
| 前置基线 | `4.x-phase4e-baseline.zip` sha256 `275f9a1aa5f4f2f493df10dabcbfd544438146d40679ff47951433d90eb0f55b` |
| **新基线** | `4.x-phase4f-baseline`：357 文件 / 7,759,635 字节 / zip sha256 `214374a1d14a6daf2729c7a8df63056bb8562dcaa4fa5e27e4e5d7cd59f45a23`（`verify_baseline.py` **MATCH**） |
| manifest | `baseline/baseline_manifest_4.x-phase4f-baseline.json` |
| 快照（非基线） | `snapshots/4.x-phase4f-20260916.{zip,db,json}`（DB sha256 `5bda3091f06eef59…`） |
| 证据 | `logs/phase4f_bgm_evidence.json`、`logs/phase4f_evidence_summary.txt` |
| 变更清单 | `logs/phase4f_change_list.json`（代码 修改 2 / 新增 2 / 删除 0） |

## 2. 交接要点（继续时先看这里）

1. **不要**把 `tools.bgm.enabled` 默认改成 true（授权要求"Optional Extension、默认关闭"）。
2. **BGM 路径的母带是两遍线性 loudnorm**（`core/audio.normalize_two_pass`）：因为**单遍动态** loudnorm 在
   含 BGM 的大动态混音上实测只到 -19.5 LUFS（偏差 3.5 LU > 3 LU 收尾校正上限 → 按契约 fail-closed）。
   BGM 关闭时**不启用**该函数，既有单遍链一字未改；改这条链前请先读 `PHASE4F_REPORT.md` §6。
3. **ducking 是"时间段规则"，不是信号侧链**：时间段来自 voice 产物的逐段真实时长；改它会改变 `volume` 表达式
   与实测差值（`tests/bgm_ducking_test.py` B/E 组会失败）。
4. **不许**为了"让 BGM 用上"而绕过校验（许可/attribution/sha256/静音/异常响度）——那是本阶段的核心不变量。
5. 4-B 真值仍钉 `a_2ed5f41d6b58`；4-C 版本链当前 **v5 `t_b8f866ddc062`**；4-D 缓存/重试默认关闭；4-E 检索改进默认关闭。
6. 两项 Wikimedia 真实网络用例仍记 `PENDING（环境）`（本轮实测通过，**状态不得改写**）。
7. 进入 4-G、接入第二 Provider 或真实音乐来源：**需要新的授权**。

## 3. 复现命令（离线，约 3–6 分钟）

```powershell
cd C:\mp4agent\video-studio
C:\python3.13\python.exe tests\bgm_ducking_test.py                  # 48/48（含 10 条路径）
C:\python3.13\python.exe docs\regression_2x\phase4f_evidence.py      # 证据（校验矩阵/ducking 实测/成片）
C:\python3.13\python.exe docs\regression_2x\run_all_suites.py        # 40/40
C:\python3.13\python.exe docs\regression_2x\verify_baseline.py 4.x-phase4f-baseline
```
