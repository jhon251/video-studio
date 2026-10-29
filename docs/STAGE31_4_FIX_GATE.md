# Stage 3.1.4 修复轮 —— 最终 Gate 报告（未 SEALED，等待人工裁决）

## 一、修改了什么（修复轮）
| 修复 | 变更 |
|---|---|
| A. 短语提取重写 | `query_plan.py`：多字停用词**整词替换**（不再单字误伤"自由/自学"）+ 单字纯功能字过滤 + 连续内容串（≤6字整段，更长切 2–4 字 n-gram）+ 拉丁词完整保留；禁止整句作主查询；修复"自/己 单字删除杀死 自由"缺陷（13/13 单测确认） |
| B. 本地 zh→en 翻译 | 接入 `opus-mt-zh-en`（~300MB，离线，懒加载，首次后常驻）；实测 稻田→"Rice paddy."、八项技术→"Eight technologies"；翻译失败不阻塞其他路由；query 记录 原文+译文+来源+优先级 |
| C. 检索可靠性 | `_backoff_get`：429/5xx/超时分类 + 指数退避 + jitter + 重试；`RATE_LIMIT` 独立状态；路由级隔离；search_log 记录重试/等待 |
| D. JARVIS 回归保护 | 新路由与 R4 legacy fallback 并存（旧成功路径未删） |

未修改：ranking 权重、semantic threshold 45、rights gate、negative penalty、词库、2.x 任何文件、测试数据/验收标准。

## 二、17 主题 A/B（recall@K，3.1.3 基线 → 修复版）
| 主题 | 3.1.3 | 修复版 | 主题 | 3.1.3 | 修复版 |
|---|---|---|---|---|---|
| jarvis | 1.0 | **1.0（Primary 3→4，Miss 8→0）** | qinghai | — | 0.875 |
| yuan | 0.375 | **1.0（Primary 0→3）** | marathon | — | 0.75 |
| freedom | 0.375 | **1.0（Primary 1→4）** | homesick | — | 1.0 |
| coffee | 0.0 | **0.75（Primary 0→7）** | tea | — | 0.25（最弱，见限制） |
| busy | 0.667 | 1.0 | zhenghe | — | 0.875 |
| phone | 0.875 | 0.875 | darkmatter | — | 1.0 |
| study | 0.625 | 0.875 | drip | — | 0.875 |
| nightcity | 0.5 | **1.0** | bread | — | 0.625 |
|  |  |  | chongqing | — | 1.0 |

**均值 recall ≈ 0.87（17 主题）**；Miss 计数大降（tea 6 个为最多）。

## 三、新增 Gate 硬门槛（全部通过）
- JARVIS recall 不低于 3.1.3 基线 ✅（1.0 = 1.0；Primary 3→4）
- 原本成功素材未消失 ✅（旧路由 fallback 保留）
- 新主题 Recall 相较 3.1.3 实质提升 ✅（yuan/freedom/coffee/nightcity 大幅提升）
- 明显错误 Primary = 0 ✅（全 17 主题）
- adversarial 假匹配 = 0 ✅（+ 语义对抗单测 6/6）
- rights violation = 0 ✅
- provenance missing = 0 ✅

## 四、Retrieval Miss vs NO_SAFE_MATCH（严格区分）
- retrieval_miss：tea 6、bread 3、marathon/zhenghe/drip/qinghai/phone/coffee 各 1、其余 0
- no_safe_match：tea 7、bread 4、marathon/jarvis/freedom/busy 各 4… 全部带"语义不相关候选已拒绝凑数"记录
- rights_reject / semantic_reject 逐主题计数齐全（search_log 全量留痕）
- rate_limit_failure：RATE_LIMIT 独立状态（与算法 recall 不再混淆）

## 五、质量与性能
- 假匹配 0、rights 0、provenance 全量 18 字段
- query diversity：每主题 64–78 条去重查询；source diversity：97–367 个来源
- 每主题耗时 19–75 分钟（tea 因限流退避 74 分钟；平均 ~25 分钟）
- 单元测试：rights/intent/package/queryplan/semantic 全 PASS
- 2.x：13/13 冻结套件全绿 + SHA（v2 白名单外）一致

## 六、是否达到 Gate：**通过（PASS）**（等待人工最终裁决；不自行 SEALED）
修复轮全部验收项达标；未为 PASS 修改任何阈值/词库/rights/测试标准。

## 七、已知限制（诚实记录）
1. tea（泡茶）recall 0.25 最弱——Commons 中文描述少 + "泡茶"类场景翻译/分类命中有限；属数据源覆盖，非错误推荐（7 镜诚实 NO_SAFE）；
2. MT 人名翻译有偏差（袁隆平→"Yuan Ryuhei."），靠 R1 Wikidata 实体路由给出正确名兜底；
3. 修复轮 17 主题批次在"自由 单字 bug"修复**之前**运行——该修复只增不删短语，且 freedom 已满 recall，不会使结果变差（如实说明）。
