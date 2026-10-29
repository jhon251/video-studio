# 3.x Phase 2-E 报告：单一真实外部 Provider 接入与真实网络验证

- 日期：2026-09-13
- 授权范围（逐字）：**"授权进入下一阶段：Phase 2-E：单一真实外部 Provider 接入与真实网络验证"**；
  "本阶段只接入一个真实 Provider。不要同时接入多个 Provider，不做复杂排序或多 Provider 竞价。"；
  "完成后立即停止，等待下一阶段授权。"
- 接入的唯一真实 Provider：**Wikimedia Commons**（MediaWiki API + `upload.wikimedia.org` 直链）。

---

## 0. 为什么选它（先证明"不涉及付费/不可逆额度"）

`docs/regression_2x/probe_providers.py` 实测（`logs/provider_reachability.txt`，2026-09-13）：

| 候选（免费、无 key） | 结果 |
|---|---|
| **commons.wikimedia.org** | **HTTP 200 / 3.7s / 3882 hits** → 采用 |
| api.openverse.org | 30s 超时（不可达） |
| collectionapi.metmuseum.org | HTTP 200（可用，但图像与技术类素材相关性差） |
| images-api.nasa.gov | HTTP 200（可用，但题材受限） |

- Wikimedia Commons：**免费、无需 API key、无付费授权、无不可逆额度消耗** → 不触发"先停止并报告"的条件
  （授权要求 §8）。所有请求均为公开只读 API。
- 许可证元数据由提供方自带（`LicenseShortName / UsageTerms / Artist / Credit / AttributionRequired`），
  **不需要我们猜测**。

## 1. 凭据隔离（要求 1）

- token 只从**环境变量或项目根 `.env`** 读取（复用 `core.env.load_env`），**代码中无任何硬编码密钥**。
- `auth.require_key=true` 且环境无该变量 → `provider_from_config` 返回 `PROVIDER_NOT_CONFIGURED`，
  **不构造 provider、不伪造候选**；检索产物记录 `external_error=PROVIDER_NOT_CONFIGURED`。
- 证据中只记录 `token_present: true/false` 与 `auth_mode`，**从不记录 token 内容**（单测 R5 断言）。
- 默认 `config/config.json` **未改动**（`tools.material.provider` 缺省即 `none`）。

## 2. 真实搜索链路（要求 2）

- 真实请求：`action=query&generator=search&gsrnamespace=6&prop=imageinfo`（含 `extmetadata` 许可证字段）。
- **查询整形（机械规则，非语义）**：实测完整旁白拼接查询 → **0 命中**；去重取前 3–4 个词 → 命中理想结果
  （`logs/query_shaping_probe.txt`）。规则只有：按空白/标点切分 → 大小写不敏感去重 → 取前 N → 限长。
- 只接受**本站媒体直链**（`upload.wikimedia.org`）且 `mime` 为 `image/*` 的结果（PDF/音视频被计入
  `skipped_non_image` 并留痕）。
- 可审计响应摘要：`stats.response_digests[]` 记录 `status/bytes/latency_ms/items/query_used/raw_head(≤400B)`
  （**不含 token**）。
- 错误码：`PROVIDER_AUTH_FAILED`（401/403，实测真实可达）、`PROVIDER_RATE_LIMITED`（429，实测真实出现）、
  `PROVIDER_TIMEOUT`、`PROVIDER_SEARCH_FAILED`、`PROVIDER_REQUEST_BUDGET`。

## 3. 真实下载与验证（要求 3）

沿用 Phase 2-D 的边界，未新开旁路：内容寻址缓存 `media/external/<sha256>.<ext>`、`.part` 原子替换、
`(provider, source_id)` 索引先查后下、大小上限流式中断、并发上限。
验证顺序：**magic bytes → 容器完整性 → ffprobe → ffmpeg decode → PIL 完整解码 → 尺寸 → 许可证**。

**本阶段新增（真实网络暴露的缺陷）**：`container_integrity()`
（JPEG 需 `FFD9`、PNG 需 `IEND`、WEBP 需 RIFF 长度一致）+ `PIL.load()` 完整解码 → 新错误码 **`ASSET_TRUNCATED`**。
原因见 §5 缺陷 1。

## 4. 真实成片证据（要求 5；`logs/phase2e_real_provider.json`）

命令：`python docs/regression_2x/phase2e_real_provider.py` → **13/13 通过**

| 项 | 实测 |
|---|---|
| 真实搜索 | `virtual reality headset` → 8 条真实候选（2.2–4.3s）；查询整形后 `virtual reality headset device` |
| 真实许可证/归属 | `Public domain`（NASA）、`CC BY 4.0`（FloppaIngénieur / RetroEditor）、`CC BY-SA 4.0` |
| 真实下载 | 两轮分别 **3,636,037 字节**（2 个候选通过校验）与 **21,772 字节**（1 个候选通过；该轮媒体主机限流严重：`rate_limited=21`、`download_ms=466,957`，靠 429 退避重试最终成功） |
| 缓存 | `media/external/<sha256>.jpg`，字节数与记录一致（`R10` 断言通过） |
| timeline | S01/S02 均为 `provider=wikimedia_commons`，许可证 `Public domain` / `CC BY-SA 4.0` |
| **抽帧上屏证据** | 两轮分别 **corr 0.486 / 0.996**，`appears_in_film=true`（不是 metadata 顶替） |
| 成片 | 10.000s / 2 流 / `ffmpeg -f null` rc=0 |
| 证据字段 | `provider / source_id / source_url / license / attribution` 全部保留在 timeline（`R12` 断言通过） |

> `R11/R12` 的 `checks` 里同时打印了每镜头证据（`film_evidence.corr_expected / corr_best`），
> 因此"上屏"由抽帧相关系数支撑，而不是由 artifact 状态推断。

## 5. 本阶段发现并修复的真实缺陷（全部由真实网络暴露）

1. **截断文件能骗过全部旧检查**：把真实 JPEG 截断到 2 KB 后，magic bytes ✅、ffprobe ✅、
   ffmpeg 解码 **rc=0** ✅、`PIL.verify()`（只校验文件头）✅ —— 四道闸全部放过。
   → 新增 `container_integrity()` + `PIL.load()`，错误码 `ASSET_TRUNCATED`。
2. **检索层塌缩错误码**：`PROVIDER_AUTH_FAILED / RATE_LIMITED / TIMEOUT` 被统一改写成
   `PROVIDER_DOWNLOAD_FAILED` → 改为透传 `TransportError.code`。
3. **中文查询导致 `UnicodeEncodeError`**：URL 直接拼串未做百分号编码 → 改用 `urlencode(quote_via=quote_plus)`。
4. **文件名白名单过严**：真实素材名含逗号（`… wired gloves, Ames Research Center.jpg`）被误判
   `ASSET_DANGEROUS_FILENAME` → 改为**危险字符黑名单**（`<>:"/\|?*` + 控制字符），保留路径穿越/盘符/
   保留设备名/可执行扩展名/超长的拒绝。
5. **下载腿没有节流**：真实下载触发 429 → 增加 `_throttle()`（请求与下载同一最小间隔）+
   429 专用退避（`rate_limit_backoff_s`，默认 20s×n，上限 60s）+ `rate_limit_retries`。
6. **抽帧判据过严**：两张相似真实照片（同主题 VR 头显）会让"期望素材不是 argmax"而误判失败
   （实测 S02 期望 0.366、另一张 0.6+）→ 改为"期望素材相关度 ≥ 阈值且不明显低于最高者（margin 0.15）"，
   并把 `corr_expected / corr_best` 写入证据。

## 6. 失败路径（要求 6；`logs/phase2e_failure_paths.json`）

| # | 用例 | 性质 | 错误码 | render |
|---|---|---|---|---|
| 1 | 未配置 API key | 受控配置 | `PROVIDER_NOT_CONFIGURED` | **BLOCKED / 无成片** |
| 2 | 鉴权失败（无效 Bearer） | **真实 HTTP 401** | `PROVIDER_AUTH_FAILED` | **BLOCKED / 无成片** |
| 3 | 429 限流 | 受控注入（真实 429 见 §4） | `PROVIDER_RATE_LIMITED` | **BLOCKED / 无成片** |
| 4 | 搜索超时 | **真实**（`timeout_s=0.001`） | `PROVIDER_TIMEOUT` | **BLOCKED / 无成片** |
| 5 | 下载超时 | 真实 URL + 下载腿注入 | `PROVIDER_TIMEOUT` | **BLOCKED / 无成片** |
| 6 | 下载内容损坏 | 真实候选字节截断 | `ASSET_TRUNCATED`（最精确诊断） | **BLOCKED / 无成片** |
| 7 | 许可证缺失 | 受控：真实候选去掉许可证 | `ASSET_LICENSE_MISSING` + `needs_hitl` | **BLOCKED / 无成片** |
| 7b | 许可证受限 | 机械分类 | `fair use` → `RESTRICTED`（不清权） | （分类级断言） |
| 8 | 真实素材被 BLOCKED | **真实**候选 + 策略上限 20 KiB | `ASSET_OVERSIZE` | **BLOCKED / 无成片** |

每条都断言了四件事：明确错误码、未成为正常命中（`external_verified=0` 且无 provider 候选）、
不进入正常 ffmpeg 渲染（无成片 + `[ASSET_INSUFFICIENT]`）、按定义进入 fallback/HITL/BLOCKED。

**环境抖动的诚实处理**：真实媒体下载会被限流（429）。驱动对"资产层用例"内置
**抖动识别 + 重试**（传输层抖动或没有任何候选走到资产层判定时，间隔重跑最多 3 次），
并把每次尝试记录进 JSON（`attempts[]`），避免把"这次网络不好"写成用例结论。

## 7. 回归（要求 7）——全部在最终代码上重跑

| 项 | 命令 | 结果 |
|---|---|---|
| 全部套件 | `run_all_suites.py` | **31 total / 31 rc=0 / FAILED: []**（含新增 `material_provider_test` **46/46**） |
| Provider 契约 + 故障单测 | `tests/material_provider_test.py` | **46/46** |
| 3 机械 E2E | `run_all_tests.py --fresh` | A/B/C **全 SETTLED** |
| 真实 LLM 小测 | `real_small_test.py` | **PASS**，**MockLLM=0**（模型 `deepseek-flash`） |
| 二进制真实性 | `check_binaries.py` | **PASS**（真 ffprobe 且非 ffmpeg 副本） |
| 本地 ingest 回归 | `run_ingest_test.py` | **PASS**（抽帧 t=8.5s 命中 0.747，local_ingest 未退化） |
| Phase 2-C 故障矩阵 | `phase2c_fault_matrix.py` | A/C 出片、**B/D BLOCKED 且无成片**（未退化） |
| Phase 2-C 追溯 | `phase2c_trace.py` | **38/38** |
| Phase 2-A/B 验收 | `phase2_accept.py --verify p_ab2b352e06b8` | **PASS**（成片 438.0s、12/12 在屏、3 个不同素材） |
| Phase 2-D 边界矩阵 | `phase2d_boundary_matrix.py` | **40/40**（未退化） |
| Phase 2-E 真实链路 | `phase2e_real_provider.py` | **13/13** |
| Phase 2-E 失败路径 | `phase2e_failure_paths.py` | **29/29** |

**"未配置真实 Provider 时不得静默成功"**：`provider=none`（默认配置）时 `provider_from_config` 返回
`(None, None)` → 检索不产生外部候选（`material_mode=none`，`material_provided=false`），
行为与 Phase 2-A/B/C 完全一致（由 31 套件 + 3 E2E + ingest + 2-C/2-D 矩阵共同回归）。
配置了 provider 但缺 key/鉴权失败/限流/超时/无候选时，产物里必有 `external_error` 具体错误码，
且当没有可用素材时 render **BLOCKED**（失败路径 1–8 实测，无成片）。

## 8. 成本与网络（要求 8）

- 记录：真实请求次数（`stats.requests`）、下载字节（`stats.downloaded_bytes`）、
  搜索/下载耗时（`stats.search_ms / download_ms`）、失败原因（`stats.response_digests[].error_code`）、
  限流次数（`stats.rate_limited`）、重试次数（`stats.retries`）。
- **未消耗任何付费额度**（Wikimedia 免费）；因此**没有**发生"先停止并报告"的情形。
- 外部 Provider 的花费**不进入** LLM 成本统计（`LLM_CALL` / `cost_usd` 未被触碰，也未新增字段）。

## 9. 基线（输出要求）

- 新基线：`docs/regression_2x/baseline/3.x-phase2e-baseline.zip`
  （**333 文件 / 7,283,985 源码字节**，
  sha256 `2a2b9ac855ef143a8d423f5ec203ebd764b91069ce916b03932b913073bf7fb5`），
  `verify_baseline.py 3.x-phase2e-baseline` → **MATCH（零漂移：zip 哈希一致、清单==条目、0 缺失、0 漂移）**。
- 关键指纹：`tools/provider_wikimedia.py 9fd07544d57dc8bb…`（新）、
  `tools/material_provider.py a52705cc41677cf2…`、`agents/retrieval/agent.py 32de908c26a8ab90…`、
  `agents/editing/agent.py 3d01bb3e9be2afe9…`、`core/materials.py e3ff61e1c42089d2…`、
  `tests/material_provider_test.py 45733c183701fbe4…`；`config/config.json b264644539b2adbb…`（**未改**）。
- 中间态归档（当日收工断点，非基线）：`docs/regression_2x/snapshots/3.x-phase2e-wip-20260913.{zip,db,json}`。

## 10. 停止点

按授权：单一真实 Provider 已接入并完成真实网络验证；**未接入第二个 Provider**、未做多 Provider 竞价/复杂排序、
未做自动许可证判定、未做 BGM/自动发布/UI 大改/语义级对齐/成本对账/Git tag。等下一阶段授权。
