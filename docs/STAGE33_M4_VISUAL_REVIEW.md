# STAGE33 M4 VISUAL REVIEW（Coral Round 1）

> 唯一变量=视觉表达：两版使用同一冻结稿/VO/字幕语义/20 镜/时长口径/分辨率/响度链。

## 对照件

- 3.3 P1：`output/stage33/coral/stage33_p1_m4.mp4`
- 3.2b legacy：`output/stage33/coral/legacy_3.2b.mp4`
- Visual Plan：`output/stage33/coral/visual_plan.json`（plan_sha=b122f0bda2cac4dd…）

## 机器证据摘要

- beats: 25；motion 渲染确认 22/25；缺 clip: []；黑帧: []
- TEXT_CARD: 3（12.0%；3.2b legacy=45%）
- 视频裸播(SOURCE_NATIVE): 0
- 连续同构图最长: 6；≥3 连段: [('B007', 'FULL_BLEED', 3), ('B008', 'FULL_BLEED', 4), ('B009', 'FULL_BLEED', 5), ('B010', 'FULL_BLEED', 6), ('B015', 'FULL_BLEED', 3)]
- climax_beat=B022（intensity=HIGH，motion=HOLD_MICRO）；开场=SLOW_PUSH_IN；收束=SLOW_PULL_OUT
- motif: ['M-OPENING-CLOSING']

## 逐镜对应（Director 意图 → 实际画面）

| beat | 镜 | 想表达什么（口播/类型） | Director 决策 | 实际画面（机器证据） | 渲染确认 |
|---|---|---|---|---|---|
| B001 | S01 | 在海水下面，…（SPACE_CHANGE） | SELF_CREATED_GRAPHIC·ESTABLISHING·SLOW_PUSH_INDOWN·FULL_BLEED | luma=35.2 std=21.3 白字=0.0087 Δ动=3.2 clip=True | OK |
| B002 | S01 | 有一座正在慢慢褪色的城市。…（DATA/TIME_CHANGE/ACTION） | DATA_GRAPHIC·DATA·SLOW_PUSH_IN·UPPER_TITLE | luma=37.4 std=28.6 白字=0.0156 Δ动=6.3 clip=True | OK |
| B003 | S02 | 珊瑚不是石头，也不是植物，而是千…（DATA） | SELF_CREATED_GRAPHIC·DETAIL·HOLD_MICRO·FULL_BLEED | luma=42.1 std=39.1 白字=0.0231 Δ动=1.63 clip=True | OK |
| B004 | S03 | 潜水员下到十米深的地方，眼前是大…（DATA） | SAFE_IMAGE·DATA·SLOW_PUSH_IN·CENTER_CROP·M-S03-162 | luma=78.0 std=58.9 白字=0.0314 Δ动=36.43 clip=True | OK |
| B005 | S04 | 健康的珊瑚礁是彩色的，鱼群像彩带…（DATA/EMOTION） | SAFE_IMAGE·EVIDENCE·SLOW_PUSH_IN·FULL_BLEED·M-S04-224 | luma=137.3 std=41.1 白字=0.0279 Δ动=23.18 clip=True | OK |
| B006 | S05 | 白化不是死亡，而是珊瑚把体内的藻…（DATA/EMOTION/TRANSITIONAL） | SELF_CREATED_GRAPHIC·DETAIL·SLOW_PUSH_IN·FULL_BLEED | luma=39.3 std=34.9 白字=0.0245 Δ动=8.63 clip=True | OK |
| B007 | S06 | 海水温度只要升高一两度，珊瑚就会…（DATA） | SAFE_VIDEO·DATA·HOLD_MICRO·FULL_BLEED·M-S06-323 | luma=161.0 std=48.0 白字=0.0669 Δ动=24.58 clip=True | 人工看 |
| B008 | S07 | 海洋吸收了大气里多余的二氧化碳，…（EMOTION/DATA） | SAFE_IMAGE·DATA·SLOW_PUSH_IN·FULL_BLEED·M-S07-358 | luma=238.0 std=52.3 白字=0.8907 Δ动=26.02 clip=True | OK |
| B009 | S08 | 珊瑚礁只占海底不到百分之一，却养…（DATA） | SAFE_IMAGE·DATA·SLOW_PUSH_IN·FULL_BLEED·M-S08-407 | luma=207.0 std=49.1 白字=0.6014 Δ动=30.71 clip=True | OK |
| B010 | S09 | 海龟从白化的珊瑚旁游过，像穿过一…（DATA/EMOTION） | SAFE_IMAGE·EMOTIONAL·SLOW_PUSH_IN·FULL_BLEED·M-S09-456 | luma=119.3 std=58.8 白字=0.0633 Δ动=30.69 clip=True | OK |
| B011 | S10 | 科学家用绳子把珊瑚苗绑在架子上，…（ACTION） | TEXT_CARD·SUBJECT·PAN_VUP·CENTER_CROP | luma=38.5 std=32.3 白字=0.0197 Δ动=9.83 clip=True | OK |
| B012 | S10 | 像在水下种树。…（SPACE_CHANGE） | TEXT_CARD·SUBJECT·PAN_VDOWN·THIRDS_LEFT | luma=35.4 std=20.9 白字=0.0074 Δ动=4.65 clip=True | OK |
| B013 | S11 | 珊瑚修复是一场和温度赛跑的接力。…（TRANSITIONAL/EMOTION/DATA） | SAFE_IMAGE·BACKGROUND·SLOW_PUSH_IN·FULL_BLEED·M-S11-552 | luma=88.5 std=44.1 白字=0.0126 Δ动=25.18 clip=True | OK |
| B014 | S12 | 渔民的网掠过水面，海面之下的变化…（TRANSITIONAL/EMOTION/DATA/CONCLUSION） | SAFE_IMAGE·BACKGROUND·SLOW_PUSH_IN·FULL_BLEED·M-S12-607 | luma=109.8 std=41.6 白字=0.0107 Δ动=11.59 clip=True | OK |
| B015 | S13 | 如果珊瑚消失了，很多人的饭碗也会…（DATA） | SELF_CREATED_GRAPHIC·DATA·PAN_V·FULL_BLEED | luma=41.6 std=38.3 白字=0.0228 Δ动=2.07 clip=True | OK |
| B016 | S14 | 小丑鱼躲在海葵里，海葵也在慢慢失…（TRANSITIONAL） | SELF_CREATED_GRAPHIC·DATA·SLOW_PULL_OUT·UPPER_TITLE | luma=41.7 std=38.4 白字=0.0228 Δ动=0.53 clip=True | 人工看 |
| B017 | S15 | 洋流带来营养，…（EMOTION/DATA） | SELF_CREATED_GRAPHIC·CONTEXT·HOLD_MICRO·CENTER_CROP | luma=35.8 std=20.9 白字=0.0043 Δ动=0.33 clip=True | OK |
| B018 | S15 | 也带来越来越热的海水。…（EMOTION/DATA） | SELF_CREATED_GRAPHIC·CONTEXT·HOLD_MICRO·CENTER_CROP | luma=39.4 std=32.8 白字=0.0136 Δ动=1.07 clip=True | OK |
| B019 | S16 | 海洋不是离我们很远的地方，…（CONTRAST） | SELF_CREATED_GRAPHIC·COMPARISON·HOLD_MICRO·SPLIT_H | luma=36.3 std=22.2 白字=0.0042 Δ动=1.09 clip=True | OK |
| B020 | S16 | 它每天都在改变天气。…（TIME_CHANGE/ACTION） | TEXT_CARD·SUBJECT·HOLD_MICRO·THIRDS_LEFT | luma=37.1 std=26.2 白字=0.0104 Δ动=0.58 clip=True | OK |
| B021 | S17 | 有些珊瑚挺过了白化，重新长回了颜…（DATA/DATA/DATA） | SELF_CREATED_GRAPHIC·DATA·HOLD_MICRO·FULL_BLEED | luma=40.5 std=35.7 白字=0.0187 Δ动=1.27 clip=True | OK |
| B022 | S18 | 珊瑚礁的生死，取决于我们接下来十…（EMOTION/DATA） | SELF_CREATED_GRAPHIC·DATA·HOLD_MICRO·CENTER_CROP | luma=41.3 std=37.8 白字=0.0221 Δ动=2.01 clip=True | OK |
| B023 | S19 | 海边的小孩第一次戴上潜水面镜，看…（EMOTION/DATA） | SAFE_IMAGE·TRANSITION·HOLD_MICRO·CENTER_CROP·M-S19-954 | luma=139.1 std=55.9 白字=0.1687 Δ动=5.81 clip=True | 人工看 |
| B024 | S20 | 那是一座会呼吸的城市，…（EMOTION） | SAFE_VIDEO·EMOTIONAL·HOLD_MICRO·UPPER_TITLE·M-S20-1034 | luma=14.9 std=27.0 白字=0.005 Δ动=1.07 clip=True | OK |
| B025 | S20 | 而它正在等待降温。…（DATA/EMOTION） | SELF_CREATED_GRAPHIC·DATA·SLOW_PULL_OUT·FULL_BLEED | luma=37.1 std=27.7 白字=0.0121 Δ动=5.62 clip=True | OK |

## 运动语义审计（motion 是否因为语义而存在）

| beat | 方向 | 口播含语义词 | 口播片段 |
|---|---|---|---|
| B001 | DOWN | True | 在海水下面， |
| B011 | UP | True | 科学家用绳子把珊瑚苗绑在架子上， |
| B012 | DOWN | True | 像在水下种树。 |

## 12 项失败模式检查（机器列 + 人工列）

| 模式 | 机器证据 | 人工裁决 |
|---|---|---|
| 绿幕裸播 | P1 无视频叠字（SAFE_COMPOSITE=0）；green_frac 见 visual_qc.json（检测属 P3） | 人工看视频 beat |
| 图片+文字机械堆叠 | P1 图片无叠字 | 人工看 |
| 视频裸播 | SOURCE_NATIVE=0（0=无裸播） | 人工看 |
| 连续相似构图 | 最长连段 6；≥3 连段 [('B007', 'FULL_BLEED', 3), ('B008', 'FULL_BLEED', 4), ('B009', 'FULL_BLEED', 5), ('B010', 'FULL_BLEED', 6), ('B015', 'FULL_BLEED', 3)] | 人工看 |
| 无意义 PUSH/HOLD | 见 visual_qc.json push_hold_audit（含理由与语义词命中） | 人工逐条判 |
| 文字卡替代可视化 | 违例 beat: []（应空） | 人工看 |
| 数据没图形化 | 违例 beat: ['B003', 'B006', 'B015', 'B017', 'B018', 'B021', 'B022', 'B025'] | 人工看 |
| 因果未可视化 | CAUSE/EFFECT beats: [] | 人工看 |
| 高潮不明显 | climax=B022 intensity=HIGH motion=HOLD_MICRO | 人工看 S18 |
| 开头/结尾无收束 | 开场=SLOW_PUSH_IN；收束=SLOW_PULL_OUT（Validator 归一） | 人工看 |
| 视觉元素无关系 | motif=['M-OPENING-CLOSING']（首尾呼应） | 人工看 |
| 像模板拼接 | 机器无法判 | 人工总评 |

## 人工观看要点

1. 两个 mp4 各看一遍（各 102s）；
2. 逐镜对照上表：Director 的意图是否真的出现在画面里；
3. 重点裁决：motion 是否因语义存在、文字卡是否真的少了、高潮/收束/呼应是否成立；
4. 结论一句话：**3.3 P1 是否让 Coral 肉眼可见地变好了？**

---

## 人工观看优先级（按顺序看，机器指标只是辅助，不构成通过依据）

> 重要声明：TEXT_CARD 45%→12%、18 张图形、2 个视频、motion 22/25、motif、climax、13/13 技术 QC——这些**只能作为辅助证据，不能直接证明 P1 成功**。唯一验收依据：同一 VO、同一字幕、同一内容下，3.3 是否比 legacy 更像一条经过视觉设计的成片。

### A. 最能证明 P1 成功的镜头（先看这些，判断"表达而非模板"）

| 时间点 | 镜头 | 为什么能证明 P1 |
|---|---|---|
| ≈27.3–32.1s | **S06（B007）** | 数据句"升高一两度"从 legacy 的**静态海温图 Ken Burns**，变成**真实海温变化视频 + 稳定构图**——表达随信息类型升级，不是"有图放图" |
| ≈49.0–54.4s | **S10（B011/B012）** | legacy 是一张静态白字卡；3.3 拆成两张卡，且"绑在架子上"配 **PAN_V UP**、"像在水下种树"配 **PAN_V DOWN**——**motion 因为语义而存在**，全片最直接的证据 |
| ≈77.2–80.2s | **S16（B019）** | "不是…而是…"对比句被做成 **SPLIT_H 左右分栏对比排版**——对比被视觉化，而不是白字 |
| ≈97.6–102.2s | **S20（B024/B025）** | 结尾从"城市夜景图 Ken Burns"升级为**城市延时视频 + 收束图形 SLOW_PULL_OUT**，且与开场 B001 同一母题（首尾呼应）——收束成立 |
| ≈32.1–37.5s | **S07（B008）** | legacy 因 primary 45.2 分判了文字卡；3.3 白名单纳入 alternatives 后**用上了真实海洋热含量图**——"素材不足≠自动文字卡"的直接体现 |

### B. 最能暴露 P1 缺陷的镜头（重点挑刺）

| 时间点 | 镜头 | 检查什么 |
|---|---|---|
| ≈27.3–49.0s | **B007–B010 四连 FULL_BLEED**（S06/S07/S08/S09） | 四个素材段全部满屏构图、全部推入——**连续构图单调**是否让中段显得"素材流"？ |
| ≈68.4–73.1s | **S14（B016）** | 有合格的小丑鱼素材（legacy 用的 M-S14-687）却选了排版图形——**"有素材却不用"是否合理？** |
| ≈82.5–86.7s | **S17（B021）** | 同上：有合格彩色珊瑚素材（M-S17-825）却用图形——判断 Director 的取舍对不对 |
| ≈22.2–27.3s | **S05（B006）** | 有健康/白化对比素材（M-S05-276）却用图形——同一个问题第三例 |
| ≈63.6–77.2s | **S13–S15（B015/B017/B018）** | 连续图形段几乎静止（Δ动 0.33–2.07）——是否从"深色文字卡流"变成了"深色图形卡流"？**HOLD/PUSH 占 20/25** 的观感在这里集中体现 |
| ≈86.7–91.6s | **S18（B022，climax）** | 高潮 beat 是**安静的排版图形 + HOLD_MICRO**——"视觉高潮"是否真的成立了，还是只有 intensity 标签？ |
| ≈0–4.4s | **S01（B002）** | 该 beat 被旧版 NUM_RE 误标 DATA（"一座"的"一"）导致数字图形档——开场图形是否因此显得错位？（已修复，但本片为冻结计划） |

### C. 最需要直接与 legacy 对比的镜头（同时间点两版对照）

| 时间点 | 镜头 | legacy 是什么 | 3.3 改成什么 | 人眼应观察的差异 |
|---|---|---|---|---|
| 0–4.4s | S01 | 深青底+白字卡（"在海水下面…"） | 拆 2 beats：建立图形（含 DOWN 方向推入）+ 数字排版图形 | 开场是否从"PPT 卡"变成"有设计的片头" |
| 10.4–16.2s | S03 | TEXT_CARD（cubiclé 拒绝后无素材） | 真实电影剧照 SAFE_IMAGE（M-S03-162，sem 50.0 边际） | 画面信息量提升 vs **边际素材是否语义错配**（本片最该挑刺的素材） |
| 27.3–32.1s | S06 | 静态海温图 + 统一 Ken Burns | 海温变化**视频** + 稳定构图 | 动态信息表达 vs 静态图片的差距 |
| 32.1–37.5s | S07 | TEXT_CARD（48.6 拒绝后无素材） | 海洋热含量图 SAFE_IMAGE | 数据句终于"被看见" |
| 49.0–54.4s | S10 | 静态 TEXT_CARD | 两张卡 + UP/DOWN 语义方向运动 | 同样没有素材，运动语言是否让文字不再死板 |
| 63.6–77.2s | S13/S15/S16 | 三张静态 TEXT_CARD（连续） | 图形（PAN_V）/ 图形 ×2 / SPLIT_H 对比分栏 | 连续无素材段的观感升级幅度是否足够 |
| 86.7–91.6s | S18 | TEXT_CARD（"十年的选择"） | 高潮排版图形 + 稳定构图 | 收束前的高潮是否立得住 |
| 97.6–102.2s | S20 | 城市夜景图 + Ken Burns | 城市延时视频 + 拉远收束 + 母题回收 | 片尾完成度差异 |

---

## 人工评分框架（8 问 × 1–5 分，只评 3.3 版；legacy 可作为基准对照在心里打分）

| # | 维度 | 1 分 | 3 分 | 5 分 |
|---|---|---|---|---|
| 1 | 表达准确性 | 只是"相关"素材/卡 | 大体贴合句子含义 | 画面就是这句话的视觉翻译 |
| 2 | 视觉层级 | 元素堆在一起 | 主次基本可辨 | 主视觉/辅助信息/字幕层级一眼清晰 |
| 3 | 镜头关系 | 随机拼接 | 顺序合理但无关联 | 相邻镜头有视觉/叙事承接与呼应 |
| 4 | 节奏 | 匀速平铺 | 略有快慢 | 变化跟随信息密度与叙事高潮 |
| 5 | 运动合理性 | 为动而动 | 多数可接受 | 每个运动都有语义理由 |
| 6 | 信息可视化 | 数据/因果靠字幕 | 部分图形化 | 数据/对比/因果/变化被真正视觉化 |
| 7 | 风格一致性 | 素材拼贴感 | 局部一致 | 全片像一个导演做出来的 |
| 8 | 完成度 | 工程 Demo 感 | 接近产品 | 像正常"文字成视频/科普视频"产品 |

评分表（观看后填写）：

| 维度 | 分数(1-5) | 一句话证据 |
|---|---|---|
| 1 表达准确性 |  |  |
| 2 视觉层级 |  |  |
| 3 镜头关系 |  |  |
| 4 节奏 |  |  |
| 5 运动合理性 |  |  |
| 6 信息可视化 |  |  |
| 7 风格一致性 |  |  |
| 8 完成度 |  |  |
| 合计 /40 |  |  |

---

## 最终裁决（二选一，必须附证据镜头）

**P1-VISUAL = CLEARLY_BETTER**（肉眼能明显感知升级）
/ **BETTER_BUT_NOT_ENOUGH**（有明显进步，但仍存在模板化/粗糙/表达不足）
/ **NOT_MEANINGFULLY_BETTER**（技术指标改善，但观看体验没有实质改善）

- 裁决：______________
- 证据镜头（逐条写，正反各列）：______________

> 由人工观看后填写；机器不代判、不预填、不暗示。
