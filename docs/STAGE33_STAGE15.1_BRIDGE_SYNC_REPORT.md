# Stage 15.1:拍内转折同步修复 报告

> 实现方式:测试侧 harness fork(run_14_final.py → run_15_final.py)。**零下载**(复用 Stage 14 asset cache,同 key 命中);Stage 14 fallback 指派与运动策略原样加载(冻结);冻结模块、M3 口径、字幕/TTS 零触碰。仅 4 个已审计 beat 改变,范围未扩大。

## 1. 改动内容(4 拍,precise)

| Beat | 转折标记 | 尾窗 | 尾段素材 | 来源类型 | 新增链 |
|---|---|---|---|---|---|
| S15-B02 | —— | 7.95s | S16-B01 "Department of Traffic and Engineering worker…" | 下一拍(其对应素材) | bridge_sync |
| S12-B02 | ： | 6.89s | S13-B01 "Bethesda downtown intersection…" | 下一拍(其对应素材) | bridge_sync |
| S19-B02 | —— | 6.26s | S01-B02 "Adult using smartphone indoors…" | 池内匹配(gap 45) | 无 |
| S26-B01 | —— | 2.77s | S28-B01 "Central Control Room, Intelligent Transportation…" | 池内匹配(gap 6) | 无 |

- 池内匹配依据为**冻结 CV-2 reason 文本**(零新调用):S26-B01 尾"当AGI接管关键决策" ↔ "交通控制中心与大型监控屏幕墙,与话题高度相关";S19-B02 尾设问 ↔ 人+设备反思意象。按验收链数上限(≤2),两条最长尾窗使用下一拍素材,另两条池内匹配——**枚举延展型与 S17-B01 均未处理**,与授权范围一致。
- 每拍在标记点硬切为 head(原素材+原运动)+ tail(新素材+新运动);尾段运动遵循 Stage 14 规则(≠头段、≠源拍自身运动、≠前一拍运动,aspect 分流,1.06–1.08 包络)。
- 尾段非兜底,**无「中性画面」角标**;provenance 全量落盘 `stage15_bridge.json`(标记位置、拆分时间、尾素材 URL/标题、匹配依据、reuse_reason="bridge_sync")。

## 2. 修改前后对比

| 指标 | Stage 14(前) | Stage 15.1(后) | 验收 |
|---|---|---|---|
| 成片时长 / A-V | 508.29s / +0.14s | 508.25s / **+0.10s** | ≤±0.3s ✅ |
| CORRESPONDING | 56 拍 / 309.26s / 60.86% | **完全不变** | ≥60.86% ✅ |
| 真转折尾窗覆盖 | 0s(4 拍滞留) | **23.87s** | ≥20s ✅ |
| 素材链总数 | 0 | **2**(均 len 2) | ≤2 ✅ |
| 新增链标记 | — | 2/2 `bridge_sync` | 全标记 ✅ |
| 相邻同型运动 | 0 | **0**(尾段运动经排除法) | 不回退 ✅ |
| 慢推类占比 | 17.8%(16/90) | 20.2%(19/94 段) | 无模板化回退 ✅(4 个新尾段中 2 个 zoom,包络不变) |
| SOURCE_NATIVE 静态 | 31 | 31 | 不变 ✅ |
| 黑帧/绿幕/纯色/异常静帧/音频空洞 | 0/0/0/0/0 | **0/0/0/0/0**(`stage15_verify.json`,94 段逐段) | =0 ✅ |

成片:`stage15_audit/render_15/final_long.mp4`(508.25s,渲染 90/90,逐段时长对账通过)。

## 3. Provenance(`stage15_bridge.json`)

4 条 bridge_sync 记录,每条含:beat、marker 字符、split_local_s/tail_s(cue 时间轴映射,与 Stage 15 审计值偏差 <0.05s 断言校验)、tail 素材 title/URL、来源类型(next_beat / pool_match + 冻结 reason 引文)、`reuse_reason: "bridge_sync"`。

## 4. 结论

4 拍真语义转折尾窗全部获得语义对应画面;口播转折处不再滞留旧画面;两条二连链均为设计内的语义连续(预切素材即下一拍主素材),全部标记 bridge_sync;correspondence、Stage 14 复用/运动指标、工程审计六项全部不回退。

```
STAGE15.1 = PASS · STOP
4 拍修复 · 尾窗覆盖 23.87s(≥20) · correspondence 60.86% 不变 · 新增链 2/2 bridge_sync(≤2) · 工程审计全零 · A/V +0.10s
STOP——等待下一步授权
```
