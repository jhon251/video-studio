# Stage 16.2:运动决策 v2 —— STATIC 一等公民 报告

> 实现:测试侧 harness fork(run_161_final.py → run_162_final.py)。仅运动决策层变化;素材指派 v3 原样加载(零改动 → 零新增相邻同字节);运动类型不增(仍 5 类);`motion_vf14` 强度/anchor/clamp 冻结参数原样;冻结模块、M3、字幕/TTS 零触碰;零下载。

## 1. 决策规则(确定性,逐拍落账 `stage162_motion.json`)

按序判定,首中即停:
1. **冻结 storyboard 判定**(SOURCE_NATIVE/STATIC 31 拍)→ 维持静态;
2. **fallback(34 拍)** → STATIC(`fallback_atmosphere_static`);
3. **物件/文档/艺术类**(标题含 painting / advertisement / surveillance / camera / board 等)→ STATIC;
4. **明确适合运动的构图**(标题含 aerial / skyline / plaza / square / control room / trading floor / Times Square / panorama)→ 保留运动,类型按宽高比(宽→PAN_LR/RL,竖→PAN_UD,方形→ZOOM);
5. **人物/群体/室内活动照**(man / woman / people / silhouette / student / worker / professional / meeting / classroom 等)→ STATIC;
6. **默认** → STATIC(无明确运动理由)。

**实施中发现并修正一处规则设计缺陷**:首版把冻结 CV-2 reason 文本一并匹配,reason 中"缺少…城市天际线"等批评语造成假命中(如 S01-B02 人物照因"未见天际线"被误保留运动)——已改为**仅匹配素材标题**(视觉类型是图像的属性),重跑生效。

## 2. 修改前后对照

| 指标 | 前(14–16.1) | 后(16.2) |
|---|---|---|
| 运动段数 | 59/90 拍(65.6%) | **6/90 拍 + 1 bridge 尾段(7/94 段,7.4%)** |
| 运动时长占比 | **68.5%(348.1s)** | **8.9%(45.5s)** |
| 分布(拍) | PAN_LR 28 / PAN_RL 15 / ZOOM_IN 12 / ZOOM_OUT 4 / SOURCE_NATIVE 31 | STATIC 52 / SOURCE_NATIVE 31 / PAN_LR 6 / PAN_UD 1 |
| 转静态 | — | **52 拍**(34 fallback + 18 物件/人物/室内素材) |
| 连续同型运动 | 0 | **0**(`mover_runs_ge2=[]`;运动拍互不相邻) |
| CORRESPONDING | 56 / 309.26s / 60.86% | **不变** ✅ |
| 素材指派 | v3 | **原样**(零新增相邻同字节)✅ |
| A/V | +0.10s | **+0.14s** ≤±0.3s ✅ |
| 工程审计 | 全零 | **全零**(94 段逐段 signalstats + 全片 black/freeze/silence)✅ |

## 3. 保留运动的 7 处(逐拍 provenance)

| Beat | 类型 | 信号 | 宽高比 |
|---|---|---|---|
| S01-B03 | PAN_LR | aerial(城市路口航拍) | 1.50 |
| S08-B03 | PAN_LR | control room(多屏控制中心) | 1.50 |
| S12-B02 | PAN_LR | plaza/square(空旷城市广场) | 1.78 |
| S23-B01 | PAN_LR | skyline(Milwaukee 天际线) | 1.50 |
| S27-B01 | PAN_UD | trading floor(纽交所交易大厅,竖幅) | 0.78 |
| S28-B01 | PAN_LR | control room(交通控制中心大屏墙) | 1.50 |
| S34-B02 | PAN_LR | Times Square(城市广场密集屏) | 1.78 |

bridge 尾段 4 处:3 处随源拍转 STATIC(S16-B01/S13-B01/S01-B02 源),1 处源为运动拍(S28-B01)按"同素材不同运动"规则取 PAN_RL。

## 4. Provenance

- `stage162_motion.json`:90 拍 + 4 尾段逐条 `{v14, v2, rule(命中规则+关键词), class}` + 三条正则规则全文;
- `stage162_metrics.json`:前后分布、运动段数、连续同型检查、correspondence、A/V;
- `stage162_verify.json`:全片工程审计。

## 5. 结论

"不是每张图都需要动"落地:运动从 68.5% 时长降到 8.9%,仅保留 7 处有明确构图理由的运动(航拍/天际线/广场/控制室/交易大厅);STATIC 成为默认结果;连续同型运动 0;correspondence 与素材指派零变化;工程审计全零。

```
STAGE16.2 = PASS · STOP
运动时长 68.5%→8.9%(348.1s→45.5s) · 运动拍 59→6(+1尾段) · 转静态 52 拍 · 保留运动 7 处全部有构图信号 · 连续同型 0 · correspondence 60.86% 不变 · 工程审计全零 · A/V +0.14s
STOP——等待下一步授权
```
