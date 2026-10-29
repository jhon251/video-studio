# PHASE5F 续作状态（2026-09-18 会话 · 外部网络阻塞，fail-closed 停止）

## 接手核验（全部通过）

| 项 | 结果 |
|---|---|
| 5-E 基线 zip | 实测 `3934369a7f62e14ca93a08b58c24b898…` 与 BASELINE_README/PHASE5E_CHECKPOINT/PHASE5E_REPORT 三处权威记录**一致**；断点卡 §4 的"授权值" `…c24a898…` 为**一位笔误（a→b）**，文件无漂移 |
| 收工归档 zip | sha256 `0b594674…` 与断点卡一致 ✅ |
| Judge 真值覆盖层 | `a6332858a94d4a7f1a808ca7e4e5c93…` 与断点卡一致 ✅ |
| 断点可接手 | 是 |

## 本次会话完成

1. **步骤① DRIFT 复验**：`phase5f_restore_frozen.py` → 503 文件、中断改写 0、回拷后 DRIFT 0 ✅
2. **环境差异根因查明**：harness 注入 `PYTHONUTF8=1` → `subprocess_encoding_test` 的 2 项 GBK 前置断言在 utf-8 模式下不可复现而 FAIL；**在用户正常环境（PYTHONUTF8 去除，preferred=cp936）下该套件 6/6 全过**。此为环境差异，非产品缺陷。
3. **电池三跑**（两次 GBK + 一次 utf-8 复验），每次均以"跑完自动恢复冻结日志"收尾，每轮后均复验冻结恢复。

## 唯一剩余阻断（外部网络，实测）

**wikimedia 对本线路的 TLS 握手超时**（电池后立即双次实测：30.4s/32.3s 握手超时；今晨 10:26–11:03 电池窗口内网络健康）。

- 后果：GB 环境电池 **24/25 步 rc=0**，唯一红项随网络状态**漂移**：
  - GBK#1（12:2x–13:28）：`phase2e_failure_paths` 25/29（4 项网络注入失败）
  - GBK#3（14:2x–16:0x 独占干净轮）：同一套件部分项仍网络失败，且 `phase2e_real_provider` 以未捕获 TransportError 中断（wikimedia 当时不可达）
- 非网络项（含全部 5-F 实现：judge 43/43、冻结 14 例 14/14、DoD 12/12）**全部稳定通过**
- utf-8 对照轮（今晨）：25/25 rc=0 全绿（当时网络健康），唯一红为编码套件环境项
- 证据汇编现状：suites 46/46 rc=0 ✅（ 陈旧 `phase5f_rerun/` 失败件已移位存档 `logs/phase5f_rerun_stale_20260918_dir/`，evidence 的 rerun-first 优先级不再误读）；ALL_GREEN=False 仅因 `phase2e_failure_paths`（needs_network）

## 已如实披露的过程事件（不影响冻结证据）

- 我方调度失误：GBK#1 未结束即启动 GBK#2，两电池在 13:05–13:28 并发写同一日志组；随后一次恢复脚本也跑在 GBK#2 中途。三者均不动三层原始证据（每轮后 DRIFT 复验 0），但使当轮日志内容交错——**以最后一次独占轮的 summary 为准**。
- `phase5f_rerun/`（12:17 的 5 mm 套件失败记录）确认为首轮 GBK 的中间失败件，已整体移位存档；完成轮（第二轮 GBK）的套件实测 **46/46 全过**。

## 恢复条件与续作（网络窗口出现后，按序）

1. 探测确认 wikimedia 恢复（项目 UA 搜索 <5s 响应）
2. 重跑电池（GBK 环境，即用户正常环境去除 PYTHONUTF8）：期望 **25/25 rc=0**
3. `phase5f_evidence.py` → 期望 **ALL_GREEN=true**
4. 冻结 `5.x-phase5f-baseline`（make_baseline → make_manifest_one → verify MATCH → delta 修改 3/新增 4/删除 0 → make_snapshot）
5. 报告 §10/§11 + BASELINE_README 5-F 行 + 断点卡改"已结项" → 结项归档 → present → **STOP（不进入 5.x Final）**

## 纪律重申

未动 4-B/5-A/5-D 阈值与判定逻辑；未覆盖三层原始证据（每轮电池后恢复并 DRIFT 0）；未为通过率放宽任何条件；UNKNOWN 合法保留；2 项 Wikimedia 真实网络项保持 `PENDING（环境）`。

## 网络窗口探测记录（2026-09-18 收尾尝试 · 未出现窗口）

按"5-F 网络恢复后最终收尾"授权执行轻量探测（项目 UA 单次搜索，未压测）：
- 探测 1（即时）：TLS 握手超时 21.4s
- 探测 2（+4 分钟）：TLS 握手超时 20.4s
- 探测 3（+4 分钟）：TLS 握手超时 23.4s

**窗口未出现 → 未启动电池 → 保持 PENDING**；未做任何改写/冻结/归档/覆盖。
再次探测命令见本档历史（探测成功即按 §恢复条件与续作 五步执行）。

## 2026-09-19 补充：5-G 执行至 F 步停止（电池环境级联）

- 已完成：A 普查 / B 期望域草案 / C 双轮看片标注（p_ab2b 12 拍 7M+4MM+1U 边界；p_8f05 6 拍纯色 UNKNOWN）/ D v2 冻结（master sha256 a9fc7379…，32 例/3 项目，v1 原样 7eb952f2 未动）/ E 校验器 v2 分支（mm_quality_test 34/34 零回归）
- v2 三项目评估完成：p_f4b 14/14 OK 零回归（judge 14 行与 5-F 一致）；p_ab2b 10 OK + 2 VIOLATION（S06/S12 实例粒度分歧，如实披露）；p_8f05 6 拍层拒绝发证（fail-closed 正确）
- **F 步失败（停止）**：电池 24/25——`3a_regression_batch` rc=1（`phase2e_real_provider` TransportError，wikimedia 线路再次劣化）+ 5e 套件 F1 红项（DB 字节+行数断言与电池跨阶段累积不兼容——**基础设施作用域问题，需 F1 改为自身前后比对**，约 1 行改动，按停止纪律未实施）
- 5-G 基线未冻结（D6/D7 要求电池绿）；冻结证据已恢复 DRIFT 0
- 恢复后最小路径：网络窗口 → F1 作用域修正（1 行）→ 重跑电池 25/25 → evidence ALL_GREEN → 冻结 5.x-phase5g-baseline → G 步文档收尾

## 2026-09-19 补充 2：代理环境电池实测 + 定稿配方

代理电池实测（GBK + 代理，无 NO_PROXY）：**24/25 步 rc=0**。唯一红 = 批次内 4 项网络/环境失败：
1. `cost_boundary` / `real_small_test`：**localhost 连接被路由进代理**（WinError 10061 拒绝）——缺 NO_PROXY；
2. `real_small_test` LLM 调用走代理 → ProxyError——需 NO_PROXY=api.deepseek.com；
3. `phase2e_failure_paths` / `phase2e_real_provider`：wikimedia 直连已从 TLS 超时恶化为 TCP 拒绝（WinError 10061）——须走代理，但代理出口在批内被 wikimedia 限流。

**定稿配方（下次电池 = 本配方，零代码改动）**：
```
env -u PYTHONUTF8 \
  HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 ALL_PROXY=http://127.0.0.1:7890 \
  NO_PROXY="localhost,127.0.0.1,api.deepseek.com,.deepseek.com" \
  python -u docs/regression_2x/phase5f_regression.py
```
预期：本地 mock 直连 ✅ · DeepSeek 直连 ✅ · wikimedia 走代理（batch 35min 内若出口未被限流则 4 项全过）→ **25/25**。
若 wikimedia-via-proxy 仍限流 → 该 4 项红 → PENDING 继续（等待代理出口 IP 解封或更换出口）。

其余全部 5-G 实质工作已完成并验证（v2 真值集 32 例/3 项目/双轮标注/签核；v2 校验器分支；mm_quality 34/34；v2 三项目评估披露；v1 零回归）。

---

# 2026-09-19 深夜断点（关机归档 · 5-G 执行至 F 步中途）

## 当前状态
- **5-G = PENDING（执行至 F 步电池中途被关机中断）**；A-E 全部完成，F 未跑完
- 中断轮（run4，NO_PROXY 修正配方）跑到套件阶段被 taskkill 终止；其日志保留于 `logs/phase5g_regression_run4.txt`（原始证据，未删除）
- 恢复脚本报 DRIFT 1 = run4.txt 自身（冻结备份为启动时空文件，cosmetic；三层原始证据 5c/5d/5e 不受影响——restore 自身 drift_after 除该项外为空）

## 已完成（全部落盘）
- v2 真值集 master：`tests/fixtures/mm_truth_set_v2.json` sha256 `8adc2985d7fa044c1a3da24bfbed14c7fd7069c7ec066bc2a74e3fa0a919eb30`（32 例/3 项目；v1 14 例原样并入且 v1 文件 sha 7eb952f2 未动）
- 3 个子集：`mm_truth_set_v2_p_*.json`（每项目评估用）
- mm_quality.py 校验器 v2 分支 + mm_quality_test 34/34 零回归
- 中断前最后一轮完整电池（exec_cfc79014，20:32 完成）：24/25 rc=0，唯一红 = 5f G5（mm_quality sha vs 5-F 冻结值——**已授权改动的预期守卫动作**，非网络非缺陷）

## 明天开机续作（按序，约 60 分钟）
1. 探测 wikimedia（代理配方 NO_PROXY 不变）→ 可达即续
2. `python docs/regression_2x/phase5f_regression.py`（GBK 环境即系统默认；**勿设 PYTHONUTF8**；代理变量按需）→ 目标 **25/25 rc=0**（含 5f G5 转绿：守卫现钉 5-G manifest）
3. 若 25/25：`phase5f_evidence.py` → ALL_GREEN=true → 已冻结的 5.x-phase5g-baseline 即为有效基线（无需重新冻结）
4. 5-G 报告/KNOWN_ISSUES #43/#44 改写/STATUS/CHANGELOG → 验收报告 → STOP
5. 若 wikimedia 仍不可达：保持 PENDING，不冻结，不进 5.x Final

## 不变量（续作后复验）
v1 sha 7eb952f2 未动 · v2 master 8adc2985 · 冻结 14/14 · Run01-04 母片哈希不变 · mm_judge.py 零改动 · 阈值零触碰

## 2026-09-19 深夜补充 2：restore 循环根因定位（ALL_GREEN 唯一阻断）

- 现象：restore 重跑多次，`drift_after` 恒为 `[phase5g_regression_run5.txt]`
- 根因：**冻结备份文件与 MANIFEST 钉定哈希互相不一致**——
  - MANIFEST 钉定 run5.txt = **空文件**（e3b0c442…，电池启动时 redirect 刚创建的空文件被计入备份清单）
  - 备份目录中的 run5.txt = **59 字节**（上一轮电池 wrapper 的 "BATTERY_EXIT=0" 追加行被后续备份捕获）
  - restore 回拷 59B 备份 → 与 MANIFEST 空钉比较 → 恒 DRIFT
- **两者均为冻结证据基础设施内的记录载体**，修正任一都需要授权（不属 5-G 评估范围）
- 三层原始证据（5c/5d/5e 的实质内容）**不受此影响**（drift 项仅为电池退出码日志行）

## 恢复后最小路径（需授权，二选一）
1. 授权修正冻结备份：将 `logs_5e_frozen/phase5g_regression_run5.txt` 截断为空（与 MANIFEST 空钉一致）→ restore → DRIFT 0 → evidence ALL_GREEN
2. 授权修正 MANIFEST：将该条目 sha 更新为 59B 实测值 → 同效
（两者都只动冻结基础设施簿记，不动任何评估/判定/生产内容）
