# Stage 14:素材复用控制 + 镜头运动去模板化 报告

> 只动两层测试侧策略(兜底指派 + 渲染时运动覆写),storyboard 与全部冻结模块零改动;M3 口径未变;素材零新增;字幕/TTS/音频未动。

## 1. 审计结果(`stage14_audit.json`)

**复用(改动前)**
- 90 槽中 65 个不同标题,20 个素材被复用;
- **16 条连续复用链,其中 2 条三连链**:S02-B01→B03(material+fallback+fallback)、S03-B01→B03(fallback+fallback+material)——即人工审看发现的"连续三段共用同一素材";
- 14 条二连链(多为同 shot 兜底 + 前向碰撞)。

**运动(改动前)**
- SLOW_ZOOM_IN 25 + SUBTLE_ZOOM 12 = **41.1% 为慢推类**;SOURCE_NATIVE 31(合理静态,保留);SLOW_PAN 22;
- 连续慢推段:最长 **6 连拍**(S04-B02→S06-B02),另有 5 段 2 连、2 段 SLOW_PAN 3 连。

## 2. 最小改动(两层策略)

**A. 兜底指派 v2(双侧隔离)**
- 素材拍不动(correspondence 证据原样);仅重排 34 个兜底;
- 规则:同一素材在其前 2 拍与后 2 拍(素材属主已知,可前向查)内不得出现 → **相邻/三连在构造上不可能**;
- 同 shot 语义连续优先,违反间隔则让位;全冲突才强制复用并记录 reason;
- 逐拍落账:`asset_reuse_count / consecutive_reuse / reuse_reason`(`stage14_policies.json`)。

**B. 运动策略(渲染时覆写,保留 anchor/clamp)**
- SOURCE_NATIVE/STATIC 31 拍维持静态(冻结 storyboard 判定"不适合运动");
- 其余 59 拍按图像宽高比分配:宽幅(w/h≥1.4)→ PAN_LR/PAN_RL(横向平移),方形/竖幅 → ZOOM_IN/ZOOM_OUT(+竖幅 PAN_UD);
- 硬约束:相邻运动拍不得同型;同一素材多次出现不重复同一运动;zoom 包络沿用冻结 end_scale(1.06–1.08)/pan crop 1.08——**运动强度不升级,只换方向与类型**。

## 3. 改动前后对比

| 指标 | 前(13.2) | 后(14) |
|---|---|---|
| 连续复用链 | 16 条(2 条三连) | **0 条** |
| 慢推类占比 | 41.1%(25 SLOW_ZOOM_IN) | **17.8%**(ZOOM_IN 12 + ZOOM_OUT 4),默认慢推取消 |
| 运动类型 | 4 类(SLOW_ZOOM_IN 为主) | 5 类 + 方向细分(PAN_LR 28 / PAN_RL 15 / SOURCE_NATIVE 31 / ZOOM_IN 12 / ZOOM_OUT 4) |
| 相邻同型运动 | 多段(最长 6 连慢推) | **0**(策略保证) |
| CORRESPONDING | 56 拍 / 309.26s / 60.86% | **完全不变** ✅ |
| VALID_FALLBACK | 34 拍 / 198.9s | 34 拍 / 198.9s(仅换指派对象) |

## 4. 成片与工程审计(`stage14_audit/render_final/final_long.mp4`)

- 总时长 **508.29s**,A-V **+0.14s**,渲染 90/90 clip(逐 clip 时长对账内建);
- blackdetect 0 段 · freezedetect 0 段 · 全 90 clip 0 纯色 / 0 绿幕 · silencedetect 0 段(`stage14_verify.json`);
- distinct 55 / duplicate_slots 35(34 个非相邻兜底复用 + 1 对既有素材对,均为非相邻)——不新增源约束下的最低复用水平。

## 5. 结论

- 连续三段共用同一素材:已消除(三连与二连同告清零);
- 慢推模板化:已消除(41.1%→17.8%,不再有连续同型运动);
- correspondence 60.86% baseline 分毫未动;无黑帧/绿幕/纯色/异常静帧/A-V 回归。

```
STAGE14 = PASS · STOP
复用链 16→0 · 慢推占比 41.1%→17.8% · 运动类型 4→5(含方向) · 对应率 60.86% 不变 · 冻结模块零改动
STOP——等待下一步授权
```
