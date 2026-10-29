# Stage 12.14:多源素材供给验证报告

> **`STAGE12.14 = PASS(验证完成)· 结论:SOURCE_NOT_USEFUL · STOP`**
> 受控小规模验证:11 个代表性失败拍 × 双臂(A=Commons 基线 / B=Commons+NASA),同一冻结 Gate→V1→CV-2,同一 Candidate Contract。零冻结组件改动。
> 数据:`stage12_14_second_source/results_1214.json`(11 拍双臂全 trace)。

## 1. 第二源选型(诚实过程)

| 候选源 | 结果 |
|---|---|
| Openverse(首选,无 key CC 聚合) | **本网络不可达**(超时×3) |
| LOC / archive.org | 不可达(403 / 超时) |
| Pexels/Pixabay/Unsplash/Smithsonian | 需 API key(.env 无);Tavily 图片结果无许可控制,不合法 |
| **NASA Image Library(选定)** | **可达(2.3s)、公有领域(NASA 媒体政策)、稳定 JSON、无需 key**;域:真实机器人/任务控制室/服务器/地球夜景/工业装配 |

## 2. 验证设计

- 样本(11 拍,授权要求的全部三类代表失败 + 回归金丝雀):
  Hook/AI 家庭场景 S01-B01/B02/B03、S31-B01/B02;Commons 噪声但有候选 S03-B01、S05-B01;候选存在但 Gate/CV-2 空 S24-B01、S29-B02;金丝雀(12.13 ok)S14-B01、S23-B01;
- 两臂均用 12.13 已存 refined-T1/T2/T3(不重写、不改 pool_precision 核心逻辑);NASA 适配器(`stage33/nasa_source.py`)输出与 Commons 完全同 contract 的候选(title/thumburl/url/tier=second_source + src{nasa_id,center,date_created,license,description}),经**同一** pool_precision 重排(原样复用)与**同一** gate 前 6 → V1 → CV-2 top-1;
- provenance 全留痕(src 块逐候选保存,license=Public domain 记录在案)。

## 3. 对照结果(11 拍)

| 指标 | Arm A(基线) | Arm B(+NASA) |
|---|---|---|
| NASA 候选注入总量 | — | 25(6 拍为 0,最多 +12) |
| **NASA 候选进入 Gate 前 6** | — | **0 / 11 拍** |
| 最终素材(ok) | 4 拍 | **4 拍(完全相同,S31-B01/S24-B01/S14-B01/S23-B01)** |
| empty→ok 翻盘 | — | **0 拍** |
| Gate KEEP 总数 | 26 | 27 |
| CV-2 fit(ok 拍) | 0.4/0.55/0.55/0.72 | 0.4/0.55/0.55/0.72(同拍同值或同层) |
| 金丝雀回归 | — | **无**(两拍双臂均 ok) |

## 4. 为什么无效(归因,不是调参建议)

1. **素材域错配(根本原因)**:NASA 库 = 航天/航空/地球科学;本片缺失的视觉域 = 家庭清晨内景(hook)、现代街道/教室/办公室。叙事锚定的检索词("smart speaker bedroom"、"business meeting screen charts")在 NASA 返回 0-3 条,与 Commons 缺口**不重叠**;
2. **统一 contract + 统一池排序下,NASA 标题与 tier 查询词几乎零词重叠** → pool_precision(未改动)永远不把它排进前 6,只沉淀池尾——这不是排序 bug,而是"同查询语义"的正确结果;
3. 方法论备注:同池双臂出现 1 例 gate 判定漂移(S01-B01 A=cv2_not_usable / B=gate_rejected_all)→ gate LLM 存在 run 级方差,单拍 A/B 差异需谨慎解读(本阶段 ok 集完全一致,结论不受影响)。

## 5. 判定

按授权要求 6:第二来源在本视频素材域上**无明显增益**(0 翻盘、0 进前 6、ok 集不变),且验证过程未做任何域翻译/调参以求"证明有效"——

```
结论:SOURCE_NOT_USEFUL(NASA 源在统一 contract 下无增益,不予采用)
STAGE12.14 = PASS(验证本身严格完成、数据充分、无绕过、provenance 完整)
STOP —— 不自动进入下一阶段
```

备注:残余 70 个 HONEST_EMPTY 的主因仍在 **CV-2 层(23 拍)与素材域稀缺(hook 家庭场景,需key 制图库如 Pexels/Pixabay 或域内专用源)**——是否申请 key 制图库授权,留给用户决策;本阶段未实施。
