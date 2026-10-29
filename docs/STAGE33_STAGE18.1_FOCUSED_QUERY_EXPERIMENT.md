# Stage 18.1:单主体 Visual Focus + 新 Query 重检索实验报告(Top-10)

> 唯一改变的环节:检索 Query/Intent(授权内)。其余全部为冻结生产链原样调用(`two_pass_material.acquire_beat_material`:frozen retrieval → pool_precision → Gate head-6 → V1 → CV-2 top-3 → eligibility;pass-1 空 则 pass-2 pexels 配额片)。同一素材源(commons+pexels),零新源,零冻结模块改动,零阈值放宽。VerdictCache = 1226 存量副本 + 新判定(重复标题判定稳定)。intent 一次性冻结,`vf` 与 Stage 18 设计件逐字段校验一致。

## 1. 逐拍 A/B(旧 Intent/Query vs 新 Intent/Query)

| Beat | 旧 Query(复合) | 新 Query(单主体) | 池/进Gate | 旧素材(fit) | 新最佳(fit / rel) | 旧级 | SWAP? |
|---|---|---|---|---|---|---|---|
| S12-B02 | 城市广场+迷茫眼神特写+天平契约 | `construction worker portrait` 等 | 6/✅ | Empty plaza(0.35) | **Westmoreland 纪实工人肖像(0.72 / HIGH)** | MISMATCH | ✅ **SWAP** |
| S30-B01 | 未来工厂人机协作+字幕数据 | `robotic arm factory worker` 等 | 6/✅ | Tesla megacasting(0.50) | **Robot arm operates machine(0.70 / HIGH)** | MISMATCH | ✅ **SWAP** |
| S02-B01 | 未来城市全景+职业情感抉择 | `pedestrian crossing city intersection` 等 | 6/✅ | Strand crossing(0.60) | **Zamboanga 十字路口实景(0.72 / HIGH)** | GENERIC | ✅ **SWAP** |
| S24-B01 | 光芒地平线+自动化港口 | `city skyline sunrise` 等 | 6/✅ | HCMC(0.55) | Milwaukee 天际线(**0.95 USABLE / HIGH**)但已被相邻 S23-B01 使用 → 复用规则拦截,无其他合格候选 | MISMATCH | ⛔ KEEP(复用规则) |
| S33-B02 ⚠️ | 互动屏教室+圆桌讨论 | `students raising hands classroom` 等 | 6/✅ | Classroom Activities(0.40) | 同素材(0.40 / HIGH,查询回收到同候选) | MISMATCH | KEEP |
| S13-B02 | 思考特写+抽象符号 | `community meeting people discussing` 等 | 6/✅ | Camp Foster(0.60) | **Garner Complex 社区会议实景(0.90 USABLE / HIGH)** | GENERIC | ✅ **SWAP** |
| S34-B01 | 发光AGI形象+并肩站立 | `human robot collaboration` 等 | 6/✅ | 花朵隐喻图(0.70) | **实验服女子与机械臂互动(0.75 / HIGH)** | MISMATCH | ✅ **SWAP** |
| S29-B02 | 全息课堂+人机互动 | `students tablet classroom` 等 | 6/✅ | Abi Hanifa(0.55) | Minister Distributes Tablets(0.40 / MEDIUM,动作错位:交接≠课堂使用) | GENERIC | KEEP |
| S08-B03 | 谈判桌+天平图标 | `control room operator monitors` 等 | 4/✅ | Toronto TV 控制室(0.60) | **CERN 控制室多屏监控(0.95 USABLE / HIGH)** | MISMATCH | ✅ **SWAP** |
| S16-B01 | 全球资源网络被接管 | `traffic control room operator` 等 | 6/✅(全部缓存命中,零新候选) | Traffic control map(0.50) | 同素材(0.50 / MEDIUM) | MISMATCH | KEEP |

## 2. 门槛核对

| 门槛 | 要求 | 实测 | 结果 |
|---|---|---|---|
| 严格优于 | ≥7/10 | **6/10** | ❌ |
| HIGH | ≥3/10 | **6**(全部 SWAP 均 HIGH) | ✅ |
| 明显退化 | 0 | **0** | ✅ |
| correspondence | 不降 | 不变(56/309.26s/60.86%) | ✅ |
| reuse | 不增 | multi_use 27→27,相邻同素材 0→0 | ✅ |
| 工程 | 无回归 | 未渲染(FAIL) | n/a |

**→ `STAGE18.1 = FAIL · STOP`**(6/10 < 7/10,差 1 拍),不渲染、不扩大。

## 3. 失败归因:检索失败 vs Intent 失败

**Intent 失败:0 例。** 新单主体 intent+query 凡是检索到**新的合格候选**,6/6 全部严格优于原素材且 relevance 全 HIGH(S12/S30/S02/S13/S34/S08)。解耦假设在可测范围内**完全成立**:命中率 100%,平均 fit 提升 +0.23(0.72/0.70/0.72/0.90/0.75/0.95 vs 0.35/0.50/0.60/0.60/0.70/0.60)。

**检索失败:4 例(全部非 Intent 原因):**
1. **S24-B01(差 1 拍的直接原因)**:检索成功命中 0.95 USABLE 的真实天际线,但该素材已被相邻 S23-B01 使用 → "禁止连续 beat 同素材"硬规则拦截;cv2_rows 内无其他合格备选(仅 1 候选进 CV-2)。属**池薄+碰撞**,非 Intent 问题;
2. **S33-B02**:单主体查询回收到同一泛用课堂图(0.4=旧);真证据候选(Gaza)仍被质量链拒绝;
3. **S29-B02**:查询命中主体(平板/学生)但动作错位(交接仪式≠课堂使用),0.4<0.55——查询的动作精度不足;
4. **S16-B01**:新查询空间塌缩到与旧查询相同的候选集(全部缓存命中,0 个新候选)。

## 4. 诚实证限与下一步边界

- 复用规则与 PASS 门槛存在一次**政策性碰撞**:S24-B01 若允许"同素材二次使用"(语义相近的天际线镜头)即可 7/10 通过——但硬规则(禁止相邻复用)优先级更高,按规则执行;
- 6 处 SWAP(全部通过冻结 Gate→V1→CV2,rel=HIGH,reuse 无冲突)**已留档**;若未来授权"多查询变体检索/增加 CV-2 判定席位"(仍是同源、同冻结链),S24-B01 类碰撞可解,Top-10 有望 ≥7/10;
- 本轮零渲染、零生产链改动;correspondence 60.86% 口径与成片维持不变。

```
STAGE18.1 = FAIL · STOP
严格优于 6/10(<7,差 1 拍) · HIGH 6/6 SWAP 全 HIGH · 退化 0 · reuse 27→27 相邻 0 · correspondence 不变
归因:Intent 失败 0 例(新合格候选 6/6 全部改善,均 HIGH);检索失败 4 例(S24-B01 复用碰撞 / S33-B02 查询回收同质 / S29-B02 动作错位 / S16-B01 查询塌缩)
6 处 SWAP 留档备查,不渲染
STOP——等待下一步授权
```
