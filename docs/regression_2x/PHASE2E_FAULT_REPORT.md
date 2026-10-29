# 3.x Phase 2-E 故障注入报告：真实外部 Provider（Wikimedia Commons）失败路径

- 日期：2026-09-13
- 驱动：`python docs/regression_2x/phase2e_failure_paths.py`（本轮 **29/29 通过**）
- 原始记录：`logs/phase2e_failure_paths.json`（含每次尝试的 `attempts[]`）
- 相关证据：`logs/auth_probe.txt`（真实 401 可达性）、`logs/query_shaping_probe.txt`（查询整形）、
  `logs/provider_reachability.txt`（provider 可达性选型）、`logs/phase2e_real_provider.json`（成功链路）

## 性质标注（真实 / 受控）

| # | 用例 | 性质 | 说明 |
|---|---|---|---|
| 1 | 未配置 API key | **受控配置** | `auth.require_key=true` 且环境无该变量 |
| 2 | 鉴权失败 | **真实** | 向真实端点发送无效 Bearer → 真实 HTTP 401 |
| 3 | 429 限流 | **受控注入** | 真实 429 亦在成功链路中实测到（`rate_limited=21`） |
| 4 | 搜索超时 | **真实** | `timeout_s=0.001` 打真实端点 |
| 5 | 下载超时 | 真实 URL + **下载腿注入** | 搜索为真实网络，仅下载腿注入超时 |
| 6 | 下载内容损坏 | **真实 provider 字节**（缓存复用，sha256 可核对）+ 受控截断 | 媒体主机限流时使用此前真实下载并校验过的字节 |
| 7 | 许可证缺失 | 受控（真实候选去掉许可证字段） | 真实搜索 + 真实候选 |
| 7b | 许可证受限 | 机械分类断言 | `fair use` → `RESTRICTED`（不清权） |
| 8 | 真实素材被 BLOCKED | **真实候选 + 真实字节**（缓存复用）+ 策略上限 20 KiB | 流式大小上限触发拒绝 |

## 结果（全部断言通过）

| # | 错误码（实测） | 是否成为正常命中 | 是否落盘 | render | 成片 |
|---|---|---|---|---|---|
| 1 | `PROVIDER_NOT_CONFIGURED` | 否（verified=0） | 否 | **BLOCKED** | 无 |
| 2 | `PROVIDER_AUTH_FAILED`（真实 401） | 否 | 否 | **BLOCKED** | 无 |
| 3 | `PROVIDER_RATE_LIMITED` | 否 | 否 | **BLOCKED** | 无 |
| 4 | `PROVIDER_TIMEOUT` | 否 | 否 | **BLOCKED** | 无 |
| 5 | `PROVIDER_TIMEOUT`（逐候选） | 否 | 否 | **BLOCKED** | 无 |
| 6 | `ASSET_TRUNCATED`（逐候选） | 否 | 否 | **BLOCKED** | 无 |
| 7 | `ASSET_LICENSE_MISSING`（逐候选）+ `needs_hitl=true` | 否 | 否 | **BLOCKED** | 无 |
| 7b | `RESTRICTED` → 不清权（拒收路径） | 否 | 否 | — | — |
| 8 | `ASSET_OVERSIZE`（逐候选） | 否 | 否 | **BLOCKED** | 无 |

每条用例都断言四件事：
1. **明确错误码/状态**（候选 `status=REJECTED` + `error_code`，或 `external_error` 具体码）；
2. **未成为正常命中**：`external_verified=0` 且候选列表里没有该 provider 的条目；
3. **不进入正常 ffmpeg 渲染**：无成片 + `render BLOCKED` + 错误文案含 `[ASSET_INSUFFICIENT]`；
4. **按定义进入 fallback / HITL / BLOCKED**：许可证类候选置 `needs_hitl=true`，其余按 Phase 2-C
   `ASSEMBLY_BLOCKED` 阻断。

## 真实 401 的原始证据（`logs/auth_probe.txt`）

```
{"case": "read_anon",          "auth": false, "status": 200, "head": "{\"batchcomplete\":\"\",\"query\":{\"general\":..."}
{"case": "read_anon",          "auth": true,  "status": 401,
 "head": "{\"httpCode\":401,\"httpReason\":\"Jwt is not in the form of Header.Payload.Signature with two dots and 3 sections\"}"}
```

## 环境抖动的诚实处理（重要）

真实媒体主机（`upload.wikimedia.org`）在短时间内多次下载后会返回 **429**，而**搜索 API 仍正常**。
本轮实测：`rate_limited=21`，单轮 `download_ms` 高达 466,957 ms（靠退避重试最终成功 1 个候选）。
因此：

- 代码侧：`_throttle()` 让请求与下载共用最小间隔；429 使用独立退避
  （`rate_limit_backoff_s`，默认 10 s×n、上限 30 s）与独立重试预算（`rate_limit_retries`，默认 3）；
  限流次数计入 `stats.rate_limited`（要求 8 的"失败原因/请求次数/耗时"）。
- 驱动侧：资产层用例内置**抖动识别 + 重跑**（传输层抖动、或没有任何候选走到资产层判定时重跑，最多 3 次），
  每次尝试写入 `attempts[]`；并在媒体持续限流时改用**此前真实下载并校验过的缓存字节**
  （`byte_source=cached_real_download:<sha256>`，sha256 可核对）施加受控变形——
  **不把"这次网络不好"写成用例结论，也不伪造字节**。

## 未做（越界）

未接入第二个 Provider；未做多 Provider 竞价/复杂排序；未做自动许可证判定；
未做 BGM/自动发布/UI 大改/语义级对齐/成本对账/Git tag。
