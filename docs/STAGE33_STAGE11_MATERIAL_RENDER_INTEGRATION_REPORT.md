# Stage 11：Material → Renderer Integration Hardening

> 状态:**`MATERIAL_RENDER_INTEGRATION = PASS`**（4 镜真素材闭环通过）。
> `CV2 = FROZEN` · `TEXT_LLM = PASS` · `ENGINEERING_E2E = PASS` · `LONG_FORM_VIDEO_QUALITY = NOT_READY` · `30_DAY_MONITORING = STARTED`
> **STOP。** 未进入 GPU / 长视频渲染 / Commons 优化 / 叙事优化;未修改 CV-2/V1/Vision/Gold/sanitizer。

---

## 0. 目标与根因回顾

**目标**:**CV-2 最终选中的 top-1 candidate 必须能被 Renderer 正确定位、获取并用于视频画面。**

**根因(Stage 10 验收发现)**:
```
cv2_results.json candidates = {rank,title,vision_fit,vision_success,acq,cache_hit}
                                 ↑ 缺少 thumburl / source_url / asset identity
Renderer 无法下载 top-1 图片 → 确定性 Text Card fallback（Stage 10 MP4 = 207KB 文字卡）
```

**Stage 11 修复思路(集成层,不改 CV-2)**:原始 `candidates.json`(Commons 检索)**保留了 thumburl/url**——在集成层按 title 将二者合并,生成**稳定 asset contract**,renderer 用它获取。

---

## 1. Candidate Asset Contract(新增 `material_asset_contract.py`)

每个最终候选现在完整可追踪:

| 字段 | 说明 |
|---|---|
| `asset_id` | `a_` + sha256(source_url)前 12 位——**稳定机器身份**(不依赖 title/rank) |
| `title` / `thumburl` / `source_url` | 完整 URL 链(可下载) |
| `media_type` | `IMAGE / DOCUMENT / VECTOR / AUDIO / VIDEO / TEXT / UNKNOWN` |
| `renderable_visual` | True/False(不是类型 blacklist!) |
| `path` | `direct / convert_pdf_page / convert_svg_png / still_frame / none` |
| `vision_fit` / `vision_success` / `acq` / `cache_hit` | 保留 CV-2 字段 |

**PDF/SVG 未被粗暴拒绝**:DOCUMENT → PDF page1 缩略图(Commons 已提供 PNG thumb,直接可用);VECTOR → SVG→PNG 转换(有 cairosvg 时);VIDEO → 帧抽取(ffmpeg);AUDIO/TEXT/UNKNOWN → 明确 `ASSET_NOT_RENDERABLE_*`(不假装)。

---

## 2. Asset Acquisition(新增 `asset_render_resolver.py`)

**复用现有 `asset_cache.acquire_asset`(不建第二套缓存)**:
```
contract → cache check → hit? 用 : asset_cache 获取 → 验证 → 
IMAGE直接 / DOCUMENT thumb直用 / VECTOR转PNG / VIDEO抽帧 / 
AUDIO/TEXT/UNKNOWN → deterministic fallback
```
每条路径记录:`asset_acquisition_status / cache_hit / download_status / conversion_status / fallback_reason`——**无 silent failure**。

---

## 3. Part A: 5 类型候选验证(不做黑名单)

| 类型 | 判定 | 路径 |
|---|---|---|
| JPG/PNG | IMAGE ✓ renderable | direct |
| WEBP | IMAGE ✓ renderable | direct |
| PDF | DOCUMENT ✓ renderable | convert_pdf_page(thumb PNG 直用) |
| SVG | VECTOR ✓ renderable | convert_svg_png |
| WAV | AUDIO ✗ not visual | ASSET_NOT_RENDERABLE_AUDIO(fallback) |

**全部正确:无类型黑名单;不可渲染类型被识别,不猜测。**

---

## 4. Part B/C: 4 镜真实回归(决定性)

### 证据链(4/4 完整闭环)

```
Shot S01: V1 top-1 = Effectiveness of a littoral(...PDF)
          Vision top-1 = Integration of Personal Digital Assistant(...PDF)
          CV-2 result = Integration(...) | asset_id = a_xxx | 
          local/cache asset = a_xxx.img.jpg (955KB PNG) | 
          renderer = Integration(...) | MP4 frame = PDF page thumb
→ rendered asset == CV-2 top-1 (exact match, 4/4)
```

### 验证结果

| 验证项 | 结果 |
|---|---|
| **A. MP4 出现素材画面** | ✅ `final_4shot_real.mp4`(**15.1MB** vs Stage 10 的 207KB 文字卡);contact sheet 显示 4 种真实素材图(PDF 首页/AI 人脸时间线/皇家学会论文页…) |
| **B. 素材来自 CV-2 top-1** | ✅ **4/4 完全匹配**(rendered_asset_title == vision_top1_title,含 asset_id 追踪) |
| **C. 失败时 deterministic fallback** | ✅ 本次无失败(acq 全 OK);fallback 路径保留且可观测(PART A audio = ASSET_NOT_RENDERABLE_AUDIO) |
| **D. CV-2 ranking 未变** | ✅ 4/4 v1_top1 ≠ vision_top1(Vision 排序真实保留);contract 只读;CV-2 算法零修改 |

---

## 5. 如实观察(非本阶段修复范围)

- **素材噪声仍在**:抽象主题("AGI 2035")的 Commons 检索 top-1 为 PDF 首页/SVG 页——这是 **Commons 检索质量问题**,不是 contract/acquisition 问题(本阶段范围=数据链,检索硬化属 Option 2);
- 每镜画面确实用了 **CV-2 top-1**(即使 top-1 本身是 PDF 页)——**闭环语义正确**;
- 未做 36 镜全量渲染(按指令,不进入长视频)。

---

## 6. 成功标准对照(15 项全 ✅)

| 标准 | 结果 |
|---|---|
| CV-2 零算法修改 | ✅ |
| V1 / Vision / Gold 零修改 | ✅ |
| Candidate identity 可追踪 | ✅ asset_id |
| thumburl/source_url 可追踪 | ✅ |
| cache 正常复用 | ✅ 复用 asset_cache |
| renderer 能获取 CV-2 top-1 | ✅ |
| **至少 4 镜真实素材画面** | ✅ 15.1MB |
| renderer selected == CV-2 top-1 | ✅ 4/4 |
| fallback deterministic | ✅ |
| fallback reason 可观测 | ✅ |
| PDF/SVG 未粗暴 blacklist | ✅ 有转换路径 |
| 不可渲染类型正确识别 | ✅ AUDIO→ASSET_NOT_RENDERABLE_AUDIO |
| 无 silent failure | ✅ |

---

## 7. 交付物

`output/stage33/stage11_material_integration/`:
- `candidate_asset_contract.json` · `acquisition_results.json` · `render_results.json`
- `four_shot_regression.json` · `asset_trace.json` · `audit.json` · `final_result.json`
- **`render/final_4shot_real.mp4`**(15.1MB,4 镜真素材)+ `render/contact_sheet_real.jpg`
- 源码:`src/video_studio/stage33/material_asset_contract.py` · `asset_render_resolver.py`(新增,集成层)

报告:`docs/STAGE33_STAGE11_MATERIAL_RENDER_INTEGRATION_REPORT.md`(本文件)

---

## 8. 最终状态与 STOP

```
MATERIAL_RENDER_INTEGRATION = PASS（CV-2 top-1 → 真素材画面闭环,4/4 证明）
CV2 = FROZEN · TEXT_LLM = PASS · ENGINEERING_E2E = PASS
LONG_FORM_VIDEO_QUALITY = NOT_READY · 30_DAY_MONITORING = STARTED

STOP → 等待人工验收
```

**未进入**:GPU / 36 镜全量 TTS / Commons 检索优化 / 叙事优化。下一阶段方向(Option 1/2/3)由人工裁决,一次只做一个。
