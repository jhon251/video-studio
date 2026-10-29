# Stage 3.3 V3-MVP Implementation Plan（Proof-of-Visual-Quality · Coral）

> 状态：**仅实施计划，零代码**。待授权后实现。
> 目标（唯一）：在完全相同的 Coral VO/字幕/时长/内容/素材条件下，让 v3 成片相对 3.2b legacy 与 P1 产生**肉眼明确可感知**的视觉提升；证明 Visual Statement + 克制执行 + 注意力关系成立。
> 依据：`docs/STAGE33_P1_FAILURE_REVIEW.md`、`docs/STAGE33_V3_ARCHITECTURE_STRESS_TEST.md`（均已获认可）。

---

## 1. 范围声明（先划边界）

**做**：Coral 20 镜一版新成片；Visual Statement Director（LLM 输出命题而非模板）；极简高质量画面生成（9 种基础视觉行为）；注意力流（5 种关系）；整数帧运动管线；jitter=0 硬 Gate；A/B/C 三版对照 + 人工裁决材料。

**明确不做**：转场（全片硬切）；BGM/SFX；绿幕；MotifRegistry 扩展；章节/片头片尾模板；新模板库；图表库扩展；Test B/C/D 多主题；与剪映盲测（本轮只做 A/B/C 三版人工裁决）；u2net 分割；视频理解驱动裁剪；生成式画面；P2/P3/P4。

**失败即停的自我检查**（实现过程中一旦发现 Director 退化为"数据句→图形模板、人物句→图片模板、因果句→箭头模板"→ 立即 STOP 报告，不继续堆模板）。

---

## 2. 文件变更清单

### 2.1 修改（仅 stage33 自包 + 自有脚本/测试；其余全部零改动）

| 文件 | v3 变更 |
|---|---|
| `src/video_studio/stage33/__init__.py` | `STAGE33_VERSION="3.3-v3-mvp"`，`STAGE33_STATUS="DEV"` |
| `src/video_studio/stage33/schemas.py` | 重写：**删除模板枚举作为输出字段**；新增 Visual Statement 字段枚举（relation 类型/层角色/运动意图/时序阶段名/视觉行为能力清单） |
| `src/video_studio/stage33/director.py` | 重写：命题式 system prompt（7 问 + 铁律 + 能力清单）+ 新 json_schema（statement 结构）；保留 llama-server 管理与回退链 |
| `src/video_studio/stage33/planner_fallback.py` | 重写：规则回退也输出 statement（字节级确定；理由模板不含模板名） |
| `src/video_studio/stage33/realizer.py`（新） | statement → 具体执行规格（分层内容/整数运动轨迹/时序脚本）——**模板只存在于这一层（LLM 不可见）** |
| `src/video_studio/stage33/motion.py`（新） | 整数帧运动轨迹生成器（§6 算法） |
| `src/video_studio/stage33/graphics.py` | 重写：锚点词分层帧渲染（bg 色带/mg 视觉/fg 锚点词 ≤12 字 + 几何遮罩 + 强调 + 时序显隐） |
| `src/video_studio/stage33/executor.py` | 重写 beat 渲染管线：PIL 逐帧 → ffmpeg 编码（**废除 zoompan**）；3.2b 兼容工件产出逻辑保留 |
| `src/video_studio/stage33/validator.py` | 新增 S2 结构层 + S4 完整性层（§5）；保留 P1 安全层 |
| `src/video_studio/stage33/visual_qc.py` | 更新：jitter=0 全片 25fps 审计、statement 完整性、A/B/C 对照报告 |
| `scripts/run_stage33.py` | 新增 v3 阶段：`plan-v3 / execute-v3 / v3-gate / compare` |
| `tests/stage33_*_test.py` | 更新既有 3 套件 + 新增 `stage33_motion_test.py`（整数轨迹/单调/无抖动）、statement 反模板回归测试 |

### 2.2 绝对禁止修改（沿用既有边界）
`stage32b/**`、`stage31/**`、2.x、Truth/Evidence、Creator Style、冻结稿、Material Package、rights gate、阈值、`docs/STAGE32B_SEAL.md`、P1 全部产物（`output/stage33/coral/visual_plan.json`、`exec/`、`stage33_p1_m4.mp4` 保持为失败基线）。

---

## 3. Visual Statement Schema（LLM 输出，不含任何模板名）

```json
{
  "shot_id": "S06",
  "beats": [{
    "beat_text": "海水温度只要升高一两度，珊瑚就会开始发烧。",
    "narrative_intent": "因果兑现：小的温度变化造成大的后果",
    "attention_target": "一两度",
    "attention_path": "第一眼看极小的「一两度」→第二眼看到「发烧」放大入侵，理解小因大果",
    "visual_evidence": "素材 M-S06-323（海温变化视频，白名单）｜原文数字「一两度」「发烧」",
    "visual_metaphor": "无素材时：先极小锚点「一两度」停留，再让「发烧」高对比放大进入——用空间体量差演绎因果",
    "composition": {
      "layers": [
        {"role": "midground", "content": "海温视频（素材证据）", "purpose": "提供真实数据语境"},
        {"role": "foreground", "content": "锚点词「一两度」", "purpose": "注意力焦点"}
      ]
    },
    "shot_language": "固定机位观察（视频自身运动承载过程）",
    "temporal_behavior": {"stages": [
      {"name": "enter", "action": "海温视频淡入", "purpose": "先建立语境"},
      {"name": "hold", "action": "锚点「一两度」出现并停留", "purpose": "焦点落在数字上"}
    ]},
    "relation_to_previous": {"type": "handoff", "explain": "上一镜焦点「温度」在本镜同一位置转化为数字「一两度」"},
    "relation_to_next": {"type": "escalation", "explain": "本镜后果「发烧」将放大为下一镜的白化画面"},
    "graphic_layer": {"text": "一两度", "purpose": "数字焦点，字幕已给全文"},
    "motion": {"necessity": "删掉「发烧」放大进入，观众将失去因果落差的体验", "intent": "attention_shift", "describe": "仅锚点词由小变大一次"},
    "audio_relationship": "静默强调（数字句，VO 是主角）",
    "director_note": "让观众用眼睛经历小原因到大后果：先看见微不足道的数字，再被后果的体量压倒。"
  }]
}
```

字段约束（硬）：
- `attention_target`：必须是 beat_text 子串，或白名单素材视觉描述中的对象词；
- `graphic_layer.text`：≤12 字，必须来自 beat_text（禁止整句、禁止新事实）；
- `visual_metaphor`：必须引用原文词；无素材 beat 必须有 `temporal_behavior.stages ≥1`；
- `motion.necessity`：非空（"删掉它观众损失什么"）；`motion.intent ∈ {attention_shift, process_expression, revelation, none}`；
- 所有文本字段禁止出现模板/枚举名（见 §5 S2 反模板规则）；
- `relation_*.type ∈ {continuation, contrast, escalation, release, handoff, none}`，`none` 必须写清"为什么不强造关系"。

---

## 4. LLM 输入/输出完整协议

### 4.1 输入（sanitized context，同 P1 安全口径）
- 全片：风格契约（v3 版：色罩/字体/字量上限/克制声明）、叙事弧摘要（pacing 曲线 + climax_shot + 上一镜焦点交接提示）、能力清单（§7，LLM 只能要求可执行行为）；
- 每镜：口播原文、shot_role、白名单候选（material_id/content_type/语义分/画面描述，无 URL）、上一镜 statement 摘要（焦点坐标+关系类型）。

### 4.2 两阶段调用（沿用 P1 节奏，耗时 ≈6–8 分钟）
- **调用 A（全片）**：attention flow 规划——每镜一句话"焦点是什么、与上一镜什么关系"（climax_shot 标注 + pacing 说明）；输出 ≤800 tokens；
- **调用 B（逐镜 20 次）**：完整 statement（§3 schema），json_schema 约束，失败重试 ≤2 → 规则回退（回退输出同构 statement，标记 `RULE_FALLBACK`）。

### 4.3 铁律（system prompt 内明示 + Validator 兜底）
1. 你的第一职责是回答"观众第一眼看什么、为什么"，不是选择模板；
2. 画面不重复字幕：图形层只放锚点词/数字（≤12 字）；
3. 证据必须 grounded（素材白名单/原文数字）；禁止发明事实；
4. 运动默认静止；要运动必须写"删掉它观众损失什么"；
5. 禁止在文本中使用模板名作为理由；禁止输出你无法要求执行的行为；
6. 每镜必须声明与上一镜的注意力关系（或明确写出"本镜独立"的理由）。

---

## 5. Validator 规则（四层，v3-mvp）

- **S1 schema**：jsonschema + 枚举校验（同 P1 框架）；
- **S2 结构/语义**（新增重点）：
  - beat 文本逐字覆盖（split_n 落地，沿用）；
  - `attention_target ∈ beat_text ∪ 白名单对象词`；
  - `graphic_layer.text ⊆ beat_text 且 ≤12 字`；**graphic 文本长度 == 整句长度 → REJECT（全文复制）**；
  - 无素材 beat 必须有 ≥1 时序阶段；
  - `motion.necessity` 非空且长度 ≥8 字；
  - 每层有独立 purpose（层职责去重）；
  - **反模板规则**：所有 statement 文本字段若包含 `DATA_GRAPHIC/SAFE_IMAGE/TEXT_CARD/FULL_BLEED/SPLIT_H/TYPO…` 等模板/枚举名 → REJECT（这是"高级模板系统"回归的直接拦截）；
  - 关系类型枚举 + explain 非空；
- **S3 安全/Truth**（P1 全保留）：白名单/rights/threshold/sem≥50/素材一致、数字⊆原文、稿文未改、不重检索；
- **S4 完整性（Executor 可表达性）**：statement 要求的行为全部 ∈ §7 能力清单（幻觉计划 → REJECT）；层数 ≤3；
- 结论：PASS / PASS_WITH_REPAIRS（junk ≤5%，修复留痕）/ REJECTED（拒绝→按镜重试→回退，同 P1 机制）。

---

## 6. 整数帧运动算法设计（motion.py，核心新组件）

### 6.1 原则
`natural > meaningful > smooth > restrained`；HOLD=绝对静止；**禁止 zoompan / 正弦 / 亚像素浮点轨迹**；jitter=0 为硬 Gate。

### 6.2 轨迹模型
- 每条轨迹 = 帧序列 `[t_0..t_N]`，每帧一个**整数**裁剪矩形 `(x, y, w, h)`（源图 ≥1920×1080，目标 1920×1080）；
- 运动区间两端各 ≥0.3s **静止帧**（head/tail static），中途允许停顿（hold 段）；
- 三种缓动阶段（加速 20% / 匀速 60% / 减速 20%），**用整数分配而非浮点**：
  1. 总位移 D（整数 px）或总缩放差 Δz（整数 px 计）；
  2. 用 **Bresenham 误差扩散**把 D 分配到每帧 → 每帧增量 ∈ {0,1,…} 且**单调不减**（保证无 0↔1 交替、无方向反转）；
  3. 缩放同理：目标尺寸差按帧整数分配，每帧 (w,h) 单调变化，crop 原点随缩放中心整数对齐；
- 幅度门槛：运动总幅度 ≥ 可感知下限（平移 ≥ 源宽 2%；缩放 ≥ 4%），**低于下限的运动一律删除（改为 HOLD）**；
- HOLD：同一矩形重复全部帧（逐帧像素差恒为 0）。

### 6.3 渲染管线
- PIL 按帧整数裁剪 + LANCZOS 缩放 → RGB 帧流 → ffmpeg `-f rawvideo -pix_fmt rgb24 -framerate 25 -i pipe:` 编码（libx264 yuv420p，规格同 3.2b）；
- 分层画面：每层先按层内轨迹渲染帧，再 PIL 逐帧合成（透明度/遮罩均为整数 0–255，逐帧插值单调）；
- 性能预估：25fps×5s=125 帧/beat，PIL 合成 ≈15–30ms/帧 → 每 beat ≈2–4s，全片 25 beats ≈1–2 分钟（CPU 可行）。

### 6.4 jitter=0 Gate 实现
- 渲染后逐 beat 全 25fps 灰度帧差审计（复用失败诊断方法）：
  - HOLD/无运动段：帧差必须**全 0**；
  - 运动段：帧差序列必须**单调平稳**（无 0↔N 交替、无尖峰、无方向反转）；
  - 违规 → Gate FAIL，STOP（不回退阈值）。

---

## 7. Executor 能力边界（Director Expressiveness Contract，v3-mvp 版）

**可执行（LLM 可要求）**：静止构图；整数帧平移；整数帧缩放（推近/拉远）；分层合成（≤3 层：素材图/色块/锚点词/简单图形）；几何遮罩（矩形/圆角/圆形）；时序显隐（进入/停留/揭示/退出，帧级整数透明度）；强调/高亮（字号/颜色/描边/明度对比）；对比关系（左右/大小并置）；数字/关键词的有限动态呈现（进入/点亮/淡出各一次）。

**不可执行（v3-mvp；Validator 直接 REJECT）**：任意路径动画；物体分割/语义抠像；视频内容理解驱动裁剪；生成式画面/风格重绘；音频合成；复杂转场。

---

## 8. 3.2b / 3.3 边界（不变）

- 3.2b 零修改（v3 同 P1：产出 3.2b 兼容工件 → import 调用 `render.build_final`/`qc.run_qc`）；
- v3 输出目录 `output/stage33/coral/v3/`（P1 产物原样保留为 B 基线）；VO segments、subtitles.ass、alignment/vo/subtitle/blocked manifests 全部复用只读；
- legacy 字节级回归已由 M3 证明且 3.2b 无改动，本轮不再重跑；A/B 两版直接使用既有冻结副本（`legacy_3.2b.mp4`、`stage33_p1_m4.mp4`）。

---

## 9. A/B/C 对照方案

| 版 | 来源 | 路径 |
|---|---|---|
| A = 3.2b legacy | 既有冻结副本 | `output/stage33/coral/legacy_3.2b.mp4` |
| B = P1 | 既有冻结副本 | `output/stage33/coral/stage33_p1_m4.mp4` |
| C = V3-MVP | 新渲染 | `output/stage33/coral/stage33_p1_v3.mp4` |

三者：同冻结稿、同 VO（同音轨字节）、同字幕、同 20 镜、同总时长（≈102.2s）、同 1080p25/aac48k、同响度链——唯一变量=视觉表达。对照材料：`docs/STAGE33_V3_MVP_VISUAL_REVIEW.md`（C 版逐镜 statement↔画面表 + 12 项失败模式检查 + 8 维评分表 + A/B/C 三档裁决栏）。

---

## 10. Coral 20 镜逐镜验证方式

每镜机器验证项（v3-gate 自动输出表）：
1. statement 七问完整性（intent/target/path/evidence/metaphor/motion.necessity/note 非空）；
2. attention_target 存在于渲染画面元素（锚点词帧内检测：该词文本像素存在）；
3. evidence grounded（素材 SHA 链 / 数字⊆原文）；
4. 层职责非空且 ≤3；graphic 字量 ≤12 且 ≠ 整句；
5. 时序阶段已渲染（帧序列存在 enter/hold/exit 变化）；
6. 运动轨迹：HOLD 帧差全 0 / 运动段单调整数（§6.4）；
7. 关系声明与上一镜焦点坐标重叠度（handoff 检查）；
8. 技术 QC 13 项（复用 3.2b qc 于 v3 输出目录）。

重点镜（人工重点看）：S01（开场锚点）、S06（数字→后果的因果演绎）、S08（1% vs 25% 体量对比）、S10（动作相位）、S13–S16（无素材连续段的反退化）、S18（高潮落差）、S20（收束+呼应）。

---

## 11. 新 Gate 清单（v3-mvp）

| Gate | 内容 | 失败动作 |
|---|---|---|
| G1 | statement schema + 结构/语义校验（§5 S1/S2） | STOP 报告 |
| G2 | 反模板规则（LLM 文本无模板名；图形无全文复制） | REJECT→重试→回退 |
| G3 | 安全层（P1 全部：白名单/rights/阈值/数字/稿文） | STOP 报告 |
| G4 | Executor 可表达性（无幻觉计划） | REJECT |
| G5 | **jitter=0**（25fps 全片帧差审计：静止=0、运动=单调整数） | **STOP，不回退阈值** |
| G6 | 渲染 + 技术 QC 13 项（3.2b qc 复用） | STOP 报告 |
| G7 | 无黑帧/冻结/字幕碰撞；statement 完整性；attention_target 存在 | STOP 报告 |
| G8 | A/B/C 三件 + 对照文档齐备 | STOP 缺件 |
| GH | **人工观看三档裁决（唯一视觉质量 Gate，机器不代判）** | 等待人工 |

**数量型指标（motion 种类数/graphic 数/TEXT_CARD 占比）一律不作为 Gate。**

---

## 12. 回滚方案

- 实现前：快照 `stage33/**/*.py`、`scripts/run_stage33.py`、`tests/stage33_*` 到 `output/stage33/_v3_pre_snapshot/`（SHA 记录）；
- 回滚触发：任一 Gate FAIL 且裁决停止 v3 / 自我检查发现"高级模板系统"回归 → 从快照恢复源码；P1 产物目录从未被写，天然完好；
- 3.2b/3.1.4/2.x 无改动 → 无需回滚。

---

## 13. 实施顺序（获授权后）

1. 快照 → schemas/director/fallback 重写 + 单测（statement 协议）；
2. motion.py + graphics.py + realizer.py + executor.py 重写 + 运动/抖动单测；
3. validator S2/S4 + visual_qc 更新 + 全套测试；
4. `plan-v3`：生成 v3 statement plan（LLM，≈6–8 分钟）→ G1–G4；
5. `execute-v3`：渲染 C 版 → G5–G7；
6. `compare`：A/B/C 对照材料 → G8；
7. **STOP → 人工观看 → 三档裁决**。

---

## 14. 本轮停止线

- 本轮仅本计划文档；零代码、零渲染、零产物改动；
- 待授权：① 本实施计划是否批准；② 批准后从第 1 步（快照）开始执行 V3-MVP；
- **如果 V3-MVP 人工裁决仍"不明显优于 P1"：按裁决停止堆模板/规则，转而判断是否已触及"素材供给/视觉理解/生成能力"天花板（见压力测试 §10 结论）。**
