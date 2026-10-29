# 3.x Phase 3-A 断点（2026-09-13 收工归档 → 2026-09-15 **已闭合**）

> **状态：本断点已于 2026-09-15 续做闭合，仅供追溯，不再是续做入口。**
> 网络恢复后真实链路已跑通（**全链路核验 16/16 PASS / 0 FAIL / 0 PENDING**），阶段判定 **PASS**，
> 基线 `3.x-phase3a-baseline` 已冻结；结论看 **`PHASE3A_REPORT.md`**，进度看 **`STATUS.md`**。
> 本文保留的价值：① 首轮为何记 PENDING（环境证据）；② 收工时的归档指纹；③ **`--resume` 语义的更正**（§3）。

---

## 1. 首轮（收工时）的状态

3-A 的**代码、交付物、断言、回归全部完成**（`attribution`/credits 台账 + 许可机械分类与门禁 + 查询整形修正），
真实 LLM / 真实 TTS / 旁白闸门 / 时间轴 / 渲染 / 解码已在真实项目跑通；
**当时唯一未完成项**：本次真实搜索+下载 Wikimedia 素材——执行期间 Wikimedia 全部域名被网络链路阻断
（TLS 握手超时），故该项记 **PENDING（环境）**，**未冒充 PASS**。次日网络恢复后重跑即全绿（含又修掉一个
查询整形缺陷，见报告 §7 缺陷 9）。

## 2. 已完成（可直接引用，无需重跑）

| 项 | 结果 | 证据 |
|---|---|---|
| 署名/许可台账交付物 | **24/24** | `tests/attribution_compliance_test.py`；样例见报告 §1 |
| 真实链路（LLM/TTS/闸门/时长/渲染/解码） | PASS | 项目 `p_f4b466a4a024`；`logs/phase3a_real_chain.json` |
| 真实下载字节上的外部素材链路 | **13/13** | 项目 `p_a2fe33da8739`（redo render v2 `t_36cc6ee3df8f`，attribution `a_3f45053226a6`） |
| 32/32 套件 rc=0 | PASS | `logs/suites_summary.json`（见 §4 的**口径说明**） |
| 3 机械 E2E / ingest / 2-C / 2-D / 2-A·B | 全绿 | `logs/phase3a_*.log`、`logs/phase3a_regression_batch.json` |
| 阶段快照 | **MATCH** | `3.x-phase3a-wip`（sha 见 §6），`verify_baseline.py` 零漂移 |

**本阶段修的真实缺陷（8 项，含 1 次真实回归）**：见 `PHASE3A_REPORT.md` §7。
其中最重要的是：新增分类阶段许可门禁**过度适用**（把 local_ingest 自带素材也拦掉）→ 冻结套件 3 个失败（29/32）
→ 收窄为"外部素材"范围后 **32/32 恢复**；以及 `attribution` 先挂载导致 `render_output` 不再是 `artifacts[0]`
（`pipeline_mock` 失败）→ 改为**先写文件、后挂载**。

## 3. 续做时的实际经过（含一处**更正**：`--resume` 不重跑取数链）

### 更正：`phase3a_real_chain.py --resume <pid>` **只做核验**，不会重做已 SUCCEEDED 的任务

续做时先按原计划执行 `phase3a_real_chain.py --resume p_f4b466a4a024` → 它只推进未结算任务（此处 0 个）并复核，
因此读到的仍是**首轮**产物（`used="画面并置 Quest PSVR2 PICO"`、`downloaded_bytes=0`），核验依旧 FAIL。
**正确的重跑取数链命令**（次日实际使用的就是这一串）：

```bat
cd C:\mp4agent\video-studio
C:\python3.13\python.exe docs\regression_2x\list_tasks.py p_f4b466a4a024          :: 取 retrieval/render 的 task_id
C:\python3.13\python.exe run.py --config config\config.real.provider.json redo t_e21a0e842b9b   :: retrieval
C:\python3.13\python.exe run.py --config config\config.real.provider.json run p_f4b466a4a024 --limit 4
C:\python3.13\python.exe run.py --config config\config.real.provider.json redo t_ec83e67de429   :: render
C:\python3.13\python.exe run.py --config config\config.real.provider.json run p_f4b466a4a024 --limit 4
C:\python3.13\python.exe docs\regression_2x\phase3a_real_chain.py --resume p_f4b466a4a024        :: 只核验
```

### 实际结果（2026-09-15）

1. 网络恢复（`commons` TLS 1.74s、`upload` TLS 4.62s）。
2. 实时查询阶梯实测（`logs/phase3a_query_ladder.txt`）：4 词 0 命中 / 3 词 0 / 2 词 1 条非图片 / 单词 8 条
   → 定位到**第二个查询整形缺陷**（跨镜头品牌被 AND 成一个查询），修为**按拉丁词簇逐条查询**。
3. redo retrieval：`material_mode=external`、**真实下载 11,543,130 字节**、4 个候选通过全部校验。
4. redo render：6 镜头全用外部素材、`assembly=SUCCEEDED`、台帐 6 条。
5. 全链路核验：**16/16 PASS / 0 FAIL / 0 PENDING**（`logs/phase3a_real_chain.json`）。
6. 全批次回归在同一份代码上重跑，`phase3a_classify_batch.py` → **非预期结果 = 0**。
7. 冻结基线 `3.x-phase3a-baseline` 并校验 **MATCH**。

> **判定口径（保持不变）**：只有真实链路通过，才把报告 §0 第 9 项从 PENDING 改成 PASS；
> **绝不允许**跳过真实链路直接把 `-wip` 改名成 `-baseline` 或把 PENDING 写成 PASS。

## 4. 口径说明（避免明天误读）

- **`3.x-phase3a-wip` 不是验收基线**：它只是"最终代码 + 最终根文档"的可复现快照；2-E 基线仍是当前**唯一验收基准**。
- 报告 §8 的 **32/32** 来自最终编辑前的代码状态；两个消费被改文件的套件已在最终代码上重跑绿（见第 1 步）。
- run 1 的 `B1/B2/B3/C1/C2/D3/D4` 是**空集上的通过**（当时没有外部素材），**不得**当作"合规已证"；
  合规证据是套件（构造受限候选）+ 真实字节核验（13/13）。
- `config/config.json` **未改动**（`b264644539b2adbb…`，默认 `provider=none`）；真实链路一律用
  `config/config.real.provider.json`。
- 本地自带素材（local_ingest）**不在许可门禁范围**（3-A 新增的两道门禁只作用于外部候选）；
  provider 层既有门禁未改，空/未声明许可证在 2-E 与 3-A 下结果相同（报告 §2 已逐字核对 2-E 源码）。

## 5. 环境事实（明天先看这个）

- **Wikimedia 被链路阻断**（当日实测，连续 30+ 次、跨 ~50 分钟全部失败）：
  - `commons/upload/api.wikimedia.org`、`en.wikipedia.org`：**TCP 0.2s 可连，TLS 握手超时**（TLS1.2/1.3 都一样）；
  - DNS 解析为真实 Wikimedia 网段 `103.102.166.224/240`（**不是** DNS 污染）；
  - 同机 `api.deepseek.com`、`speech.platform.bing.com`、`www.baidu.com`、`www.example.com` **TLS 全部正常**。
  - 证据：`logs/phase3a_net_probe.txt`、`logs/phase3a_tls_probe.txt`、`logs/phase3a_dns_probe.txt`、
    `logs/phase3a_network_wait.txt`、`logs/phase3a_network_watch_long.txt`。
- Phase 2-E 当日同一代码可达 Commons → 说明是**外部环境变化**，不是本机代码/配置/凭据问题。
- Windows/PowerShell 陷阱（继续遵守）：不要用内联 heredoc 写 Python（写成 `.py` 文件再跑）；
  不要用 `Get-Content | Set-Content` 处理中文；控制台乱码是显示问题，以 `read` 工具输出为准。

## 6. 归档清单（收工时的数据）

| 归档 | 路径 | 指纹 |
|---|---|---|
| 断点快照（工作树） | `docs/regression_2x/snapshots/3.x-phase3a-wip-20260913.zip` | sha256 `ae377d45223ad0374e317f96bd92ce9f2a4c56a805f4ebd37c19b04f4dcf2920` |
| 断点快照（项目 DB） | `docs/regression_2x/snapshots/3.x-phase3a-wip-20260913.db` | sha256 `5b41a600af30f0cf2f39d3cf6f7eb07739a6cd409b6965260283e9d6923c670e`（7,045,120 B） |
| 快照元数据 | `docs/regression_2x/snapshots/3.x-phase3a-wip-20260913.json` | 335 文件 / 7,326,138 源码字节 |
| 阶段快照（含 manifest） | `docs/regression_2x/baseline/3.x-phase3a-wip.zip` + `baseline_manifest_3.x-phase3a-wip.json` | 同上 zip sha；`verify_baseline.py` → **MATCH** |
| 上一验收基线（未动） | `docs/regression_2x/baseline/3.x-phase2e-baseline.zip` | sha256 `2a2b9ac855ef143a8d423f5ec203ebd764b91069ce916b03932b913073bf7fb5` |
| 报告 | `docs/regression_2x/PHASE3A_REPORT.md` | §0 判定表、§10 快照身份 |
| 原始日志 | `docs/regression_2x/logs/phase3a_*`、`logs/suites_summary.json` | 全部保留 |

## 7. 不要顺手做的事（越界清单）

BGM、第二个 Provider、多 Provider 竞价、语义级自动改选材、响度统一、成本对账、`run.py report`、
UI 大改、Git tag、推翻重构、把 PENDING 改写成 PASS。**这些都要等下一阶段授权。**
