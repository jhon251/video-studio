# Stage 13.2:Coverage Closure 报告

> 目标:M3 口径下视频时长对应率 ≥60%;消灭文字卡;EMPTY 全部转为合法可看兜底。
> 零冻结改动(T1/T2、pool_precision、Gate、V1、CV2、Gold、sanitizer、source_quota、two_pass_material、Renderer/Composition/Motion/Subtitle 全程未动);M3 口径未变。

## 1. 释放裁决(B 项核查结果)

对 36 个 EMPTY 拍的全量 verdict 缓存扫描(`empty_lever_scan.json`)发现 **3 个拍存在生产路径合格判定**——12.25 R1 回归重放(同一冻结链)判定其 Pexels 候选合格并持久化进生产 verdict store,但 12.26 生产运行时 rerank 将 Commons 排前、Pexels 席位未进 keeps,故判 EMPTY。 EMPTY 拍零位移风险;素材已在获取范围;判定为冻结链产物 → **合法释放**:

| Beat | 素材 | 冻结判定 | 重测 relevance | 时长 |
|---|---|---|---|---|
| S01-B03 | Aerial view of people crossing…(pexels 10121600) | CONDITIONALLY_USABLE | **MEDIUM**(冻结 CV-2) | 3.83s |
| S19-B02 | A man silhouetted at sunset…(pexels 2301857) | CONDITIONALLY_USABLE | **MEDIUM**(冻结 CV-2) | 9.47s |
| S18-B02 | Crowd at Alexanderplatz | USABLE | —(12.24 时代候选,thumburl/ID 不在已获取范围,**保守放弃**) | 5.62s |

释放 **13.30s**(需求仅 8.94s),图像按记录的 pexels_id 经标准 CDN URL 同源重获取(非新检索、非新源)。

## 2. 最终对应账本(90 拍 / 508.16s)

| 类别 | 拍数 | 时长 | 时长占比 |
|---|---|---|---|
| **CORRESPONDING**(M3:USABLE 或 relevance HIGH/MEDIUM) | **56** | **309.26s** | **60.86% ✅** |
| **VALID_FALLBACK**(中性氛围画面,不计入对应率) | **34** | 198.90s | 39.14% |
| **INVALID_PLACEHOLDER**(文字卡/绿幕/纯色) | **0** | 0 | 0% |
| EMPTY(未闭环) | 0 | 0 | 0% |

**目标达成:60.86% ≥ 60%(超出 4.36s)。**

## 3. VALID_FALLBACK 设计(诚实兜底)

- 来源:同 shot 优先、其次时间线最近对应素材的图像复用(34/90 拍);
- 渲染:沿用该拍**冻结 storyboard 自身的 motion/composition** 参数 + 右下角半透明角标「中性画面」——**视觉与账本双重不伪装**;
- 明确不计入 correspondence rate;`fallback_assignments.json` 记录每个兜底的 origin_beat/URL/性质;
- 副作用(如实):distinct 55 / duplicate_slots 35(34 个兜底复用 + 1 个既有重复)——这是"不新增源"约束下兜底的固有代价。

## 4. 最终成片与工程审计(`render_final/final_long.mp4`)

| 项 | 值 |
|---|---|
| 总时长 | **508.29s(8 分 28 秒,∈ 8–12 分钟)** |
| 音频轨 | 508.15s,与 12.26 同源 |
| A-V 偏差 | **+0.14s**(与 12.26 逐位一致) |
| 渲染成功率 | 90/90 clip、6 项 part burn 全过、3/3 part concat |
| 文字卡 | **0**(HONEST_EMPTY 渲染路径未触发) |
| 逐 clip 时长对账 | 90/90 通过(±0.25s 阈值,静默截断防护已内建) |
| signalstats 抽检(6 clip) | 0 近纯色、0 绿幕嫌疑 |
| 抽检帧 | `stage13_2_coverage/audit_*.png`(供人工复核) |

过程记录:首轮渲染暴露测试侧 bug(SOURCE_NATIVE 兜底 clip 的 `-loop 1` 误置于 `-i` 之后 → 10 个 0.04s 空帧 clip、总长 −51.95s);修复选项顺序并内建逐 clip 时长对账后重跑,全部通过。冻结模块零涉及。

## 5. 交付物

- `render_final/final_long.mp4` — 最终成片
- `coverage_metrics.json` — 最终账本(上表数据)
- `fallback_assignments.json` — 释放 + 兜底全量 provenance
- `empty_lever_scan.json` / `release_relevance.json` — B 项扫描与 relevance 测量原始记录
- `correspondence_audit.py`(13.2 复用)、`run_132_final.py`、`spot_check.py`、`audit_*.png`

```
STAGE13.2 = PASS · STOP
对应率 60.86% ≥ 60% · 文字卡 0 · VALID_FALLBACK 34 拍诚实兜底 · 成片 508.29s 工程审计全过
冻结模块零改动 · M3 口径未变 · STOP——等待下一步授权
```
