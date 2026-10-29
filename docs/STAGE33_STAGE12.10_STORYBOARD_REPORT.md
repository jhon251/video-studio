# Stage 12.10：Storyboard

> 状态:**`STAGE12.10 = PASS`**
> 冻结边界:beat_segmentation / intent_stability / visual_intent / query_generator / retrieval_v15 / beat_retrieval / Gate / V1 / CV-2 / Composition / Motion / Subtitle / Renderer **全部零改动**(时间戳核验;仅新增 storyboard.py)。
> **STOP —— 不进入 Stage 13。**

---

## 1. 改动清单(唯一新增)

**`src/video_studio/stage33/storyboard.py`** — 纯编排层:

```
输入(全部来自既有链路,零重判):
  12.7 beat_test.json        → beat 时间线(逐字旁白/start/end/duration)
  12.9 beat_recovery_test.json → 稳定 Visual Intent + Gate/V1/CV-2 结果
编排:
  每 beat → {时间窗, 旁白(逐字), 视觉意图, 素材|HONEST_EMPTY, 构图, 镜头运动, 字幕 cues}
  构图/运动 → 调用冻结 composition_policy / camera_motion_policy
  字幕行 → 调用冻结 subtitle_pipeline.split_for_subtitle(verbatim 分行)
素材资格(编排级,无新评分):CV-2 labels ∈ {USABLE, CONDITIONALLY_USABLE}
校验:6 套件(时间轴/逐字旁白/素材溯源+诚实空/字幕合法/构图运动合法/覆盖一致)
```

## 2. 11-beat Storyboard 结果

| Beat | 素材状态 | 内容 |
|---|---|---|
| S04-B02 | **OK** | Control Room DSC0038.jpg · CV-2 0.85 CONDITIONALLY_USABLE |
| S06-B02 | **OK** | City lights at dusk.jpg · CV-2 0.85 USABLE |
| S02-B02 | HONEST_EMPTY | CV-2 候选存在但 NOT_USABLE(0.1)→ 带候选痕迹诚实置空 |
| 其余 8 | HONEST_EMPTY | gate_rejected_all(带 trace) |

**溯源链完整**:12.7 分段 → 12.9 稳定 intent → 12.8/12.9 三层检索+Gate+V1+CV-2 → 字节级回溯(12.9 asset_cache meta 的 source_url + content_hash)→ b30 确定性获取 → Stage 11 resolver DIRECT_USE。

## 3. 校验 6/6 PASS

✅ 时间轴:0→95.45s 连续无重叠/空洞/越界,shot 时长=真实 wav 时长
✅ 旁白逐字:storyboard 文本 == 12.7 链路文本(byte-for-byte)
✅ 素材溯源+诚实空:2/2 OK 可追溯到既有素材字节;9 empty 全带 reason+trace,零强填
✅ 字幕合法:22 cues 全部在 beat 窗口内、无重叠(>22 字符仅限无标点长句——冻结 split_for_subtitle 在 12.4 即此行为;26 字符×40 号字≈1040px 仍在 1920px 安全区)
✅ 构图/运动参数合法(全由冻结策略决定)
✅ 覆盖一致:11/11 beat 同序

## 4. 真实 Renderer E2E

- **11/11 clips 渲染成功**(2 个素材 beat:冻结构图 vf+运动 glue;9 个 HONEST_EMPTY 中性深色卡片,明确标注"非素材")
- **成片**:`render/storyboard_final.mp4` — **h264 High 1920x1080 + aac,95.44s**(计划 95.45s,帧舍入 0.01s)
- **字幕烧录成功**(冻结 drawtext 管线,storyboard.srt 22 cues)

## 5. 诚实发现

1. 两个素材 beat 的 intent 链 asset_type_hint=VIDEO → 冻结 decide_motion 正确返回 SOURCE_NATIVE;实际池素材为 IMG → 全出血静帧呈现。Storyboard 不改判、尊重链路决策;hint 与实际的类型错位是 intent 链的观察项(未来阶段);
2. 空拍卡片是中性"非素材"占位(HONEST_EMPTY 字样),empty beat 的呈现策略不在 12.10 范围;
3. 过程修复 3 个测试侧 bug:offset 按 beat 误累加(→按 shot)、resolver 缺 thumburl、IMG→IMAGE 契约标签映射(与 Stage 11 contract 对齐,非改判)。

## 6. 交付物

- `output/stage33/stage12_10_storyboard/storyboard.json`(11 beat 全编排+provenance)
- `output/stage33/stage12_10_storyboard/{storyboard_validation.json, render_results.json, final_result.json}`
- `output/stage33/stage12_10_storyboard/run_storyboard_test.py`
- 源码:`src/video_studio/stage33/storyboard.py`
- 成片:`render/storyboard_final.mp4` + `render/video_audio.mp4` + `storyboard.srt`
- 本报告:`docs/STAGE33_STAGE12.10_STORYBOARD_REPORT.md`

```
STAGE12.10 = PASS
  11/11 合法 Storyboard · 素材 100% 可溯源 · HONEST_EMPTY 零强填
  时间轴 0.01s 内合法 · Renderer 真实出片 95.44s · 冻结组件零回归
STOP —— 等待授权
```
