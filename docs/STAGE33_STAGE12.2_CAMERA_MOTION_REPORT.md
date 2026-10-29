# Stage 12.2：Camera Motion Policy

> 状态:**`STAGE12.2 = PASS`**（复用 motion.py 建立 intent-aware motion policy + 6-shot regression + 渲染证明）。
> 冻结边界:CV-2 / V1 / Gold / Top-5 / sanitizer / asset_cache / motion.py / Stage 11 contract / Stage 12.1 模块 **全部未改**。
> **STOP —— 不进入 Composition / Subtitle / 完整 E2E。**

---

## 0. 目标与范围

本阶段只解决"素材基本正确后,镜头如何呈现"。核心:消除无意义统一运镜、默认左上漂移、所有素材同 motion、静态截图无焦点。

**未做**:Composition / Subtitle / 完整 8-12 分钟 E2E / GPU / TTS 优化 / 新素材源 / CV-2 修改。

---

## 1. 复用 motion.py(未改)

现有 `stage33/motion.py` 已提供:
- `plan_hold`(HOLD,帧差恒 0);
- `plan_pan`(LEFT/RIGHT/UP/DOWN,头尾静止+三段缓动,速度≥1px/帧);
- `plan_zoom`(zoom_in/out,anchor 固定,偶数步长);
- 不可行 → `None`(调用方降级 HOLD)。

**未创建第二套运动系统**。新增 `camera_motion_policy.py` 只做**决策**(asset_type + visual_intent + focus → motion_type/direction/reason),轨迹仍由 motion.py 生成。

---

## 2. Camera Motion Policy(决策规则)

| asset_type + intent | motion | 理由 |
|---|---|---|
| 人物/办公室 | SLOW_ZOOM_IN | 逐渐聚焦主体 |
| 地图 | SLOW_PAN RIGHT | 左→右区域扫描(地图阅读习惯) |
| 文献/PDF(无焦点) | **STATIC** | 无焦点则静止,不漂移 |
| 图表/数据 | SLOW_ZOOM_IN | 细节聚焦 |
| 未来城市(未来+城市) | SLOW_PAN RIGHT | 电影式天际线横扫 |
| 历史建筑/场景 | **STATIC** | 尊重档案,静止 |
| 普通照片 | SUBTLE_ZOOM | 轻微聚焦 |
| 视频 | SOURCE_NATIVE | 保留原生运动 |
| 不确定 | **STATIC** | 无可视理由则静止 |

**核心原则**:宁可静止,不无意义运动。每个非 STATIC 运动都有 direction + reason(记录在 trace)。

---

## 3. 方向必须有理由(已实现)

- map → RIGHT(左→右阅读);
- future city → RIGHT(电影式天际线);
- 其余 → 无方向(STATIC / zoom in center);
- **无固定默认方向**;`no_fixed_direction=true`。

trace 记录:`shot_id / asset_id / motion_type / motion_direction / start_scale / end_scale / focus_point / motion_reason`。

---

## 4. 6-shot Regression 结果

**真实 6-shot**(Stage 12.1 的 kept 候选):
- 6 个 kept 候选**全是 DOCUMENT**(上游数据局限:Commons 对抽象意图缺真实场景照片);
- Policy **正确** 把它们都判 STATIC(无焦点文档→静止)——**这是正确行为**(静止优于无意义运动),但真实 shot 上未展示运动多样性。

**Policy 分支覆盖(合成 9 用例)**:
```
person → SLOW_ZOOM_IN | map → SLOW_PAN RIGHT | document → STATIC
chart → SLOW_ZOOM_IN | future_city → SLOW_PAN RIGHT | historical → STATIC
ordinary → SUBTLE_ZOOM | unknown → STATIC | video → SOURCE_NATIVE
→ 4 distinct motions + SOURCE_NATIVE;3 个 STATIC;全部有 reason
```

**渲染证明(OLD vs NEW)**:
- OLD:`zoompan z=1.0+0.06*on`(统一漂移);
- NEW:STATIC(文档无焦点);
- 输出 `old_uniform.mp4` + `new_static.mp4` + contact sheets。

---

## 5. 成功标准对照

| 标准 | 结果 |
|---|---|
| 无意义运动明显减少 | ✅(文档/不确定→STATIC) |
| 默认左上运动消失 | ✅(无固定方向;仅 map/future 有理由的 RIGHT) |
| 不确定素材安全 STATIC | ✅ |
| 不同素材不同 motion | ✅(4 种 distinct + SOURCE_NATIVE) |
| Visual Intent 影响 motion | ✅(future→pan, historical→static, person→zoom) |
| 旧 Stage 11 renderer 不回归 | ✅(复用,未改) |
| motion trace 可解释 | ✅(每决策有 reason) |
| 不把主体移出画面 | ✅(motion.py 的 anchor/center + clamp) |
| 无抖动/跳变 | ✅(motion.py 整数帧 + 头尾静止) |

---

## 6. 诚实说明

1. **真实 6-shot 全 DOCUMENT → 全 STATIC** 是**上游数据局限**(Stage 12.1 kept 池文档主导),不是 motion 失败。运动多样性通过合成分支覆盖证明;
2. Camera Motion **只负责呈现,不重新判断素材质量**(不"救回"gate 拒绝的素材);
3. 未引入任何视觉模型(CLIP/detector/人脸检测/segmentation/tracking)。

---

## 7. 交付物

`output/stage33/stage12_camera_motion/`:
- `motion_policy_trace.json`(6-shot 真实 trace)
- `motion_regression.json`(回归 + 成功标准)
- `motion_branch_coverage.json`(9 用例分支覆盖)
- `render_results.json` + `render/old_uniform.mp4` + `render/new_static.mp4` + contact sheets
- `final_result.json`
- 源码:`src/video_studio/stage33/camera_motion_policy.py`(新增,复用 motion.py)

报告:`docs/STAGE33_STAGE12.2_CAMERA_MOTION_REPORT.md`(本文件)

---

## 8. 状态与 STOP

```
STAGE12.2 = PASS
CV2 = FROZEN · TEXT_LLM = PASS · Stage11 = PASS · Stage12.1 = PASS · 30_DAY = STARTED

STOP —— 等待人工授权 Phase 12.3（Composition）
```

**未进入** Composition / Subtitle / 完整 E2E。按授权顺序,Phase 12.2 人工检查后进入 Phase 12.3。
