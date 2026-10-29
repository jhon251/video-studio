# Stage 12.9：Beat Visual Intent Stability

> 状态:**`STAGE12.9 = PASS`**
> 冻结边界:beat_segmentation / beat_retrieval / retrieval_v15 / query_generator / Gate / V1 / CV-2 / Composition / Motion / Subtitle / Renderer **全部零改动**(仅改 visual_intent.py + 新增 intent_stability.py)。
> **STOP —— 不进入 Storyboard / Stage 13。**

---

## 1. 改动(均在授权范围)

**新增 `intent_stability.py`**(最小稳定化模块):内容寻址 intent 缓存

```
key = sha256(旁白 + 完整 prompt)      ← 与 shot_id 无关,非固定映射
首次生成:真实 LLM 调用(12.6 校准 prompt + temperature 0.0),入库
重复生成:CACHE_HIT,逐字返回同一 intent(可追踪)
prompt/旁白变更 → key 变更 → 自然重生成
```

**`visual_intent.py`**:temperature 0.3→0.0;缓存接入(带 hit/key 痕迹);+1 行通用原则(非 shot 规则、非黑名单):

> 核心主体优先:旁白同时含核心主体与历史类比时,画面跟随核心主体("人类社会"),类比("工业革命")只作背景参照。

## 2. 实测一:稳定性探针

- **11 beats × 2 次生成:11/11 稳定**(首抽 temp 0.0 LLM,复次 CACHE_HIT 逐字一致);
- **S06-B02 × 6:全部一致**;
- S06-B02 稳定锚点:**现代城市天际线与街道上的人群**("现代城市中的人群与交通在黄昏时分流动,象征社会变革的宏大与深刻")——核心主体原则使首抽即选城市语义(旁白主语=人类社会),类比不再劫持画面;缓存随后将其钉死。

## 3. 实测二:11-beat 回归(同 12.8 管线,稳定 intent)

| 指标 | 12.8 | 12.9 |
|---|---|---|
| empty | 9/11 | **8/11** |
| Gate KEEP 总数 | 2 | **6** |
| 有最终素材 | 2/11 | **3/11** |

**S06-B02 恢复**:12.8 因 intent 重跑漂移(工厂)→ rejected;12.9 稳定城市意图 → **kept 4 → CV-2 0.85 'City lights at dusk' USABLE**(曼哈顿 0.7 同样通过)。12.8 的回退已修复,且该结果**跨运行可复现**。

其余:S04-B02 0.85(12.8: 0.75);S02-B02 0.1(弱,诚实记录)。每 beat 均保持 12.8 时代主题——跨 beat 零漂移。

## 4. PASS 判定

✅ **同一 Beat Intent 无明显主题漂移**(11/11 + S06-B02 ×6 逐字一致)
✅ **语义锚点保留**(城市/天际线/黄昏锚定;各 beat 主题与 12.8 一致)
✅ **Retrieval / Gate / V1 / CV-2 零回归**(模块未动;时间戳核验)
✅ **无硬编码强制**(缓存按内容寻址、非 shot 映射;无黑名单;新增 1 行为通用语义优先原则)

**诚实保留**:①缓存保证重复稳定,但首抽"哪个主题正确"由核心主体原则引导——若未来改该原则,旧缓存条目保留旧主题直至 prompt 变更;②gate/CV-2 候选排序方差仍在(S04-B02 0.75→0.85 等),属冻结组件内 LLM 非确定性;③empty 8/11 仍受 gate 判定深度(池前 8)主导——未来阶段杠杆,本轮范围外。

## 5. 交付物

- `output/stage33/stage12_9_intent_stability/stability_probe.json` + `final_result.json`
- `output/stage33/stage12_9_intent_stability/run_stability_probe.py` + `run_regression_11beat.py`
- 源码:`intent_stability.py`(新增)、`visual_intent.py`(修改)
- 缓存:`output/stage33/intent_cache/`(11 条)
- 本报告:`docs/STAGE33_STAGE12.9_INTENT_STABILITY_REPORT.md`

```
STAGE12.9 = PASS
  Intent 重复生成 11/11 逐字稳定 · S06-B02 恢复(0.85 USABLE 可复现)
  下游零回归 · empty 9/11→8/11 · 无硬编码
STOP —— 等待授权
```
