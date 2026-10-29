# EXP-5G 步骤 F 前置评估结果（v2 三项目 · 2026-09-19）

## 评估矩阵（v2 真值集 32 例 = v1 14 + p_ab2b 12 + p_8f05 6）

| 项目 | 用例 | 层评估结果 | 违例 | 判读 |
|---|---|---|---|---|
| p_f4b466a4a024（v1） | 14 | **14/14 OK** | **0** | v1 零回归：与 5-F 冻结一致（judge 14 行 final=MATCH4/MISMATCH3/UNKNOWN6 与 5-F 完全相同） |
| p_ab2b352e06b8（多镜头 12 段） | 12 | 10 OK + 2 VIOLATION | 8 | 2 处真实"层-人分歧"：S06/S12 人工判域内 MATCH（拆解画面/收尾元旁白），5-A/5-D 判 MISMATCH（实例粒度漂移：该成片 12 段复用同 3 张静帧，旁白却覆盖不同设备）——**如实披露为发现，不调参** |
| p_8f054c227bd4（纯色底 6 段） | 6 | 6 UNRESOLVED | 12 | 层对该项目无法取证（无素材时间轴→MM_NO_FRAMES/MMT_NO_FRAMES）→ **fail-closed 正确**：零 MATCH/MISMATCH 误判，符合 expect allow [UNKNOWN] 语义 |

## 判读

1. **v1 零回归成立**（judge 14 行与 5-F 完全一致 + quality 14/14 OK + 0 违例）。
2. **v2 新覆盖的价值实证**：p_ab2b 的 2 处 VIOLATION 是 5-A/5-D 在"12 段复用 3 张静帧"项目上的实例粒度漂移检出——人工域级标注认为可用，层在实例级反对；两者都是有效结论，分歧如实入档交人工。
3. **纯色底 fail-closed 实证**：p_8f05 6 拍零视觉证据，层全部拒绝发证（UNRESOLVED），零误判——G10/5-F 的 fail-closed 语义在 v2 数据类上成立。
4. 运动素材 = 0（全库 LIMITATION，如前）。

## 待电池完成后核验

- 电池 25/25 rc=0（mm_quality.py 改动后）
- 套件 46/46、DRIFT 0
- evidence ALL_GREEN（5-F v1 路径）
- 5-G 报告/KNOWN_ISSUES/基线 5.x-phase5g-baseline
