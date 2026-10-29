# Stage 12.22:T3 具体对应物查询扩展受控 A/B 实验报告

> **`STAGE12.22 = PASS · T3 路线关闭 · STOP`**
> 51 目标拍(27 cv2_not_usable + 24 gate=0 已测;7 排除拍未纳入)。A = 现状存档(32 素材);B = 冻结管线 + 新独立 T3 模块(`t3_counterpart.py`,唯一新增代码)。冻结组件零改动;T3 判定按 (beat,title) 复用 12.13/12.20 缓存。
> 数据:`stage12_22_t3/results_t3.json`(51 拍逐拍 + summary)。
> **方法论备注**:首轮 19 拍因 rerank 词表遗漏新 T3 queries(伪影)废弃重跑;本报告全部数据来自修正后运行。

## 1. 八项统计

| # | 指标 | 值 |
|---|---|---|
| 1 | T3 新增候选 | **376**(DOC 237 / IMG 138 / VIDEO 1) |
| 2 | T3 进入 Gate Top-6 | **0 / 51 拍** |
| 3 | T3 KEEP | **0** |
| 4 | T3 最终 USABLE/CONDITIONALLY | **0** |
| 5 | 新增最终素材 | **0**(32 → 32) |
| 6 | 调用成本 | 51 T3-LLM + 74 gate(新进入者)+ 16 CV-2 = **141 次,增益 0** |
| 7 | 原有成功素材改变 | **0(构造性;ok 拍不在目标集)** |
| 8 | 稀缺域 | hook S01-B01/B02/B03 无翻转(S31-B01 已 ok,S31-B02 属排除集);办公域 25 拍全无翻转 |

## 2. 失败机制(trace 可证,非推测)

T3 查询质量本身正常(51/51 生成成功,均为具体实物名词短语);**堵点在冻结池排序**:
1. **T3 候选 63% 是 DOC**(Commons 上"control room equipment"、"home office desk"类具体词命中多为报告/论文 PDF)——冻结 `pool_precision` 结构项对 DOC −4.0 直接掩埋;
2. 138 个 IMG 候选的词法重叠按 **counterpart 权重 1.0** 计(冻结),不及 precise-tier 候选的 2.0,加上稳定排序的池序平局优势,**0 个进入 gate 切片**;
3. 因此 T3 候选从未获得 gate/CV-2 判定机会——**IMG 候选质量未知(INSUFFICIENT_EVIDENCE)**,关闭的是"T3 经现有管线的增益",不是"查询词质量"。

**12.21 结论修正**:Commons 对这些具体词并非"无素材",而是"素材以文档形态存在/照片被排序掩埋"——覆盖问题的真实形态比 12.21 判定的更偏**排序与索引形态**,纯域稀缺(hook 居家晨景)依然成立。

## 3. 预定义关闭条件核对

- **条件 1 触发**:"T3 新增候选很多(376)但最终素材增益 = 0" → **T3 关闭**(作为现有冻结管线下的方案);
- 未因任何单案例上线(无案例);不扩大 T3 复杂度;
- 唯一重启路径(需新授权):调整 pool_precision 中 counterpart 权重 / DOC 结构项——属冻结权重变更,本阶段未动。

## 4. 冻结与回归核对

✅ Intent / T1/T2 / Gate(prompt/threshold/depth) / V1 / CV-2(prompt/threshold/weights/Gold/sanitizer) / Composition/Motion/Renderer 全部未动 ✅ 无外部图库 ✅ 零回归(构造性)✅ 141 次调用成本完整留痕 ✅ A/B 逐拍原始 JSON 完整

```
STAGE12.22 = PASS · T3 路线 CLOSED · STOP(不自行进入 12.23)
```
