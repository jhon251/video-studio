# 断点归档：3.x Phase 2-E（2026-09-13 收工）

> 用户要求关机、归档数据、次日从断点继续。本文件是**唯一续做入口**：
> 先读本文件 → 再读 `PHASE2E_*` 未完成清单 §4 → 按 §5 顺序执行 → 完成后才写报告并冻结 baseline。

## 1. 归档物（已落盘，可直接核对）

| 归档 | 路径 | sha256 |
|---|---|---|
| 工作树快照（333 文件 / 7,274,958 源码字节，**非基线**） | `docs/regression_2x/snapshots/3.x-phase2e-wip-20260913.zip` | `913107db59c2c9de9306d5925998ff5193a0bd66e77fd845fd3fb38368e0f174` |
| 项目状态库（5,140,480 字节，185 项目 / 2266 任务 / 1941 产物） | `docs/regression_2x/snapshots/3.x-phase2e-wip-20260913.db` | `9e97b83811abce64b1e35d6dabf0fc3c59fc94fc727795635744b3b7a192e02f` |
| 快照元数据 | `docs/regression_2x/snapshots/3.x-phase2e-wip-20260913.json` | — |

- 快照内容 = `src/ config/ tests/ scripts/` + 根文件（`run.py pyproject.toml README.md CHANGELOG.md STATUS.md`），
  排除 `docs/ projects/ output/ bin/ .venv_tts/`。重建：`python docs/regression_2x/make_snapshot.py <tag>`。
- **当前基线仍是 `3.x-phase2d-baseline`**（sha256 `27b28f7d…`，ZIP 与清单一致、无缺失；
  因 Phase 2-E 改了 5 个源码文件，`verify_baseline` 会按预期报 `drifted vs tree`）。
  Phase 2-E **尚未冻结基线**（阶段未完成，等 §5 全绿后再冻结 `3.x-phase2e-baseline`）。

## 2. 收工时的状态（诚实记录）

- 已停掉后台任务；被中断的 1 个任务已用**既有机制** `python run.py recover` 恢复（`p_c7622f655cf2 / t_e44587cae462 retrieval`：
  RUNNING → INTERRUPTED → PENDING）。当前 `RUNNING/DISPATCHED` 任务数 **0**。
- 全部改动文件语法检查通过（`python docs/regression_2x/checkpoint_check.py`）。
- 收工时**最后一个验证批次被中断**（3 条命令只跑完一部分）：`tests/material_provider_test.py`、
  `phase2e_failure_paths.py`、`phase2d_boundary_matrix.py` 需要按 §5 重跑（这是唯一"未跑完"的动作）。

## 3. Phase 2-E 已完成并经真实证据确认的部分

| 项 | 结论 | 证据 |
|---|---|---|
| 真实 Provider 选型与可达性 | **Wikimedia Commons**（免费、无 key、无付费/不可逆额度；HTTP 200 / 3.9s / 3882 hits） | `logs/provider_reachability.txt`（另测：Openverse 超时、Met 200、NASA 200） |
| 真实搜索 → 标准化 | 8 条真实候选，`provider/source_id/source_url/license/attribution` 齐全；许可证类别机械分类（`PUBLIC_DOMAIN` / `FREE_ATTRIBUTION`） | `logs/phase2e_real_provider.json`（`provider_stats.response_digests[0]`） |
| 真实下载 → 校验 → 缓存 | 3,636,037 字节真实下载；内容寻址缓存 `external/<sha256>.jpg`；真实 **HTTP 429** 触发重试并被记录（`retries=10`） | 同上 `provider_stats` |
| 真实成片链路上屏 | S01 `Public domain`（corr **0.486**）、S02 `CC BY-SA 4.0`（corr **0.996**）均 `appears_in_film=true`；成片 10.0s / 2 流 / decode rc=0 | `logs/phase2e_real_provider.json` → `render.material_timeline` |
| 失败路径（8 类） | 28/29 断言通过（唯一"失败"是我漏列了新错误码 `ASSET_TRUNCATED`，已修断言，待重跑） | `logs/phase2e_failure_paths.json` |
| 真实 401 可达性 | 真实端点 + 无效 Bearer → **HTTP 401**（"Jwt is not in the form of Header.Payload.Signature…"） | `logs/auth_probe.txt` |
| 真实查询整形必要性 | 完整旁白拼接查询 → **0 命中**；去重取前 3–4 词 → 命中理想结果（含中文查询 0 命中的真实现象） | `logs/query_shaping_probe.txt` |

## 4. 本阶段新发现并已修的 4 个真实缺陷（都在代码里，未冻结）

1. **截断文件能骗过全部旧检查**（真实下载被截断时）：magic bytes / ffprobe / ffmpeg 解码 rc=0 / `PIL.verify()`
   全部通过 → 新增 `container_integrity()`（JPEG EOI、PNG IEND、WEBP RIFF 长度）+ `PIL.load()` 完整解码
   → 新错误码 **`ASSET_TRUNCATED`**。
2. **检索层把具体错误码塌缩**成 `PROVIDER_DOWNLOAD_FAILED` → 改为透传 `TransportError.code`
   （`PROVIDER_AUTH_FAILED` / `PROVIDER_RATE_LIMITED` / `PROVIDER_TIMEOUT` / `PROVIDER_SEARCH_FAILED`）。
3. **中文查询导致 `UnicodeEncodeError`**（URL 未编码）→ 改用 `urlencode(quote_via=quote_plus)`。
4. **文件名白名单过严**误伤真实素材名（含逗号/括号）→ 改为危险字符黑名单；并新增**查询整形**
   （去重取前 N 词，纯查询卫生，非语义）与**下载腿节流**（真实 429）。

另有 1 处为真实数据驱动的判据放宽（**已修**）：抽帧核验原先要求 argmax 等于期望素材，两张相似真实照片
（同一主题）会误判失败 → 改为"期望素材相关度达标且不明显低于最高者（margin 0.15）"，并把
`corr_expected / corr_best` 写入证据。

## 5. 次日续做顺序（照抄执行即可）

```powershell
cd C:\mp4agent\video-studio

# 0) 先确认环境与断点
python docs\regression_2x\checkpoint_check.py          # 期望：stuck tasks = 0，语法全 OK
python docs\regression_2x\verify_baseline.py 3.x-phase2d-baseline
#   注意：该命令会把**冻结 ZIP** 与**当前工作树**对比。Phase 2-E 改了源码，因此
#   `drifted vs tree` 会列出 5–6 个文件、VERDICT=DIFF —— 这是**预期**（阶段进行中，树已前进）。
#   只需确认前 3 行：`zip exists: True`、`zip hash matches manifest: True`、
#   `manifest file list == zip entries: True`、`missing in tree: 0 []` —— 即**冻结基线本身完好**。
python -c "print(open(r'docs/regression_2x/snapshots/3.x-phase2e-wip-20260913.json',encoding='utf-8').read())"

# 1) 重跑收工时被中断的 3 项验证（Phase 2-E 证据收口）
python tests\material_provider_test.py                 # 期望 46/46
python docs\regression_2x\phase2e_failure_paths.py     # 期望 29/29（已补 ASSET_TRUNCATED 断言）
python docs\regression_2x\phase2d_boundary_matrix.py   # 期望 40/40（不得退化）

# 2) 真实 Provider 全链路（真实网络；无 key、无付费）
python docs\regression_2x\phase2e_real_provider.py     # 期望 13/13（真实搜索/下载/上屏）

# 3) Phase 2-E 要求的完整回归
python docs\regression_2x\run_all_suites.py            # 期望 31/31（含新增 provider 测试）
python docs\regression_2x\run_all_tests.py --fresh     # 期望 3 组全 SETTLED
python docs\regression_2x\real_small_test.py           # 期望 PASS 且 MockLLM=0
python scripts\check_binaries.py                       # 期望 ffprobe 真实性 PASS
python docs\regression_2x\run_ingest_test.py           # 期望 PASS（local_ingest 未退化）
python docs\regression_2x\phase2c_fault_matrix.py      # 期望 A/C 出片、B/D BLOCKED（不退化）
python docs\regression_2x\phase2c_trace.py             # 期望 38/38
python docs\regression_2x\phase2_accept.py --verify p_ab2b352e06b8   # 期望 PASS（2-A/B 契约未变）

# 4) 以上全绿后：写报告 → 更新文档 → 冻结基线
#    PHASE2E_REPORT.md / PHASE2E_FAULT_REPORT.md（含真实请求/下载/许可证证据）
python docs\regression_2x\make_baseline.py 3.x-phase2e-baseline --no-docs
python docs\regression_2x\rebuild_manifests.py
python docs\regression_2x\verify_baseline.py 3.x-phase2e-baseline   # 必须 MATCH
#    并更新 CHANGELOG/STATUS/README/BASELINE_README（把新基线写进表）
```

## 6. 未做 / 明确越界（次日不要顺手做）

- 未接入第二个 Provider；未做多 Provider 竞价/复杂排序；未做自动许可证判定。
- 未做 BGM、自动发布、UI 大改、语义级镜头↔旁白对齐、成本对账、Git tag。
- 未冻结 Phase 2-E 基线（阶段未完成）；未把任何 BLOCKED/FAILED/PENDING 改写成 PASS。
- 真实 Provider **未配置**时默认行为不变：`config/config.json` 仍是 `provider=none`（未被改动）。

## 7. 需要注意的环境事实（避免重复踩坑）

- 本机网络：`commons.wikimedia.org` / `upload.wikimedia.org` 可达；`api.openverse.org` 超时；
  `raw.githubusercontent.com` 不可达；`speech.platform.bing.com` 间歇性断开（影响 TTS，见 Phase 2-B.1）。
- Wikimedia 礼仪：请求与**下载**都要节流（实测下载 429）；已内置 `min_interval_s=1.0` 与 429 退避重试。
- PowerShell 5.1 中文陷阱：不要用 `Get-Content | Set-Content` 处理中文文件；不要用内联 heredoc 写 Python
  （写成临时 `.py` 文件再执行）；控制台输出乱码属显示问题，文件内容以 `read` 工具为准。
