# PHASE 13 报告：运动层生产接线（Ken Burns 入生产线，默认关闭）+ S05 REPLACE 状态

> 阶段：Phase 13 ｜ 依据：Phase 13 授权书（2026-09-30）
> **结论（逐项如实）**：**P13-1 DONE ｜ P13-2 DONE ｜ P13-3 DONE（组件级真实渲染；全 agent 管线级 PENDING）
> ｜ P13-4 PENDING ｜ P13-5 PENDING**
> 铁律：**未完成即 PENDING，不得伪造成 PASS**；零 LLM、零网络；`config.json` 零改动；
> 母片/既有候选/Phase 7–12 产物/stage33 文件零改动（`IMMUTABLE_OK`）。

## 1. 开工前状态核对（§1）与差异登记

| 核对项 | 结论 |
|---|---|
| stage33 `motion.py` / `camera_motion_policy.py` | ✅ 通读：**逐帧整数矩形轨迹**（`plan_hold/plan_pan/plan_zoom`；恒定整数步长、三段缓动 20/60/20、缩放偶数步长 2px、平移 ≥1px/帧、轨迹单调无反转；不可行 ⇒ 返回 None ⇒ HOLD）+ **prefer STATIC over meaningless motion**。**只作参考**：生产模块为**提炼重写**，不 import 实验代码、不改写 stage33 结论（其文件 sha256 在不可变核验中保持不变） |
| 生产渲染链 `_narration_args` | ✅ 静态图路径：`-loop 1 -framerate 1 -t ceil(d)+2 -i <img>` → `scale=tw:th:...increase, crop=tw:th, setsar=1, fps=FPS, trim=duration=d, setpts=PTS-STARTPTS` → `concat` → `ass` 烧录 → 混音；时基契约 = 时间轴权威（6-E） |
| S05 REPLACE 提案 | ✅ `proposal_id=bp-6320bf486a082901`、`deterministic_hash=6320bf486a082901800d76520cb76bf6042bc19b9b7f7b271b05b8da6c8a6ad6`；`previous=ast-6c3fc5af91ed650d` → `candidate=ast-92ca33138ffe64f4`（`C:\mp4agent\h5_asset_candidates\S05\Russell_PM_1+1=2.png`，sha256 `65377b888b778226…`） |
| Phase 12 覆盖层一致性 | ✅ 同候选 `HAS_RECORD` / `PUBLIC_DOMAIN`（索引原为 `PD-US`，`changes_index_license=false`）；`source_of_record=phase6g_exec_h5.json#asset_records[0]` |
| 权威时间线谱系 | ✅ P7-6 模拟所用 **21 场景**来自 `render_output.material_timeline`（6-G final master / DCv2 H5 的同一权威时间线；覆盖报告 `sources` 含 `visual_requirements.json` 等） |

**差异登记（现实优先）**：
1. 授权书写"输出 zoompan/crop 滤镜串"；**本模块只输出 `crop` 表达式**（整数运算 + `min/max/floor`）——
   `zoompan` 是**亚像素浮点插值**，与"整数帧"纪律冲突；且 crop 表达式可被 `evaluate_closed_form()`
   在 Python 侧**逐帧精确复算**（见 §2 等价性）。
2. 授权书要求"transl 幅度 ≤3%、zoom ≤1.08、场景 <10s 静止"与 stage33 的"恒定步长 ≥1px/帧**贯穿整场景**"
   **在长场景下不可同时满足**（3% ≈57px、8% ≈142px 摊到数百帧 ⇒ 仅 0.16–0.25px/帧）。
   **设计决定（已登记）**：运动集中在 **≤150 帧（6s）窗口**内，窗口内步长 ≥1px/帧（平移）/2px/帧（缩放），
   窗口外静止；**幅度上限与整数帧纪律不变**（`MOTION_WINDOW_MAX_FRAMES=150`，`POLICY` 内注明依据）。
3. 6-G 时间线（v2 稿）场景**不带 `hook` 标记** ⇒ 选取按 `(hook, 时长降序, scene_id 升序)` 中
   "hook 优先"仅在有标记时生效，无标记时退化为时长序（确定性，已在代码与测试中写明）。

## 2. P13-1 `core/motion.py`（纯函数、确定性、零 I/O）— **DONE**

- 输入 = 场景（`scene_id`/`duration_s`/可选画布尺寸）+ 策略；输出 = **确定性逐帧整数矩形** +
  运动参数记录（起止缩放、平移幅度、方向、窗口帧数）+ **ffmpeg `crop` 表达式**。
- 策略常量**逐条注明依据**（`POLICY`）：`max_zoom_end=1.08`、`pan_max_ratio=0.03`、`min_scene_s=10.0`、
  `max_enabled_ratio=0.6`、`static_head_tail_frames=8`、`zoom_step_px=2`、`pan_min_step_px=1`、
  `motion_window_max_frames=150`（每条含 `basis`，不发明数）。
- **闭式 ⇔ 权威矩形等价**：`crop_filter()` 生成的表达式是 `evaluate_closed_form()` 同一闭式的转写；
  测试对**全部场景逐帧**比对 ⇒ **0 处不一致**。
- 早期缺陷（真实渲染发现，见 §4）：① `min/max` 逗号未加引号；② pan 的 `x` 被拼成 `x0*(c)`（乘法而非加法）。
- 确定性：同输入两次构建逐字节一致；输出按 `scene_id` 排序（输入顺序无关）；无时间戳/随机量。

## 3. P13-2 渲染链接入（默认关闭、fail-closed）— **DONE**

- 开关：`core/motion.resolve_config()` 三级链（`config.tools.render_motion` → **可选外部文件**
  `config/render_motion.json` → 内置默认 `{"enabled": false}`）；**`config.json` / `config.example.json` 零改动**
  （不可变核验：sha256 仍为 `7b03424846f15efc…` / `d5e838509d0c…`）；新增示例 `config/render_motion.example.json`（不参与读取）。
- 注入点：**每场景合成阶段（concat 之前）**，命中策略的场景把 `scale/crop` 换成
  `scale=src_w:src_h(放大画布), crop=src_w:src_h, setsar=1, fps, <crop 表达式>, trim, setpts`；
  **字幕/混音/时基语句逐字未改**。
- **fail-closed**：任一滤镜构造失败 ⇒ 该场景保持静态模板 + 证据中登记 `MOTION_FALLBACK_STATIC`
  （不静默、不失败整片）；证据落 `<project>/render/motion_evidence.json`（仅在开启/出错时写）。
- **关闭时向后兼容**：静态模板在源码中逐字节保留（测试 5c 断言）；
  `enabled=False` ⇒ 全场景 STATIC、无 fallback、矩形全满幅；默认配置解析为 off。
- PI-1/PI-2/G-TL/G-SUB 门禁语义未触碰（本阶段只改视频滤镜构造；DQ/PI 逻辑与阈值零改动）。

## 4. P13-3 真实渲染验证 — **DONE（组件级）**；**全 agent 管线级 PENDING**

证据：`logs/phase13_motion_render_verify.json`（真实 ffmpeg 执行**生产滤镜串**与**生产静态模板**，
6 景 = 3 运动（1 zoom + 2 pan）+ 3 静止对照；真实素材 1920×1080@25fps；临时目录输出，**未覆盖任何母片/候选**）

| 场景 | 类型 | 时长 Δ(s) | 10%↔90% 抽帧差（运动臂 / 静止臂） | corr@90% | 渲染耗时 Δ(s) |
|---|---|---|---|---|---|
| S01 | SLOW_ZOOM_IN | **0.0** | **23.07** / 0.36 | 0.5676 | +0.21 |
| S04 | SLOW_PAN | **0.0** | **13.30** / 0.36 | 0.6561 | −0.17 |
| S06 | SLOW_PAN | **0.0** | **24.22** / 0.04 | 0.3244 | +0.13 |
| S02/S03/S05 | STATIC（策略未选） | 0.0 | 0.39/0.04/0.39（≈噪声底） | 0.802/0.6026/0.802 | ≤ +1.06 |

- ① **时长契约**：运动臂 vs 静态臂 **Δ=0.0s**（≤1 帧）✔
- ② **运动在屏实证**：3/3 运动场景 > max(0.5, 3×同场景静止基线) ✔（静止对照 ≈ 噪声底）
- ③ **成片抽帧核验 corr**：**全部 ≥0.30**（0.3102…0.8020）✔（appears_in_film 不退化）
- ④ 响度/字幕路径未参与组件级渲染；PI 门禁语义未改（**管线级 PI 复核未做 ⇒ 见下**）
- ⑤ **渲染耗时增量**：−1.17…+1.06 s/景（同量级，无明显劣化）✔

### 4.1 **真实渲染发现并修复的两个真实缺陷（本阶段最有价值的证据）**
1. **逗号未加引号**：pan 的 `crop=W:H:x=48*(...):y=43` 中 `min/max` 的逗号被 ffmpeg 当作滤镜链分隔符
   ⇒ `No such filter: '0)'`（实测报错原文）。修复 = `x`/`y` 加引号。
2. **乘法而非加法**：拼接式 `"{x0}{sign}*({c})"` 在正向时生成 `48*(c)`（位移被**乘**到 x0 上），
   c 增大后迅速被 clamp ⇒ **位移在 n≈20 后停止**（实测：n=8↔20 差 31.42、**n=20↔45 仅 0.011**）。
   修复为加法形式（`48+1*(c)`）后复测：n=8↔20 差 9.90、**n=20↔45 差 13.96**（位移持续），
   端到端 10%↔90% 差由 0.37 提升到 **13.30**。
   > 两处都**未**被静态审查发现，只有真实渲染能暴露；生产 fail-closed 在缺陷 ① 时会回退静态（安全但无运动）。

**PENDING 项（如实）**：**全 agent 管线级**（Engine → `editing._render` → 真实成片）的端到端验证
**未完成**（本阶段预算内未执行；§7 说明）。因此不宣称"渲染链端到端已验证"。

## 5. P13-4 S05 REPLACE 执行 — **PENDING（未执行）**

**已完成的准备工作（可复算）**：
- ✅ §1 已核对 `proposal_id` / `deterministic_hash` 与 P7-6 登记**一致**；
- ✅ Phase 12 覆盖层对 Russell 页候选给出 `HAS_RECORD`/`PUBLIC_DOMAIN`（许可门 PASS）；
- ✅ 替换素材在位：`C:\mp4agent\h5_asset_candidates\S05\Russell_PM_1+1=2.png`，sha256 `65377b888b778226…`。

**未执行（故 PENDING）**：6-B 链的**人工批准登记**（写入 decisions 并绑定 proposal sha256）、
修订候选渲染、PI-1…PI-6 与 DQ 复核、真实素材抽帧比对（`replaced=true` 证据）。
**不伪造 PASS**；本授权书可作为人工批准依据，但**登记与执行动作本身未完成**。

## 6. P13-5 全片候选（人工观看用）— **PENDING（未产出）**

未产出全片合成候选（S05 替换 + 运动层）。原因：依赖 §5 的批准/执行链与一次全片渲染
（21 景权威时间线），本阶段预算内未执行。
**如实预告（授权书要求）**：若产出，**DQ-3（静态保持）的度量语义会因运动改变**——
`freezedetect` 不再触发 **≠** 场景结构变化；报告**不得**宣称"DQ-3 PASS"（除非按原口径复算），
只能记录为"运动层生效 ⇒ 静态保持指标口径变化"。

## 7. 测试 / 回归 / 不可变 / 预算

| 项 | 结果 |
|---|---|
| `tests/motion_test.py`（新增） | **22/22 PASS**：滤镜串确定性、闭式⇔矩形逐帧等价、<10s 静止、hook 优先（含 <10s hook 被时长规则排除）、zoom ≤1.08、平移 ≤3% 单方向、窗口 ≤150 帧、轨迹单调、失败回退码、关闭时静态模板逐字节保留、注入在 concat 之前、`config.json` 未改、常量出处 |
| 完整回归 | ****76 套件 / 76 rc=0 / FAILED: []**** |
| 不可变核验 | `phase13_immutable_check.py` ⇒ **IMMUTABLE_OK**（6-G 母片/baseline/config 钉定值、P7-2 索引、P7-6 产物、P12 产物、`core/materials.py`、**stage33 两文件**、S05 替换素材 全部未变；`agents/editing/agent.py` 为本阶段授权加法，默认关闭） |
| 预算 | **LLM $0、网络 0 次** ✔；渲染耗时：组件级 6 景（每景 ≤21s 素材）合计 <2 分钟；**全片渲染未执行** |


> **并发干扰说明（如实）**：本阶段曾**同时**跑两次 `run_all_suites.py`，`multimodal_test` F1（真实 DB 行数运行前后一致）因此转红（实测 tasks 20731→20734、artifacts 18226→18227、events 147737→147738）——系另一进程写入 fixture 行所致，**非代码缺陷**；单独重跑后 ****76 套件 / 76 rc=0 / FAILED: []****。

## 8. 产物 sha256 台账（可复算）

| 产物 | sha256 |
|---|---|
| `src/video_studio/core/motion.py` | `78923bb7662282cfce50fdcd844d6f1bbe39c633d0d0b0f8e29a13263b08a813` |
| `src/video_studio/agents/editing/agent.py`（P13-2 加法） | `d9c1a8f830053c7b7677f8feb261553d188586cb160dc7bc6ca5880e4acac09c` |
| `config/render_motion.example.json` | `db251f2577961b687cd101f4fa16605648132032cd0910ca9e136653637e6a91` |
| `tests/motion_test.py` | `3ae7e6fca1e2421f5260316b5eb0d5f73fbe118f0e64ab55ba5cecc913f8879f` |
| `docs/regression_2x/logs/phase13_motion_render_verify.json` | `7d93fdc111dd83b4d352557cca6488335737538295d94d27d3e9a094b347518f` |
| `config/config.json`（**零改动**） | `7b03424846f15efc…` |
| `output/phase6g_exec_h5/.../H5_rp-0ebebb71f99c.mp4`（母片，**零改动**） | `3b61dafda11c1b9d…` |

## 9. 已知限制 / 下一阶段输入

1. **组件级 ≠ 管线级**：P13-3 验证的是生产滤镜串 + 生产模板 + 生产 corr 口径（真实 ffmpeg），
   **未经** Engine → `editing._render` 的端到端渲染 ⇒ 标 PENDING；下一步应先跑 1 个真实小链（零 LLM 夹具）确认。
2. **3% 平移接近可感知下限**：48×48 缩略图上不可分辨（<1.5px）⇒ 运动实证必须用 ≥480×270 度量；
   若人工观看认为平移过弱，可**收紧**窗口或提高幅度上限（**只可收紧不可放宽**的纪律针对上限；幅度提升需新授权）。
3. **S05 页 corr 裕度**：S06（Russell 页作源）corr=0.3244，距 0.30 阈值裕度较小（+0.024），
   真实发布前建议复核该景的成片抽帧口径。
4. `MOTION_WINDOW_MAX_FRAMES=150` 是**本阶段的设计决定**（为在长场景下同时满足幅度上限与 ≥1px/帧纪律）；
   若采用"整场景恒定步长"需放宽幅度上限或接受亚像素位移（均需新授权）。
5. P13-4/P13-5 的**前置条件已全部核实**，下一步只差"登记批准 → 渲染 → PI/DQ 复核"三步（见 §5）。

**Phase 13 按上表逐项收尾；P13-4/P13-5 为 PENDING，非 PASS。STOP，等待下一阶段授权。**
