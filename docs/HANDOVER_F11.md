# F11 渲染交接笔记（Phase 57 续作 · 2026-10）

## 当前状态（已验证）
- 第十二部候选 F10.1 已登记（p_3e9292101f10，与 F9 分配 36/36 一致 + 词级字幕）。
- 黑板主线 21 张已生成并监理复核通过：`output/mainline_v2/<scene_id>.png`
  （统一构图：同一黑板 + 木粉笔槽 + 直视机位；概念逐景提炼自 visual_hint；
  6 张照片漂移已重生成修复；P09_2 讲台空座为语义精准的实拍，接受）。
- 保留的真实/强素材（keep 集，不上主线）：23e71 邮戳、65377 Principia、
  30dd 图染色、3f0b 球堆、5144 几何构图、acaa 图论、301ff 数学之树、
  a3f0 函数图表、1d2fe 发光公式、a3aff 白板、1e9d Lean、bd38/cfae 棋（仅 P09_3/4）。

## F11 渲染配方（四步）
1. **注册主线入池**：读 `docs/regression_2x/logs/p45_4_merged_payload.json`（结构见
   `docs/regression_2x/p46_4_merge.py:100-118`），把 21 张主线图追加为 candidates
   （每条：sha256（实测）、path（复制到 p_96efdc03e1aa/media/acquired_materials/）、
   name="GenConcept <scene_id>"（语言中立！P49 规则）、license="Generated (wanx2.1)",
   license_cleared=true, license_class="FREE_ATTRIBUTION", provider="generated",
   media_type="png"），写为 `logs/p57_merged_payload.json`。
2. **写 F11 pins**：格式兼容 `logs/p56_2_f9_pins.json`（schema p56-2-f9-pinned-assignment-v1，
   字段 pins={scene_id: sha256 全串}）。锚定实拍景沿用 F10.1 的 pin（来自
   p56_2_f9_pins.json）；抽象景 pin 到主线图 sha256。**注意 agent 的 pins 路径硬编码为
   `logs/p56_2_f9_pins.json`（agent.py:651）——用新文件覆盖它，或同步改两处**。
3. **渲染**：复用 F10.1 的渲染入口（参照 `docs/regression_2x/p47_5_gfeas.py` 的
   payload 消费方式；沙箱工程 p_3e9292101f10 复用，引擎重跑 editing 任务）。
4. **门（以烧录产物为测对象）**：字幕四门（覆盖≥95%/时长/排他/词级同步）+
   锚定守卫（错配景=0：P01_1/P03_1/P04_1/P04_3/P05_1/P06_2/P07_1/P07_2 等）+
   DQ-2/3/3e + 内容排除 4/4 + 比喻配额 7/7 + 家族份额报告（A/E/G 新构成）。
   全门过 ⇒ 登记第十一部候选 F11（append-only、零 promotion）。

## 终审交付
F11 路径 + 与 F10.1 的逐景对照表 → 用户第七次终审（两裁决点：字幕跟嘴、黑板主线）。
通过 ⇒ promotion + 发布试跑（Pexels Videos 源已实测可用：同一把 key 打
api.pexels.com/videos/search，Phase A 集成方案在对话记录中）。

## 已知陷阱（连续性保障）
- 工作目录会漂移：**每个 Bash 调用都带 `cd /c/mp4agent/video-studio &&`**。
- .env 的 VLM_API_KEY 值曾粘中文注释：直接读 .env 必须经 core/env.load_env
 （D1 剥离生效），禁止裸解析。
- 匹配器消费的元数据字段必须语言中立（P49 规则，tests asset_name_neutral_test）。
- 回归串行独占（并发写库会打破只读断言）；每个 Bash 调用带 cd 前缀。

## ⛔ P56 后续终审发现的最高优先缺陷（2026-10，监理帧检+ASS 转储）
**F10.1 烧录 ASS 完全损坏**：105 条 cue 全部压缩在 0.1-178.36s（每条 ~1s，
cue2 长达 58.6s），178.4s 后 519s 零字幕。词级金门（median 0.0000s）测的是
构建器输出——生产路径（agent 内 cue 构建）从未接入 P54/P55 的
build_cues_from_words_exact，仍走 P51 时代旧路径（钳制级联 + 压缩时刻）。
**"测试修了、生产没接"第五例**（前四例：P22 bank、P21 绑定展开、P47 gen name、
P22 派生景核验）。用户自 F6 起报告的"报幕/字幕慢/对不上"真因即此
（监理曾误诊为公式墙素材与感知家族，两次修错层——erratum）。

### 修复（Phase 57 续，下一轮执行）
1. agent 的 cue 构建调用替换为 build_cues_from_words_exact（P55 已验证版，
   输入 = words_manifest + 景窗 + 切片连续性数据，调用形状与 P55 验证一致）；
2. 生产路径断言：构建后 cue 跨度 ≈ 音频时长（±2s）、median ≥3s、重叠 0，
   违反即 fail-closed；
3. 渲染 F12 → **以烧录 ASS 为对象复测四门**（覆盖/时长/排他/同步）→
   登记 → 用户第六次终审（字幕跟嘴）。
