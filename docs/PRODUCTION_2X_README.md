# AI Video Agent 2.x — 生产文档（Production README）

> STATUS = PRODUCTION READY ｜ 版本 2.0.0 ｜ 链版本 `2x-final-8q`
> 本系统只产出可审核的 Production Plan / Scene Blueprint（含成本/平衡/素材标注），
> **不生成视频、不配音、不剪辑、不发布**——这些能力明确不在 2.x 范围（见 §9）。

## 1. 如何启动生产

```powershell
cd video-studio
python bin/produce_2x.py <输入.json> [-o 输出目录]
```

或模块方式：

```powershell
python -m video_studio.production2x <输入.json> [-o 输出目录]
```

- 无需 API 密钥、无需联网（evidence 由输入提供，本入口不做检索）。
- 依赖：Python 3.13 + `requests`（`pip install requests`，仅被检索模块引用，生产链本身不发起网络请求）。
- 退出码：`0` = OK；`1` = FAIL_INPUT / FAIL_INTERNAL（错误原因打印到 stdout 并写入日志）。

## 2. 输入格式（input.json）

```json
{
  "video": {
    "title": "视频标题",
    "claims": [
      {
        "claim_text": "2023年，科学家完成了成年果蝇的全脑连接组——十四万个神经元……",
        "evidence": [
          {"url": "https://news.cn/a", "title": "果蝇连接组", "snippet": "……",
           "body": "已提取的正文文本（证据正文；为空时自动退化为 title+snippet）"}
        ]
      }
    ]
  },
  "style": "casual",
  "platforms": ["bilibili", "youtube", "shipinhao", "gongzhonghao"],
  "target_seconds": 600
}
```

| 字段 | 必填 | 说明 |
|---|---|---|
| video.title | 否 | 视频标题 |
| video.claims | **是** | 至少 1 条；每条至少 1 条 evidence（url/title/snippet/body） |
| style | 否 | `academic` / `casual` / `sharp` / `gentle`，默认 casual |
| platforms | 否 | 四平台子集，默认全部四个 |
| target_seconds | 否 | 目标总时长（秒）；作用于参考平台 B站（6s/镜），10 分钟级=600、15 分钟级=900 |

## 3. 参数说明

- **style**：频道风格档案（严谨学术/轻松科普/犀利锐评/温和启发），只改表达不改证据。
- **platforms**：视频号 1.5s/镜、B站 6s/镜、YouTube 8s/镜、公众号图文（无镜头时长）。
- **target_seconds**：仅当给定且平台为 bilibili 时做密度加权时长分配；其余平台使用各自节奏。
- 生产链**全确定性**：同输入 → 同输出（输入指纹 `input_fingerprint` 可复核）。

## 4. 输出目录结构（-o 指定，默认为当前目录）

```
<输出目录>/
├── final_production_plan.json   # 完整生产包（见 §5）
├── plan_bilibili.txt            # 平台可读 Production Plan（文本）
├── plan_youtube.txt
├── plan_shipinhao.txt
├── plan_gongzhonghao.txt
└── production.log               # 运行日志（阶段日志 + 状态）
```

## 5. 每个输出文件含义

**final_production_plan.json** 关键字段：

| 字段 | 含义 |
|---|---|
| status | OK / FAIL_INPUT / FAIL_INTERNAL |
| production_version / chain_version | 2.0.0 / 2x-final-8q |
| input_fingerprint | 输入 SHA256 前 16 位（回放/审计） |
| references | 全局证据引用表 [1..N]（url/title/source_tier） |
| total_scenes / total_duration | 每平台场景数与总时长 |
| calibrated_cost | 三标准校准成本（个人/小团队/专业媒体，内容分钟 × 生命周期） |
| balance | claim 覆盖 / 数据表达覆盖 / 密度（自适应带） |
| material | 素材 difficulty / fallback / 证据零漂移 |
| plans.<平台>.plan.scenes | **最终 Scene Blueprint**：scene_id/脚本/画面/B-roll/字幕重点/证据引用/源段落/时长 |
| plans.<平台>.calibrated.scenes | 校准后场景（成本/复杂度/难度/fallback/fact 拆分） |

**plan_*.txt**：人类可读的 Production Plan（含【场景】【情绪】【证据引用】【参考来源】与"未自动生成视频"声明）。

## 6. 如何检查 Evidence / Truth

1. **引用表**：`references` 必须等于输入 evidence 的 URL 去重集（多一/少一即异常）。
2. **行内引用**：场景文本中 `[n]` 与 `fact_refs.ref_index` 必须 ∈ [1, len(references)]。
3. **Truth 不漂移**：每条 claim 的子命题原文（按 。；？！切分）必须逐字出现在场景文本并集中；
   "存疑/待补"段落列出未覆盖元素（`gaps`），提示"切勿凭空断言"。
4. **覆盖**：`balance.claim_covered` 的数字/实体计数应为 N/N。

## 7. 如何判断生产成功

- `status == "OK"`；
- 退出码 0；
- 四平台 `plan_*.txt` 全部生成；
- `total_duration.bilibili` 在 `target_seconds ±10%` 内（给了 target 时）；
- 每 scene 含 `visual_target` / `subtitle_emphasis` / `duration_hint` / `source_paragraphs`；
- `material.zero_drift == true` 且 `hard_ratio ≤ 15%`。

## 8. 常见失败及处理方式

| 现象 | 原因 | 处理 |
|---|---|---|
| FAIL_INPUT: claims 为空 | 输入无 claims | 补 claims |
| FAIL_INPUT: evidence 为空 | 某 claim 无证据 | 补证据（url/title/snippet/body） |
| FAIL_INPUT: style/platform 非法 | 拼写错误 | 使用 §2 合法值 |
| FAIL_INTERNAL: KeyError/TypeError | 输入结构不合规 | 对照 §2 检查 JSON 结构 |
| 中+困难素材占比 > 45%（WARN） | 数据可视化场景多（属"中"素材） | 软约束，仅提示，不阻断 |

## 9. 当前 2.x 明确不支持的能力

- 自动视频生成 / 自动配音（TTS）/ 自动剪辑 / 自动发布（入口输出仅到 Scene Blueprint）。
- 在线检索与证据抓取（生产链消费输入 evidence；检索属研究侧 8D/8E 资产）。
- 素材库 / 许可素材接入。
- 专业媒体流水线成本建模（efficiency factor，见 3.x Registry）。
- 极端超密内容（6+ 年份多源引用）的密度细粒度加权。

## 10. 3.x Enhancement Registry（登记保留，2.x 不实现）

1. 专业媒体效率因子 + 资产/并行工作流建模。
2. 密度细粒度加权（实体/数字/事实项分权）+ 跨 scene 重复去重。
3. 素材库/许可素材接入。
4. 平台级细粒度节奏/密度适配。
5. 昂贵变体（概念动画）成本优化。
6. 多 Agent 并行制作。
7. 极端内容（多时间线超密）专项适配。

## 附：生产/实验边界

- **PRODUCTION**：仅 `src/video_studio/production2x/`（入口）+ `src/video_studio/tools/`（2.x 冻结链）。
  不读取 `projects/_drafts/`、不读取实验缓存、不使用测试 claim、不执行任何 `scripts/eval_*` / `scripts/_dbg_*`。
- **EXPERIMENT / DIAGNOSTIC**：`scripts/`（eval/构建/标注/调试脚本）与 `projects/_drafts/`（阶段产物），
  仅供研究与回放，与生产入口物理隔离，不得作为生产输入/输出。
