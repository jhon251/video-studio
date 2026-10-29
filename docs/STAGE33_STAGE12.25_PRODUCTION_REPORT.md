# Stage 12.25:生产化集成报告 — 两遍制 + 非 Commons 来源 2 席

> **`STAGE12.25 = PASS · Production Default 已标记 · STOP`**
> 新增生产模块 `src/video_studio/stage33/two_pass_material.py`(两遍制流程 + VerdictCache 持久化);`source_quota.py` 保持独立模块(仅切片构造,`pool_precision` 零改动)。标记文件:`output/stage33/production_defaults.json`。
> 验证数据:`stage12_25_prod/prod_validation.json`(含全量 provenance trace)。

## 1. 生产化设计(按授权 10 条逐项落实)

| 要求 | 实现 |
|---|---|
| 1 第一遍冻结管线 | `acquire_beat_material` pass1 = 冻结检索→冻结 rerank→Gate head-6→V1→CV-2,零改动 |
| 2 仅 EMPTY 进第二遍 | pass1 ok → 返回,pass2 = "skipped" |
| 3 第二遍 2 席、Pexels 优先 | pass2 = 冻结重取池 + Pexels 候选 → 冻结 rerank → `quota_slice(QUOTA_SEATS=2)`(Commons 前 4 席按冻结序 + Pexels 前 2 席) |
| 4 pool_precision 不修改 | quota 在 rerank 之后重建切片,模块独立 |
| 5 quota 不直接成为素材 | 切片内所有候选(含 Pexels)必经冻结 Gate→V1→CV-2 |
| 6 ok 拍不重跑 | 构造性跳过 + 验证确认(见 R3) |
| 7 provenance 记录 | 每拍 trace:source/席位表(含 pexels_id/photographer/license)/被挤出候选/Gate/CV2/最终结果/缓存命中 |
| 8 key 外读、无 Pixabay | key 从 `C:\mp4agent\pexels key\key.txt` 读取 |
| 9 冻结不动 | T1/T2、pool_precision、Gate、V1、CV-2、Gold、sanitizer、Composition/Motion/Renderer 零改动 |
| 10 四项回归 | 全部通过(见下) |

## 2. 回归结果(4/4 通过)

### R1 · Stage 12.24 回归 — PASS(12/12)
两遍制生产模块在 12 个空拍上与 12.24 q2 结论**完全一致**:
- 5 翻转复现:S01-B02(hook)、S05-B01、S08-B03、S14-B02、S34-B01;
- 7 非翻转复现(S01-B03、S18-B02、S19-B02、S01-B01、S31-B02、S07-B01、S02-B02)。

### R2 · 最小生产回归 — PASS
- ok 拍(S23-B02、S27-B01)banked 素材 → pass2 跳过,零重判;
- **渲染边界兼容**:S01-B02 的 Pexels 素材走 `asset_render_resolver.resolve_renderable` → `asset_acquisition_status=OK`,`conversion=DIRECT_USE`,`renderable=True`(本地文件就绪;Renderer 未动)。

### R3 · 金丝雀 — PASS
两遍制下 S23-B02/S27-B01 均不重跑(12.24 干跑已留痕:单遍制配额会将 S23-B02 获胜者留在切片外 → 两遍制为强制设计)。

### R4 · 成本与重复调用 — PASS
- 本次验证 **gate/CV-2 fresh 调用 = 0/0**(VerdictCache 全命中:12.13–12.24 traces + 持久化 `verdict_store.json`);
- **运行内 fresh 重复 = 0**;Pexels API 33 次(限流内);
- 每拍 verdicts 持久化,后续运行不重复判定。

## 3. 运行事故记录(透明)

首次验证运行(pwsh-48)因工具调用中断导致 python 子进程成孤儿、阻塞于死父进程 stdout 管道(进程 CPU 0.4s、无下载活动,确认为管道挂起而非判定问题)。杀孤儿后以**分离进程 + 文件日志**重启,重跑一次通过——顺带验证了增量持久化设计(7 拍结果与 verdict store 均未丢失)。重启后 S01-B01 快速通过,证明该拍本身无问题。

## 4. 最终状态

```
STAGE12.25 = PASS
生产默认:两遍制 + 非 Commons 2 席(Pexels 优先),仅 EMPTY 拍第二遍
素材现态:33/90 已入账;两遍制对空拍池的可释放上限 = +5 → 38/90
          (实际 +5 需对全部 58 空拍执行生产跑,未在本次授权范围)
Stage 12 收官:Query(T1 fix/T3 关)→ Gate(诊断/Top-12 不默认)→ V1/CV-2
(Top-3 定稿)→ 源(NASA 关/Pexels 上线)→ 排序(quota 2 席为 Production Default)
STOP——不扩展新来源,不扩展新排序策略
```
