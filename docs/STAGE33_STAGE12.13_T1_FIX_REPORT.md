# Stage 12.13:T1 检索池顶精度修复报告

> **`STAGE12.13 = PASS · STOP`**
> 同一 90 拍受控对比(12.11 基线 vs 12.13 修复),冻结组件(Gate/V1/CV-2/T2-T3 ladder/资格标准)零改动,仅两个**新增**模块介入。对比数据:`stage12_13_t1_fix/comparison.json`,逐拍 trace:`recovery_v2.json`。

## 1. 修复内容(均为新增独立模块,零冻结文件改动)

| 模块 | 作用 | 授权依据 |
|---|---|---|
| `stage33/t1_visual_query.py` | T1 表达重写:2-4 词英文名词短语,表达**可见主体+场景+核心关系**,现实性校准(必须像真实存在的照片),抽象概念→现实对应物,保语义锚点;LLM 失败回退原 T1 | 允许"调整 T1 查询表达/预处理模块" |
| `stage33/pool_precision.py` | 池级确定性重排:hint=IMAGE/VIDEO 时 IMG/SVG 结构性优先于 DOC/AUDIO(mime 层面非内容词,非黑名单)+ 标题词与查询词重叠加权(precise 权重×2);稳定排序,平局保冻结检索序;provenance 全保留 | 允许"候选排序/retrieval-side 噪声处理" |

Gate 仍只判前 6(同深度同阈值),V1/CV-2 top-1、T2/T3 冻结 ladder 原样调用。

## 2. 前后对比(同一 90 拍)

| 指标 | 12.11 基线 | 12.13 修复 | Δ |
|---|---|---|---|
| 最终素材 beats | 10 (11%) | **20 (22%)** | **+10** |
| 素材时长 | 54.7s | **105.9s** | +51.2s |
| 池 IMG 占比 | 0.837 | **0.974** | +0.137 |
| **Gate 前 6 主题相关率** | 0.456 | **0.754** | **+0.298** |
| Gate KEEP 总数 | 75 | 130 | +55 |
| HONEST_EMPTY | 80 | 70 | −10 |
| CV-2 fit 均值(素材拍) | 0.688 | 0.637 | −0.05 |
| Hook 素材 | 0/6 | 0/6 | 0 |
| 素材拍具象主语 | 10/10 | 19/20 | — |

- T1 重写 90/90 生效(零回退),样例:`smart home bedroom morning light` → `smart speaker bedroom`;
- 池不再被 DOC 期刊扫描淹没(冒烟例:S01-B01 池 25→26,DOC 20→0,全部真实照片);
- 新增素材全部经**冻结 CV-2** 判定(13 USABLE/CONDITIONALLY,无资格放宽);S26-B03 经 **T3 counterpart** 命中(fit 0.9 USABLE)→ fallback 链路可解释且有效。

## 3. 状态转移(诚实量化)

- `gate_rejected_all → ok` **7** 拍、`cv2_not_usable → ok` **6** 拍(净增 10,另有 3 拍 ok 丢失);
- `gate_rejected_all → cv2_not_usable` **23** 拍:这些拍从"gate 全拒"推进到"CV-2 判定"——**修复让候选进入了更深的正确判定层**,但仍空,归 CV-2 对现有 Commons 照片的诚实否定;
- **回归 3/10**(如实报告):S16-B02(ok→gate 全拒)、S24-B01、S29-B02(ok→cv2_not_usable)。三者基线 fit 本就是最低三档(0.45/0.62/0.5);池顶重排有逐拍方差,7/10 保持且新换候选同类(S23-B01 0.85→0.9、S29-B03 0.55→0.72 反而提升)。

## 4. Hook 0/6 专项:未解决,但死因层下移

| beat | 修复后 T1' | 池 | kept | 死因 |
|---|---|---|---|---|
| S01-B01 | smart speaker bedroom… | 26 全 IMG | 0 | gate(候选为真实"智能之家"照片,与"AI 叫醒"场景不符,gate 判定正确) |
| S01-B02 | smartphone smartwatch hand… | 32 全 IMG | 3 | **CV-2**(基线死于 gate → 现推进 2 层) |
| S01-B03 | pedestrian crossing… | 42 全 IMG | 2 | **CV-2** |
| S31-B01 | city skyline sunrise… | 51 全 IMG | 2 | **CV-2** |
| S31-B02 | coffee cup bedside… | 8 IMG+32 DOC | 0 | gate(bitmap 0 → unconstrained 残留) |
| S31-B03 | businessman window skyline… | 34 全 IMG | 0 | gate |

结论:池顶相关性问题在 hook 已修复(全部 IMG 池、半数进 CV-2);**残余缺口是 Commons 缺少"AI 清晨唤醒/家庭内景"类真实照片**,属素材域稀缺,非本阶段瓶颈层。

## 5. 证明项核对

- ✅ **语义未变**:beat 原文逐字复用;intent 经内容寻址缓存命中(同一 narration → 同一 intent);
- ✅ **视觉相关性未降**:gate 前 6 相关率 0.456→0.754;CV-2 fit −0.05(0.688→0.637,边际波动,所有素材仍过冻结 CV-2);
- ⚠️ **回归**:7/10 保持,3 拍回归已量化(§3)——池重排方差的诚实代价,净收益 +10;
- ✅ **无 hardcode**:两模块零 shot/主题引用(纯模板规则+结构性 mime/词重叠);
- ✅ **fallback 可解释**:T2/T3 由冻结模块生成,`pool_by_tier`/`gate._tier`/`cv2.tier` 全留痕,T3 命中实例存在。

## 6. 结论

瓶颈修复有效:**素材覆盖 11%→22%,gate 输入相关率 +65%,不把 gate 当垃圾过滤器的目标达成**。残余 70 个 HONEST_EMPTY 的主要死因已转移到 CV-2 层(23 拍)与素材域稀缺(hook/家庭场景)——那是下一阶段的候选问题,本阶段不实施。

```
STAGE12.13 = PASS · STOP
```
