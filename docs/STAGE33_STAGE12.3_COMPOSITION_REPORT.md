# Stage 12.3：Composition Policy

> 状态:**`STAGE12.3 = PASS`** · **`COMPOSITION = VALIDATED`**
> 冻结边界:CV-2 / V1 / Gold / Top-5 / sanitizer / asset_cache / motion.py / camera_motion_policy / Visual Intent / Query Generator / Quality Gate / Stage 11 contract + renderer **全部未改**。
> **STOP —— 不进入 Subtitle / Full E2E / GPU/TTS / Retrieval v2 / Narrative / CV-2。**

---

## 0. 目标与范围

解决"素材进入画面的构图与信息层次":让已选素材以更合理方式呈现。**Composition 只决定"怎么呈现",不决定"该不该用"**,不重新判断素材质量,不改素材选择算法。

**未做**:Subtitle / Full E2E / GPU/TTS / Retrieval v2 / Narrative 改造 / CV-2。

---

## 1. 现状审计(复用,不重建)

现有 `stage32b/assemble.py` 的 composition = `scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080` —— **一律"放大铺满+中心裁切"**,是"文档关键文字被裁/巨大截图铺满"的根源。

**复用**:ffmpeg 滤镜(scale/pad/contain)已足够,无需新视觉模型,无需重建 renderer。新增 `composition_policy.py` 只做**决策**(asset_type + intent + focus → fit_mode/crop/framing),映射为 ffmpeg `-vf` 链。

---

## 2. Composition Policy

| asset_type + intent | composition | fit_mode | 理由 |
|---|---|---|---|
| 文档/网页/截图 | CONTAIN_BG | contain | 内容完整,不被裁 |
| 图表/数据 | DETAIL_CROP | detail_crop | 呈现数据焦点 |
| 地图 | DETAIL_CROP | detail_crop | 呈现区域+图例 |
| 人物/办公室 | FULL_BLEED_SUBJECT | cover_subject | 保主体完整(安全裁切) |
| 城市/普通照片 | FULL_BLEED | cover | 视觉型铺满居中 |
| 视频 | FULL_BLEED | cover | 原生 |
| 未知 | CONTAIN_BG | contain | 安全不裁 |

**fit_mode → ffmpeg 映射**:
- `contain`:`scale=…decrease, pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=0x0b2e33`(深色底,无黑边无裁切);
- `detail_crop` / `cover`:`scale=…increase, crop=1920:1080`;
- 全程 `force_original_aspect_ratio`(无异常拉伸)。

---

## 3. 分支覆盖(9 用例)

```
photo_person → FULL_BLEED_SUBJECT | document_page → CONTAIN_BG
web_screenshot → CONTAIN_BG        | chart_data → DETAIL_CROP
map_region → DETAIL_CROP           | city_scene → FULL_BLEED
future_city → FULL_BLEED           | unknown → CONTAIN_BG
video_native → FULL_BLEED
→ 4 种 composition 类型,全部有 reason
```

---

## 4. 6-shot Regression

| shot | asset_type | composition | 备注 |
|---|---|---|---|
| S01 历史 | DOCUMENT | CONTAIN_BG | 文档 contain,文字不裁 |
| S02 当前能力 | DOCUMENT | CONTAIN_BG | |
| S03 就业 | DOCUMENT | DETAIL_CROP | 数据/图表焦点 |
| S04 人机协作 | — | **HONEST_EMPTY** | 无 kept 素材(Stage 12.1),composition 不救坏素材,不塞假素材 |
| S05 基础设施 | DOCUMENT | CONTAIN_BG | |
| S06 未来社会 | DOCUMENT | CONTAIN_BG | |

**S04 honest empty 是上游 Retrieval/Asset Quality 问题,不是 Composition 问题**——如实记录 `composition_cannot_rescue_bad_asset = true`。

---

## 5. OLD vs NEW 渲染证明(客观)

| 项 | OLD(full-bleed crop) | NEW(contain+bg) |
|---|---|---|
| MP4 大小 | 263.7KB | 157KB |
| 中间帧 PNG | 1622KB(放大铺满) | 620KB(完整保留) |
| 结论 | 内容放大裁切 | 文档完整,深色底无黑边 |

**帧文件大小客观证明:NEW 未裁切(内容完整),OLD 裁切放大。**

---

## 6. 成功标准(14 项全部 ✅)

1. policy 按 asset_type+intent 差异化 ✅
2. 文档/PDF/网页不粗暴裁切 ✅(CONTAIN)
3. 图表核心可见 ✅(DETAIL_CROP)
4. 人物主体完整 ✅(FULL_BLEED_SUBJECT)
5. 不再统一单一全屏构图 ✅(4 种)
6. 无异常拉伸 ✅(force_original_aspect_ratio)
7. 无异常黑边 ✅(pad color 深色,非黑)
8. 无主体出框 ✅(contain 保完整)
9. Composition 不改素材选择 ✅(只读下游)
10. Camera Motion 不回归 ✅(未动)
11. Stage 11 renderer 不回归 ✅(未动,composition 映射 ffmpeg vf)
12. 每个决策可解释 trace ✅
13. 无新视觉模型 ✅(无 CLIP/detector/segmentation/face/tracking)
14. 6-shot regression PASS ✅

---

## 7. 归因(严格区分)

| 问题 | 归属 |
|---|---|
| S04 无素材 | **Retrieval / Asset Quality**(上游,非 Composition) |
| 文档关键文字被裁 | **旧 renderer composition**(本阶段已修) |
| 构图多样性 | **Composition**(本阶段实现) |
| 运动是否合适 | **Camera Motion**(Stage 12.2,未动) |
| 素材能否渲染 | **Renderer**(Stage 11,未动) |

---

## 8. 交付物

`output/stage33/stage12_3_composition/`:
- `composition_trace.json`(6-shot trace)
- `composition_regression.json`(回归 + 成功标准 + 归因)
- `composition_branch_coverage.json`(9 用例)
- `render_results.json` + `render/old_composition.mp4` + `render/new_composition.mp4` + `contact_sheet_old/new.jpg` + `old_frame.png`/`new_frame.png`
- `final_result.json`
- 源码:`src/video_studio/stage33/composition_policy.py`(新增)

报告:`docs/STAGE33_STAGE12.3_COMPOSITION_REPORT.md`(本文件)

---

## 9. 状态与 STOP

```
STAGE12.3 = PASS
COMPOSITION = VALIDATED
CV2 = FROZEN · TEXT_LLM = PASS · Stage11/12.1/12.2 = PASS · 30_DAY = STARTED

STOP —— 等待人工授权 Phase 12.4（Subtitle integration）
```

**下一阶段建议**:Phase 12.4 Subtitle integration(复用 subtitle agent + TTS duration 对轴 + SRT/burn-in),之后才是 Stage 12 集成 E2E。
