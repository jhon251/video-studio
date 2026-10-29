# 3.x Phase 2-C 故障注入报告：素材不足四类真实构造

- 日期：2026-09-13
- 驱动：`python docs/regression_2x/phase2c_fault_matrix.py`
- 原始记录：`logs/phase2c_fault_matrix.log`、`logs/phase2c_fault_matrix.json`

## 构造方式（真实项目，不 mock 素材与渲染）

每个用例都建**真实项目**、用 `run.py ingest` 登记**真实素材文件**、跑**真实 retrieval** 与**真实 ffmpeg 渲染**
（脚本产物由驱动写入，仅避免消耗 LLM 额度；其余全部走生产代码路径）。

| 用例 | 构造 | 素材 |
|---|---|---|
| A_normal | 脚本第 1 段与素材名强匹配、第 2 段完全无关 | 真实图片 `皮肤界面截图_01.jpg` |
| B_no_candidate | 只有与脚本毫无词面交集的素材 | 真实图片 `mountain_view.jpg` |
| C_low_match | 素材名只与脚本共享 1 个字（分数 1 < 阈值 3） | 真实图片 `面.jpg` |
| D_unusable | 素材文件损坏（伪装 `.jpg` 的文本文件） | `皮肤界面截图_损坏.jpg`（无法解码） |

脚本（确定性 2 段）：`S01 皮肤界面截图展示鲸鱼娘皮肤。` / `S02 这一段讲完全无关的内容。`

## 结果

| 用例 | render | 逐镜头分类 | 装配级 | 成片 |
|---|---|---|---|---|
| **A_normal** `p_4aa4468e3f97` | SUCCEEDED | S01 `NONE`→`LOCAL_INGEST`（命中 6）；S02 `NO_CANDIDATE`→`SOLID_COLOR_CARD`（`selected_asset=null`，needs_hitl=true） | NONE（PARTIAL 装配） | 10.000s / 2 流 / decode rc=0；抽帧：S01 命中分配素材、**S02 占位被证实**（不是任何素材） |
| **B_no_candidate** `p_5bac5e31b984` | **BLOCKED**（3 轮：失败→重试→Blocked） | S01/S02 均 `NO_CANDIDATE`→占位 | **ASSEMBLY_BLOCKED** | **无成片**；错误码 `[ASSET_INSUFFICIENT]`，`class_counts={NO_CANDIDATE:2}` |
| **C_low_match** `p_4a41155020ff` | SUCCEEDED | S01 `LOW_MATCH`（**分数 1 < 阈值 3**）→`THEME_FALLBACK`（needs_hitl=true）；S02 `NO_CANDIDATE`→占位 | NONE | 10.000s / 2 流 / decode rc=0；抽帧：**降级素材确实在屏**，且记录明确标注为降级（非正常命中） |
| **D_unusable** `p_240b84a2edef` | **BLOCKED**（3 轮） | S01 `ASSET_UNUSABLE`（`ASSET_DECODE_FAILED: UnidentifiedImageError`）；S02 `NO_CANDIDATE` | **ASSEMBLY_BLOCKED** | **无成片**；损坏素材**从未进入 ffmpeg**；`class_counts={ASSET_UNUSABLE:1, NO_CANDIDATE:1}` |

## 阻断文案（B / D，节选真实文本）

```
[ASSET_INSUFFICIENT] {"assembly_class": "ASSEMBLY_BLOCKED",
 "assembly_reason": "已提供本地素材（material_mode=local_ingest）但 2 个镜头全部无法把真实素材上屏
                     （selected_asset 全为 null），装配无法完成",
 "class_counts": {"NO_CANDIDATE": 2}, "degraded_scenes": ["S01","S02"], "material_mode": "local_ingest",
 "policy": {"min_match_score": 3, "low_match_policy": "theme_fallback",
            "asset_reuse_policy": "prefer_unused", "block_when_all_degraded": true},
 "scenes": [{"scene_id":"S01","insufficiency_class":"NO_CANDIDATE","fallback_state":"SOLID_COLOR_CARD",
             "fallback_reason":"无候选素材命中（关键词交集为空）"}, ...]}
```

D 用例的 `fallback_reason` 保留原始错误码：
`候选素材不可用：ASSET_DECODE_FAILED: UnidentifiedImageError: cannot identify image file '...'`

## 关键点（对照"禁止静默降级"）

1. **低匹配没有被伪装成命中**：C 用例 S01 的 `fallback_state=THEME_FALLBACK`、`fallback_reason` 明写
   `最高素材分=1 < 阈值 3`、`needs_hitl=true`；成片里那张图确实在屏（抽帧证实）——"用了但如实标注"。
2. **占位没有被当作素材驱动**：A 用例 S02 `selected_asset=null`，成片抽帧确认该窗口**不匹配任何素材**
   （`placeholder_verified`），`visual_source`/`fallback_scenes` 一致。
3. **不可用素材没有被送进渲染**：D 用例在**调用 ffmpeg 之前**就因 `ASSET_UNUSABLE` 阻断，无成片产出，
   错误码与文件路径完整保留。
4. **BLOCKED 未被改写**：B/D 的 render 任务终态为 `BLOCKED`，`retry_count=2`（用尽重试），
   项目输出目录**没有新增 mp4**。
5. **阻断项目的追溯不丢**：决策记录在 render 前的 `MATERIAL_TIMELINE` 事件里（既有事件类型，未新增），
   包含逐镜头分类/原因/`needs_hitl`/`allowed_in_final_render`。
