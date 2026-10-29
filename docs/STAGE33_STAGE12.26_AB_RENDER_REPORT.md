# Stage 12.26(2/2):成片 A/B 对比报告 — Storyboard → Renderer 全链

> A = 33/90 banked baseline;B = 33 + 第二遍实际释放素材(54)。
> Renderer / Composition / Motion / Subtitle 全部保持现状(12.11 验证模式逐位复刻);音频轨两臂完全一致(同一 VO segments)。
> 数据:`stage12_26_prod/ab_metrics.json`;成片:`render_A/final_long.mp4`、`render_B/final_long.mp4`。

## 1. 主对照

| 指标 | A(33 baseline) | B(33+21 释放) | Δ |
|---|---|---|---|
| 素材覆盖(拍/90) | 33 | **54** | **+21** |
| 有效素材时长 | 174.08s | **295.96s** | **+121.88s** |
| EMPTY runtime(HONEST_EMPTY 卡) | 334.08s(65.7%) | **212.20s(41.8%)** | **−121.88s(−36.5%)** |
| 素材重复 | 32 distinct / 1 重复槽 | **53 distinct / 1 重复槽** | 重复零新增 |
| 视频总时长 | 508.29s | 508.29s | 0 |
| A-V 偏差 | +0.14s | +0.14s | 0 |
| 渲染成功率 | 90/90 clip,6/6 part,3/3 burn | 同左 | 无差异 |

## 2. 关键结论

1. **释放素材 100% 转化为成片**:21 个释放拍全部通过 Resolver→Renderer 实际上屏,21/21 为新 distinct 素材(重复槽维持 baseline 原有的 1 个,零新增);
2. **EMPTY runtime 下降 36.5%**(334s→212s):释放素材精准落在原 HONEST_EMPTY 时段;
3. **时长与音画零扰动**:两臂总时长与 A-V 偏差逐位一致(508.29s / +0.14s),音频轨同源——差异唯一来自素材层,归因干净;
4. **渲染成功率无回归**:B 臂新增素材全部走 `resolve_renderable` 正常路径(Pexels 图像 DIRECT_USE),无一 fallback。

## 3. 过程透明记录(A/B 脚本两处缺陷,均已修复后重跑)

首轮 A/B 暴露两个**测试侧脚本**缺陷(冻结模块零涉及):
1. 音频按 beat 复制 shot 级 wav → 分段音频膨胀 → 探测值错乱 → 字幕负时戳 → burn 空 filter → final 截断为 174s;
2. 漏写 material status 覆写 → 仅 12.11 时代 10 席渲染(8 成功)。
修复为 per-shot 音频(12.11 模式)+ ledger status 覆写后,A 臂与 12.11 基线**时长逐位一致(508.29s)**,证明修复后管线等价于已验证链路。

## 4. 预定义成功标准核对(全过)

- ✅ 释放素材产生(21);
- ✅ B 相比 A 可验证实际贡献(+21 拍 / +121.9s / 重复零新增);
- ✅ 无构造性回归(A≈12.11 基线;ok 素材零损失);
- ✅ 可恢复 + provenance 完整(逐拍 JSON、全 trace、verdict store)。

```
STAGE12.26 = PASS · STOP
素材终态(实验口径):54/90(60%)· EMPTY runtime 334s→212s · Pexels 释放 20/21
Production Default 未改动;54/90 是否定为正式 banked 状态由用户决定
STOP——不自动扩展,不修改任何规则
```
