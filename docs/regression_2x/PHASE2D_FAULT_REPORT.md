# 3.x Phase 2-D 故障注入报告：外部素材 Provider 边界（10 类）

- 日期：2026-09-13
- 驱动：`python docs/regression_2x/phase2d_boundary_matrix.py`
- 原始记录：`logs/phase2d_boundary_matrix.json`
- 单测（同一边界的确定性覆盖）：`tests/material_provider_test.py` **46/46**

## 注入方式（真实项目、真实校验、真实渲染）

每个用例建**真实项目**，配置 `local_catalog` provider（本地目录 + `catalogue.json`，模拟外部服务；
**生产 config 不变**，仅在驱动进程内注入），catalogue 内放**一条"命中但故障"的候选**，然后跑真实
`retrieval`（经 provider 层：搜索 → 下载 → 逐项校验）与真实 `render`。

传输层故障（超时/404/500/空响应）通过**进程内替换传输层**注入（与 Phase 2-B.1 的注入方式一致，不改生产代码）；
文件层故障使用真实文件（损坏 JPEG、伪装 jpg 的文本、截断文件、超大文件、危险文件名）。

## 结果（全部 40/40 断言通过）

| 用例 | 错误码（实测） | 是否成为候选 | 是否落盘 | render | 成片 |
|---|---|---|---|---|---|
| 下载超时 | `PROVIDER_TIMEOUT` | 否（verified=0） | 否 | **BLOCKED** | 无 |
| HTTP 404 | `PROVIDER_HTTP_404` | 否 | 否 | **BLOCKED** | 无 |
| HTTP 500 | `PROVIDER_HTTP_5XX` | 否 | 否 | **BLOCKED** | 无 |
| 空响应 | `PROVIDER_EMPTY_RESPONSE` | 否 | 否 | **BLOCKED** | 无 |
| 文件损坏 | `ASSET_PROBE_FAILED` | 否 | 否 | **BLOCKED** | 无 |
| 非媒体文件伪装 | `ASSET_TYPE_MISMATCH` | 否 | 否 | **BLOCKED** | 无 |
| 超过大小限制 | `ASSET_OVERSIZE` | 否 | 否 | **BLOCKED** | 无 |
| ffprobe/解码失败（截断文件） | `ASSET_PROBE_FAILED` | 否 | 否 | **BLOCKED** | 无 |
| 缺少许可证 | `ASSET_LICENSE_MISSING` | 否 | 否 | 降级：**SUCCEEDED**（用本地素材）+ HITL | 有（本地素材） |
| 路径穿越/危险文件名 | `ASSET_DANGEROUS_FILENAME` | 否 | 否 | **BLOCKED** | 无 |

每个用例都断言了授权要求的四条：
1. **有明确错误码/状态**（上表第 2 列，且候选 `status=REJECTED`）；
2. **不进入正常 ffmpeg 渲染** —— 9 个无权降级用例**无成片且 render BLOCKED**；许可证用例按定义降级到
   `local_ingest`（外部那条被拒，绝不入片）；
3. **不被标记为正常素材命中** —— `external_verified=0`，且 `candidates` 中不存在该 provider 的条目；
4. **按定义进入 fallback / HITL / BLOCKED** —— 阻断文案 `[ASSET_INSUFFICIENT]` + `assembly_class=ASSEMBLY_BLOCKED`；
   许可证用例场景 `needs_hitl=true`、`license_pending=true`，且被拒候选写入该镜头的 `excluded_candidates`。

## 阻断文案（节选真实文本）

```
[ASSET_INSUFFICIENT] {"assembly_class": "ASSEMBLY_BLOCKED",
 "assembly_reason": "已提供素材（本地素材索引或外部 provider 返回过候选）但 1 个镜头全部无法把真实素材上屏
                     （selected_asset 全为 null），装配无法完成",
 "class_counts": {"NO_CANDIDATE": 1}, "material_mode": "external_configured_no_candidate",
 "policy": {"min_match_score": 3, "low_match_policy": "theme_fallback",
            "asset_reuse_policy": "prefer_unused", "block_when_all_degraded": true}, ...
```

## 关键实现细节（对应"不允许仅凭 URL 或扩展名认定可用"）

- 扩展名只做**白名单初筛**（.jpg/.jpeg/.png/.webp）；可执行/脚本类扩展名在**文件名层**即拒绝
  （`ASSET_DANGEROUS_FILENAME`），白名单是第二道闸（`ASSET_EXTENSION_NOT_ALLOWED`）。
- 实际类型由 **magic bytes** 判定（JPEG `FFD8FF`、PNG `89504E47`、WEBP `RIFF…WEBP`）→ 伪装文件必被
  `ASSET_TYPE_MISMATCH` 拦下。
- 之后依次：**ffprobe** 必须有图像/视频流且尺寸有效 → **ffmpeg 解码 rc=0** → **PIL verify** →
  尺寸下限（320×180）→ 许可证判定。任一失败即 REJECTED，**文件不会进入 ffmpeg**。
- 不合格候选**不落盘**（`downloaded_path` 为空）：大小上限在**流式累计**阶段即中断；
  文件名检查在写盘之前。

## 补充：端到端（provider 素材真的上屏）

`python docs/regression_2x/phase2d_provider_e2e.py`（12/12 通过）：S01 使用 `provider=local_catalog /
source_id=ext-ccby-001 / license=CC BY 4.0` 的外部素材，**抽帧证实出现在成片**（t=2.0s，corr 0.696）；
S02 只命中一条**无许可证**候选 → 被拒 → 占位 + `needs_hitl=true` + `license_pending=true`，
且占位画面经抽帧证实"不是任何素材"。成片 10.0s、2 流、`ffmpeg -f null` rc=0。
