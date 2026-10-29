# Stage 12.7：Visual Beat Segmentation

> 状态:**`STAGE12.7 = PASS`**
> 冻结边界:visual_intent / query_generator / retrieval_v15 / V1 / Top-5 / CV-2 / Gate / Asset Contract / Composition / Motion / Subtitle / Renderer **全部零改动**(时间戳核验:本轮仅新增 beat_segmentation.py)。
> **STOP —— 不进入 Storyboard / 8-12 分钟生产 / Stage 13。**

---

## 1. 新增模块(唯一改动)

**`src/video_studio/stage33/beat_segmentation.py`**(~150 行):

```
narration → 确定性子句切分(标点附着,逐字保留)
→ LLM 分组子句索引(1-4 beat,时长规则:单素材≤8-10s;音频>12s→≥2 beat,单子句除外)
→ 校验:每个子句恰用一次/顺序连续/beat 文本=原文逐字拼接(语义连续零改写)
→ 时间轴:beat 时长 = shot真实音频时长 × beat字符占比(构造上连续/无重叠/无空洞)
→ fallback 仅在 LLM 失败时(确定性均衡分组,留痕),本轮 0 次触发
```

不通过硬规则强行制造镜头:S03 最初由 LLM 自主选择 1 beat;修正时长规则后由子句结构自然分出 2 beat。

## 2. 6-shot 实测结果

| shot | 音频 | beats | holds | 时间轴 | 结果 |
|---|---|---|---|---|---|
| S01 | 17.67s | 2 | 8.84+8.83 | ✅ | 分割正确;beats honest-empty |
| S02 | 16.52s | 2 | 8.48+8.04 | ✅ | 同上 |
| S03 | 16.60s | 1→**2** | 16.6→**11.3+5.3** | ✅ | 规则收紧后修复(子句粒度限制,11.3s 诚实记录) |
| S04 | 16.20s | 2 | 8.47+7.73 | ✅ | |
| S05 | 14.12s | 2 | 5.95+8.17 | ✅ | 语义切分清晰:"进入城市，交通调度、" / "电力分配、医疗分诊…" |
| S06 | 14.34s | 2 | 6.49+7.85 | ✅ | **B02 → 曼哈顿天际线全景,CV-2 fit 0.95 USABLE(全项目最高)** |

**修复前后对比**:12.6 及之前每镜 1 图覆盖 14-18s;12.7 全部拆为 2 beat,单素材停留 5.9-11.3s(除修复前 S03 的 16.6s)。

## 3. 验收对照

✅ **长旁白不再"一图到底"**:6/6 multi-beat(修复后),max hold 17.7s→11.3s
✅ **Beat 与旁白语义对应**:beat 文本=原文逐字子句拼接,零改写;每个 beat 独立 focus
✅ **时间轴正确**:6/6 timeline_valid;连续/无重叠/无空洞/总和=真实音频时长
✅ **每 beat 独立 Intent/Query**:13 个 beat 管线全部独立生成(证据在 beat_test.json)
✅ **完整链路逐 beat 重跑**:Intent→Query→Retrieval v1.5(阶梯 trace)→Gate→V1→CV-2;S06-B02 端到端 IMG(CV-2 0.95)
✅ **诚实 empty**:10/13 beat 按 class 记录(gate_rejected_all);无凑数素材、无假数据
✅ **无硬规则强造**:fallback 0 次触发;S03 案例见上
✅ **冻结链路零回归**:全部冻结组件时间戳早于本轮

**诚实修正**:测试脚本 `holds_over_10s` 字段误只统计多-beat shot——实际修复后仍存 1 处(S03-B01 11.3s,子句粒度所限,不改写旁白无法更细),在 final_result.json 中如实更正。

## 4. 诚实发现(需新授权)

1. **beat 级粒度放大已知瓶颈**:beat intent 更窄 → query 更 niche → Commons 相关性噪声主导前 6 条候选 → keep 率降至 10/13 empty(与 12.6 发现#1 同源,现被 beat 粒度放大)。下一阶段杠杆:加深 gate 判定深度/池排序改进——超出 12.7 范围;
2. S03-B01 11.3s:子句粒度限制(不改写旁白约束下的最优);
3. beat 级 gate verdicts 未持久化到 beat_test.json(测试工件缺口,仅存计数;gate 正确性已在 12.6 逐条核验)。

## 5. 交付物

- `output/stage33/stage12_7_beat_segmentation/beat_test.json`(6 shot × 13 beat 全 trace)
- `output/stage33/stage12_7_beat_segmentation/final_result.json`
- `output/stage33/stage12_7_beat_segmentation/run_beat_test.py` + asset_cache
- 源码:`src/video_studio/stage33/beat_segmentation.py`
- 本报告:`docs/STAGE33_STAGE12.7_BEAT_SEGMENTATION_REPORT.md`

```
STAGE12.7 = PASS
  6/6 multi-beat · 时间轴 6/6 valid · 逐字语义切分 · S06-B02 CV-2=0.95 全项目最高
  冻结链路零回归(仅新增 beat_segmentation.py)
STOP —— 等待授权
```
